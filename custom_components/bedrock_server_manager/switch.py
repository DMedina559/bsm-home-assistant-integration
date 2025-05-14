# custom_components/bedrock_server_manager/switch.py
"""Switch platform for Bedrock Server Manager."""

import logging
from typing import Any, Optional, Dict, Tuple

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

# --- IMPORT FROM LOCAL MODULES ---
from .coordinator import MinecraftBedrockCoordinator
from .const import DOMAIN


from pybedrock_server_manager import (
    BedrockServerManagerApi,
    APIError,
    AuthError,
    CannotConnectError,
    ServerNotFoundError,
    ServerNotRunningError,
)


_LOGGER = logging.getLogger(__name__)

SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="server_control",
    name="Server",
    icon="mdi:minecraft",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    try:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        servers_data: dict = entry_data.get("servers", {})
        manager_identifier: Tuple[str, str] = entry_data["manager_identifier"]
    except KeyError as e:
        _LOGGER.error(
            "Missing expected data for entry %s (Key: %s). Cannot set up switches.",
            entry.entry_id,
            e,
        )
        return

    if not servers_data:
        _LOGGER.debug(
            "No servers found for entry %s (Manager ID: %s). Skipping switch setup.",
            entry.entry_id,
            manager_identifier[1],
        )
        return

    _LOGGER.debug(
        "Setting up switches for servers: %s (Manager ID: %s)",
        list(servers_data.keys()),
        manager_identifier[1],
    )
    switches_to_add = []
    for (
        server_name,
        server_data_dict,
    ) in servers_data.items():
        coordinator = server_data_dict.get("coordinator")
        if not coordinator:
            _LOGGER.warning(
                "Coordinator missing for server '%s' (Manager ID: %s). Skipping its switch.",
                server_name,
                manager_identifier[1],
            )
            continue

        if coordinator.last_update_success and coordinator.data:
            switches_to_add.append(
                MinecraftServerSwitch(
                    coordinator=coordinator,
                    description=SWITCH_DESCRIPTION,
                    server_name=server_name,
                    manager_identifier=manager_identifier,
                )
            )
        else:
            _LOGGER.warning(
                "Coordinator for server '%s' (Manager ID: %s) has no data or last update failed; skipping its switch.",
                server_name,
                manager_identifier[1],
            )

    if switches_to_add:
        _LOGGER.info(
            "Adding %d switch entities for entry %s (%s)",
            len(switches_to_add),
            entry.title,
            entry.entry_id,
        )
        async_add_entities(switches_to_add)
    else:
        _LOGGER.debug(
            "No switch entities to add for entry %s (%s)", entry.title, entry.entry_id
        )


