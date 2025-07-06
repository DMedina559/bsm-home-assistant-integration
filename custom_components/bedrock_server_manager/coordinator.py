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
        self._api_call_timeout = max(MIN_API_TIMEOUT, scan_interval - 5)

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
                # Check if it's an APIError that signifies the server process is not running
                # but the API itself responded (e.g., HTTP 200 with an error message in payload).
                if isinstance(process_info_result, APIError):
                    msg = getattr(
                        process_info_result, "api_message", str(process_info_result)
                    ).lower()
                    # Check for your specific "process not found" message
                    # Also include a general "not running" check for robustness if API changes slightly
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
                        coordinator_data["process_info"] = (
                            None  # Explicitly set to None
                        )
                        coordinator_data["status"] = (
                            "success"  # Overall fetch considered successful for this state
                        )
                        coordinator_data["message"] = getattr(
                            process_info_result,
                            "api_message",
                            f"Server process '{self.server_name}' not running or info inaccessible.",
                        )
                        status_info_handled_as_offline = (
                            True  # Mark that we handled this specific APIError
                        )
                    else:
                        # Other APIErrors are still critical and should be handled by _handle_critical_exception
                        _LOGGER.warning(
                            "Unhandled APIError for status_info for '%s', passing to critical handler.",
                            self.server_name,
                        )
                        self._handle_critical_exception(
                            "status_info", process_info_result
                        )  # This will raise
                else:
                    # Other exceptions (CannotConnectError, AuthError, etc.) are critical
                    _LOGGER.warning(
                        "Non-APIError exception for status_info for '%s', passing to critical handler.",
                        self.server_name,
                    )
                    self._handle_critical_exception(
                        "status_info", process_info_result
                    )  # This will raise

            elif (
                isinstance(process_info_result, dict)
                and process_info_result.get("status") == "success"
            ):
                coordinator_data["process_info"] = process_info_result.get(
                    "process_info"
                )
                coordinator_data["status"] = "success"
                coordinator_data["message"] = process_info_result.get(
                    "message", "Status fetched successfully"
                )
                if (
                    coordinator_data["process_info"] is None
                    and coordinator_data["message"]
                    is not None  # Ensure message is not None before .lower()
                    and "not running" in coordinator_data["message"].lower()
                ):
                    _LOGGER.debug(
                        "Server '%s' reported as not running by status_info (API success response).",
                        self.server_name,
                    )
            elif (
                not status_info_handled_as_offline
            ):  # Only if not already handled as a specific APIError case
                _LOGGER.error(
                    "Invalid or unexpected API response structure for status_info for '%s': %s",
                    self.server_name,
                    process_info_result,
                )
                raise UpdateFailed(
                    f"Invalid response structure for critical status_info for server '{self.server_name}'"
                )

            # --- Process Non-Critical Data Points ---
            # (Your existing logic for non-critical data points remains the same)
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

            # Allowlist Backups
            if isinstance(allowlist_backups_result, Exception):
                fetch_errors_details.append(
                    f"AllowlistBackups: {type(allowlist_backups_result).__name__} ({allowlist_backups_result})"
                )
            elif (
                isinstance(allowlist_backups_result, dict)
                and allowlist_backups_result.get("status") == "success"
            ):
                coordinator_data["allowlist_backups"] = allowlist_backups_result.get(
                    "backups", []
                )
            else:
                fetch_errors_details.append(
                    f"AllowlistBackups: Invalid response ({allowlist_backups_result})"
                )

            # Permissions Backups
            if isinstance(permissions_backups_result, Exception):
                fetch_errors_details.append(
                    f"PermissionsBackups: {type(permissions_backups_result).__name__} ({permissions_backups_result})"
                )
            elif (
                isinstance(permissions_backups_result, dict)
                and permissions_backups_result.get("status") == "success"
            ):
                coordinator_data["permissions_backups"] = (
                    permissions_backups_result.get("backups", [])
                )
            else:
                fetch_errors_details.append(
                    f"PermissionsBackups: Invalid response ({permissions_backups_result})"
                )

            # Properties Backups
            if isinstance(properties_backups_result, Exception):
                fetch_errors_details.append(
                    f"PropertiesBackups: {type(properties_backups_result).__name__} ({properties_backups_result})"
                )
            elif (
                isinstance(properties_backups_result, dict)
                and properties_backups_result.get("status") == "success"
            ):
                coordinator_data["properties_backups"] = properties_backups_result.get(
                    "backups", []
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
                if (
                    coordinator_data["status"] == "success"
                ):  # If status_info was handled as offline successfully
                    coordinator_data[
                        "message"
                    ] += f". Partial failures on other items: {len(fetch_errors_details)}."
                else:  # Should not happen if status_info error handling is complete
                    coordinator_data["status"] = "partial_error"  # Or keep 'error'
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
        ) as e:  # Catch specific raised exceptions
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
            raise  # Re-raise to let HA handle it
        except asyncio.TimeoutError as err:
            _LOGGER.warning(
                "Timeout fetching data for server '%s': %s", self.server_name, err
            )
            raise UpdateFailed(
                f"Timeout communicating with API for server {self.server_name}"
            ) from err
        except Exception as err:  # Catch-all for truly unexpected issues
            _LOGGER.exception(
                "Unexpected error fetching data for server '%s'", self.server_name
            )
            raise UpdateFailed(
                f"Unexpected error updating server {self.server_name}: {err}"
            ) from err

    def _handle_critical_exception(self, data_key: str, error: Exception):
        """Helper to handle exceptions for critical data points.
        NOTE: This will now only be called for status_info if the APIError
              message doesn't match the "process not found/inaccessible" criteria.
        """
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
        if isinstance(
            error, (APIError, CannotConnectError)
        ):  # APIError here means it wasn't the "process not found" type
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
