# custom_components/bedrock_server_manager/button.py
"""Button platform for Bedrock Server Manager."""

import logging
from typing import Any, Optional, Dict  # Keep imports

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
from homeassistant.exceptions import HomeAssistantError  # Keep this

# --- IMPORT FROM LOCAL MODULES ---
from .coordinator import MinecraftBedrockCoordinator  # Keep coordinator import
from .const import DOMAIN  # Removed CONF_SERVER_NAME as it's not directly used here

# --- IMPORT FROM THE NEW LIBRARY ---
from pybedrock_server_manager import (
    BedrockServerManagerApi,
    APIError,
    AuthError,
    CannotConnectError,
    ServerNotFoundError,  # Kept just in case, though less likely for buttons
    ServerNotRunningError,  # Kept just in case
)

# --- END IMPORT FROM NEW LIBRARY ---


_LOGGER = logging.getLogger(__name__)

# --- Descriptions for Server-Specific Buttons (Unchanged) ---
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
        key="trigger_server_backup", name="Backup", icon="mdi:backup-restore"
    ),  # Key updated to match method
    ButtonEntityDescription(
        key="export_server_world",
        name="Export World",
        icon="mdi:file-export-outline",
        entity_category=EntityCategory.CONFIG,
    ),  # Key updated
    ButtonEntityDescription(
        key="prune_server_backups",
        name="Prune Backups",
        icon="mdi:delete-sweep",
        entity_category=EntityCategory.CONFIG,
    ),  # Key updated
)

# --- Descriptions for Manager-Global Buttons (Unchanged) ---
MANAGER_BUTTON_DESCRIPTIONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="scan_players",
        name="Scan Player Logs",
        icon="mdi:account-search",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


