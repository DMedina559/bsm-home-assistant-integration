# custom_components/bedrock_server_manager/coordinator.py
"""DataUpdateCoordinator for the Bedrock Server Manager integration."""

import asyncio
import logging
from datetime import timedelta

import async_timeout  # For explicit timeout on asyncio.gather

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
)  # Standard HA exception for auth issues

from bsm_api_client import (
    BedrockServerManagerApi,
    APIError,
    AuthError,
    CannotConnectError,
    ServerNotFoundError,
)
from bsm_api_client.models import (
    GeneralApiResponse,
    BackupRestoreResponse,
    PluginApiResponse,
    ContentListResponse,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Define a minimum sensible timeout for API calls if scan_interval is very short
MIN_API_TIMEOUT = 180  # seconds


class MinecraftBedrockCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Minecraft Server Manager API for a specific server."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: BedrockServerManagerApi,
        server_name: str,
        scan_interval: int,
    ) -> None:
        self.api = api_client
        self.server_name = server_name
        self._api_call_timeout = MIN_API_TIMEOUT

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} Server Coordinator ({server_name})",
            update_interval=timedelta(seconds=scan_interval),
        )
        _LOGGER.debug(
            "Initialized MinecraftBedrockCoordinator for '%s' with update interval %ds (API timeout %ds)",
            server_name,
            scan_interval,
            self._api_call_timeout,
        )

    async def _async_update_data(self) -> dict:
        _LOGGER.debug("Coordinator: Updating data for server '%s'", self.server_name)
        coordinator_data = {
            "status": "error",
            "message": "Update data collection failed",
            "process_info": None,
            "allowlist": [],
            "properties": {},
            "server_permissions": [],
            "world_backups": [],
            "allowlist_backups": [],
            "permissions_backups": [],
            "properties_backups": [],
        }

        try:
            async with async_timeout.timeout(self._api_call_timeout):
                results = await asyncio.gather(
                    self.api.async_get_server_process_info(self.server_name),
                    self.api.async_get_server_allowlist(self.server_name),
                    self.api.async_get_server_properties(self.server_name),
                    self.api.async_get_server_permissions_data(self.server_name),
                    self.api.async_list_server_backups(self.server_name, "world"),
                    self.api.async_list_server_backups(self.server_name, "allowlist"),
                    self.api.async_list_server_backups(self.server_name, "permissions"),
                    self.api.async_list_server_backups(self.server_name, "properties"),
                    return_exceptions=True,
                )

            (
                process_info_result,
                allowlist_result,
                properties_result,
                permissions_result,
                world_backups_result,
                allowlist_backups_result,
                permissions_backups_result,
                properties_backups_result,
            ) = results

            fetch_errors_details = []
            status_info_handled_as_offline = False

            # --- Process Status Info (Considered critical for the coordinator's success) ---
            if isinstance(process_info_result, Exception):
                if isinstance(process_info_result, APIError):
                    msg = getattr(
                        process_info_result, "api_message", str(process_info_result)
                    ).lower()
                    if (
                        "not found or information is inaccessible" in msg
                        and "server process" in msg
                    ) or ("server process" in msg and "not running" in msg):
                        _LOGGER.info(
                            "Server '%s' status_info resulted in APIError but message indicates process not running/inaccessible: '%s'. "
                            "Treating as server offline.",
                            self.server_name,
                            getattr(
                                process_info_result,
                                "api_message",
                                str(process_info_result),
                            ),
                        )
                        coordinator_data["process_info"] = None
                        coordinator_data["status"] = "success"
                        coordinator_data["message"] = getattr(
                            process_info_result,
                            "api_message",
                            f"Server process '{self.server_name}' not running or info inaccessible.",
                        )
                        status_info_handled_as_offline = True
                    else:
                        _LOGGER.warning(
                            "Unhandled APIError for status_info for '%s', passing to critical handler.",
                            self.server_name,
                        )
                        self._handle_critical_exception(
                            "status_info", process_info_result
                        )
                else:
                    _LOGGER.warning(
                        "Non-APIError exception for status_info for '%s', passing to critical handler.",
                        self.server_name,
                    )
                    self._handle_critical_exception("status_info", process_info_result)

            elif isinstance(process_info_result, GeneralApiResponse):
                if process_info_result.data:
                    coordinator_data["process_info"] = process_info_result.data.get(
                        "process_info"
                    )
                coordinator_data["status"] = "success"
                coordinator_data["message"] = (
                    process_info_result.message or "Status fetched successfully"
                )
                if (
                    coordinator_data["process_info"] is None
                    and coordinator_data["message"]
                    and "not running" in coordinator_data["message"].lower()
                ):
                    _LOGGER.debug(
                        "Server '%s' reported as not running by status_info (API success response).",
                        self.server_name,
                    )
            elif not status_info_handled_as_offline:
                _LOGGER.error(
                    "Invalid or unexpected API response structure for status_info for '%s': %s",
                    self.server_name,
                    process_info_result,
                )
                raise UpdateFailed(
                    f"Invalid response structure for critical status_info for server '{self.server_name}'"
                )

            # --- Process Non-Critical Data Points ---
            if isinstance(allowlist_result, Exception):
                fetch_errors_details.append(
                    f"Allowlist: {type(allowlist_result).__name__} ({allowlist_result})"
                )
            elif isinstance(allowlist_result, GeneralApiResponse):
                coordinator_data["allowlist"] = allowlist_result.players or []
            else:
                fetch_errors_details.append(
                    f"Allowlist: Invalid response ({allowlist_result})"
                )

            if isinstance(properties_result, Exception):
                fetch_errors_details.append(
                    f"Properties: {type(properties_result).__name__} ({properties_result})"
                )
            elif isinstance(properties_result, GeneralApiResponse):
                coordinator_data["properties"] = properties_result.properties or {}
            else:
                fetch_errors_details.append(
                    f"Properties: Invalid response ({properties_result})"
                )

            if isinstance(permissions_result, Exception):
                fetch_errors_details.append(
                    f"Permissions: {type(permissions_result).__name__} ({permissions_result})"
                )
            elif isinstance(permissions_result, GeneralApiResponse):
                if permissions_result.data:
                    coordinator_data["server_permissions"] = (
                        permissions_result.data.get("permissions", [])
                    )
            else:
                fetch_errors_details.append(
                    f"Permissions: Invalid response ({permissions_result})"
                )

            if isinstance(world_backups_result, Exception):
                fetch_errors_details.append(
                    f"WorldBackups: {type(world_backups_result).__name__} ({world_backups_result})"
                )
            elif isinstance(world_backups_result, BackupRestoreResponse):
                coordinator_data["world_backups"] = world_backups_result.backups or []
            else:
                fetch_errors_details.append(
                    f"WorldBackups: Invalid response ({world_backups_result})"
                )

            if isinstance(allowlist_backups_result, Exception):
                fetch_errors_details.append(
                    f"AllowlistBackups: {type(allowlist_backups_result).__name__} ({allowlist_backups_result})"
                )
            elif isinstance(allowlist_backups_result, BackupRestoreResponse):
                coordinator_data["allowlist_backups"] = (
                    allowlist_backups_result.backups or []
                )
            else:
                fetch_errors_details.append(
                    f"AllowlistBackups: Invalid response ({allowlist_backups_result})"
                )

            if isinstance(permissions_backups_result, Exception):
                fetch_errors_details.append(
                    f"PermissionsBackups: {type(permissions_backups_result).__name__} ({permissions_backups_result})"
                )
            elif isinstance(permissions_backups_result, BackupRestoreResponse):
                coordinator_data["permissions_backups"] = (
                    permissions_backups_result.backups or []
                )
            else:
                fetch_errors_details.append(
                    f"PermissionsBackups: Invalid response ({permissions_backups_result})"
                )

            if isinstance(properties_backups_result, Exception):
                fetch_errors_details.append(
                    f"PropertiesBackups: {type(properties_backups_result).__name__} ({properties_backups_result})"
                )
            elif isinstance(properties_backups_result, BackupRestoreResponse):
                coordinator_data["properties_backups"] = (
                    properties_backups_result.backups or []
                )
            else:
                fetch_errors_details.append(
                    f"PropertiesBackups: Invalid response ({properties_backups_result})"
                )

            if fetch_errors_details:
                _LOGGER.warning(
                    "Partial data fetch failure for server '%s': %s",
                    self.server_name,
                    "; ".join(fetch_errors_details),
                )
                if coordinator_data["status"] == "success":
                    coordinator_data[
                        "message"
                    ] += f". Partial failures on other items: {len(fetch_errors_details)}."
                else:
                    coordinator_data["status"] = "partial_error"
                    coordinator_data["message"] = (
                        f"Failed some non-critical data points: {'; '.join(fetch_errors_details)}"
                    )

            _LOGGER.debug(
                "Coordinator update processed for server '%s'. Overall Status: %s, Message: %s, process_info is %s.",
                self.server_name,
                coordinator_data["status"],
                coordinator_data["message"],
                "present" if coordinator_data["process_info"] else "None",
            )
            return coordinator_data

        except (
            ConfigEntryAuthFailed,
            UpdateFailed,
        ) as e:
            _LOGGER.log(
                (
                    logging.ERROR
                    if isinstance(e, ConfigEntryAuthFailed)
                    else logging.WARNING
                ),
                "Update for server '%s' failed critically: %s",
                self.server_name,
                e,
            )
            raise
        except asyncio.TimeoutError as err:
            _LOGGER.warning(
                "Timeout fetching data for server '%s': %s", self.server_name, err
            )
            raise UpdateFailed(
                f"Timeout communicating with API for server {self.server_name}"
            ) from err
        except Exception as err:
            _LOGGER.exception(
                "Unexpected error fetching data for server '%s'", self.server_name
            )
            raise UpdateFailed(
                f"Unexpected error updating server {self.server_name}: {err}"
            ) from err

    def _handle_critical_exception(self, data_key: str, error: Exception):
        if isinstance(error, AuthError):
            _LOGGER.error(
                "Auth error fetching %s for %s: %s", data_key, self.server_name, error
            )
            raise ConfigEntryAuthFailed(
                f"Auth error for {data_key}: {error.api_message or error}"
            ) from error
        if isinstance(error, ServerNotFoundError):
            _LOGGER.error(
                "Server %s not found when fetching %s: %s",
                self.server_name,
                data_key,
                error,
            )
            raise UpdateFailed(
                f"Server not found for {data_key}: {error.api_message or error}"
            ) from error
        if isinstance(error, (APIError, CannotConnectError)):
            _LOGGER.error(
                "API/Connection error fetching %s for %s: %s",
                data_key,
                self.server_name,
                error,
            )
            raise UpdateFailed(
                f"API/Connection error for {data_key}: {error.api_message or error}"
            ) from error

        _LOGGER.exception(
            "Unexpected error fetching %s for %s", data_key, self.server_name
        )
        raise UpdateFailed(f"Unexpected error for {data_key}: {error}") from error


class ManagerDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching global data from the Bedrock Server Manager API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: BedrockServerManagerApi,
        scan_interval: int,
    ):
        self.api = api_client
        self._api_call_timeout = max(MIN_API_TIMEOUT, scan_interval - 3)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} Manager Data Coordinator",
            update_interval=timedelta(seconds=scan_interval),
        )
        _LOGGER.debug(
            "Initialized ManagerDataCoordinator with update interval %ds (API timeout %ds)",
            scan_interval,
            self._api_call_timeout,
        )

    async def _async_update_data(self) -> dict:
        _LOGGER.debug("Manager Coordinator: Updating global data.")
        manager_data = {
            "status": "error",
            "message": "Manager data update failed",
            "info": None,
            "global_players": [],
            "available_worlds": [],
            "available_addons": [],
            "plugins_status": None,
        }

        fetch_errors_details = []

        try:
            async with async_timeout.timeout(self._api_call_timeout):
                results = await asyncio.gather(
                    self.api.async_get_info(),
                    self.api.async_get_players(),
                    self.api.async_get_content_worlds(),
                    self.api.async_get_content_addons(),
                    self.api.async_get_plugin_statuses(),
                    return_exceptions=True,
                )

            (
                info_result,
                players_result,
                worlds_result,
                addons_result,
                plugins_status_result,
            ) = results
            at_least_one_success = False

            if isinstance(info_result, Exception):
                fetch_errors_details.append(
                    f"Info: {type(info_result).__name__} ({info_result})"
                )
            elif isinstance(info_result, GeneralApiResponse):
                manager_data["info"] = info_result.info
                at_least_one_success = True
            else:
                fetch_errors_details.append(f"Info: Invalid response ({info_result})")

            if isinstance(players_result, Exception):
                self._handle_exception_for_manager_data(
                    "global_players", players_result, fetch_errors_details
                )
            elif isinstance(players_result, GeneralApiResponse):
                manager_data["global_players"] = players_result.players or []
                at_least_one_success = True
            elif isinstance(players_result, dict) and "players" in players_result:
                manager_data["global_players"] = players_result["players"] or []
                at_least_one_success = True
            else:
                fetch_errors_details.append(
                    f"GlobalPlayers: Invalid response ({players_result})"
                )

            if isinstance(worlds_result, Exception):
                self._handle_exception_for_manager_data(
                    "available_worlds", worlds_result, fetch_errors_details
                )
            elif isinstance(worlds_result, ContentListResponse):
                manager_data["available_worlds"] = worlds_result.files or []
                at_least_one_success = True
            else:
                fetch_errors_details.append(
                    f"AvailableWorlds: Invalid response ({worlds_result})"
                )

            if isinstance(addons_result, Exception):
                self._handle_exception_for_manager_data(
                    "available_addons", addons_result, fetch_errors_details
                )
            elif isinstance(addons_result, ContentListResponse):
                manager_data["available_addons"] = addons_result.files or []
                at_least_one_success = True
            else:
                fetch_errors_details.append(
                    f"AvailableAddons: Invalid response ({addons_result})"
                )

            if isinstance(plugins_status_result, Exception):
                self._handle_exception_for_manager_data(
                    "plugins_status", plugins_status_result, fetch_errors_details
                )
            elif isinstance(plugins_status_result, PluginApiResponse):
                manager_data["plugins_status"] = plugins_status_result.data or {}
                at_least_one_success = True
            else:
                fetch_errors_details.append(
                    f"PluginsStatus: Invalid response ({plugins_status_result})"
                )

            if at_least_one_success:
                manager_data["status"] = "success"
                manager_data["message"] = "Manager data fetched."
                if fetch_errors_details:
                    _LOGGER.warning(
                        "Partial data fetch failure for manager data: %s",
                        "; ".join(fetch_errors_details),
                    )
                    manager_data[
                        "message"
                    ] += f" (Partial failures: {len(fetch_errors_details)} items)"
            else:
                final_error_summary = (
                    "; ".join(fetch_errors_details) or "Unknown reasons"
                )
                manager_data["message"] = (
                    f"Failed to fetch any manager data: {final_error_summary}"
                )
                _LOGGER.error(manager_data["message"])
                raise UpdateFailed(manager_data["message"])

            _LOGGER.debug(
                "Manager coordinator update processed. Status: %s",
                manager_data["status"],
            )
            return manager_data

        except ConfigEntryAuthFailed:
            _LOGGER.error("Authentication failure during manager data update.")
            raise
        except UpdateFailed:
            _LOGGER.warning("Update failed for manager data coordinator.")
            raise
        except asyncio.TimeoutError as err:
            _LOGGER.warning("Timeout fetching manager data: %s", err)
            raise UpdateFailed(
                f"Timeout communicating with API for manager data"
            ) from err
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching manager data")
            raise UpdateFailed(
                f"Unexpected error fetching manager data: {err}"
            ) from err

    def _handle_exception_for_manager_data(
        self, data_key: str, error: Exception, error_list: list
    ):
        if isinstance(error, AuthError):
            _LOGGER.error("Auth error fetching %s for manager: %s", data_key, error)
            raise ConfigEntryAuthFailed(
                f"Auth error for {data_key}: {error.api_message or error}"
            ) from error

        _LOGGER.warning(
            "Error fetching %s for manager: %s (%s)",
            data_key,
            type(error).__name__,
            error,
        )
        error_list.append(f"{data_key}: {type(error).__name__}")
