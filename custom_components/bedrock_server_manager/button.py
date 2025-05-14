# custom_components/bedrock_server_manager/button.py
"""Button platform for Bedrock Server Manager."""

import logging
from typing import (
    Any,
    Optional,
    Dict,
    Tuple,
    List,
)  # Ensure List is imported for options

from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
    ButtonDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
)  # For configuration_url in device_info
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.components.persistent_notification import (
    async_create as async_create_notification,
)

# --- IMPORT FROM LOCAL MODULES ---
from .coordinator import (
    MinecraftBedrockCoordinator,
    ManagerDataCoordinator,
)
from .const import (
    DOMAIN,
    CONF_SERVER_NAMES,
)  # Make sure CONF_SERVER_NAMES is imported if used


from pybedrock_server_manager import (
    BedrockServerManagerApi,
    APIError,
    AuthError,
    CannotConnectError,
    ServerNotFoundError,
    ServerNotRunningError,
)


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
        key="trigger_server_backup_all", name="Backup All", icon="mdi:backup-restore"
    ),
    ButtonEntityDescription(
        key="export_server_world",
        name="Export World",
        icon="mdi:file-export-outline",
        entity_category=EntityCategory.CONFIG,
    ),
    ButtonEntityDescription(
        key="prune_server_backups",
        name="Prune Backups",
        icon="mdi:delete-sweep",
        entity_category=EntityCategory.CONFIG,
    ),
)

