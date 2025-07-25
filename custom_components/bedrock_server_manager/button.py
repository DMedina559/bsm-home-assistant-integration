# custom_components/bedrock_server_manager/button.py
"""Button platform for Bedrock Server Manager."""

import logging
from typing import Any, Optional, Dict, Tuple, List, cast

from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
    ButtonDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.components.persistent_notification import (
    async_create as async_create_notification,
)

from .coordinator import MinecraftBedrockCoordinator, ManagerDataCoordinator
from .const import DOMAIN, ATTR_INSTALLED_VERSION, CONF_BASE_URL
from bsm_api_client import (
    BedrockServerManagerApi,
    APIError,
    AuthError,
    CannotConnectError,
    ServerNotFoundError,
    ServerNotRunningError,
)

_LOGGER = logging.getLogger(__name__)

# --- Descriptions for Server-Specific Buttons ---
SERVER_BUTTON_DESCRIPTIONS: Tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="restart_server",
        name="Restart Server",
        icon="mdi:restart",
        device_class=ButtonDeviceClass.RESTART,
        entity_registry_enabled_default=False,
    ),
    ButtonEntityDescription(
        key="update_server",
        name="Update Server",
        icon="mdi:update",
        device_class=ButtonDeviceClass.UPDATE,
    ),
    ButtonEntityDescription(
        key="trigger_server_backup_all",
        name="Backup All",
        icon="mdi:archive-arrow-down-outline",
    ),
    ButtonEntityDescription(
        key="export_server_world",
        name="Export World",
        icon="mdi:earth-box",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    ButtonEntityDescription(
        key="prune_server_backups",
        name="Prune Backups",
        icon="mdi:archive-refresh-outline",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
)

# --- Descriptions for Manager-Global Buttons ---
MANAGER_BUTTON_DESCRIPTIONS: Tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="scan_players",
        name="Scan for Players",
        icon="mdi:account-search-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ButtonEntityDescription(
        key="reload_plugins",
        name="Reload Plugins",
        icon="mdi:puzzle-outline",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities from a config entry."""
    _LOGGER.debug("Setting up button platform for BSM entry: %s", entry.entry_id)
    try:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        api_client = cast(BedrockServerManagerApi, entry_data["api"])
        original_manager_identifier_tuple = cast(
            Tuple[str, str], entry_data["manager_identifier"]
        )
        manager_coordinator = cast(
            Optional[ManagerDataCoordinator], entry_data.get("manager_coordinator")
        )
        servers_config_data: Dict[str, Dict[str, Any]] = entry_data.get("servers", {})
    except KeyError as e:
        _LOGGER.error(
            "Button setup failed for entry %s: Missing expected data (Key: %s). "
            "This might happen if __init__.py did not complete successfully.",
            entry.entry_id,
            e,
        )
        return

    manager_identifier_for_buttons = original_manager_identifier_tuple

    entities_to_add: List[ButtonEntity] = []

    bsm_os_type_for_servers: str = "Unknown"  # Default value
    if (
        manager_coordinator
        and manager_coordinator.last_update_success
        and manager_coordinator.data
    ):
        manager_info = manager_coordinator.data.get("info", {})
        if isinstance(manager_info, dict):
            bsm_os_type_for_servers = manager_info.get("os_type", "Unknown")
        _LOGGER.debug(
            "BSM OS type determined as: %s for entry %s",
            bsm_os_type_for_servers,
            entry.title,
        )
    else:
        _LOGGER.warning(
            "ManagerDataCoordinator for BSM '%s' not available, has no data, or last update failed; "
            "BSM OS type for server devices will default to '%s'.",
            entry.title,
            bsm_os_type_for_servers,
        )

    # Setup Manager Buttons
    if manager_coordinator:
        _LOGGER.debug(
            "Setting up manager-level buttons for BSM: %s",
            manager_identifier_for_buttons[1],
        )
        for description in MANAGER_BUTTON_DESCRIPTIONS:
            entities_to_add.append(
                MinecraftManagerButton(
                    config_entry_id=entry.entry_id,  # Pass config_entry_id for API client retrieval
                    api_client=api_client,  # Can pass directly or retrieve via hass.data
                    description=description,
                    manager_identifier=manager_identifier_for_buttons,
                    manager_coordinator=manager_coordinator,  # Pass for potential refresh
                )
            )
    else:
        _LOGGER.warning(
            "ManagerDataCoordinator not found for BSM '%s', skipping manager-level buttons.",
            entry.title,
        )

    # Setup Server-Specific Buttons
    if not servers_config_data:
        _LOGGER.info(
            "No servers configured for BSM '%s'; no server-specific buttons will be created.",
            entry.title,
        )

    for server_name, server_entry_data in servers_config_data.items():
        coordinator = cast(
            Optional[MinecraftBedrockCoordinator], server_entry_data.get("coordinator")
        )
        if not coordinator:
            _LOGGER.warning(
                "Coordinator missing for server '%s' under BSM '%s'. Skipping its buttons.",
                server_name,
                entry.title,
            )
            continue

        # Get static version for initial DeviceInfo
        installed_version_static = server_entry_data.get(ATTR_INSTALLED_VERSION)

        if coordinator.last_update_success and coordinator.data is not None:
            for description in SERVER_BUTTON_DESCRIPTIONS:
                entities_to_add.append(
                    MinecraftServerButton(
                        coordinator=coordinator,
                        description=description,
                        server_name=server_name,
                        manager_identifier=manager_identifier_for_buttons,
                        installed_version_static=installed_version_static,
                        bsm_os_type=bsm_os_type_for_servers,
                    )
                )
        else:
            _LOGGER.warning(
                "Coordinator for server '%s' (BSM '%s') has no data or last update failed; "
                "skipping its button entities.",
                server_name,
                entry.title,
            )

    if entities_to_add:
        _LOGGER.info(
            "Adding %d BSM button entities for BSM '%s'.",
            len(entities_to_add),
            entry.title,
        )
        async_add_entities(entities_to_add)
    else:
        _LOGGER.info("No button entities were added for BSM '%s'.", entry.title)


class MinecraftServerButton(
    CoordinatorEntity[MinecraftBedrockCoordinator], ButtonEntity
):
    """Representation of a button entity for a specific Minecraft server action."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MinecraftBedrockCoordinator,
        description: ButtonEntityDescription,
        server_name: str,  # This is the key from config flow (e.g., "s1", "survival_world")
        manager_identifier: Tuple[str, str],  # (DOMAIN, manager_host_port_id string)
        installed_version_static: Optional[str],  # Can be None
        bsm_os_type: Optional[str],
    ) -> None:
        """Initialize the server button."""
        super().__init__(coordinator)  # Initialize CoordinatorEntity
        self.entity_description = description
        self._server_name = (
            server_name  # Store the server name (e.g., "s1", "my_world")
        )
        self._manager_host_port_id = manager_identifier[1]
        self._bsm_os_type = bsm_os_type

        # Construct unique_id for the button entity itself
        # Uses manager_host_port_id to ensure uniqueness across BSM instances if host/port are part of it.
        self._attr_unique_id = (
            f"{DOMAIN}_{self._manager_host_port_id}_{self._server_name}_{description.key}".lower()
            .replace(":", "_")
            .replace(".", "_")
        )  # Make it a safe string for an entity ID

        _LOGGER.debug(
            "Init ServerButton '%s' for server '%s' (Manager ID: %s), UniqueID: %s",
            description.name,  # The specific action name like "Restart Server"
            self._server_name,
            self._manager_host_port_id,
            self._attr_unique_id,
        )

        config_entry_data = coordinator.config_entry.data
        safe_config_url = config_entry_data.get(CONF_BASE_URL)

        # Construct the model string
        base_model_name = "Minecraft Bedrock Server"
        model_name_with_os = base_model_name
        # Define uninformative OS types that shouldn't alter the base model name
        uninformative_os_types = ["Unknown", None, ""]
        if self._bsm_os_type and self._bsm_os_type not in uninformative_os_types:
            model_name_with_os = f"{base_model_name} ({self._bsm_os_type})"
        else:
            _LOGGER.debug(
                "BSM OS type for server '%s' is '%s' (or uninformative), using base model name: '%s'.",
                server_name,
                self._bsm_os_type,
                base_model_name,
            )

        # Define the device for this specific Minecraft server.
        # It's linked to the main BSM Manager device via `via_device`.
        self._attr_device_info = dr.DeviceInfo(
            identifiers={
                (DOMAIN, f"{self._manager_host_port_id}_{self._server_name}")
            },  # Unique identifier for this server's device
            name=f"{self._server_name} ({self._manager_host_port_id})",
            manufacturer="Bedrock Server Manager",
            model=model_name_with_os,
            # Try to get a dynamic version from coordinator first, then static, then Unknown
            sw_version=(
                self.coordinator.data.get("version") if self.coordinator.data else None
            )
            or installed_version_static
            or "Unknown",
            via_device=manager_identifier,  # Link this server device TO the BSM manager device
            configuration_url=safe_config_url,  # URL to the BSM manager interface (where this server is managed)
        )

    @property
    def available(self) -> bool:
        """Return True if the button action can be performed."""
        # Most buttons depend on the coordinator being available and having data.
        # Specific buttons might have different availability logic if needed.
        return (
            super().available
            and self.coordinator.last_update_success
            and bool(self.coordinator.data)
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        action_key = self.entity_description.key
        api: BedrockServerManagerApi = (
            self.coordinator.api
        )  # Get API client from coordinator

        _LOGGER.info(
            "Button '%s' pressed for server '%s' (Manager: %s). Action: %s",
            self.entity_description.name,
            self._server_name,
            self._manager_host_port_id,
            action_key,
        )

        api_call_coro: Optional[Any] = None  # To store the coroutine for the API call
        success_notification_message = f"Action '{self.entity_description.name}' for server '{self._server_name}' initiated successfully."
        failure_message_prefix = f"Failed action '{self.entity_description.name}' for server '{self._server_name}'"

        try:
            if action_key == "restart_server":
                api_call_coro = api.async_restart_server(self._server_name)
            elif action_key == "update_server":
                api_call_coro = api.async_update_server(self._server_name)
                success_notification_message = (
                    f"Update check initiated for server '{self._server_name}'."
                )
            elif action_key == "trigger_server_backup_all":
                api_call_coro = api.async_trigger_server_backup(
                    self._server_name, backup_type="all"
                )
                success_notification_message = (
                    f"Full backup initiated for server '{self._server_name}'."
                )
            elif action_key == "export_server_world":
                api_call_coro = api.async_export_server_world(self._server_name)
                success_notification_message = (
                    f"World export initiated for server '{self._server_name}'."
                )
            elif action_key == "prune_server_backups":
                api_call_coro = api.async_prune_server_backups(
                    self._server_name, keep=None
                )  # Uses BSM default for keep
                success_notification_message = (
                    f"Backup pruning initiated for server '{self._server_name}'."
                )
            else:
                _LOGGER.error(
                    "Unhandled server button action key: '%s' for server '%s'",
                    action_key,
                    self._server_name,
                )
                raise HomeAssistantError(f"Unknown server button action: {action_key}")

            if api_call_coro:
                response = await api_call_coro
                _LOGGER.debug(
                    "API response for action '%s' on server '%s': %s",
                    action_key,
                    self._server_name,
                    response,
                )
                _LOGGER.info(success_notification_message)
                # Create a persistent notification for success
                async_create_notification(
                    self.hass,
                    success_notification_message,
                    title=f"BSM Server Action: {self.entity_description.name}",
                )

                # Refresh coordinator for actions that change server state or data
                if action_key in [
                    "restart_server",
                    "update_server",
                    "trigger_server_backup_all",
                    "prune_server_backups",
                    "export_server_world",
                ]:
                    await self.coordinator.async_request_refresh()

        except (
            AuthError,
            CannotConnectError,
            ServerNotFoundError,
            ServerNotRunningError,
            APIError,
        ) as err:
            err_msg_detail = (
                err.api_message
                if hasattr(err, "api_message") and err.api_message
                else str(err)
            )
            full_err_msg = (
                f"{failure_message_prefix}: {err_msg_detail} ({type(err).__name__})"
            )
            _LOGGER.error(full_err_msg)
            async_create_notification(
                self.hass,
                full_err_msg,
                title=f"BSM Action Failed: {self.entity_description.name}",
                notification_id=f"bsm_action_fail_{self.unique_id}",
            )
            # Re-raise as HomeAssistantError to signal failure to HA UI if appropriate
            raise HomeAssistantError(full_err_msg) from err
        except Exception as err:  # Catch-all for truly unexpected issues
            _LOGGER.exception(
                "%s: Unexpected error", failure_message_prefix
            )  # .exception logs traceback
            full_err_msg = f"{failure_message_prefix}: An unexpected error occurred ({type(err).__name__}). Check logs."
            async_create_notification(
                self.hass,
                full_err_msg,
                title=f"BSM Action Failed: {self.entity_description.name}",
                notification_id=f"bsm_action_fail_{self.unique_id}",
            )
            raise HomeAssistantError(full_err_msg) from err


class MinecraftManagerButton(
    ButtonEntity
):  # Does not need CoordinatorEntity if not reading state from it
    """Representation of a button entity for a global BSM manager action."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        config_entry_id: str,  # Pass config_entry_id
        api_client: BedrockServerManagerApi,  # API client passed directly
        description: ButtonEntityDescription,
        manager_identifier: Tuple[str, str],  # (DOMAIN, manager_host_port_id)
        manager_coordinator: Optional[
            ManagerDataCoordinator
        ] = None,  # For refreshing after action
    ) -> None:
        """Initialize the manager button."""
        self.entity_description = description
        self._config_entry_id = (
            config_entry_id  # Store for retrieving API client if not passed directly
        )
        self._api = api_client  # Store the passed API client
        self._manager_coordinator = manager_coordinator  # Store for refresh
        self._manager_host_port_id = manager_identifier[1]

        self._attr_unique_id = (
            f"{DOMAIN}_{self._manager_host_port_id}_{description.key}".lower().replace(
                ":", "_"
            )
        )
        self._attr_device_info = dr.DeviceInfo(
            identifiers={manager_identifier}
        )  # Attach to manager device
        self._attr_available = True  # Manager buttons are generally always available if integration is loaded

        _LOGGER.debug(
            "Init ManagerButton '%s' for manager '%s', UniqueID: %s",
            description.name,
            self._manager_host_port_id,
            self._attr_unique_id,
        )

    async def async_press(self) -> None:
        """Handle the button press for a manager-level action."""
        action_key = self.entity_description.key
        _LOGGER.info(
            "Button '%s' pressed for BSM manager '%s'. Action: %s",
            self.entity_description.name,
            self._manager_host_port_id,
            action_key,
        )

        api_call_coro: Optional[Any] = None
        success_notification_message = f"Global BSM action '{self.entity_description.name}' initiated successfully."
        failure_message_prefix = (
            f"Failed global BSM action '{self.entity_description.name}'"
        )

        try:
            if action_key == "scan_players":
                api_call_coro = self._api.async_scan_players()
            elif action_key == "reload_plugins":
                api_call_coro = self._api.async_reload_plugins()
                success_notification_message = "Plugin reload initiated successfully."
            else:
                _LOGGER.error("Unhandled manager button action key: '%s'", action_key)
                raise HomeAssistantError(f"Unknown manager button action: {action_key}")

            if api_call_coro:
                response = await api_call_coro
                _LOGGER.debug(
                    "API response for global action '%s': %s", action_key, response
                )
                _LOGGER.info(success_notification_message)
                async_create_notification(
                    self.hass,
                    success_notification_message,
                    title=f"BSM Manager Action: {self.entity_description.name}",
                )

                # Refresh manager coordinator if the action might have changed its data
                if (
                    action_key in ["scan_players", "reload_plugins"]
                    and self._manager_coordinator
                ):
                    _LOGGER.debug(
                        "Requesting refresh of ManagerDataCoordinator after action '%s'.",
                        action_key,
                    )
                    await self._manager_coordinator.async_request_refresh()

        except (
            AuthError,
            CannotConnectError,
            APIError,
        ) as err:  # Covers most client errors
            err_msg_detail = (
                err.api_message
                if hasattr(err, "api_message") and err.api_message
                else str(err)
            )
            full_err_msg = (
                f"{failure_message_prefix}: {err_msg_detail} ({type(err).__name__})"
            )
            _LOGGER.error(full_err_msg)
            async_create_notification(
                self.hass,
                full_err_msg,
                title=f"BSM Action Failed: {self.entity_description.name}",
                notification_id=f"bsm_action_fail_{self.unique_id}",
            )
            raise HomeAssistantError(full_err_msg) from err
        except Exception as err:  # Catch-all
            _LOGGER.exception("%s: Unexpected error", failure_message_prefix)
            full_err_msg = f"{failure_message_prefix}: An unexpected error occurred ({type(err).__name__}). Check logs."
            async_create_notification(
                self.hass,
                full_err_msg,
                title=f"BSM Action Failed: {self.entity_description.name}",
                notification_id=f"bsm_action_fail_{self.unique_id}",
            )
            raise HomeAssistantError(full_err_msg) from err
