# custom_components/bedrock_server_manager/switch.py
"""Switch platform for Bedrock Server Manager."""

import logging
from typing import Any, Optional, Dict

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.exceptions import HomeAssistantError

# --- IMPORT FROM LOCAL MODULES ---
from .coordinator import MinecraftBedrockCoordinator
from .const import DOMAIN


from pybedrock_server_manager import (
    BedrockServerManagerApi,
    APIError,
    AuthError,
    CannotConnectError,
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
        servers_data: dict = entry_data["servers"]
        manager_identifier: tuple = entry_data["manager_identifier"]
    except KeyError as e:
        _LOGGER.error(
            "Missing expected data for entry %s (%s). Cannot set up switches.",
            entry.entry_id,
            e,
        )
        return

    if not servers_data:
        _LOGGER.debug(
            "No servers found for entry %s. Skipping switch setup.", entry.entry_id
        )
        return

    _LOGGER.debug("Setting up switches for servers: %s", list(servers_data.keys()))
    switches_to_add = []
    for server_name, server_data in servers_data.items():
        coordinator = server_data.get("coordinator")
        if not coordinator:
            _LOGGER.warning(
                "Coordinator missing for server '%s'. Skipping switch.", server_name
            )
            continue
        switches_to_add.append(
            MinecraftServerSwitch(
                coordinator=coordinator,
                description=SWITCH_DESCRIPTION,
                entry=entry,
                server_name=server_name,
                manager_identifier=manager_identifier,
            )
        )
    if switches_to_add:
        _LOGGER.info(
            "Adding %d switch entities for entry %s (%s)",
            len(switches_to_add),
            entry.title,
            entry.entry_id,
        )
        async_add_entities(switches_to_add)


class MinecraftServerSwitch(
    CoordinatorEntity[MinecraftBedrockCoordinator], SwitchEntity
):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MinecraftBedrockCoordinator,
        description: SwitchEntityDescription,
        entry: ConfigEntry,
        server_name: str,
        manager_identifier: tuple,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._server_name = server_name
        self._attr_unique_id = f"{DOMAIN}_{self._server_name}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._server_name)},
            name=f"bsm-{self._server_name}",
            via_device=manager_identifier,
        )

    @property
    def is_on(self) -> Optional[bool]:
        if not self.available:
            return None
        coordinator_data = self.coordinator.data
        if not isinstance(coordinator_data, dict):
            _LOGGER.warning("Coordinator data invalid for %s.", self.unique_id)
            return None
        process_info = coordinator_data.get("process_info")
        return isinstance(process_info, dict)

    async def async_turn_on(self, **kwargs: Any) -> None:
        api_client: BedrockServerManagerApi = self.coordinator.api
        server_name = self._server_name
        _LOGGER.info("Attempting to turn ON server '%s'", server_name)
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
        except APIError as err:
            _LOGGER.error("API error starting server %s: %s", server_name, err)
            raise HomeAssistantError(
                f"Failed to start server {server_name}: {getattr(err, 'message', err)}"
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
        _LOGGER.info("Attempting to turn OFF server '%s'", server_name)
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
        except APIError as err:
            msg = str(getattr(err, "message", err)).lower()
            if "not running" in msg or "already stopped" in msg:
                _LOGGER.warning(
                    "Attempted to stop server %s, but it was already stopped.",
                    server_name,
                )
                await self.coordinator.async_request_refresh()
                return
            _LOGGER.error("API error stopping server %s: %s", server_name, err)
            raise HomeAssistantError(
                f"Failed to stop server {server_name}: {getattr(err, 'message', err)}"
            ) from err
        except Exception as err:
            _LOGGER.exception(
                "Unexpected error turning OFF server %s: %s", server_name, err
            )
            raise HomeAssistantError(
                f"Unexpected error stopping server {server_name}."
            ) from err
