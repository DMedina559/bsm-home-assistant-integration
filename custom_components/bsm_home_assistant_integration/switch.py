"""Switch platform for Minecraft Bedrock Server Manager."""

import logging
from typing import Any, Optional, Dict

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT 
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .coordinator import MinecraftBedrockCoordinator
from homeassistant.exceptions import HomeAssistantError

# Import constants and API
from .const import DOMAIN, CONF_SERVER_NAME
from .api import MinecraftBedrockApi, APIError, ServerNotRunningError, ServerNotFoundError

_LOGGER = logging.getLogger(__name__)

# Switch Description 
SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="server_control", # Unique key for this switch type within a server device
    name="Server",       # Base name, device name will prefix this ("Minecraft Server (commu) Server")
    icon="mdi:minecraft",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities for all selected servers for this config entry."""
    # Retrieve the central data stored by __init__.py
    try:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        servers_data: dict = entry_data["servers"] # Dict keyed by server_name
        manager_identifier: tuple = entry_data["manager_identifier"] # Get manager identifier tuple
        # api_client is accessed via coordinator now
    except KeyError as e:
        _LOGGER.error("Missing expected data for entry %s: %s. Cannot set up switches.", entry.entry_id, e)
        return

    if not servers_data:
        _LOGGER.debug("No servers configured or successfully initialized for manager entry %s. Skipping switch setup.", entry.entry_id)
        return

    _LOGGER.debug("Setting up switches for servers: %s", list(servers_data.keys()))

    switches_to_add = []
    # --- Loop through each server managed by this entry ---
    for server_name, server_data in servers_data.items():
        # Check if coordinator exists for this server
        coordinator = server_data.get("coordinator")
        if not coordinator:
            _LOGGER.warning("Coordinator object missing for server '%s' in entry %s. Skipping switch.", server_name, entry.entry_id)
            continue

        # --- Create the switch entity for *this* server ---
        switches_to_add.append(
            MinecraftServerSwitch(
                coordinator=coordinator, # Pass the correct coordinator
                description=SWITCH_DESCRIPTION, # Use the shared description
                entry=entry, # Pass entry for context if needed
                server_name=server_name, # Pass the specific server name
                manager_identifier=manager_identifier # Pass manager identifier tuple for linking
            )
        )

    if switches_to_add:
        _LOGGER.info("Adding %d switch entities for manager entry %s", len(switches_to_add), entry.entry_id)
        # No update needed before add for switches typically
        async_add_entities(switches_to_add)


# Use specific coordinator type hint
class MinecraftServerSwitch(CoordinatorEntity[MinecraftBedrockCoordinator], SwitchEntity):
    """Represents the main control switch for a specific Minecraft server instance."""

    _attr_has_entity_name = True # Use description.name as base entity name ("Server")

    def __init__(
        self,
        coordinator: MinecraftBedrockCoordinator,
        description: SwitchEntityDescription,
        entry: ConfigEntry,
        server_name: str, # Explicitly receive server_name
        manager_identifier: tuple, # Receive manager identifier tuple
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator) # Pass the specific coordinator for this server
        self.entity_description = description
        self._entry = entry # Store entry if needed, e.g. for accessing entry.data elsewhere
        self._server_name = server_name # Store the specific server name

        # Unique ID: domain_servername_switchkey
        self._attr_unique_id = f"{DOMAIN}_{self._server_name}_{description.key}"

        # --- Device Info links to the specific server device ---
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._server_name)}, # Use server name as identifier for THIS device
            # Let HA merge name/model etc from sensor platform if defined there
            # Link to the manager device via its identifier tuple
            via_device=manager_identifier,
        )
        # --- End Device Info ---

    @property
    def is_on(self) -> Optional[bool]:
        """Return true if the switch is on (server is running)."""
        # Logic uses self.coordinator (specific to this server)
        if not self.coordinator.data or (isinstance(self.coordinator.data, dict) and self.coordinator.data.get("status") == "error"):
             if isinstance(self.coordinator.data, dict):
                  error_type_name = self.coordinator.data.get("error_type")
                  if error_type_name in [ServerNotRunningError.__name__, ServerNotFoundError.__name__]:
                      return False # Known stopped or not found state
             return None # Unknown state

        process_info = self.coordinator.data.get("process_info")
        # On if process_info is a dictionary (meaning server running)
        return isinstance(process_info, dict)

    @property
    def available(self) -> bool:
        """Return True if coordinator last succeeded."""
        # Availability depends on the health of this server's specific coordinator
        return self.coordinator.last_update_success


    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the server on."""
        # Access API client via the coordinator for this server
        api_client = self.coordinator.api

        _LOGGER.info("Attempting to turn ON server: %s", self._server_name)
        _LOGGER.info("Switch Entity '%s' (Unique ID: %s) calling start for server_name: '%s'", self.entity_id, self.unique_id, self._server_name)
        try:
            # Use the stored self._server_name for the API call
            await api_client.async_start_server(self._server_name)
            # Request refresh for THIS server's coordinator
            await self.coordinator.async_request_refresh()
        except APIError as err:
            _LOGGER.error("Failed to turn ON server %s: %s", self._server_name, err)
            raise HomeAssistantError(f"Failed to start server {self._server_name}: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error turning ON server %s: %s", self._server_name, err)
            raise HomeAssistantError(f"Unexpected error starting server {self._server_name}: {err}") from err


    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the server off."""
        # Access API client via the coordinator for this server
        api_client = self.coordinator.api

        _LOGGER.info("Attempting to turn OFF server: %s", self._server_name)
        try:
            # Use the stored self._server_name for the API call
            await api_client.async_stop_server(self._server_name)
            # Request refresh for THIS server's coordinator
            await self.coordinator.async_request_refresh()
        except APIError as err:
            # Check if the error specifically means it was already stopped
            if "already stopped" in str(err).lower():
                 _LOGGER.warning("Attempted to stop server %s, but it was already stopped.", self._server_name)
                 await self.coordinator.async_request_refresh() # Still refresh state just in case
                 return # Don't raise HA error if already stopped
            _LOGGER.error("Failed to turn OFF server %s: %s", self._server_name, err)
            raise HomeAssistantError(f"Failed to stop server {self._server_name}: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error turning OFF server %s: %s", self._server_name, err)
            raise HomeAssistantError(f"Unexpected error stopping server {self._server_name}: {err}") from err