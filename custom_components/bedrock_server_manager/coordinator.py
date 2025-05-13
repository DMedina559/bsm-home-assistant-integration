# custom_components/bedrock_server_manager/coordinator.py
"""DataUpdateCoordinator for the Bedrock Server Manager integration."""

import asyncio
import logging
from datetime import timedelta

import async_timeout  # Keep this import

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

# --- IMPORT FROM THE NEW LIBRARY ---
from pybedrock_server_manager import (
    BedrockServerManagerApi,
    APIError,
    AuthError,
    CannotConnectError,
    ServerNotFoundError,
    ServerNotRunningError,
)

# --- END IMPORT FROM NEW LIBRARY ---

from .const import DOMAIN  # Keep local constant import

_LOGGER = logging.getLogger(__name__)


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
        self._timeout_seconds = max(5, scan_interval - 5)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} Coordinator ({server_name})",
            update_interval=timedelta(seconds=scan_interval),
        )
        _LOGGER.debug(
            "Initialized MinecraftBedrockCoordinator for '%s' with interval %ds",
            server_name,
            scan_interval,
        )

    async def _async_update_data(self) -> dict:
        _LOGGER.debug("Coordinator: Updating data for server '%s'", self.server_name)
        coordinator_data = {
            "status": "error",
            "message": "Update failed",
            "process_info": None,
            "allowlist": None,
            "properties": None,
            "server_permissions": None,
            "world_backups": None,
            "config_backups": None,
        }

        try:
            async with async_timeout.timeout(self._timeout_seconds):
                # --- UPDATED METHOD CALLS ---
                results = await asyncio.gather(
                    self.api.async_get_server_status_info(self.server_name),
                    self.api.async_get_server_allowlist(self.server_name),  # Renamed
                    self.api.async_get_server_properties(
                        self.server_name
                    ),  # Name was OK
                    self.api.async_get_server_permissions_data(
                        self.server_name
                    ),  # Name was OK
                    self.api.async_list_server_backups(
                        self.server_name, "world"
                    ),  # Renamed
                    self.api.async_list_server_backups(
                        self.server_name, "config"
                    ),  # Renamed
                    return_exceptions=True,
                )
                # --- END UPDATED METHOD CALLS ---

            (
                status_info_result,
                allowlist_result,
                properties_result,
                permissions_result,
                world_backups_result,
                config_backups_result,
            ) = results

            # --- Process Status Info (Critical) ---
            if isinstance(status_info_result, Exception):
                if isinstance(status_info_result, AuthError):
                    _LOGGER.error(
                        "Auth error fetching status for %s: %s",
                        self.server_name,
                        status_info_result,
                    )
                    raise ConfigEntryAuthFailed(
                        f"Auth error fetching status: {status_info_result}"
                    ) from status_info_result
                if isinstance(status_info_result, ServerNotFoundError):
                    _LOGGER.error(
                        "Server %s not found when fetching status: %s",
                        self.server_name,
                        status_info_result,
                    )
                    raise UpdateFailed(
                        f"Server not found fetching status: {status_info_result}"
                    ) from status_info_result
                if isinstance(status_info_result, (APIError, CannotConnectError)):
                    _LOGGER.error(
                        "API/Connection error fetching status for %s: %s",
                        self.server_name,
                        status_info_result,
                    )
                    raise UpdateFailed(
                        f"API/Connection error fetching status: {status_info_result}"
                    ) from status_info_result
                _LOGGER.exception(
                    "Unexpected error fetching status info for %s: %s",
                    self.server_name,
                    status_info_result,
                )
                raise UpdateFailed(
                    f"Unexpected error fetching status: {status_info_result}"
                ) from status_info_result
            elif isinstance(status_info_result, dict):
                if status_info_result.get("status") == "error":
                    msg = status_info_result.get("message", "Unknown API error")
                    _LOGGER.warning(
                        "API error fetching status for %s: %s", self.server_name, msg
                    )
                    raise UpdateFailed(f"API error fetching status: {msg}")
                else:
                    coordinator_data["process_info"] = status_info_result.get(
                        "process_info"
                    )
                    coordinator_data["status"] = "success"
                    coordinator_data["message"] = "Status fetched"
                    if coordinator_data["process_info"] is None:
                        coordinator_data["message"] = "Server stopped"
            else:
                _LOGGER.error(
                    "Invalid response type for status info for %s: %s",
                    self.server_name,
                    type(status_info_result),
                )
                raise UpdateFailed(
                    f"Invalid response type for status info: {type(status_info_result).__name__}"
                )

            fetch_failures = []
            # Process Allowlist
            if isinstance(allowlist_result, Exception):
                _LOGGER.warning(
                    "Error fetching allowlist for %s: %s",
                    self.server_name,
                    allowlist_result,
                )
                fetch_failures.append(f"Allowlist ({type(allowlist_result).__name__})")
            elif isinstance(allowlist_result, dict):
                if allowlist_result.get("status") == "error":
                    msg = allowlist_result.get("message", "Unknown API error")
                    _LOGGER.warning(
                        "API error fetching allowlist for %s: %s", self.server_name, msg
                    )
                    fetch_failures.append(f"Allowlist (API: {msg[:30]}...)")
                else:
                    coordinator_data["allowlist"] = allowlist_result.get(
                        "existing_players", []
                    )
            else:
                _LOGGER.warning(
                    "Invalid response type for allowlist for %s: %s",
                    self.server_name,
                    type(allowlist_result),
                )
                fetch_failures.append(
                    f"Allowlist (Invalid Type: {type(allowlist_result).__name__})"
                )

            # Process Properties
            if isinstance(properties_result, Exception):
                _LOGGER.warning(
                    "Error fetching server properties for %s: %s",
                    self.server_name,
                    properties_result,
                )
                fetch_failures.append(
                    f"Properties ({type(properties_result).__name__})"
                )
            elif isinstance(properties_result, dict):
                if properties_result.get("status") == "error":
                    msg = properties_result.get("message", "Unknown API error")
                    _LOGGER.warning(
                        "API error fetching properties for %s: %s",
                        self.server_name,
                        msg,
                    )
                    fetch_failures.append(f"Properties (API: {msg[:30]}...)")
                else:
                    coordinator_data["properties"] = properties_result.get(
                        "properties", {}
                    )
            else:
                _LOGGER.warning(
                    "Invalid response type for properties for %s: %s",
                    self.server_name,
                    type(properties_result),
                )
                fetch_failures.append(
                    f"Properties (Invalid Type: {type(properties_result).__name__})"
                )

            # Process Permissions
            if isinstance(permissions_result, Exception):
                _LOGGER.warning(
                    "Error fetching server permissions for %s: %s",
                    self.server_name,
                    permissions_result,
                )
                fetch_failures.append(
                    f"Permissions ({type(permissions_result).__name__})"
                )
            elif (
                isinstance(permissions_result, dict)
                and permissions_result.get("status") == "success"
            ):
                permissions_data_obj = permissions_result.get("data")
                if isinstance(permissions_data_obj, dict):
                    coordinator_data["server_permissions"] = permissions_data_obj.get(
                        "permissions", []
                    )
                else:
                    _LOGGER.warning(
                        "Unexpected structure for server_permissions for %s: %s",
                        self.server_name,
                        permissions_result,
                    )
                    coordinator_data["server_permissions"] = []
                    fetch_failures.append("Permissions (Bad Structure)")
            else:
                _LOGGER.warning(
                    "Invalid or error response fetching server permissions for %s: %s",
                    self.server_name,
                    permissions_result,
                )
                fetch_failures.append("Permissions (Invalid Resp)")

            # Process World Backups
            if isinstance(world_backups_result, Exception):
                _LOGGER.warning(
                    "Error fetching world backups for %s: %s",
                    self.server_name,
                    world_backups_result,
                )
                fetch_failures.append(
                    f"World Backups ({type(world_backups_result).__name__})"
                )
            elif (
                isinstance(world_backups_result, dict)
                and world_backups_result.get("status") == "success"
            ):
                coordinator_data["world_backups"] = world_backups_result.get(
                    "backups", []
                )
            else:
                _LOGGER.warning(
                    "Invalid or error response fetching world backups for %s: %s",
                    self.server_name,
                    world_backups_result,
                )
                fetch_failures.append("World Backups (Invalid Resp)")

            # Process Config Backups
            if isinstance(config_backups_result, Exception):
                _LOGGER.warning(
                    "Error fetching config backups for %s: %s",
                    self.server_name,
                    config_backups_result,
                )
                fetch_failures.append(
                    f"Config Backups ({type(config_backups_result).__name__})"
                )
            elif (
                isinstance(config_backups_result, dict)
                and config_backups_result.get("status") == "success"
            ):
                coordinator_data["config_backups"] = config_backups_result.get(
                    "backups", []
                )
            else:
                _LOGGER.warning(
                    "Invalid or error response fetching config backups for %s: %s",
                    self.server_name,
                    config_backups_result,
                )
                fetch_failures.append("Config Backups (Invalid Resp)")

            if coordinator_data["status"] == "success" and fetch_failures:
                coordinator_data[
                    "message"
                ] += f" (Failures: {', '.join(fetch_failures)})"
            elif coordinator_data["status"] == "error":  # Should have been raised
                raise UpdateFailed(
                    coordinator_data.get("message", "Unknown update error state")
                )

            _LOGGER.debug(
                "Coordinator update successful for server '%s'", self.server_name
            )
            return coordinator_data

        except ConfigEntryAuthFailed:
            raise
        except UpdateFailed:
            raise
        except asyncio.TimeoutError as err:
            _LOGGER.warning("Timeout fetching data for %s", self.server_name)
            raise UpdateFailed(
                f"Timeout communicating with API for server {self.server_name}: {err}"
            ) from err
        except Exception as err:
            _LOGGER.exception(
                "Unexpected error fetching data for %s: %s", self.server_name, err
            )
            raise UpdateFailed(
                f"Unexpected error updating server {self.server_name}: {err}"
            ) from err


class ManagerDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching global data from the Bedrock Server Manager API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: BedrockServerManagerApi,
        scan_interval: int,
    ):
        self.api = api_client
        self._timeout_seconds = max(5, scan_interval - 3)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} Manager Data Coordinator",
            update_interval=timedelta(seconds=scan_interval),
        )
        _LOGGER.debug(
            "Initialized ManagerDataCoordinator with interval %ds", scan_interval
        )

    async def _async_update_data(self) -> dict:
        _LOGGER.debug("Manager Coordinator: Updating data.")
        manager_data = {
            "status": "error",
            "message": "Manager data update failed",
            "info": None,
            "global_players": None,
            "available_worlds": None,
            "available_addons": None,
        }
        partial_success = False

        try:
            async with async_timeout.timeout(self._timeout_seconds):
                # --- UPDATED METHOD CALLS ---
                results = await asyncio.gather(
                    self.api.async_get_info(),  # Renamed
                    self.api.async_get_players(),  # Renamed
                    self.api.async_get_content_worlds(),  # Renamed
                    self.api.async_get_content_addons(),  # Renamed
                    return_exceptions=True,
                )
                # --- END UPDATED METHOD CALLS ---

            info_result, players_result, worlds_result, addons_result = results
            fetch_failures = []

            # Process Manager Info
            if isinstance(info_result, Exception):
                _LOGGER.warning("Error fetching manager info: %s", info_result)
                fetch_failures.append(f"Info ({type(info_result).__name__})")
            elif isinstance(info_result, dict):
                # Assuming the 'data' key from your HTTP API docs for /api/info
                if "data" in info_result and isinstance(info_result["data"], dict):
                    manager_data["info"] = info_result["data"]
                else:  # Fallback if 'data' key is missing or not a dict
                    manager_data["info"] = (
                        info_result  # Store raw response if structure is unexpected
                    )
                partial_success = True
            else:
                _LOGGER.warning(
                    "Invalid response type for manager info: %s", type(info_result)
                )
                fetch_failures.append(
                    f"Info (Invalid Type: {type(info_result).__name__})"
                )

            # Process Global Players
            if isinstance(players_result, Exception):
                if isinstance(players_result, AuthError):
                    _LOGGER.error(
                        "Auth error fetching global players: %s", players_result
                    )
                    raise ConfigEntryAuthFailed(
                        "Auth error fetching global players"
                    ) from players_result
                _LOGGER.warning("Error fetching global players: %s", players_result)
                fetch_failures.append(f"Players ({type(players_result).__name__})")
            elif (
                isinstance(players_result, dict)
                and players_result.get("status") == "success"
            ):
                manager_data["global_players"] = players_result.get("players", [])
                partial_success = True
            else:
                _LOGGER.warning(
                    "Invalid or error response fetching global players: %s",
                    players_result,
                )
                fetch_failures.append("Players (Invalid Resp)")

            # Process Available Worlds
            if isinstance(worlds_result, Exception):
                if isinstance(worlds_result, AuthError):
                    _LOGGER.error(
                        "Auth error fetching available worlds: %s", worlds_result
                    )
                    raise ConfigEntryAuthFailed(
                        "Auth error fetching available worlds"
                    ) from worlds_result
                _LOGGER.warning("Error fetching available worlds: %s", worlds_result)
                fetch_failures.append(f"Worlds ({type(worlds_result).__name__})")
            elif (
                isinstance(worlds_result, dict)
                and worlds_result.get("status") == "success"
            ):
                manager_data["available_worlds"] = worlds_result.get("files", [])
                partial_success = True
            else:
                _LOGGER.warning(
                    "Invalid or error response fetching available worlds: %s",
                    worlds_result,
                )
                fetch_failures.append("Worlds (Invalid Resp)")

            # Process Available Addons
            if isinstance(addons_result, Exception):
                if isinstance(addons_result, AuthError):
                    _LOGGER.error(
                        "Auth error fetching available addons: %s", addons_result
                    )
                    raise ConfigEntryAuthFailed(
                        "Auth error fetching available addons"
                    ) from addons_result
                _LOGGER.warning("Error fetching available addons: %s", addons_result)
                fetch_failures.append(f"Addons ({type(addons_result).__name__})")
            elif (
                isinstance(addons_result, dict)
                and addons_result.get("status") == "success"
            ):
                manager_data["available_addons"] = addons_result.get("files", [])
                partial_success = True
            else:
                _LOGGER.warning(
                    "Invalid or error response fetching available addons: %s",
                    addons_result,
                )
                fetch_failures.append("Addons (Invalid Resp)")

            if partial_success and not fetch_failures:
                manager_data["status"] = "success"
                manager_data["message"] = "Manager data fetched successfully."
            elif partial_success and fetch_failures:
                manager_data["status"] = "success"
                manager_data["message"] = (
                    f"Partially fetched manager data (Failures: {', '.join(fetch_failures)})"
                )
            else:
                if not fetch_failures:
                    fetch_failures.append("Unknown")
                manager_data["message"] = (
                    f"Failed to fetch manager data ({', '.join(fetch_failures)})"
                )
                raise UpdateFailed(manager_data["message"])

            _LOGGER.debug(
                "Manager coordinator update finished. Status: %s",
                manager_data["status"],
            )
            return manager_data

        except ConfigEntryAuthFailed:
            raise
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
