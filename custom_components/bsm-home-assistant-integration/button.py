"""Button platform for Minecraft Bedrock Server Manager."""

import logging
from typing import Any, Optional

from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
    ButtonDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .coordinator import MinecraftBedrockCoordinator
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, CONF_SERVER_NAME
from .api import MinecraftBedrockApi, APIError, ServerNotFoundError, ServerNotRunningError

_LOGGER = logging.getLogger(__name__)

# Button Descriptions
BUTTON_DESCRIPTIONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="restart_server",
        name="Restart", # Base name, will be prefixed by device name
        icon="mdi:restart",
        device_class=ButtonDeviceClass.RESTART, # Use standard device class
    ),
    ButtonEntityDescription(
        key="update_server",
        name="Update", # Base name
        icon="mdi:update",
        device_class=ButtonDeviceClass.UPDATE, # Use standard device class
    ),
    ButtonEntityDescription(
        key="trigger_backup",
        name="Backup", # Base name
        icon="mdi:backup-restore",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities based on a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    # Type hint with specific coordinator class
    coordinator: MinecraftBedrockCoordinator = entry_data["coordinator"]

    buttons_to_add = []
    # Iterate over the *actual* tuple now
    for description in BUTTON_DESCRIPTIONS:
        buttons_to_add.append(
            MinecraftServerButton(coordinator, description, entry)
        )

    async_add_entities(buttons_to_add)


# Use specific coordinator type hint
class MinecraftServerButton(CoordinatorEntity[MinecraftBedrockCoordinator], ButtonEntity):
    """Represents an action button for a Minecraft server instance."""

    _attr_has_entity_name = True

    def __init__(
        self,
        # Use specific coordinator type hint
        coordinator: MinecraftBedrockCoordinator,
        description: ButtonEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator) # Pass the specific coordinator instance
        self.entity_description = description
        self._entry = entry
        self._server_name = entry.data[CONF_SERVER_NAME]

        # Unique ID
        self._attr_unique_id = f"{DOMAIN}_{self._server_name}_{description.key}"

        # Link to device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._server_name, entry.entry_id)},
        )

    @property
    def available(self) -> bool:
        """Return True if the coordinator last succeeded."""
        return self.coordinator.last_update_success

    async def async_press(self) -> None:
        """Handle the button press."""
        # Access API client via coordinator
        api_client = self.coordinator.api

        action = self.entity_description.key
        _LOGGER.info("Button pressed for action '%s' on server '%s'", action, self._server_name)

        # Use the api_client variable
        api_call = None
        success_message = f"Action '{action}' initiated for server {self._server_name}." # Default message
        failure_message = f"Failed to perform action '{action}' on server {self._server_name}"

        # Map button key to API method using the retrieved api_client
        if action == "restart_server":
            api_call = api_client.async_restart_server
        elif action == "update_server":
            api_call = api_client.async_update_server
        elif action == "trigger_backup":
            # Use default backup_type="all" defined in api.py
            api_call = api_client.async_trigger_backup
            success_message = f"Server {self._server_name} full backup initiated."
        else:
            _LOGGER.error("Unhandled button action: %s", action)
            raise HomeAssistantError(f"Unknown button action requested: {action}")

        # Execute the mapped API call
        if api_call:
            try:
                # For most buttons, just pass server name
                response = await api_call(self._server_name)
                _LOGGER.debug("API response for action '%s': %s", action, response)
                _LOGGER.info(success_message)

                # Optional refresh
                if action == "restart_server":
                     await self.coordinator.async_request_refresh()

            except APIError as err:
                _LOGGER.error("%s: %s", failure_message, err)
                # Use specific error message if available from err, otherwise generic
                raise HomeAssistantError(f"{failure_message}: {getattr(err, 'message', err)}") from err
            except Exception as err:
                _LOGGER.exception("Unexpected error during action '%s' on server '%s': %s", action, self._server_name, err)
                raise HomeAssistantError(f"Unexpected error during action '{action}': {err}") from err