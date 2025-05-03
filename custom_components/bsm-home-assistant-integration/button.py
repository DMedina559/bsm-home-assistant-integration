"""Button platform for Minecraft Bedrock Server Manager."""

import logging
from typing import Any, Optional, Dict # Import Dict

from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
    ButtonDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT # Import if needed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory # Import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
# Import CoordinatorEntity and the specific coordinator class
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .coordinator import MinecraftBedrockCoordinator
from homeassistant.exceptions import HomeAssistantError

# Import constants and API
from .const import DOMAIN, CONF_SERVER_NAME # Keep CONF_SERVER_NAME for identifying server
from .api import MinecraftBedrockApi, APIError, ServerNotFoundError, ServerNotRunningError

_LOGGER = logging.getLogger(__name__)

# --- Descriptions for Server-Specific Buttons ---
SERVER_BUTTON_DESCRIPTIONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="restart_server",
        name="Restart",
        icon="mdi:restart",
        device_class=ButtonDeviceClass.RESTART,
    ),
    ButtonEntityDescription(
        key="update_server",
        name="Update",
        icon="mdi:update",
        device_class=ButtonDeviceClass.UPDATE,
    ),
    ButtonEntityDescription(
        key="trigger_backup",
        name="Backup",
        icon="mdi:backup-restore",
    ),
    # Add other server-specific buttons here (e.g., export_world)
    # ButtonEntityDescription(
    #     key="export_world",
    #     name="Export World",
    #     icon="mdi:package-variant-closed-up",
    # ),
)