# --- Setup Entry Function (Unchanged from previous provided version) ---
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities from a config entry."""
    try:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        servers_data: dict = entry_data.get("servers", {})
        manager_identifier: tuple = entry_data["manager_identifier"]
        api_client: BedrockServerManagerApi = entry_data["api"]
    except KeyError as e:
        _LOGGER.error(
            "Missing expected data for entry %s (%s). Cannot set up buttons.",
            entry.entry_id,
            e,
        )
        return

    entities_to_add = []

    _LOGGER.debug("Setting up manager buttons for entry %s", entry.entry_id)
    for description in MANAGER_BUTTON_DESCRIPTIONS:
        entities_to_add.append(
            MinecraftManagerButton(
                entry=entry,
                api_client=api_client,
                description=description,
                manager_identifier=manager_identifier,
            )
        )

    if not servers_data:
        _LOGGER.debug(
            "No servers found for entry %s. Skipping server buttons.", entry.entry_id
        )
    else:
        _LOGGER.debug(
            "Setting up server buttons for servers: %s", list(servers_data.keys())
        )
        for server_name, server_data in servers_data.items():
            coordinator = server_data.get("coordinator")
            if not coordinator:
                _LOGGER.warning(
                    "Coordinator missing for server '%s' in entry %s. Skipping buttons.",
                    server_name,
                    entry.entry_id,
                )
                continue

            for description in SERVER_BUTTON_DESCRIPTIONS:
                entities_to_add.append(
                    MinecraftServerButton(
                        coordinator=coordinator,
                        description=description,
                        entry=entry,
                        server_name=server_name,
                        manager_identifier=manager_identifier,
                    )
                )

    if entities_to_add:
        _LOGGER.info(
            "Adding %d button entities for entry %s (%s)",
            len(entities_to_add),
            entry.title,
            entry.entry_id,
        )
        async_add_entities(entities_to_add)
    else:
        _LOGGER.debug("No button entities to add for entry %s", entry.entry_id)


# --- Server Button Class (Updated method calls) ---
class MinecraftServerButton(
    CoordinatorEntity[MinecraftBedrockCoordinator], ButtonEntity
):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MinecraftBedrockCoordinator,
        description: ButtonEntityDescription,
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
    def available(self) -> bool:
        return self.coordinator.last_update_success

    async def async_press(self) -> None:
        api_client: BedrockServerManagerApi = self.coordinator.api
        action_key = (
            self.entity_description.key
        )  # This is the 'key' from ButtonEntityDescription
        server_name = self._server_name

        _LOGGER.info(
            "Button pressed: Action Key '%s', Server '%s'", action_key, server_name
        )

        api_call = None
        success_message = f"Action '{action_key}' initiated for server '{server_name}'."
        failure_message = f"Failed action '{action_key}' on server '{server_name}'"

        # Map button key to the NEW API method names
        if action_key == "restart_server":
            api_call = api_client.async_restart_server
        elif action_key == "update_server":
            api_call = api_client.async_update_server
        elif action_key == "trigger_server_backup":  # Updated key

            async def backup_wrapper(s_name):  # Wrapper for default args
                return await api_client.async_trigger_server_backup(
                    s_name, backup_type="all"
                )

            api_call = backup_wrapper
            success_message = f"Full backup initiated for server '{server_name}'."
        elif action_key == "export_server_world":  # Updated key
            api_call = api_client.async_export_server_world
        elif action_key == "prune_server_backups":  # Updated key

            async def prune_wrapper(s_name):  # Wrapper for default args
                return await api_client.async_prune_server_backups(s_name, keep=None)

            api_call = prune_wrapper
            success_message = f"Backup pruning initiated for server '{server_name}'."
        else:
            _LOGGER.error(
                "Unhandled server button action key: %s for server %s",
                action_key,
                server_name,
            )
            raise HomeAssistantError(
                f"Unknown server button action requested: {action_key}"
            )

        if api_call:
            try:
                response = await api_call(server_name)
                _LOGGER.debug(
                    "API response for '%s' on '%s': %s",
                    action_key,
                    server_name,
                    response,
                )
                _LOGGER.info(success_message)
                if action_key == "restart_server":  # Still use original key for logic
                    await self.coordinator.async_request_refresh()
            except AuthError as err:
                _LOGGER.error("%s: Authentication error - %s", failure_message, err)
                raise HomeAssistantError(
                    f"{failure_message}: Authentication failed. Check credentials."
                ) from err
            except CannotConnectError as err:
                _LOGGER.error("%s: Connection error - %s", failure_message, err)
                raise HomeAssistantError(
                    f"{failure_message}: Could not connect to manager."
                ) from err
            except APIError as err:
                _LOGGER.error("%s: API error - %s", failure_message, err)
                raise HomeAssistantError(
                    f"{failure_message}: {getattr(err, 'message', err)}"
                ) from err
            except Exception as err:
                _LOGGER.exception("%s: Unexpected error - %s", failure_message, err)
                raise HomeAssistantError(
                    f"{failure_message}: An unexpected error occurred."
                ) from err


# --- Manager Button Class (Updated method call) ---
class MinecraftManagerButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: ConfigEntry,
        api_client: BedrockServerManagerApi,
        description: ButtonEntityDescription,
        manager_identifier: tuple,
    ) -> None:
        self.entity_description = description
        self._entry = entry
        self._api = api_client
        self._manager_identifier = manager_identifier
        manager_host_port_id = manager_identifier[1]
        self._attr_unique_id = f"{DOMAIN}_{manager_host_port_id}_{description.key}"
        self._attr_device_info = DeviceInfo(identifiers={self._manager_identifier})
        self._attr_available = True

    async def async_press(self) -> None:
        action_key = self.entity_description.key
        _LOGGER.info("Button pressed: Global action '%s'", action_key)

        api_call = None
        success_message = f"Global action '{action_key}' initiated."
        failure_message = f"Failed global action '{action_key}'"

        if action_key == "scan_players":
            api_call = self._api.async_scan_players  # Updated method name
        else:
            _LOGGER.error("Unhandled manager button action key: %s", action_key)
            raise HomeAssistantError(
                f"Unknown manager button action requested: {action_key}"
            )

        if api_call:
            try:
                response = await api_call()
                _LOGGER.debug(
                    "API response for global action '%s': %s", action_key, response
                )
                _LOGGER.info(success_message)
                # Optional: Refresh manager coordinator if its data changes
                # if action_key == "scan_players":
                #    if manager_coord := self.hass.data[DOMAIN][self._entry.entry_id].get("manager_coordinator"):
                #        await manager_coord.async_request_refresh()
            except AuthError as err:
                _LOGGER.error("%s: Authentication error - %s", failure_message, err)
                raise HomeAssistantError(
                    f"{failure_message}: Authentication failed. Check credentials."
                ) from err
            except CannotConnectError as err:
                _LOGGER.error("%s: Connection error - %s", failure_message, err)
                raise HomeAssistantError(
                    f"{failure_message}: Could not connect to manager."
                ) from err
            except APIError as err:
                _LOGGER.error("%s: API error - %s", failure_message, err)
                raise HomeAssistantError(
                    f"{failure_message}: {getattr(err, 'message', err)}"
                ) from err
            except Exception as err:
                _LOGGER.exception("%s: Unexpected error - %s", failure_message, err)
                raise HomeAssistantError(
                    f"{failure_message}: An unexpected error occurred."
                ) from err