class MinecraftServerSwitch(
    CoordinatorEntity[MinecraftBedrockCoordinator], SwitchEntity
):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MinecraftBedrockCoordinator,
        description: SwitchEntityDescription,
        server_name: str,
        manager_identifier: Tuple[str, str],
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._server_name = server_name
        self._manager_host_port_id = manager_identifier[1]

        self._attr_unique_id = f"{DOMAIN}_{self._manager_host_port_id}_{self._server_name}_{description.key}"
        _LOGGER.debug(
            "ServerSwitch Unique ID for %s (%s): %s for key %s",
            self._server_name,
            self._manager_host_port_id,
            self._attr_unique_id,
            description.key,
        )

        # --- CRITICAL CHANGE FOR DEVICE IDENTIFIER ---
        server_device_unique_part = f"{self._manager_host_port_id}_{self._server_name}"
        self._attr_device_info = dr.DeviceInfo(
            identifiers={
                (DOMAIN, server_device_unique_part)
            },  # Globally unique server device ID
            name=f"BSM {self._server_name} ({self._manager_host_port_id})",  # Descriptive device name
            manufacturer="Bedrock Server Manager (Server)",  # Or your main manufacturer
            model="Minecraft Server",  # Or "Minecraft Bedrock Server"
            sw_version=(
                coordinator.data.get("server_version")
                if coordinator.data
                else "Unknown"
            ),
            via_device=manager_identifier,
            configuration_url=f"http://{coordinator.config_entry.data[CONF_HOST]}:{int(coordinator.config_entry.data[CONF_PORT])}",
        )

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        if not self.coordinator.last_update_success or not self.coordinator.data:
            _LOGGER.debug(
                "Coordinator data unavailable for %s, switch state unknown (reporting off)",
                self.unique_id,
            )
            return False
        server_status = self.coordinator.data.get("status")
        if server_status == "Running":
            return True
        if server_status == "Stopped":
            return False
        process_info = self.coordinator.data.get("process_info")
        is_running = isinstance(process_info, dict) and bool(process_info)
        _LOGGER.debug(
            "Switch %s is_on based on process_info: %s", self.unique_id, is_running
        )
        return is_running

    async def async_turn_on(self, **kwargs: Any) -> None:
        api_client: BedrockServerManagerApi = self.coordinator.api
        server_name = self._server_name
        _LOGGER.info(
            "Attempting to turn ON server '%s' (Manager: %s)",
            server_name,
            self._manager_host_port_id,
        )
        try:
            await api_client.async_start_server(server_name)
            await self.coordinator.async_request_refresh()
        except AuthError as err:
            _LOGGER.error(
                "Authentication error starting server %s: %s", server_name, err
            )
            raise HomeAssistantError(
                f"Authentication failed trying to start {server_name}."
            ) from err
        except CannotConnectError as err:
            _LOGGER.error("Connection error starting server %s: %s", server_name, err)
            raise HomeAssistantError(
                f"Could not connect to manager to start {server_name}."
            ) from err
        except ServerNotFoundError as err:
            _LOGGER.error(
                "Server not found error starting server %s: %s", server_name, err
            )
            raise HomeAssistantError(
                f"Server {server_name} not found by manager."
            ) from err
        except APIError as err:
            _LOGGER.error("API error starting server %s: %s", server_name, err)
            raise HomeAssistantError(
                f"Failed to start server {server_name}: {err}"
            ) from err
        except Exception as err:
            _LOGGER.exception(
                "Unexpected error turning ON server %s: %s", server_name, err
            )
            raise HomeAssistantError(
                f"Unexpected error starting server {server_name}."
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        api_client: BedrockServerManagerApi = self.coordinator.api
        server_name = self._server_name
        _LOGGER.info(
            "Attempting to turn OFF server '%s' (Manager: %s)",
            server_name,
            self._manager_host_port_id,
        )
        try:
            await api_client.async_stop_server(server_name)
            await self.coordinator.async_request_refresh()
        except AuthError as err:
            _LOGGER.error(
                "Authentication error stopping server %s: %s", server_name, err
            )
            raise HomeAssistantError(
                f"Authentication failed trying to stop {server_name}."
            ) from err
        except CannotConnectError as err:
            _LOGGER.error("Connection error stopping server %s: %s", server_name, err)
            raise HomeAssistantError(
                f"Could not connect to manager to stop {server_name}."
            ) from err
        except ServerNotFoundError as err:
            _LOGGER.error(
                "Server not found error stopping server %s: %s", server_name, err
            )
            await self.coordinator.async_request_refresh()
            return
        except ServerNotRunningError as err:
            _LOGGER.warning(
                "Attempted to stop server %s, but it was already stopped or not running: %s",
                server_name,
                err,
            )
            await self.coordinator.async_request_refresh()
            return
        except APIError as err:
            msg = str(err).lower()
            if "not running" in msg or "already stopped" in msg:
                _LOGGER.warning(
                    "Attempted to stop server %s, API indicated it was not running: %s",
                    server_name,
                    msg,
                )
                await self.coordinator.async_request_refresh()
                return
            _LOGGER.error("API error stopping server %s: %s", server_name, err)
            raise HomeAssistantError(
                f"Failed to stop server {server_name}: {err}"
            ) from err
        except Exception as err:
            _LOGGER.exception(
                "Unexpected error turning OFF server %s: %s", server_name, err
            )
            raise HomeAssistantError(
                f"Unexpected error stopping server {server_name}."
            ) from err
