"""DataUpdateCoordinator for the Bedrock Server Manager integration."""

import asyncio
import logging
from datetime import timedelta

import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import (
    BedrockServerManagerApi,
    APIError,
    AuthError,
    CannotConnectError,
    ServerNotFoundError,
    ServerNotRunningError,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MinecraftBedrockCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Minecraft Server Manager API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: BedrockServerManagerApi,
        server_name: str,
        scan_interval: int,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api_client  # Store the API client instance
        self.server_name = server_name
        self._scan_interval = scan_interval

        super().__init__(
            hass,
            _LOGGER,
            name=f"Minecraft Manager Coordinator ({server_name})",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoints for the coordinator."""
        _LOGGER.debug("Coordinator requesting update for server '%s'", self.server_name)
        # Define default/error structure
        coordinator_data = {
            "status": "error",
            "message": "Update failed",
            "process_info": None,
            "allowlist": None,
            "properties": None,
        }

        try:
            # Use asyncio.gather to fetch status and allowlist concurrently
            async with async_timeout.timeout(self._scan_interval - 5):
                results = await asyncio.gather(
                    self.api.async_get_server_status_info(self.server_name),
                    self.api.async_get_allowlist(self.server_name),
                    self.api.async_get_server_properties(self.server_name),
                    return_exceptions=True,  # Return exceptions instead of raising immediately
                )

            # Process results
            status_info_result = results[0]
            allowlist_result = results[1]
            properties_result = results[2]

            # Handle status info result
            if isinstance(status_info_result, Exception):
                # Handle specific errors like AuthError or re-raise generic UpdateFailed
                if isinstance(status_info_result, AuthError):
                    raise ConfigEntryAuthFailed(
                        f"Auth error fetching status: {status_info_result}"
                    ) from status_info_result
                if isinstance(status_info_result, ServerNotFoundError):
                    raise UpdateFailed(
                        f"Server not found fetching status: {status_info_result}"
                    ) from status_info_result
                # Log other status errors but maybe allow allowlist fetch to succeed
                _LOGGER.warning(
                    "Error fetching status info for %s: %s",
                    self.server_name,
                    status_info_result,
                )
                coordinator_data["message"] = (
                    f"Status fetch failed: {status_info_result}"
                )
                # Keep process_info as None
            elif isinstance(status_info_result, dict):
                # Check for API reporting error in body despite 2xx code
                if status_info_result.get("status") == "error":
                    _LOGGER.warning(
                        "API reported error fetching status for %s: %s",
                        self.server_name,
                        status_info_result.get("message"),
                    )
                    coordinator_data["message"] = (
                        f"API error (status): {status_info_result.get('message')}"
                    )
                else:
                    # Success for status info
                    coordinator_data["process_info"] = status_info_result.get(
                        "process_info"
                    )
                    # Check if server is running based on process_info
                    if coordinator_data["process_info"] is None:
                        # Handle case where status call worked but server is stopped
                        if (
                            "message" in status_info_result
                        ):  # Use API message if available
                            coordinator_data["message"] = status_info_result["message"]
                        else:
                            coordinator_data["message"] = "Server stopped"
                    # Update overall status only if allowlist also succeeds below
                    # coordinator_data["status"] = "success"
                    # coordinator_data["message"] = "Status fetched" # Overwrite later if allowlist fails

            # Handle allowlist result
            if isinstance(allowlist_result, Exception):
                # Log allowlist error but don't necessarily fail the whole update if status worked
                _LOGGER.warning(
                    "Error fetching allowlist for %s: %s",
                    self.server_name,
                    allowlist_result,
                )
                # Update message if status was okay, otherwise keep status error message
                if coordinator_data.get("status") != "error":
                    coordinator_data["message"] = (
                        f"Allowlist fetch failed: {allowlist_result}"
                    )
                # Keep allowlist as None
            elif isinstance(allowlist_result, dict):
                if allowlist_result.get("status") == "error":
                    _LOGGER.warning(
                        "API reported error fetching allowlist for %s: %s",
                        self.server_name,
                        allowlist_result.get("message"),
                    )
                    if (
                        coordinator_data.get("status") != "error"
                    ):  # Prioritize status error message
                        coordinator_data["message"] = (
                            f"API error (allowlist): {allowlist_result.get('message')}"
                        )
                else:
                    # Success for allowlist info
                    coordinator_data["allowlist"] = allowlist_result.get(
                        "existing_players", []
                    )

            # --- Handle server properties result ---
            if isinstance(properties_result, Exception):
                _LOGGER.warning(
                    "Error fetching server properties for %s: %s",
                    self.server_name,
                    properties_result,
                )
                # Don't fail entire update if only properties fetch failed, set message if others were okay
                if coordinator_data.get("status") != "error":  # Prioritize other errors
                    coordinator_data["message"] = (
                        f"Properties fetch failed: {properties_result}"
                    )
                # Keep properties as None
            elif isinstance(properties_result, dict):
                if properties_result.get("status") == "error":
                    _LOGGER.warning(
                        "API reported error fetching properties for %s: %s",
                        self.server_name,
                        properties_result.get("message"),
                    )
                    if coordinator_data.get("status") != "error":
                        coordinator_data["message"] = (
                            f"API error (properties): {properties_result.get('message')}"
                        )
                else:
                    # Success for properties info
                    coordinator_data["properties"] = properties_result.get(
                        "properties", {}
                    )  # Default to empty dict

            # Determine overall success (if all critical fetches were okay)
            if not isinstance(status_info_result, Exception) and (
                isinstance(status_info_result, dict)
                and status_info_result.get("status") != "error"
            ):
                # Status is critical. Allowlist and Properties are supplementary.
                coordinator_data["status"] = "success"
                if coordinator_data.get("process_info") is not None:
                    coordinator_data["message"] = "Server running and data fetched."
                else:
                    coordinator_data["message"] = "Server stopped, data fetched."

                # Append specific fetch failures to the message if overall status is success
                if isinstance(allowlist_result, Exception) or (
                    isinstance(allowlist_result, dict)
                    and allowlist_result.get("status") == "error"
                ):
                    coordinator_data["message"] += " (Allowlist fetch failed)"
                if isinstance(properties_result, Exception) or (
                    isinstance(properties_result, dict)
                    and properties_result.get("status") == "error"
                ):
                    coordinator_data["message"] += " (Properties fetch failed)"

            return coordinator_data

        # Handle specific exceptions from the gather call or coordinator logic itself
        except ConfigEntryAuthFailed:
            raise  # Re-raise auth errors
        except UpdateFailed:
            raise  # Re-raise update failures
        except asyncio.TimeoutError as err:
            _LOGGER.warning("Timeout fetching data for %s", self.server_name)
            raise UpdateFailed(f"Timeout communicating with API: {err}") from err
        except Exception as err:  # Catch-all for unexpected errors during update
            _LOGGER.exception(
                "Unexpected error fetching data for %s: %s", self.server_name, err
            )
            raise UpdateFailed(f"Unexpected error: {err}") from err


class ManagerDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching global data from the Bedrock Server Manager API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: BedrockServerManagerApi,
        scan_interval: int,  # Use a separate scan interval for manager data if desired
    ):
        """Initialize the manager data coordinator."""
        self.api = api_client
        self._scan_interval = scan_interval

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} Manager Data Coordinator",
            update_interval=timedelta(seconds=scan_interval),
            # Consider request_refresh_debouncer if updates are frequent
        )

    async def _async_update_data(self) -> dict:
        """Fetch global manager data from API endpoints."""
        _LOGGER.debug("Manager Data Coordinator requesting update.")
        # Initialize with default/error state, ensure all expected keys present
        manager_data = {
            "status": "error",
            "message": "Manager data update failed",
            "info": None,  # From /api/info
            "global_players": None,  # From /api/players/get
        }

        try:
            async with async_timeout.timeout(self._scan_interval - 3):
                results = await asyncio.gather(
                    self.api.async_get_manager_info(),
                    self.api.async_get_global_players(),
                    return_exceptions=True,
                )

            info_result, players_result = results
            all_successful = True

            # Process Manager Info
            if isinstance(info_result, Exception):
                _LOGGER.warning("Error fetching manager info: %s", info_result)
                manager_data["message"] = (
                    f"Manager info fetch failed: {type(info_result).__name__}"
                )
                all_successful = False  # Mark as partial failure
            elif (
                isinstance(info_result, dict) and info_result.get("status") == "success"
            ):
                manager_data["info"] = info_result.get(
                    "data"
                )  # Store the nested 'data' object
            else:
                _LOGGER.warning(
                    "Invalid or error response for manager info: %s", info_result
                )
                manager_data["message"] = "Invalid manager info response"
                all_successful = False

            # Process Global Players
            if isinstance(players_result, Exception):
                _LOGGER.warning("Error fetching global players: %s", players_result)
                if all_successful:  # Don't overwrite a more critical error message
                    manager_data["message"] = (
                        f"Global players fetch failed: {type(players_result).__name__}"
                    )
                all_successful = False
            elif (
                isinstance(players_result, dict)
                and players_result.get("status") == "success"
            ):
                manager_data["global_players"] = players_result.get("players", [])
            else:
                _LOGGER.warning(
                    "Invalid or error response for global players: %s", players_result
                )
                if all_successful:
                    manager_data["message"] = "Invalid global players response"
                all_successful = False

            if all_successful:
                manager_data["status"] = "success"
                manager_data["message"] = "Manager data fetched successfully."

            return manager_data

        # Handle top-level exceptions (AuthError less likely for /api/info if unauth)
        except ConfigEntryAuthFailed:
            raise  # Should not happen if /api/info is truly unauth
        except UpdateFailed:
            raise
        except asyncio.TimeoutError as err:
            _LOGGER.warning("Timeout fetching manager data")
            raise UpdateFailed(
                f"Timeout communicating with API for manager data: {err}"
            ) from err
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching manager data: %s", err)
            raise UpdateFailed(
                f"Unexpected error fetching manager data: {err}"
            ) from err
