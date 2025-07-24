# custom_components/bedrock_server_manager/coordinator.py
"""DataUpdateCoordinator for the Bedrock Server Manager integration."""

import asyncio
import logging
from datetime import timedelta

import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

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

MIN_API_TIMEOUT = 180  # seconds


class MinecraftBedrockCoordinator(DataUpdateCoordinator):
    """Manages fetching data from the BSM API for a specific Minecraft server."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: BedrockServerManagerApi,
        server_name: str,
        scan_interval: int,
    ) -> None:
        """Initialize the coordinator."""
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
            "Initialized MinecraftBedrockCoordinator for '%s' with update interval %ds",
            server_name,
            scan_interval,
        )

    async def _async_update_data(self) -> dict:
        """
        Fetch data from the API and process it.

        This method gathers all required server data points in parallel,
        handles API errors gracefully, and returns a structured dictionary
        of the server's state.
        """
        _LOGGER.debug("Coordinator: Updating data for server '%s'", self.server_name)
        try:
            async with async_timeout.timeout(self._api_call_timeout):
                results = await asyncio.gather(
                    self.api.async_get_server_process_info(self.server_name),
                    self.api.async_get_server_version(self.server_name),
                    self.api.async_get_server_allowlist(self.server_name),
                    self.api.async_get_server_properties(self.server_name),
                    self.api.async_get_server_permissions_data(self.server_name),
                    self.api.async_list_server_backups(self.server_name, "world"),
                    self.api.async_list_server_backups(self.server_name, "allowlist"),
                    self.api.async_list_server_backups(self.server_name, "permissions"),
                    self.api.async_list_server_backups(self.server_name, "properties"),
                    return_exceptions=True,
                )
            return self._process_update_results(results)
        except asyncio.TimeoutError as err:
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

    def _process_update_results(self, results: list) -> dict:
        """Process the results of the parallel API calls."""
        (
            process_info_result,
            version_result,
            allowlist_result,
            properties_result,
            permissions_result,
            world_backups_result,
            allowlist_backups_result,
            permissions_backups_result,
            properties_backups_result,
        ) = results

        coordinator_data = {
            "status": "error",
            "message": "Update data collection failed",
            "process_info": None,
        }
        fetch_errors = []

        # --- Process Status Info (Critical) ---
        if isinstance(process_info_result, Exception):
            # Gracefully handle "server not running" as a valid state
            if (
                isinstance(process_info_result, APIError)
                and "not running" in str(process_info_result).lower()
            ):
                _LOGGER.info("Server '%s' is not running.", self.server_name)
                coordinator_data["status"] = "success"
                coordinator_data["message"] = "Server process is not running."
            else:
                self._handle_critical_exception("status_info", process_info_result)
        elif isinstance(process_info_result, GeneralApiResponse):
            coordinator_data["process_info"] = process_info_result.data.get(
                "process_info"
            )
            coordinator_data["status"] = "success"
            coordinator_data["message"] = (
                process_info_result.message or "Status fetched."
            )

        # --- Process Other Data Points ---
        coordinator_data["version"] = self._extract_data(
            version_result, "version", fetch_errors
        )
        coordinator_data["allowlist"] = self._extract_data(
            allowlist_result, "players", fetch_errors, []
        )
        coordinator_data["properties"] = self._extract_data(
            properties_result, "properties", fetch_errors, {}
        )
        coordinator_data["server_permissions"] = self._extract_data(
            permissions_result, "permissions", fetch_errors, []
        )
        coordinator_data["world_backups"] = self._extract_data(
            world_backups_result, "backups", fetch_errors, []
        )
        coordinator_data["allowlist_backups"] = self._extract_data(
            allowlist_backups_result, "backups", fetch_errors, []
        )
        coordinator_data["permissions_backups"] = self._extract_data(
            permissions_backups_result, "backups", fetch_errors, []
        )
        coordinator_data["properties_backups"] = self._extract_data(
            properties_backups_result, "backups", fetch_errors, []
        )

        if fetch_errors:
            _LOGGER.warning(
                "Partial data fetch failure for server '%s': %s",
                self.server_name,
                "; ".join(fetch_errors),
            )
            coordinator_data[
                "message"
            ] += f" (Partial failures: {len(fetch_errors)} items)"

        return coordinator_data

    def _extract_data(
        self, result: any, key: str, errors: list, default: any = None
    ) -> any:
        """Extract data from an API response, logging errors."""
        if isinstance(result, Exception):
            errors.append(f"{key.capitalize()}: {type(result).__name__}")
            return default
        if hasattr(result, key):
            return getattr(result, key)
        if hasattr(result, "data") and result.data and key in result.data:
            return result.data[key]
        return default

    def _handle_critical_exception(self, data_key: str, error: Exception):
        """Handle exceptions that should fail the entire update."""
        if isinstance(error, AuthError):
            raise ConfigEntryAuthFailed(
                f"Auth error for {data_key}: {error.api_message or error}"
            ) from error
        if isinstance(error, (ServerNotFoundError, CannotConnectError, APIError)):
            raise UpdateFailed(
                f"API/Connection error for {data_key}: {error.api_message or error}"
            ) from error
        _LOGGER.exception(
            "Unexpected critical error fetching %s for %s", data_key, self.server_name
        )
        raise UpdateFailed(
            f"Unexpected critical error for {data_key}: {error}"
        ) from error


class ManagerDataCoordinator(DataUpdateCoordinator):
    """Manages fetching global data from the BSM API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: BedrockServerManagerApi,
        scan_interval: int,
    ):
        """Initialize the manager data coordinator."""
        self.api = api_client
        self._api_call_timeout = max(MIN_API_TIMEOUT, scan_interval - 3)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} Manager Data Coordinator",
            update_interval=timedelta(seconds=scan_interval),
        )
        _LOGGER.debug(
            "Initialized ManagerDataCoordinator with update interval %ds",
            scan_interval,
        )

    async def _async_update_data(self) -> dict:
        """Fetch global data from the BSM API."""
        _LOGGER.debug("Manager Coordinator: Updating global data.")
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
            return self._process_manager_update_results(results)
        except asyncio.TimeoutError as err:
            raise UpdateFailed(
                "Timeout communicating with API for manager data"
            ) from err
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching manager data")
            raise UpdateFailed(
                f"Unexpected error fetching manager data: {err}"
            ) from err

    def _process_manager_update_results(self, results: list) -> dict:
        """Process the results of the parallel API calls for manager data."""
        (
            info_result,
            players_result,
            worlds_result,
            addons_result,
            plugins_status_result,
        ) = results

        manager_data = {"status": "error", "message": "Manager data update failed"}
        fetch_errors = []
        at_least_one_success = False

        # --- Process Individual Data Points ---
        if not isinstance(info_result, Exception) and isinstance(
            info_result, GeneralApiResponse
        ):
            manager_data["info"] = info_result.info
            at_least_one_success = True
        else:
            self._handle_manager_exception("info", info_result, fetch_errors)

        if not isinstance(players_result, Exception) and isinstance(
            players_result, dict
        ):
            manager_data["global_players"] = players_result.get("players", [])
            at_least_one_success = True
        else:
            self._handle_manager_exception(
                "global_players", players_result, fetch_errors
            )

        if not isinstance(worlds_result, Exception) and isinstance(
            worlds_result, ContentListResponse
        ):
            manager_data["available_worlds"] = worlds_result.files or []
            at_least_one_success = True
        else:
            self._handle_manager_exception(
                "available_worlds", worlds_result, fetch_errors
            )

        if not isinstance(addons_result, Exception) and isinstance(
            addons_result, ContentListResponse
        ):
            manager_data["available_addons"] = addons_result.files or []
            at_least_one_success = True
        else:
            self._handle_manager_exception(
                "available_addons", addons_result, fetch_errors
            )

        if not isinstance(plugins_status_result, Exception) and isinstance(
            plugins_status_result, PluginApiResponse
        ):
            manager_data["plugins_status"] = plugins_status_result.data or {}
            at_least_one_success = True
        else:
            self._handle_manager_exception(
                "plugins_status", plugins_status_result, fetch_errors
            )

        # --- Finalize Status ---
        if at_least_one_success:
            manager_data["status"] = "success"
            manager_data["message"] = "Manager data fetched."
            if fetch_errors:
                _LOGGER.warning(
                    "Partial data fetch failure for manager: %s",
                    "; ".join(fetch_errors),
                )
                manager_data[
                    "message"
                ] += f" (Partial failures: {len(fetch_errors)} items)"
        else:
            error_summary = "; ".join(fetch_errors) or "Unknown reasons"
            raise UpdateFailed(f"Failed to fetch any manager data: {error_summary}")

        return manager_data

    def _handle_manager_exception(
        self, data_key: str, error: Exception, error_list: list
    ):
        """Handle exceptions for non-critical manager data points."""
        if isinstance(error, AuthError):
            _LOGGER.error("Auth error fetching %s for manager: %s", data_key, error)
            raise ConfigEntryAuthFailed(
                f"Auth error for {data_key}: {error.api_message or error}"
            ) from error

        _LOGGER.warning("Error fetching %s for manager: %s", data_key, error)
        error_list.append(
            f"{data_key.replace('_', ' ').title()}: {type(error).__name__}"
        )
