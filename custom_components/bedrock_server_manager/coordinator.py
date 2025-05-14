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

from pybedrock_server_manager import (
    BedrockServerManagerApi,
    APIError,
    AuthError,
    CannotConnectError,
    ServerNotFoundError,
    # ServerNotRunningError, # Not explicitly raised by client for info endpoints, but can be inferred
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Define a minimum sensible timeout for API calls if scan_interval is very short
MIN_API_TIMEOUT = 10  # seconds


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
        # Ensure timeout is reasonable, slightly less than scan_interval but not too short
        self._api_call_timeout = max(MIN_API_TIMEOUT, scan_interval - 5)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} Server Coordinator ({server_name})",  # More specific name
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
        # Initialize with default/error state
        coordinator_data = {
            "status": "error",  # Overall status of this data fetch operation
            "message": "Update data collection failed",
            "process_info": None,  # from /status_info
            "allowlist": [],  # from /allowlist
            "properties": {},  # from /read_properties
            "server_permissions": [],  # from /permissions_data
            "world_backups": [],  # from /backups/list/world
            "config_backups": [],  # from /backups/list/config
        }

        try:
            # Using async_timeout for the entire block of API calls
            async with async_timeout.timeout(self._api_call_timeout):
                results = await asyncio.gather(
                    self.api.async_get_server_status_info(self.server_name),
                    self.api.async_get_server_allowlist(self.server_name),
                    self.api.async_get_server_properties(self.server_name),
                    self.api.async_get_server_permissions_data(self.server_name),
                    self.api.async_list_server_backups(self.server_name, "world"),
                    self.api.async_list_server_backups(self.server_name, "config"),
                    return_exceptions=True,  # Catch exceptions from individual calls
                )

            (
                status_info_result,
                allowlist_result,
                properties_result,
                permissions_result,
                world_backups_result,
                config_backups_result,
            ) = results

            fetch_errors_details = []  # To collect detailed error messages

            # --- Process Status Info (Considered critical for the coordinator's success) ---
            if isinstance(status_info_result, Exception):
                self._handle_critical_exception(
                    "status_info", status_info_result
                )  # Helper will raise
            elif (
                isinstance(status_info_result, dict)
                and status_info_result.get("status") == "success"
            ):
                coordinator_data["process_info"] = status_info_result.get(
                    "process_info"
                )
                coordinator_data["status"] = (
                    "success"  # Mark overall success if this critical part passes
                )
                coordinator_data["message"] = status_info_result.get(
                    "message", "Status fetched successfully"
                )
                if (
                    coordinator_data["process_info"] is None
                    and "not running" in coordinator_data["message"].lower()
                ):
                    _LOGGER.debug(
                        "Server '%s' reported as not running by status_info.",
                        self.server_name,
                    )
            else:  # Unexpected structure or API error status for critical data
                _LOGGER.error(
                    "Invalid or API error response for status_info for '%s': %s",
                    self.server_name,
                    status_info_result,
                )
                raise UpdateFailed(
                    f"Invalid response for critical status_info for server '{self.server_name}'"
                )

            # --- Process Non-Critical Data Points ---
            # Allowlist
            if isinstance(allowlist_result, Exception):
                fetch_errors_details.append(
                    f"Allowlist: {type(allowlist_result).__name__} ({allowlist_result})"
                )
            elif (
                isinstance(allowlist_result, dict)
                and allowlist_result.get("status") == "success"
            ):
                coordinator_data["allowlist"] = allowlist_result.get(
                    "existing_players", []
                )
            else:
                fetch_errors_details.append(
                    f"Allowlist: Invalid response ({allowlist_result})"
                )

            # Properties
            if isinstance(properties_result, Exception):
                fetch_errors_details.append(
                    f"Properties: {type(properties_result).__name__} ({properties_result})"
                )
            elif (
                isinstance(properties_result, dict)
                and properties_result.get("status") == "success"
            ):
                coordinator_data["properties"] = properties_result.get("properties", {})
            else:
                fetch_errors_details.append(
                    f"Properties: Invalid response ({properties_result})"
                )

            # Permissions
            if isinstance(permissions_result, Exception):
                fetch_errors_details.append(
                    f"Permissions: {type(permissions_result).__name__} ({permissions_result})"
                )
            elif (
                isinstance(permissions_result, dict)
                and permissions_result.get("status") == "success"
            ):
                permissions_data_nested = permissions_result.get("data", {})
                coordinator_data["server_permissions"] = permissions_data_nested.get(
                    "permissions", []
                )
            else:
                fetch_errors_details.append(
                    f"Permissions: Invalid response ({permissions_result})"
                )

            # World Backups
            if isinstance(world_backups_result, Exception):
                fetch_errors_details.append(
                    f"WorldBackups: {type(world_backups_result).__name__} ({world_backups_result})"
                )
            elif (
                isinstance(world_backups_result, dict)
                and world_backups_result.get("status") == "success"
            ):
                coordinator_data["world_backups"] = world_backups_result.get(
                    "backups", []
                )
            else:
                fetch_errors_details.append(
                    f"WorldBackups: Invalid response ({world_backups_result})"
                )

            # Config Backups
            if isinstance(config_backups_result, Exception):
                fetch_errors_details.append(
                    f"ConfigBackups: {type(config_backups_result).__name__} ({config_backups_result})"
                )
            elif (
                isinstance(config_backups_result, dict)
                and config_backups_result.get("status") == "success"
            ):
                coordinator_data["config_backups"] = config_backups_result.get(
                    "backups", []
                )
            else:
                fetch_errors_details.append(
                    f"ConfigBackups: Invalid response ({config_backups_result})"
                )

            if fetch_errors_details:
                _LOGGER.warning(
                    "Partial data fetch failure for server '%s': %s",
                    self.server_name,
                    "; ".join(fetch_errors_details),
                )
                coordinator_data[
                    "message"
                ] += f" (Partial failures: {len(fetch_errors_details)} items)"

            _LOGGER.debug(
                "Coordinator update processed for server '%s'. Data: %s",
                self.server_name,
                coordinator_data,
            )
            return coordinator_data

        except (
            ConfigEntryAuthFailed
        ):  # Re-raise if handled by _handle_critical_exception
            _LOGGER.error(
                "Authentication failure during update for server '%s'", self.server_name
            )
            raise
        except (
            UpdateFailed
        ):  # Re-raise if handled by _handle_critical_exception or other logic
            _LOGGER.warning(
                "Update failed for server '%s' coordinator.", self.server_name
            )
            raise
        except asyncio.TimeoutError as err:
            _LOGGER.warning(
                "Timeout fetching data for server '%s': %s", self.server_name, err
            )
            raise UpdateFailed(
                f"Timeout communicating with API for server {self.server_name}"
            ) from err
        except Exception as err:  # Catch-all for unexpected issues
            _LOGGER.exception(
                "Unexpected error fetching data for server '%s'", self.server_name
            )
            raise UpdateFailed(
                f"Unexpected error updating server {self.server_name}: {err}"
            ) from err

    def _handle_critical_exception(self, data_key: str, error: Exception):
        """Helper to handle exceptions for critical data points."""
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
        )  # Logs full traceback
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
            "status": "error",  # Overall status of this fetch operation
            "message": "Manager data update failed",
            "info": None,  # from async_get_info -> nested 'data' object
            "global_players": [],  # from async_get_players -> 'players' list
            "available_worlds": [],  # from async_get_content_worlds -> 'files' list
            "available_addons": [],  # from async_get_content_addons -> 'files' list
        }

        fetch_errors_details = []  # To collect detailed error messages

        try:
            async with async_timeout.timeout(self._api_call_timeout):
                results = await asyncio.gather(
                    self.api.async_get_info(),
                    self.api.async_get_players(),
                    self.api.async_get_content_worlds(),
                    self.api.async_get_content_addons(),
                    return_exceptions=True,
                )

            info_result, players_result, worlds_result, addons_result = results
            at_least_one_success = False

            # Process Manager Info (No Auth Required for this specific call)
            if isinstance(info_result, Exception):
                # This is not critical enough to fail the entire manager update if others succeed
                fetch_errors_details.append(
                    f"Info: {type(info_result).__name__} ({info_result})"
                )
            elif (
                isinstance(info_result, dict) and info_result.get("status") == "success"
            ):
                # api.async_get_info() returns {"status": "success", "data": {"os_type": ..., "app_version": ...}}
                manager_data["info"] = info_result.get(
                    "data", {}
                )  # Store the nested 'data' object
                at_least_one_success = True
            else:  # Unexpected structure
                fetch_errors_details.append(f"Info: Invalid response ({info_result})")

            # Process Global Players (Requires Auth)
            if isinstance(players_result, Exception):
                self._handle_exception_for_manager_data(
                    "global_players", players_result, fetch_errors_details
                )
            elif (
                isinstance(players_result, dict)
                and players_result.get("status") == "success"
            ):
                manager_data["global_players"] = players_result.get("players", [])
                at_least_one_success = True
            else:
                fetch_errors_details.append(
                    f"GlobalPlayers: Invalid response ({players_result})"
                )

            # Process Available Worlds (Requires Auth)
            if isinstance(worlds_result, Exception):
                self._handle_exception_for_manager_data(
                    "available_worlds", worlds_result, fetch_errors_details
                )
            elif (
                isinstance(worlds_result, dict)
                and worlds_result.get("status") == "success"
            ):
                manager_data["available_worlds"] = worlds_result.get("files", [])
                at_least_one_success = True
            else:
                fetch_errors_details.append(
                    f"AvailableWorlds: Invalid response ({worlds_result})"
                )

            # Process Available Addons (Requires Auth)
            if isinstance(addons_result, Exception):
                self._handle_exception_for_manager_data(
                    "available_addons", addons_result, fetch_errors_details
                )
            elif (
                isinstance(addons_result, dict)
                and addons_result.get("status") == "success"
            ):
                manager_data["available_addons"] = addons_result.get("files", [])
                at_least_one_success = True
            else:
                fetch_errors_details.append(
                    f"AvailableAddons: Invalid response ({addons_result})"
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
            else:  # No data point succeeded
                # If all were auth errors, ConfigEntryAuthFailed would have been raised already.
                # This means other API errors or connection issues occurred for all auth'd endpoints.
                final_error_summary = (
                    "; ".join(fetch_errors_details) or "Unknown reasons"
                )
                manager_data["message"] = (
                    f"Failed to fetch any manager data: {final_error_summary}"
                )
                _LOGGER.error(manager_data["message"])  # Log the consolidated error
                raise UpdateFailed(manager_data["message"])

            _LOGGER.debug(
                "Manager coordinator update processed. Status: %s",
                manager_data["status"],
            )
            return manager_data

        except (
            ConfigEntryAuthFailed
        ):  # Re-raise if handled by _handle_exception_for_manager_data
            _LOGGER.error("Authentication failure during manager data update.")
            raise
        except UpdateFailed:  # Re-raise if a general update failure was determined
            _LOGGER.warning("Update failed for manager data coordinator.")
            raise
        except asyncio.TimeoutError as err:
            _LOGGER.warning("Timeout fetching manager data: %s", err)
            raise UpdateFailed(
                f"Timeout communicating with API for manager data"
            ) from err
        except Exception as err:  # Catch-all for unexpected issues
            _LOGGER.exception("Unexpected error fetching manager data")
            raise UpdateFailed(
                f"Unexpected error fetching manager data: {err}"
            ) from err

    def _handle_exception_for_manager_data(
        self, data_key: str, error: Exception, error_list: list
    ):
        """Helper to handle exceptions for manager data points, possibly raising critical ones."""
        if isinstance(error, AuthError):
            _LOGGER.error("Auth error fetching %s for manager: %s", data_key, error)
            # This is critical for authenticated endpoints
            raise ConfigEntryAuthFailed(
                f"Auth error for {data_key}: {error.api_message or error}"
            ) from error

        # For other errors (APIError, CannotConnectError, etc.), just log and add to list for now.
        # If any single manager data point (other than info) being unavailable is critical,
        # you might raise UpdateFailed here too.
        _LOGGER.warning(
            "Error fetching %s for manager: %s (%s)",
            data_key,
            type(error).__name__,
            error,
        )
        error_list.append(f"{data_key}: {type(error).__name__}")