# --- Descriptions for Manager-Global Buttons ---
MANAGER_BUTTON_DESCRIPTIONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="scan_players",
        name="Scan Player Logs",
        icon="mdi:account-search",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities from a config entry."""
    try:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        servers_data: dict = entry_data.get("servers", {})
        manager_identifier: Tuple[str, str] = entry_data["manager_identifier"]
        api_client: BedrockServerManagerApi = entry_data["api"]
        manager_coordinator: Optional[ManagerDataCoordinator] = entry_data.get(
            "manager_coordinator"
        )

    except KeyError as e:
        _LOGGER.error(
            "Missing expected data for entry %s (Key: %s). Cannot set up buttons.",
            entry.entry_id,
            e,
        )
        return

    entities_to_add = []

    _LOGGER.debug(
        "Setting up manager buttons for entry %s (Manager ID: %s)",
        entry.entry_id,
        manager_identifier[1],
    )
    if manager_coordinator:  # Only add manager buttons if coordinator exists
        for description in MANAGER_BUTTON_DESCRIPTIONS:
            entities_to_add.append(
                MinecraftManagerButton(
                    entry=entry,  # Pass the full entry
                    api_client=api_client,
                    description=description,
                    manager_identifier=manager_identifier,
                    manager_coordinator=manager_coordinator,
                )
            )
    else:
        _LOGGER.warning(
            "Manager coordinator not found for entry %s, skipping manager buttons.",
            entry.entry_id,
        )

    if not servers_data:
        _LOGGER.debug(
            "No servers found for entry %s (Manager ID: %s). Skipping server buttons.",
            entry.entry_id,
            manager_identifier[1],
        )
    else:
        _LOGGER.debug(
            "Setting up server buttons for servers: %s (Manager ID: %s)",
            list(servers_data.keys()),
            manager_identifier[1],
        )
        for server_name, server_data_dict in servers_data.items():
            coordinator = server_data_dict.get("coordinator")
            if not coordinator:
                _LOGGER.warning(
                    "Coordinator missing for server '%s' (Manager ID: %s). Skipping its buttons.",
                    server_name,
                    manager_identifier[1],
                )
                continue

            # Ensure coordinator has data before adding entity
            if coordinator.last_update_success and coordinator.data:
                for description in SERVER_BUTTON_DESCRIPTIONS:
                    entities_to_add.append(
                        MinecraftServerButton(
                            coordinator=coordinator,
                            description=description,
                            server_name=server_name,
                            manager_identifier=manager_identifier,
                        )
                    )
            else:
                _LOGGER.warning(
                    "Coordinator for server '%s' (Manager ID: %s) has no data or last update failed; skipping its buttons.",
                    server_name,
                    manager_identifier[1],
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
        _LOGGER.debug(
            "No button entities to add for entry %s (%s)", entry.title, entry.entry_id
        )


class MinecraftServerButton(
    CoordinatorEntity[MinecraftBedrockCoordinator], ButtonEntity
):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MinecraftBedrockCoordinator,
        description: ButtonEntityDescription,
        server_name: str,
        manager_identifier: Tuple[str, str],
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._server_name = server_name
        self._manager_host_port_id = manager_identifier[1]

        self._attr_unique_id = f"{DOMAIN}_{self._manager_host_port_id}_{self._server_name}_{description.key}"
        _LOGGER.debug(
            "ServerButton Unique ID for %s (%s): %s for key %s",
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
            name=f"BSM {self._server_name} ({self._manager_host_port_id})",  # Make device name more descriptive
            manufacturer="Bedrock Server Manager (Server)",
            model="Minecraft Server",
            via_device=manager_identifier,
            sw_version=(
                self.coordinator.data.get("server_version")
                if self.coordinator.data
                else "Unknown"  # Provide a fallback
            ),
            configuration_url=f"http://{coordinator.config_entry.data[CONF_HOST]}:{int(coordinator.config_entry.data[CONF_PORT])}",
        )

    @property
    def available(self) -> bool:
        if self.entity_description.key == "remove_server_from_ha":
            return True  # This button should always be available if entity exists
        return self.coordinator.last_update_success and bool(self.coordinator.data)

    async def async_press(self) -> None:
        action_key = self.entity_description.key

        # Existing logic for other server buttons
        api_client: BedrockServerManagerApi = self.coordinator.api
        server_name = self._server_name
        _LOGGER.info(
            "Button pressed: Action Key '%s', Server '%s' (Manager: %s)",
            action_key,
            server_name,
            self._manager_host_port_id,
        )
        api_call_coro = None
        success_message = f"Action '{action_key}' initiated for server '{server_name}'."
        failure_message_prefix = (
            f"Failed action '{action_key}' on server '{server_name}'"
        )
        try:
            if action_key == "restart_server":
                api_call_coro = api_client.async_restart_server(server_name)
            elif action_key == "update_server":
                api_call_coro = api_client.async_update_server(server_name)
            elif action_key == "trigger_server_backup_all":
                api_call_coro = api_client.async_trigger_server_backup(
                    server_name, backup_type="all"
                )
                success_message = f"Full backup initiated for server '{server_name}'."
            elif action_key == "export_server_world":
                api_call_coro = api_client.async_export_server_world(server_name)
            elif action_key == "prune_server_backups":
                api_call_coro = api_client.async_prune_server_backups(
                    server_name, keep=None
                )
                success_message = (
                    f"Backup pruning initiated for server '{server_name}'."
                )
            else:
                _LOGGER.error(
                    "Unhandled server button action key: %s for server %s",
                    action_key,
                    server_name,
                )
                raise HomeAssistantError(
                    f"Unknown server button action requested: {action_key}"
                )

            if api_call_coro:
                response = await api_call_coro
                _LOGGER.debug(
                    "API response for '%s' on '%s': %s",
                    action_key,
                    server_name,
                    response,
                )
                _LOGGER.info(success_message)
                if action_key == "restart_server":
                    await self.coordinator.async_request_refresh()
        except AuthError as err:
            _LOGGER.error("%s: Authentication error - %s", failure_message_prefix, err)
            raise HomeAssistantError(
                f"{failure_message_prefix}: Authentication failed."
            ) from err
        except CannotConnectError as err:
            _LOGGER.error("%s: Connection error - %s", failure_message_prefix, err)
            raise HomeAssistantError(
                f"{failure_message_prefix}: Could not connect."
            ) from err
        except ServerNotFoundError as err:
            _LOGGER.error("%s: Server not found - %s", failure_message_prefix, err)
            raise HomeAssistantError(
                f"{failure_message_prefix}: Server not found by manager."
            ) from err
        except ServerNotRunningError as err:
            _LOGGER.error("%s: Server not running - %s", failure_message_prefix, err)
            raise HomeAssistantError(
                f"{failure_message_prefix}: Server is not running."
            ) from err
        except APIError as err:
            _LOGGER.error("%s: API error - %s", failure_message_prefix, err)
            raise HomeAssistantError(
                f"{failure_message_prefix}: API communication error."
            ) from err
        except Exception as err:
            _LOGGER.exception("%s: Unexpected error - %s", failure_message_prefix, err)
            raise HomeAssistantError(
                f"{failure_message_prefix}: An unexpected error occurred."
            ) from err


class MinecraftManagerButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: ConfigEntry,
        api_client: BedrockServerManagerApi,
        description: ButtonEntityDescription,
        manager_identifier: Tuple[str, str],
        manager_coordinator: Optional[ManagerDataCoordinator] = None,
    ) -> None:
        self.entity_description = description
        self._entry = entry  # Storing the config entry
        self._api = api_client
        self._manager_coordinator = manager_coordinator
        self._manager_host_port_id = manager_identifier[1]
        self._attr_unique_id = (
            f"{DOMAIN}_{self._manager_host_port_id}_{description.key}"
        )
        self._attr_device_info = dr.DeviceInfo(identifiers={manager_identifier})
        self._attr_available = True

    async def async_press(self) -> None:
        action_key = self.entity_description.key
        _LOGGER.info(
            "Button pressed: Global action '%s' (Manager: %s)",
            action_key,
            self._manager_host_port_id,
        )
        api_call_coro = None
        success_message = f"Global action '{action_key}' initiated."
        failure_message_prefix = f"Failed global action '{action_key}'"
        try:
            if action_key == "scan_players":
                api_call_coro = self._api.async_scan_players()
            else:
                _LOGGER.error("Unhandled manager button action key: %s", action_key)
                raise HomeAssistantError(
                    f"Unknown manager button action requested: {action_key}"
                )

            if api_call_coro:
                response = await api_call_coro
                _LOGGER.debug(
                    "API response for global action '%s': %s", action_key, response
                )
                _LOGGER.info(success_message)
                if action_key == "scan_players" and self._manager_coordinator:
                    _LOGGER.debug(
                        "Requesting refresh of ManagerDataCoordinator after scan_players."
                    )
                    await self._manager_coordinator.async_request_refresh()
        except AuthError as err:
            _LOGGER.error("%s: Authentication error - %s", failure_message_prefix, err)
            raise HomeAssistantError(
                f"{failure_message_prefix}: Authentication failed."
            ) from err
        except CannotConnectError as err:
            _LOGGER.error("%s: Connection error - %s", failure_message_prefix, err)
            raise HomeAssistantError(
                f"{failure_message_prefix}: Could not connect."
            ) from err
        except APIError as err:
            _LOGGER.error("%s: API error - %s", failure_message_prefix, err)
            raise HomeAssistantError(
                f"{failure_message_prefix}: API communication error."
            ) from err
        except Exception as err:
            _LOGGER.exception("%s: Unexpected error - %s", failure_message_prefix, err)
            raise HomeAssistantError(
                f"{failure_message_prefix}: An unexpected error occurred."
            ) from err