# --- Descriptions for Manager-Global Buttons ---
MANAGER_BUTTON_DESCRIPTIONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="prune_downloads",
        name="Prune Download Cache",
        icon="mdi:delete-sweep",
        entity_category=EntityCategory.CONFIG, # Config action
    ),
    ButtonEntityDescription(
        key="scan_players",
        name="Scan Player Logs",
        icon="mdi:account-search",
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
        servers_data: dict = entry_data["servers"] # Dict keyed by server_name
        manager_device_id: str = entry_data["manager_device_id"]
        api_client: MinecraftBedrockApi = entry_data["api"] # Shared API client
    except KeyError as e:
        _LOGGER.error("Missing expected data for entry %s: %s. Cannot set up buttons.", entry.entry_id, e)
        return

    entities_to_add = []

    # --- Create Buttons for the Manager Device ---
    for description in MANAGER_BUTTON_DESCRIPTIONS:
        entities_to_add.append(
            MinecraftManagerButton(
                entry=entry,
                api_client=api_client, # Pass shared API client
                description=description,
                manager_device_id=manager_device_id, # Link to manager device
            )
        )

    # --- Create Buttons for Each Server Device ---
    if not servers_data:
        _LOGGER.info("No servers configured for this manager entry (%s). Skipping server button setup.", entry.entry_id)
    else:
        _LOGGER.debug("Setting up server buttons for: %s", list(servers_data.keys()))
        # Loop through each server managed by this entry
        for server_name, server_data in servers_data.items():
            try:
                coordinator: MinecraftBedrockCoordinator = server_data["coordinator"]
            except KeyError:
                _LOGGER.error("Coordinator missing for server '%s' in entry %s. Skipping buttons for this server.", server_name, entry.entry_id)
                continue # Skip this server if coordinator setup failed

            # Create server-specific buttons
            for description in SERVER_BUTTON_DESCRIPTIONS:
                entities_to_add.append(
                    MinecraftServerButton(
                        coordinator=coordinator, # Pass the correct coordinator
                        description=description,
                        entry=entry,
                        server_name=server_name, # Pass the specific server name
                        manager_device_id=manager_device_id # Pass manager device ID for linking
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
        manager_device_id: str, # Receive manager device ID
    ) -> None:
        """Initialize the server button."""
        super().__init__(coordinator) # Pass the specific coordinator for this server
        self.entity_description = description
        self._entry = entry
        self._server_name = server_name # Store the specific server name
        # API client is accessed via self.coordinator.api

        # Unique ID: domain_servername_buttonkey
        self._attr_unique_id = f"{DOMAIN}_{self._server_name}_{description.key}"

        # --- Refactored Device Info ---
        # Link to the specific server device, which links to the manager device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._server_name)}, # Use server name as identifier for THIS device
            # Let HA merge name/model etc from sensor/switch device info
            via_device=(DOMAIN, manager_device_id), # Link to the main manager device
        )
        # --- End Refactored Device Info ---

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
        if action == "restart_server":
            api_call = api_client.async_restart_server
        elif action == "update_server":
            api_call = api_client.async_update_server
        elif action == "trigger_backup":
            # Use default backup_type="all" defined in api.py
            api_call = api_client.async_trigger_backup
            success_message = f"Server {server_name} full backup initiated."
        # Add elif for export_world etc. if implemented
        # elif action == "export_world":
        #    api_call = api_client.async_export_world
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
                if action == "restart_server":
                     await self.coordinator.async_request_refresh()

            except APIError as err:
                _LOGGER.error("%s: %s", failure_message, err)
                raise HomeAssistantError(f"{failure_message}: {getattr(err, 'message', err)}") from err
            except Exception as err:
                _LOGGER.exception("Unexpected error during action '%s' on server '%s': %s", action, server_name, err)
                raise HomeAssistantError(f"Unexpected error during server action '{action}': {err}") from err


# --- Manager-Specific Button Entity ---
# Does NOT inherit from CoordinatorEntity as it doesn't depend on a specific server's state
class MinecraftManagerButton(ButtonEntity):
    """Represents an action button for the overall Minecraft Server Manager."""

    _attr_has_entity_name = True # Use description.name as base entity name

    def __init__(
        self,
        entry: ConfigEntry,
        api_client: MinecraftBedrockApi, # Receive shared API client directly
        description: ButtonEntityDescription,
        manager_device_id: str, # Receive manager device ID
    ) -> None:
        """Initialize the manager button."""
        # Don't call super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._api = api_client # Store the shared API client
        self._manager_device_id = manager_device_id

        # Unique ID: domain_manager_host_port_buttonkey
        manager_unique_id = f"{entry.data[CONF_HOST]}:{int(entry.data[CONF_PORT])}"
        self._attr_unique_id = f"{DOMAIN}_{manager_unique_id}_{description.key}"

        # --- Device Info links directly to the Manager Device ---
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._manager_device_id)}, # Use manager device ID
            # Let HA merge name/model etc. from the device created in __init__
        )
        # --- End Device Info ---

        # Manager buttons are generally always available if the integration is loaded
        self._attr_available = True

    async def async_press(self) -> None:
        """Handle the button press for a manager-global action."""
        action = self.entity_description.key
        _LOGGER.info("Button pressed for global manager action '%s'", action)

        api_call = None
        success_message = f"Global action '{action}' initiated."
        failure_message = f"Failed to perform global action '{action}'"

        # Map button key to GLOBAL API method
        # These methods likely don't exist yet in api.py - need to be added!
        if action == "prune_downloads":
            # Assume api_client has a method like async_prune_download_cache()
            if hasattr(self._api, "async_prune_download_cache"):
                 api_call = self._api.async_prune_download_cache
            else:
                 _LOGGER.error("API method async_prune_download_cache not implemented.")
                 raise HomeAssistantError("Prune downloads action not implemented in API client.")
        elif action == "scan_players":
            # Assume api_client has a method like async_scan_player_logs()
             if hasattr(self._api, "async_scan_player_logs"):
                 api_call = self._api.async_scan_player_logs
             else:
                 _LOGGER.error("API method async_scan_player_logs not implemented.")
                 raise HomeAssistantError("Scan player logs action not implemented in API client.")
        else:
            _LOGGER.error("Unhandled manager button action: %s", action)
            raise HomeAssistantError(f"Unknown manager button action requested: {action}")

        # Execute the mapped API call
        if api_call:
            try:
                # Global calls might not need arguments, or might need specific ones
                response = await api_call() # Call without server_name
                _LOGGER.debug("API response for global action '%s': %s", action, response)
                _LOGGER.info(success_message)
                # No coordinator refresh needed for global actions usually

            except APIError as err:
                _LOGGER.error("%s: %s", failure_message, err)
                raise HomeAssistantError(f"{failure_message}: {getattr(err, 'message', err)}") from err
            except Exception as err:
                _LOGGER.exception("Unexpected error during global action '%s': %s", action, err)
                raise HomeAssistantError(f"Unexpected error during global action '{action}': {err}") from err
