"""Switch platform for Minecraft Bedrock Server Manager."""

import logging
from typing import Any, Optional

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
# Import CoordinatorEntity separately and the specific coordinator class
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .coordinator import MinecraftBedrockCoordinator # <-- Import specific coordinator
from homeassistant.exceptions import HomeAssistantError

# Import constants and API
from .const import DOMAIN, CONF_SERVER_NAME
from .api import MinecraftBedrockApi, APIError, ServerNotRunningError, ServerNotFoundError

_LOGGER = logging.getLogger(__name__)

# SWITCH_DESCRIPTION remains the same
SWITCH_DESCRIPTION = SwitchEntityDescription( key="server_control", name="Server", icon="mdi:minecraft", )

async def async_setup_entry( hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback, ) -> None:
    """Set up switch entities based on a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    # Type hint with specific coordinator class
    coordinator: MinecraftBedrockCoordinator = entry_data["coordinator"]
    async_add_entities([MinecraftServerSwitch(coordinator, SWITCH_DESCRIPTION, entry)], True)

# Use specific coordinator type hint
class MinecraftServerSwitch(CoordinatorEntity[MinecraftBedrockCoordinator], SwitchEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        # Use specific coordinator type hint
        coordinator: MinecraftBedrockCoordinator,
        description: SwitchEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator) # Pass the specific coordinator instance
        self.entity_description = description
        self._entry = entry
        self._server_name = entry.data[CONF_SERVER_NAME]
        # --- API Client is now accessed via self.coordinator.api ---
        # REMOVE self._api = ... line if it was accidentally left

        self._attr_unique_id = f"{DOMAIN}_{self._server_name}_{description.key}"
        self._attr_device_info = DeviceInfo( identifiers={(DOMAIN, self._server_name, entry.entry_id)}, )

    # is_on property remains the same
    @property
    def is_on(self) -> Optional[bool]:
        # ... (logic remains the same) ...
        if not self.coordinator.data or (isinstance(self.coordinator.data, dict) and self.coordinator.data.get("status") == "error"):
             if isinstance(self.coordinator.data, dict):
                  error_type_name = self.coordinator.data.get("error_type")
                  if error_type_name == ServerNotRunningError.__name__: return False
                  if error_type_name == ServerNotFoundError.__name__: return False
             return None
        process_info = self.coordinator.data.get("process_info")
        return isinstance(process_info, dict)

    # available property remains the same
    @property
    def available(self) -> bool: return self.coordinator.last_update_success

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the server on."""
        # --- Access API client via coordinator ---
        api_client = self.coordinator.api
        # --- End Access ---

        _LOGGER.info("Attempting to turn ON server: %s", self._server_name)
        try:
            await api_client.async_start_server(self._server_name) # Use the client
            await self.coordinator.async_request_refresh()
        except APIError as err:
            _LOGGER.error("Failed to turn ON server %s: %s", self._server_name, err)
            raise HomeAssistantError(f"Failed to start server {self._server_name}: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error turning ON server %s: %s", self._server_name, err)
            raise HomeAssistantError(f"Unexpected error starting server {self._server_name}: {err}") from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the server off."""
        # --- Access API client via coordinator ---
        api_client = self.coordinator.api
        # --- End Access ---

        _LOGGER.info("Attempting to turn OFF server: %s", self._server_name)
        try:
            await api_client.async_stop_server(self._server_name) # Use the client
            await self.coordinator.async_request_refresh()
        except APIError as err:
            if "already stopped" in str(err).lower():
                 _LOGGER.warning("Attempted to stop server %s, but it was already stopped.", self._server_name)
                 await self.coordinator.async_request_refresh()
                 return
            _LOGGER.error("Failed to turn OFF server %s: %s", self._server_name, err)
            raise HomeAssistantError(f"Failed to stop server {self._server_name}: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error turning OFF server %s: %s", self._server_name, err)
            raise HomeAssistantError(f"Unexpected error stopping server {self._server_name}: {err}") from err