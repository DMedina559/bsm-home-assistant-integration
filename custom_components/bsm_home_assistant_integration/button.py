"""Button platform for Minecraft Bedrock Server Manager."""

import logging
from typing import Any, Optional, Dict # Import Dict

from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
    ButtonDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .coordinator import MinecraftBedrockCoordinator
from homeassistant.exceptions import HomeAssistantError

# Import constants and API
from .const import DOMAIN, CONF_SERVER_NAME
from .api import MinecraftBedrockApi, APIError, ServerNotFoundError, ServerNotRunningError

_LOGGER = logging.getLogger(__name__)

# --- Descriptions for Server-Specific Buttons ---
SERVER_BUTTON_DESCRIPTIONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="restart_server", name="Restart", icon="mdi:restart",
        device_class=ButtonDeviceClass.RESTART,
    ),
    ButtonEntityDescription(
        key="update_server", name="Update", icon="mdi:update",
        device_class=ButtonDeviceClass.UPDATE,
    ),
    ButtonEntityDescription(
        key="trigger_backup", name="Backup", icon="mdi:backup-restore",
    ),
    #ButtonEntityDescription(key="export_world", name="Export World", icon="mdi:package-variant-closed-up"),
)

# --- Descriptions for Manager-Global Buttons ---
MANAGER_BUTTON_DESCRIPTIONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="scan_players", name="Scan Player Logs", icon="mdi:account-search",
        entity_category=EntityCategory.DIAGNOSTIC, # Diagnostic action
    ),
)


# --- Refactored async_setup_entry ---
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities for manager and all selected servers."""
    # Retrieve the central data stored by __init__.py
    try:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        servers_data: dict = entry_data.get("servers", {}) # Default to empty dict if missing
        manager_identifier: tuple = entry_data["manager_identifier"]
        api_client: MinecraftBedrockApi = entry_data["api"] # Shared API client
    except KeyError as e:
        _LOGGER.error("Missing expected data for entry %s: %s. Cannot set up buttons.", entry.entry_id, e)
        return

    entities_to_add = []

    # --- Create Buttons for the Manager Device ---
    _LOGGER.debug("Setting up manager-global buttons")
    for description in MANAGER_BUTTON_DESCRIPTIONS:
        entities_to_add.append(
            MinecraftManagerButton(
                entry=entry, # Pass entry for context
                api_client=api_client, # Pass shared API client
                description=description,
                manager_identifier=manager_identifier, # Pass manager identifier tuple
            )
        )

    # --- Create Buttons for Each Server Device ---
    if not servers_data:
        _LOGGER.debug("No servers configured or initialized for manager entry %s. Skipping server button setup.", entry.entry_id)
    else:
        _LOGGER.debug("Setting up server buttons for: %s", list(servers_data.keys()))
        # Loop through each server managed by this entry
        for server_name, server_data in servers_data.items():
            # Check if coordinator exists for this server
            coordinator = server_data.get("coordinator")
            if not coordinator:
                _LOGGER.warning("Coordinator object missing for server '%s' in entry %s. Skipping server buttons.", server_name, entry.entry_id)
                continue

            # Create server-specific buttons
            for description in SERVER_BUTTON_DESCRIPTIONS:
                entities_to_add.append(
                    MinecraftServerButton(
                        coordinator=coordinator, # Pass the correct coordinator
                        description=description,
                        entry=entry, # Pass entry for context
                        server_name=server_name, # Pass the specific server name
                        manager_identifier=manager_identifier # Pass manager identifier tuple for linking
                    )
                )

    if entities_to_add:
        _LOGGER.info("Adding %d button entities for manager entry %s", len(entities_to_add), entry.entry_id)
        async_add_entities(entities_to_add)


# --- Server-Specific Button Entity ---
# Inherits from CoordinatorEntity because its availability depends on server coordinator
class MinecraftServerButton(CoordinatorEntity[MinecraftBedrockCoordinator], ButtonEntity):
    """Represents an action button for a specific Minecraft server instance."""

    _attr_has_entity_name = True # Use description.name as base entity name

    def __init__(
        self,
        coordinator: MinecraftBedrockCoordinator,
        description: ButtonEntityDescription,
        entry: ConfigEntry,
        server_name: str, # Explicitly receive server_name
        manager_identifier: tuple, # Receive manager identifier tuple
    ) -> None:
        """Initialize the server button."""
        super().__init__(coordinator) # Pass the specific coordinator for this server
        self.entity_description = description
        self._entry = entry
        self._server_name = server_name # Store the specific server name
        # API client is accessed via self.coordinator.api

        # Unique ID: domain_servername_buttonkey
        self._attr_unique_id = f"{DOMAIN}_{self._server_name}_{description.key}"

        # --- Device Info links to the specific server device ---
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._server_name)}, # Use server name as identifier for THIS device
            # Let HA merge name/model etc from sensor/switch platform
            via_device=manager_identifier, # Link to the main manager device
        )
        # --- End Device Info ---

    @property
    def available(self) -> bool:
        """Return True if the coordinator last succeeded."""
        # Server buttons depend on the server's coordinator being healthy
        return self.coordinator.last_update_success

    async def async_press(self) -> None:
        """Handle the button press for a server-specific action."""
        # Access API client via the coordinator for this server
        api_client = self.coordinator.api
        action = self.entity_description.key
        server_name = self._server_name # Use stored server name

        _LOGGER.info("Button pressed for action '%s' on server '%s'", action, server_name)

        api_call = None
        success_message = f"Action '{action}' initiated for server {server_name}." # Default message
        failure_message = f"Failed to perform action '{action}' on server {server_name}"

        # Map button key to API method using the retrieved api_client
        if action == "restart_server": api_call = api_client.async_restart_server
        elif action == "update_server": api_call = api_client.async_update_server
        elif action == "trigger_backup": api_call = api_client.async_trigger_backup; success_message = f"Server {server_name} full backup initiated."
        # elif action == "export_world": api_call = api_client.async_export_world
        else:
            _LOGGER.error("Unhandled server button action: %s for server %s", action, server_name)
            raise HomeAssistantError(f"Unknown server button action requested: {action}")

        # Execute the mapped API call
        if api_call:
            try:
                # Pass the specific server name
                response = await api_call(server_name)
                _LOGGER.debug("API response for action '%s' on server '%s': %s", action, server_name, response)
                _LOGGER.info(success_message)
                # Optional refresh for actions that change state quickly
                if action == "restart_server": await self.coordinator.async_request_refresh()
            except APIError as err:
                _LOGGER.error("%s: %s", failure_message, err)
                raise HomeAssistantError(f"{failure_message}: {getattr(err, 'message', err)}") from err
            except Exception as err:
                _LOGGER.exception("Unexpected error during action '%s' on server '%s': %s", action, server_name, err)
                raise HomeAssistantError(f"Unexpected error during server action '{action}': {err}") from err


# --- Manager-Specific Button Entity ---
# Does NOT inherit from CoordinatorEntity
class MinecraftManagerButton(ButtonEntity):
    """Represents an action button for the overall Minecraft Server Manager."""

    _attr_has_entity_name = True # Use description.name as base entity name

    def __init__(
        self,
        entry: ConfigEntry,
        api_client: MinecraftBedrockApi, # Receive shared API client directly
        description: ButtonEntityDescription,
        manager_identifier: tuple, # Receive manager identifier tuple
    ) -> None:
        """Initialize the manager button."""
        self.entity_description = description
        self._entry = entry # Store entry for context if needed
        self._api = api_client # Store the shared API client
        self._manager_identifier = manager_identifier # Store identifier

        # Unique ID: domain_manager_host_port_buttonkey
        manager_host_port_id = manager_identifier[1] # Get the host:port part
        self._attr_unique_id = f"{DOMAIN}_{manager_host_port_id}_{description.key}"

        # --- Device Info links directly to the Manager Device ---
        self._attr_device_info = DeviceInfo(
            identifiers={self._manager_identifier}, # Use the identifier tuple directly
            # Let HA merge name/model etc from the device created in __init__
        )
        # --- End Device Info ---

        # Manager buttons are generally always available if the integration is loaded
        self._attr_available = True # Could add check here if manager API has a health status

    async def async_press(self) -> None:
        """Handle the button press for a manager-global action."""
        action = self.entity_description.key
        _LOGGER.info("Button pressed for global manager action '%s'", action)

        # Use the stored self._api client
        api_call = None
        success_message = f"Global action '{action}' initiated."
        failure_message = f"Failed to perform global action '{action}'"

        # Map button key to GLOBAL API method
        if action == "scan_players":
             if hasattr(self._api, "async_scan_player_logs"): api_call = self._api.async_scan_player_logs
             else: _LOGGER.error("API method async_scan_player_logs not implemented."); raise HomeAssistantError("Scan player logs action not implemented.")
        else:
            _LOGGER.error("Unhandled manager button action: %s", action)
            raise HomeAssistantError(f"Unknown manager button action requested: {action}")

        # Execute the mapped API call
        if api_call:
            try:
                response = await api_call()
                _LOGGER.debug("API response for global action '%s': %s", action, response)
                _LOGGER.info(success_message)
            except APIError as err:
                _LOGGER.error("%s: %s", failure_message, err)
                raise HomeAssistantError(f"{failure_message}: {getattr(err, 'message', err)}") from err
            except Exception as err:
                _LOGGER.exception("Unexpected error during global action '%s': %s", action, err)
                raise HomeAssistantError(f"Unexpected error during global action '{action}': {err}") from err