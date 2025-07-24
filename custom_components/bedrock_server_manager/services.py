# custom_components/bedrock_server_manager/services.py
"""Service handlers for the Bedrock Server Manager integration."""

import asyncio
import json  # Added for parsing setting values
import logging
from typing import cast, Dict, Optional, List, Any, Set, Coroutine

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.components.persistent_notification import async_create
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    entity_registry as er,
    device_registry as dr,
    config_validation as cv,
)

from .const import (
    DOMAIN,
    SERVICE_ADD_GLOBAL_PLAYERS,
    SERVICE_SCAN_PLAYERS,
    SERVICE_SET_PLUGIN_ENABLED,
    SERVICE_TRIGGER_PLUGIN_EVENT,
    SERVICE_SEND_COMMAND,
    SERVICE_PRUNE_DOWNLOADS,
    SERVICE_RESTORE_BACKUP,
    SERVICE_TRIGGER_BACKUP,
    SERVICE_RESTORE_LATEST_ALL,
    SERVICE_INSTALL_SERVER,
    SERVICE_DELETE_SERVER,
    SERVICE_ADD_TO_ALLOWLIST,
    SERVICE_REMOVE_FROM_ALLOWLIST,
    SERVICE_SET_PERMISSIONS,
    SERVICE_RESET_WORLD,
    SERVICE_UPDATE_PROPERTIES,
    SERVICE_INSTALL_WORLD,
    SERVICE_INSTALL_ADDON,
    SERVICE_CONFIGURE_OS_SERVICE,
    FIELD_BACKUP_TYPE,
    FIELD_RESTORE_TYPE,
    FIELD_FILE_TO_BACKUP,
    FIELD_BACKUP_FILE,
    FIELD_COMMAND,
    FIELD_DIRECTORY,
    FIELD_KEEP,
    FIELD_OVERWRITE,
    FIELD_SERVER_NAME,
    FIELD_SERVER_VERSION,
    FIELD_CONFIRM_DELETE,
    FIELD_PLAYERS,
    FIELD_PLAYER_NAME,
    FIELD_IGNORE_PLAYER_LIMIT,
    FIELD_PERMISSIONS,
    FIELD_PROPERTIES,
    FIELD_FILENAME,
    FIELD_AUTOUPDATE,
    FIELD_AUTOSTART,
    FIELD_PLUGIN_NAME,
    FIELD_PLUGIN_ENABLED,
    FIELD_EVENT_NAME,
    FIELD_EVENT_PAYLOAD,
    SERVICE_SET_GLOBAL_SETTING,
    SERVICE_RELOAD_GLOBAL_SETTINGS,
    SERVICE_RESTORE_SELECT_BACKUP_TYPE,
    FIELD_SETTING_KEY,
    FIELD_SETTING_VALUE,
)

from bsm_api_client import (
    BedrockServerManagerApi,
    APIError,
    AuthError,
    CannotConnectError,
    ServerNotRunningError,
    InvalidInputError,
    ServerNotFoundError,
)
from bsm_api_client.models import (
    CommandPayload,
    PruneDownloadsPayload,
    BackupActionPayload,
    RestoreActionPayload,
    AllowlistAddPayload,
    AllowlistRemovePayload,
    PlayerPermission,
    PermissionsSetPayload,
    PropertiesPayload,
    FileNamePayload,
    ServiceUpdatePayload,
    AddPlayersPayload,
    PluginStatusSetPayload,
    TriggerEventPayload,
    SettingItem,
    RestoreTypePayload,
    InstallServerPayload,
)


from .coordinator import ManagerDataCoordinator

_LOGGER = logging.getLogger(__name__)

# --- Service Schema Definitions ---
TARGETING_SCHEMA_FIELDS = {
    vol.Optional(ATTR_DEVICE_ID): object,
    vol.Optional(ATTR_ENTITY_ID): object,
    vol.Optional(ATTR_AREA_ID): object,
}

SEND_COMMAND_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_COMMAND): cv.string,
        **TARGETING_SCHEMA_FIELDS,
    }
)
PRUNE_DOWNLOADS_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_DIRECTORY): cv.string,
        vol.Optional(FIELD_KEEP): vol.All(vol.Coerce(int), vol.Range(min=0)),
        **TARGETING_SCHEMA_FIELDS,
    }
)
TRIGGER_BACKUP_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_BACKUP_TYPE): vol.In(["all", "world", "config"]),
        vol.Optional(FIELD_FILE_TO_BACKUP): cv.string,
        **TARGETING_SCHEMA_FIELDS,
    }
)
RESTORE_BACKUP_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_RESTORE_TYPE): vol.In(
            ["world", "allowlist", "properties", "permissions"]
        ),
        vol.Required(FIELD_BACKUP_FILE): cv.string,
        **TARGETING_SCHEMA_FIELDS,
    }
)
RESTORE_LATEST_ALL_SERVICE_SCHEMA = vol.Schema(
    {
        **TARGETING_SCHEMA_FIELDS,
    }
)
INSTALL_SERVER_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_SERVER_NAME): cv.string,
        vol.Required(FIELD_SERVER_VERSION): cv.string,
        vol.Optional(FIELD_OVERWRITE, default=False): cv.boolean,
        **TARGETING_SCHEMA_FIELDS,
    }
)
DELETE_SERVER_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_CONFIRM_DELETE): True,
        **TARGETING_SCHEMA_FIELDS,
    }
)
ADD_TO_ALLOWLIST_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PLAYERS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(FIELD_IGNORE_PLAYER_LIMIT, default=False): cv.boolean,
        **TARGETING_SCHEMA_FIELDS,
    }
)
REMOVE_FROM_ALLOWLIST_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PLAYER_NAME): cv.string,
        **TARGETING_SCHEMA_FIELDS,
    }
)
SET_PERMISSIONS_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PERMISSIONS): vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required("name"): cv.string,
                        vol.Required("xuid"): cv.string,
                        vol.Required("permission_level"): vol.In(
                            ["visitor", "member", "operator"]
                        ),
                    }
                )
            ],
        ),
        **TARGETING_SCHEMA_FIELDS,
    }
)
UPDATE_PROPERTIES_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PROPERTIES): vol.Schema(
            {cv.string: vol.Any(str, int, bool)}
        ),
        **TARGETING_SCHEMA_FIELDS,
    }
)
INSTALL_WORLD_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_FILENAME): cv.string,
        **TARGETING_SCHEMA_FIELDS,
    }
)
INSTALL_ADDON_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_FILENAME): cv.string,
        **TARGETING_SCHEMA_FIELDS,
    }
)
CONFIGURE_OS_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_AUTOUPDATE): cv.boolean,
        vol.Optional(FIELD_AUTOSTART): cv.boolean,
        **TARGETING_SCHEMA_FIELDS,
    }
)
ADD_GLOBAL_PLAYERS_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PLAYERS): vol.All(
            cv.ensure_list,
            [cv.matches_regex(r"^[a-zA-Z0-9_ .\-']{1,32}:[0-9]{16,19}$")],
        ),
        **TARGETING_SCHEMA_FIELDS,
    }
)
SCAN_PLAYERS_SERVICE_SCHEMA = vol.Schema(
    {
        **TARGETING_SCHEMA_FIELDS,
    }
)

SET_PLUGIN_ENABLED_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PLUGIN_NAME): cv.string,
        vol.Required(FIELD_PLUGIN_ENABLED): cv.boolean,
        **TARGETING_SCHEMA_FIELDS,
    }
)
TRIGGER_PLUGIN_EVENT_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_EVENT_NAME): cv.string,
        vol.Optional(FIELD_EVENT_PAYLOAD): vol.Schema(dict),
        **TARGETING_SCHEMA_FIELDS,
    }
)

SET_GLOBAL_SETTING_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_SETTING_KEY): cv.string,
        vol.Required(FIELD_SETTING_VALUE): cv.string,
        **TARGETING_SCHEMA_FIELDS,
    }
)

RELOAD_GLOBAL_SETTINGS_SERVICE_SCHEMA = vol.Schema(
    {
        **TARGETING_SCHEMA_FIELDS,
    }
)

RESTORE_SELECT_BACKUP_TYPE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_RESTORE_TYPE): vol.In(
            ["world", "allowlist", "properties", "permissions"]
        ),
        **TARGETING_SCHEMA_FIELDS,
    }
)


# --- Service Handler Helper Functions ---
async def _base_api_call_handler(
    api_call_coro: Coroutine[Any, Any, Any],
    service_name: str,
    log_context: Optional[str] = None,
) -> Any:
    """
    Execute a BSM API call and handle common exceptions.

    This wrapper standardizes error handling and logging for service calls.
    """
    context_msg = f" for '{log_context}'" if log_context else ""
    try:
        response = await api_call_coro
        _LOGGER.debug(
            "Service '%s'%s successful. Response: %s",
            service_name,
            context_msg,
            response,
        )
        return response
    except ServerNotRunningError as err:
        msg = f"Service '{service_name}'{context_msg}: Server is not running. (API: {err.api_message or err})"
        raise HomeAssistantError(msg) from err
    except ServerNotFoundError as err:
        msg = f"Service '{service_name}'{context_msg}: Target server not found by API. (API: {err.api_message or err})"
        raise HomeAssistantError(msg) from err
    except InvalidInputError as err:
        msg = f"Service '{service_name}'{context_msg}: Invalid input provided. (API: {err.api_message or err})"
        raise ServiceValidationError(
            description=msg,
            translation_domain=DOMAIN,
            translation_key="service_invalid_input_api",
            translation_placeholders={"details": err.api_message or str(err)},
        ) from err
    except AuthError as err:
        msg = f"Service '{service_name}'{context_msg}: Authentication failed. (API: {err.api_message or err})"
        raise HomeAssistantError(msg) from err
    except CannotConnectError as err:
        msg = f"Service '{service_name}'{context_msg}: Cannot connect to BSM API. ({err.args[0] if err.args else err})"
        raise HomeAssistantError(msg) from err
    except APIError as err:
        msg = f"Service '{service_name}'{context_msg}: BSM API Error (Status: {err.status_code}). (API: {err.api_message or err})"
        raise HomeAssistantError(msg) from err
    except ValueError as err:
        msg = f"Service '{service_name}'{context_msg}: Invalid input value provided. ({err})"
        raise ServiceValidationError(
            description=msg,
            translation_domain=DOMAIN,
            translation_key="service_invalid_value_client",
            translation_placeholders={"details": str(err)},
        ) from err
    except Exception as err:
        _LOGGER.exception(
            "Service '%s'%s: Unexpected error.", service_name, context_msg
        )
        raise HomeAssistantError(
            f"Service '{service_name}'{context_msg}: Unexpected error - {type(err).__name__}"
        ) from err


# --- Handlers ---
async def _async_handle_send_command(
    api: BedrockServerManagerApi, server: str, command: str
):
    """Handle the send_command service call."""
    payload = CommandPayload(command=command)
    await _base_api_call_handler(
        api.async_send_server_command(server, payload), "send_command", server
    )


async def _async_handle_prune_downloads(
    api: BedrockServerManagerApi, directory: str, keep: Optional[int], manager_id: str
):
    """Handle the prune_downloads service call."""
    payload = PruneDownloadsPayload(directory=directory, keep=keep)
    await _base_api_call_handler(
        api.async_prune_downloads(payload), "prune_downloads", manager_id
    )


async def _async_handle_trigger_backup(
    api: BedrockServerManagerApi,
    server: str,
    backup_type: str,
    file_to_backup: Optional[str],
):
    """Handle the trigger_backup service call."""
    payload = BackupActionPayload(
        backup_type=backup_type, file_to_backup=file_to_backup
    )
    await _base_api_call_handler(
        api.async_trigger_server_backup(server, payload), "trigger_backup", server
    )


async def _async_handle_restore_backup(
    api: BedrockServerManagerApi, server: str, restore_type: str, backup_file: str
):
    """Handle the restore_backup service call."""
    payload = RestoreActionPayload(restore_type=restore_type, backup_file=backup_file)
    await _base_api_call_handler(
        api.async_restore_server_backup(server, payload), "restore_backup", server
    )


async def _async_handle_restore_latest_all(api: BedrockServerManagerApi, server: str):
    """Handle the restore_latest_all service call."""
    payload = RestoreActionPayload(restore_type="all")
    await _base_api_call_handler(
        api.async_restore_server_backup(server, payload), "restore_latest_all", server
    )


async def _async_handle_add_to_allowlist(
    api: BedrockServerManagerApi, server: str, players: List[str], ignore_limit: bool
):
    """Handle the add_to_allowlist service call."""
    payload = AllowlistAddPayload(players=players, ignoresPlayerLimit=ignore_limit)
    await _base_api_call_handler(
        api.async_add_server_allowlist(server, payload), "add_to_allowlist", server
    )


async def _async_handle_remove_from_allowlist(
    api: BedrockServerManagerApi, server: str, player_name: str
):
    """Handle the remove_from_allowlist service call."""
    payload = AllowlistRemovePayload(players=[player_name])
    await _base_api_call_handler(
        api.async_remove_server_allowlist(server, payload),
        "remove_from_allowlist",
        server,
    )


async def _async_handle_set_permissions(
    api: BedrockServerManagerApi, server: str, permissions_list: List[Dict[str, str]]
):
    """Handle the set_permissions service call."""
    permissions = [PlayerPermission(**p) for p in permissions_list]
    payload = PermissionsSetPayload(permissions=permissions)
    await _base_api_call_handler(
        api.async_set_server_permissions(server, payload), "set_permissions", server
    )


async def _async_handle_update_properties(
    api: BedrockServerManagerApi, server: str, properties_dict: Dict[str, Any]
):
    """Handle the update_properties service call."""
    payload = PropertiesPayload(properties=properties_dict)
    await _base_api_call_handler(
        api.async_update_server_properties(server, payload), "update_properties", server
    )


async def _async_handle_install_world(
    api: BedrockServerManagerApi, server: str, filename: str
):
    """Handle the install_world service call."""
    payload = FileNamePayload(filename=filename)
    await _base_api_call_handler(
        api.async_install_server_world(server, payload), "install_world", server
    )


async def _async_handle_install_addon(
    api: BedrockServerManagerApi, server: str, filename: str
):
    """Handle the install_addon service call."""
    payload = FileNamePayload(filename=filename)
    await _base_api_call_handler(
        api.async_install_server_addon(server, payload), "install_addon", server
    )


async def _async_handle_configure_os_service(
    api: BedrockServerManagerApi,
    server: str,
    payload_dict: Dict[str, bool],
    manager_id: str,
):
    """Handle the configure_os_service service call."""
    payload = ServiceUpdatePayload(**payload_dict)
    await _base_api_call_handler(
        api.async_configure_server_os_service(server, payload),
        "configure_os_service",
        f"{server} on manager '{manager_id}'",
    )


async def _async_handle_add_global_players(
    api: BedrockServerManagerApi, players_data: List[str], manager_id: str
):
    """Handle the add_global_players service call."""
    payload = AddPlayersPayload(players=players_data)
    await _base_api_call_handler(
        api.async_add_players(payload), "add_global_players", manager_id
    )


async def _async_handle_scan_players(api: BedrockServerManagerApi, manager_id: str):
    """Handle the scan_players service call."""
    await _base_api_call_handler(api.async_scan_players(), "scan_players", manager_id)


async def _async_handle_set_plugin_enabled(
    api: BedrockServerManagerApi, plugin_name: str, enabled: bool, manager_id: str
):
    """Handle the set_plugin_enabled service call."""
    payload = PluginStatusSetPayload(enabled=enabled)
    await _base_api_call_handler(
        api.async_set_plugin_status(plugin_name, payload),
        "set_plugin_enabled",
        f"plugin '{plugin_name}' on manager '{manager_id}'",
    )


async def _async_handle_trigger_plugin_event(
    api: BedrockServerManagerApi,
    event_name: str,
    payload_dict: Optional[Dict[str, Any]],
    manager_id: str,
):
    """Handle the trigger_plugin_event service call."""
    payload = TriggerEventPayload(event_name=event_name, payload=payload_dict)
    await _base_api_call_handler(
        api.async_trigger_plugin_event(payload),
        "trigger_plugin_event",
        f"event '{event_name}' on manager '{manager_id}'",
    )


async def _async_handle_set_global_setting(
    api: BedrockServerManagerApi, key: str, value: Any, manager_id: str
):
    """Handle the set_global_setting service call."""
    try:
        parsed_value = (
            json.loads(value)
            if isinstance(value, str) and value.strip().startswith(("{", "["))
            else value
        )
    except json.JSONDecodeError:
        _LOGGER.warning(
            "Value for setting '%s' looked like JSON but failed to parse. Sending as string.",
            key,
        )
        parsed_value = value

    payload = SettingItem(key=key, value=parsed_value)
    await _base_api_call_handler(
        api.async_set_setting(payload),
        "set_global_setting",
        f"setting '{key}' on manager '{manager_id}'",
    )


async def _async_handle_reload_global_settings(
    api: BedrockServerManagerApi, manager_id: str
):
    """Handle the reload_global_settings service call."""
    await _base_api_call_handler(
        api.async_reload_settings(), "reload_global_settings", manager_id
    )


async def _async_handle_restore_select_backup_type(
    hass: HomeAssistant,
    api: BedrockServerManagerApi,
    server: str,
    restore_type: str,
    manager_id: str,
):
    """Handle the restore_select_backup_type service call."""
    payload = RestoreTypePayload(restore_type=restore_type)
    response = await _base_api_call_handler(
        api.async_restore_select_backup_type(server, payload),
        "restore_select_backup_type",
        f"server '{server}' on manager '{manager_id}'",
    )
    if response and response.redirect_url:
        message = (
            response.message
            or f"Selected restore type '{restore_type}' for '{server}'."
        )
        message += f" API returned redirect URL: {response.redirect_url}"
        async_create(
            hass,
            message=f"For server '{server}': {message}",
            title="BSM Restore Step",
            notification_id=f"bsm_restore_select_{server}_{restore_type}",
        )
    return response


async def _async_handle_install_server(
    api: BedrockServerManagerApi,
    server_name: str,
    version: str,
    overwrite: bool,
    manager_id: str,
):
    """Handle the install_server service call."""
    log_context = f"server '{server_name}' on manager '{manager_id}'"
    payload = InstallServerPayload(
        server_name=server_name, server_version=version, overwrite=overwrite
    )
    try:
        response = await api.async_install_new_server(payload)
        if response.status == "confirm_needed":
            msg = f"Install {log_context}: Server already exists and overwrite was false. Set 'overwrite: true' to replace it."
            raise ServiceValidationError(
                description=msg,
                translation_domain=DOMAIN,
                translation_key="service_install_server_confirm_needed",
                translation_placeholders={"server_name": server_name},
            )
        _LOGGER.info(
            "Successfully requested install for %s. API Message: %s",
            log_context,
            response.message or "N/A",
        )
        return response
    except (APIError, ValueError, InvalidInputError) as err:
        err_msg = getattr(err, "api_message", str(err))
        full_error_msg = f"Install {log_context}: {type(err).__name__} - {err_msg}"
        if isinstance(err, (ValueError, InvalidInputError)):
            raise ServiceValidationError(description=full_error_msg) from err
        raise HomeAssistantError(full_error_msg) from err


async def _async_handle_delete_server(
    hass: HomeAssistant, api: BedrockServerManagerApi, server_name: str, manager_id: str
):
    """Handle the delete_server service call, including HA device removal."""
    log_context = f"server '{server_name}' on manager '{manager_id}'"
    _LOGGER.critical("Executing irreversible deletion of %s", log_context)
    try:
        response = await api.async_delete_server(server_name=server_name)
        if not response or response.status != "success":
            raise HomeAssistantError(
                f"Manager API did not confirm deletion of {log_context}. Response: {response}"
            )

        _LOGGER.info(
            "API confirmed deletion of %s. Attempting HA device removal.", log_context
        )
        device_registry_instance = dr.async_get(hass)
        device_identifier = (DOMAIN, f"{manager_id}_{server_name}")
        device_to_remove = device_registry_instance.async_get_device(
            identifiers={device_identifier}
        )

        if device_to_remove:
            device_registry_instance.async_remove_device(device_to_remove.id)
            _LOGGER.debug("Removed device for %s from HA registry.", log_context)
            ha_device_removed = True
        else:
            _LOGGER.warning(
                "Could not find HA device for %s to remove from registry.", log_context
            )
            ha_device_removed = False

        return {
            "status": "success",
            "message": response.message,
            "ha_device_removed": ha_device_removed,
        }
    except (APIError, ValueError, InvalidInputError) as err:
        err_msg = getattr(err, "api_message", str(err))
        full_error_msg = f"Delete {log_context}: {type(err).__name__} - {err_msg}"
        if isinstance(err, (ValueError, InvalidInputError)):
            raise ServiceValidationError(description=full_error_msg) from err
        raise HomeAssistantError(full_error_msg) from err


async def _async_handle_reset_world(
    hass: HomeAssistant, api: BedrockServerManagerApi, server_name: str, manager_id: str
):
    """Handle the reset_world service call."""
    log_context = f"world for server '{server_name}' on manager '{manager_id}'"
    _LOGGER.critical("Executing irreversible reset of %s", log_context)
    try:
        response = await api.async_reset_server_world(server_name=server_name)
        if response and response.status == "success":
            return {"status": "success", "message": response.message}
        raise HomeAssistantError(
            f"Manager API did not confirm reset of {log_context}. Response: {response}"
        )
    except (APIError, ValueError, InvalidInputError) as err:
        err_msg = getattr(err, "api_message", str(err))
        full_error_msg = f"Reset {log_context}: {type(err).__name__} - {err_msg}"
        if isinstance(err, (ValueError, InvalidInputError)):
            raise ServiceValidationError(description=full_error_msg) from err
        raise HomeAssistantError(full_error_msg) from err


# --- Target Resolvers and Executors ---
async def _resolve_server_targets(
    service: ServiceCall, hass: HomeAssistant
) -> Dict[str, str]:
    """
    Resolve targeted server devices/entities to a dictionary of {config_entry_id: server_name}.
    """
    servers_to_target: Dict[str, str] = {}
    entity_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    def process_device(device_entry: dr.DeviceEntry, config_entry_id: str):
        """Extract server name from device and add to target list."""
        try:
            manager_id = hass.data[DOMAIN][config_entry_id]["manager_identifier"][1]
        except KeyError:
            _LOGGER.warning(
                "Could not get manager_identifier for device %s.", device_entry.id
            )
            return

        for domain, value in device_entry.identifiers:
            if domain == DOMAIN and value.startswith(f"{manager_id}_"):
                server_name = value.split("_", 1)[1]
                if config_entry_id not in servers_to_target:
                    servers_to_target[config_entry_id] = server_name
                    _LOGGER.debug(
                        "Targeted server '%s' via device %s",
                        server_name,
                        device_entry.id,
                    )
                elif servers_to_target[config_entry_id] != server_name:
                    _LOGGER.warning(
                        "Multiple servers targeted for the same config entry. Using first: %s",
                        servers_to_target[config_entry_id],
                    )
                return

    for target in service.data.get(ATTR_DEVICE_ID, []):
        if device := dev_reg.async_get(target):
            for ce_id in device.config_entries:
                if ce_id in hass.data.get(DOMAIN, {}):
                    process_device(device, ce_id)
                    break

    for target in service.data.get(ATTR_ENTITY_ID, []):
        if (entity := entity_reg.async_get(target)) and entity.device_id:
            if (
                device := dev_reg.async_get(entity.device_id)
            ) and entity.config_entry_id:
                process_device(device, entity.config_entry_id)

    if not servers_to_target:
        raise ServiceValidationError(
            f"Service {service.domain}.{service.service} requires targeting a specific BSM server device or entity."
        )

    _LOGGER.debug(
        "Resolved server targets for service %s.%s: %s",
        service.domain,
        service.service,
        servers_to_target,
    )
    return servers_to_target


async def _resolve_manager_instance_targets(
    service: ServiceCall, hass: HomeAssistant
) -> List[str]:
    """
    Resolve targeted manager devices/entities to a list of config_entry_ids.
    """
    config_entry_ids: Set[str] = set()
    entity_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    for target in service.data.get(ATTR_DEVICE_ID, []):
        if device := dev_reg.async_get(target):
            for ce_id in device.config_entries:
                if ce_id in hass.data.get(DOMAIN, {}):
                    config_entry_ids.add(ce_id)

    for target in service.data.get(ATTR_ENTITY_ID, []):
        if (entity := entity_reg.async_get(target)) and entity.config_entry_id:
            if entity.config_entry_id in hass.data.get(DOMAIN, {}):
                config_entry_ids.add(entity.config_entry_id)

    if not config_entry_ids:
        raise ServiceValidationError(
            f"Service {service.domain}.{service.service} requires targeting a BSM manager device or entity."
        )

    _LOGGER.debug(
        "Resolved manager targets for service %s.%s: %s",
        service.domain,
        service.service,
        list(config_entry_ids),
    )
    return list(config_entry_ids)


async def _execute_targeted_service(
    service_call: ServiceCall,
    hass: HomeAssistant,
    handler: Coroutine,
    *handler_args: Any,
):
    """
    Execute a service handler for each targeted server.
    """
    try:
        resolved_targets = await _resolve_server_targets(service_call, hass)
    except ServiceValidationError as e:
        _LOGGER.error(
            "Failed to resolve targets for service %s.%s: %s",
            service_call.domain,
            service_call.service,
            e,
        )
        raise

    tasks = []
    for config_entry_id, server_name in resolved_targets.items():
        try:
            entry_data = hass.data[DOMAIN][config_entry_id]
            api_client: BedrockServerManagerApi = entry_data["api"]
            manager_id = entry_data["manager_identifier"][1]

            # Special handling for handlers that need `hass` or `manager_id`
            if handler.__name__ in (
                "_async_handle_restore_select_backup_type",
                "_async_handle_delete_server",
                "_async_handle_reset_world",
            ):
                tasks.append(
                    handler(hass, api_client, server_name, manager_id, *handler_args)
                )
            elif handler.__name__ == "_async_handle_configure_os_service":
                tasks.append(
                    handler(api_client, server_name, *handler_args, manager_id)
                )
            else:
                tasks.append(handler(api_client, server_name, *handler_args))
        except KeyError:
            _LOGGER.error(
                "Data missing for config entry %s (server %s). Skipping service.",
                config_entry_id,
                server_name,
            )

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def _execute_manager_targeted_service(
    service_call: ServiceCall,
    hass: HomeAssistant,
    handler: Coroutine,
    *handler_args: Any,
):
    """
    Execute a service handler for each targeted manager instance.
    """
    try:
        resolved_ids = await _resolve_manager_instance_targets(service_call, hass)
    except ServiceValidationError as e:
        _LOGGER.error(
            "Failed to resolve manager targets for service %s.%s: %s",
            service_call.domain,
            service_call.service,
            e,
        )
        raise

    tasks = []
    coordinators_to_refresh: List[ManagerDataCoordinator] = []

    for ce_id in resolved_ids:
        try:
            entry_data = hass.data[DOMAIN][ce_id]
            api_client: BedrockServerManagerApi = entry_data["api"]
            manager_id = entry_data["manager_identifier"][1]

            tasks.append(handler(api_client, *handler_args, manager_id))

            # Refresh coordinator if the service modifies data it owns
            if handler.__name__ in (
                "_async_handle_add_global_players",
                "_async_handle_scan_players",
                "_async_handle_install_server",
                "_async_handle_set_plugin_enabled",
            ):
                if coordinator := entry_data.get("manager_coordinator"):
                    coordinators_to_refresh.append(coordinator)
        except KeyError:
            _LOGGER.error(
                "Data missing for config entry %s. Skipping manager service.", ce_id
            )

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
        for coordinator in set(coordinators_to_refresh):
            _LOGGER.debug(
                "Requesting refresh of %s after service call.", coordinator.name
            )
            await coordinator.async_request_refresh()


# --- Main Service Handlers ---
async def async_handle_send_command_service(service: ServiceCall, hass: HomeAssistant):
    """Handle the service call to send a command to a server."""
    await _execute_targeted_service(
        service, hass, _async_handle_send_command, service.data[FIELD_COMMAND]
    )


async def async_handle_prune_downloads_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the service call to prune the downloads cache."""
    await _execute_manager_targeted_service(
        service,
        hass,
        _async_handle_prune_downloads,
        service.data[FIELD_DIRECTORY],
        service.data.get(FIELD_KEEP),
    )


async def async_handle_trigger_backup_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the service call to trigger a backup."""
    if service.data[FIELD_BACKUP_TYPE] == "config" and not service.data.get(
        FIELD_FILE_TO_BACKUP
    ):
        raise ServiceValidationError(
            f"'{FIELD_FILE_TO_BACKUP}' is required when '{FIELD_BACKUP_TYPE}' is 'config'."
        )
    await _execute_targeted_service(
        service,
        hass,
        _async_handle_trigger_backup,
        service.data[FIELD_BACKUP_TYPE],
        service.data.get(FIELD_FILE_TO_BACKUP),
    )


async def async_handle_restore_backup_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the service call to restore a backup."""
    await _execute_targeted_service(
        service,
        hass,
        _async_handle_restore_backup,
        service.data[FIELD_RESTORE_TYPE],
        service.data[FIELD_BACKUP_FILE],
    )


async def async_handle_restore_latest_all_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the service call to restore the latest of all backup types."""
    await _execute_targeted_service(service, hass, _async_handle_restore_latest_all)


async def async_handle_install_server_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the service call to install a new server."""
    await _execute_manager_targeted_service(
        service,
        hass,
        _async_handle_install_server,
        service.data[FIELD_SERVER_NAME],
        service.data[FIELD_SERVER_VERSION],
        service.data[FIELD_OVERWRITE],
    )


async def async_handle_scan_players_service(service: ServiceCall, hass: HomeAssistant):
    """Handle the service call to scan for players."""
    await _execute_manager_targeted_service(service, hass, _async_handle_scan_players)


async def async_handle_set_plugin_enabled_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the service call to enable or disable a plugin."""
    await _execute_manager_targeted_service(
        service,
        hass,
        _async_handle_set_plugin_enabled,
        service.data[FIELD_PLUGIN_NAME],
        service.data[FIELD_PLUGIN_ENABLED],
    )


async def async_handle_trigger_plugin_event_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the service call to trigger a plugin event."""
    await _execute_manager_targeted_service(
        service,
        hass,
        _async_handle_trigger_plugin_event,
        service.data[FIELD_EVENT_NAME],
        service.data.get(FIELD_EVENT_PAYLOAD),
    )


async def async_handle_delete_server_service(service: ServiceCall, hass: HomeAssistant):
    """Handle the service call to delete a server and its HA device."""
    _LOGGER.warning(
        "Executing delete_server service call. User confirmation: %s",
        service.data[FIELD_CONFIRM_DELETE],
    )

    try:
        resolved_targets = await _resolve_server_targets(service, hass)
    except ServiceValidationError as e:
        _LOGGER.error("Failed to resolve targets for delete_server: %s", e)
        raise

    tasks = {
        ce_id: _async_handle_delete_server(
            hass,
            hass.data[DOMAIN][ce_id]["api"],
            s_name,
            hass.data[DOMAIN][ce_id]["manager_identifier"][1],
        )
        for ce_id, s_name in resolved_targets.items()
    }

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    success_msgs, failure_msgs = [], []

    for (ce_id, s_name), result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            failure_msgs.append(f"'{s_name}': Failed ({result})")
        elif isinstance(result, dict) and result.get("status") == "success":
            msg = f"'{s_name}': API deletion successful."
            msg += (
                " HA device removed."
                if result.get("ha_device_removed")
                else " HA device not found/removed."
            )
            success_msgs.append(msg)
        else:
            failure_msgs.append(
                f"'{s_name}': Deletion status unclear (Result: {result})."
            )

    notification_msg = ""
    if success_msgs:
        notification_msg += f"Successes: {'; '.join(success_msgs)} "
    if failure_msgs:
        notification_msg += f"Failures: {'; '.join(failure_msgs)}"
    if not notification_msg:
        notification_msg = "No deletion actions were completed. Check logs."

    async_create(
        hass,
        notification_msg,
        "Minecraft Server Deletion Results",
        f"bsm_delete_results_{service.context.id}",
    )


async def async_handle_add_to_allowlist_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the service call to add players to the allowlist."""
    await _execute_targeted_service(
        service,
        hass,
        _async_handle_add_to_allowlist,
        service.data[FIELD_PLAYERS],
        service.data[FIELD_IGNORE_PLAYER_LIMIT],
    )


async def async_handle_remove_from_allowlist_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the service call to remove a player from the allowlist."""
    await _execute_targeted_service(
        service,
        hass,
        _async_handle_remove_from_allowlist,
        service.data[FIELD_PLAYER_NAME],
    )


async def async_handle_set_permissions_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the service call to set player permissions."""
    await _execute_targeted_service(
        service, hass, _async_handle_set_permissions, service.data[FIELD_PERMISSIONS]
    )


async def async_handle_reset_world_service(service: ServiceCall, hass: HomeAssistant):
    """Handle the service call to reset a server's world."""
    _LOGGER.warning(
        "Executing reset_world service call. User confirmation: %s",
        service.data[FIELD_CONFIRM_DELETE],
    )

    try:
        resolved_targets = await _resolve_server_targets(service, hass)
    except ServiceValidationError as e:
        _LOGGER.error("Failed to resolve targets for reset_world: %s", e)
        raise

    tasks = {
        ce_id: _async_handle_reset_world(
            hass,
            hass.data[DOMAIN][ce_id]["api"],
            s_name,
            hass.data[DOMAIN][ce_id]["manager_identifier"][1],
        )
        for ce_id, s_name in resolved_targets.items()
    }

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    success_msgs, failure_msgs = [], []

    for (ce_id, s_name), result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            failure_msgs.append(f"'{s_name}': Failed ({result})")
        elif isinstance(result, dict) and result.get("status") == "success":
            success_msgs.append(f"'{s_name}': API reset successful.")
        else:
            failure_msgs.append(f"'{s_name}': Reset status unclear (Result: {result}).")

    notification_msg = ""
    if success_msgs:
        notification_msg += f"Successes: {'; '.join(success_msgs)} "
    if failure_msgs:
        notification_msg += f"Failures: {'; '.join(failure_msgs)}"
    if not notification_msg:
        notification_msg = "No reset actions were completed. Check logs."

    async_create(
        hass,
        notification_msg,
        "Minecraft Server Reset Results",
        f"bsm_reset_results_{service.context.id}",
    )


async def async_handle_update_properties_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the service call to update server properties."""
    await _execute_targeted_service(
        service, hass, _async_handle_update_properties, service.data[FIELD_PROPERTIES]
    )


async def async_handle_install_world_service(service: ServiceCall, hass: HomeAssistant):
    """Handle the service call to install a world."""
    await _execute_targeted_service(
        service, hass, _async_handle_install_world, service.data[FIELD_FILENAME]
    )


async def async_handle_install_addon_service(service: ServiceCall, hass: HomeAssistant):
    """Handle the service call to install an addon."""
    await _execute_targeted_service(
        service, hass, _async_handle_install_addon, service.data[FIELD_FILENAME]
    )


async def async_handle_configure_os_service_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the service call to configure the OS service for a server."""
    autoupdate = service.data[FIELD_AUTOUPDATE]
    autostart = service.data.get(FIELD_AUTOSTART)

    try:
        resolved_targets = await _resolve_server_targets(service, hass)
    except ServiceValidationError as e:
        _LOGGER.error("Failed to resolve targets for configure_os_service: %s", e)
        raise

    tasks = []
    for ce_id, server_name in resolved_targets.items():
        try:
            entry_data = hass.data[DOMAIN][ce_id]
            manager_os = entry_data.get("manager_os_type", "unknown").lower()
            payload = {FIELD_AUTOUPDATE: autoupdate}
            if autostart is not None:
                if manager_os == "linux":
                    payload[FIELD_AUTOSTART] = autostart
                else:
                    _LOGGER.warning(
                        "Autostart config for '%s' ignored as manager OS is not Linux.",
                        server_name,
                    )
            tasks.append(
                _async_handle_configure_os_service(
                    entry_data["api"],
                    server_name,
                    payload,
                    entry_data["manager_identifier"][1],
                )
            )
        except KeyError:
            _LOGGER.error(
                "Data missing for config entry %s (server %s) for OS service config.",
                ce_id,
                server_name,
            )

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def async_handle_add_global_players_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the service call to add players to the global list."""
    await _execute_manager_targeted_service(
        service, hass, _async_handle_add_global_players, service.data[FIELD_PLAYERS]
    )


async def async_handle_set_global_setting_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the service call to set a global setting."""
    await _execute_manager_targeted_service(
        service,
        hass,
        _async_handle_set_global_setting,
        service.data[FIELD_SETTING_KEY],
        service.data[FIELD_SETTING_VALUE],
    )


async def async_handle_reload_global_settings_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the service call to reload global settings."""
    await _execute_manager_targeted_service(
        service, hass, _async_handle_reload_global_settings
    )


async def async_handle_restore_select_backup_type_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the service call to select a backup type for restoration."""
    await _execute_targeted_service(
        service,
        hass,
        _async_handle_restore_select_backup_type,
        service.data[FIELD_RESTORE_TYPE],
    )


# --- Service Registration/Removal ---
async def async_register_services(hass: HomeAssistant) -> None:
    """
    Register all services for the Bedrock Server Manager integration.
    """
    service_map = {
        SERVICE_SEND_COMMAND: (
            async_handle_send_command_service,
            SEND_COMMAND_SERVICE_SCHEMA,
        ),
        SERVICE_PRUNE_DOWNLOADS: (
            async_handle_prune_downloads_service,
            PRUNE_DOWNLOADS_SERVICE_SCHEMA,
        ),
        SERVICE_TRIGGER_BACKUP: (
            async_handle_trigger_backup_service,
            TRIGGER_BACKUP_SERVICE_SCHEMA,
        ),
        SERVICE_RESTORE_BACKUP: (
            async_handle_restore_backup_service,
            RESTORE_BACKUP_SERVICE_SCHEMA,
        ),
        SERVICE_RESTORE_LATEST_ALL: (
            async_handle_restore_latest_all_service,
            RESTORE_LATEST_ALL_SERVICE_SCHEMA,
        ),
        SERVICE_INSTALL_SERVER: (
            async_handle_install_server_service,
            INSTALL_SERVER_SERVICE_SCHEMA,
        ),
        SERVICE_DELETE_SERVER: (
            async_handle_delete_server_service,
            DELETE_SERVER_SERVICE_SCHEMA,
        ),
        SERVICE_ADD_TO_ALLOWLIST: (
            async_handle_add_to_allowlist_service,
            ADD_TO_ALLOWLIST_SERVICE_SCHEMA,
        ),
        SERVICE_REMOVE_FROM_ALLOWLIST: (
            async_handle_remove_from_allowlist_service,
            REMOVE_FROM_ALLOWLIST_SERVICE_SCHEMA,
        ),
        SERVICE_SET_PERMISSIONS: (
            async_handle_set_permissions_service,
            SET_PERMISSIONS_SERVICE_SCHEMA,
        ),
        SERVICE_UPDATE_PROPERTIES: (
            async_handle_update_properties_service,
            UPDATE_PROPERTIES_SERVICE_SCHEMA,
        ),
        SERVICE_INSTALL_WORLD: (
            async_handle_install_world_service,
            INSTALL_WORLD_SERVICE_SCHEMA,
        ),
        SERVICE_INSTALL_ADDON: (
            async_handle_install_addon_service,
            INSTALL_ADDON_SERVICE_SCHEMA,
        ),
        SERVICE_CONFIGURE_OS_SERVICE: (
            async_handle_configure_os_service_service,
            CONFIGURE_OS_SERVICE_SCHEMA,
        ),
        SERVICE_ADD_GLOBAL_PLAYERS: (
            async_handle_add_global_players_service,
            ADD_GLOBAL_PLAYERS_SERVICE_SCHEMA,
        ),
        SERVICE_SET_PLUGIN_ENABLED: (
            async_handle_set_plugin_enabled_service,
            SET_PLUGIN_ENABLED_SERVICE_SCHEMA,
        ),
        SERVICE_TRIGGER_PLUGIN_EVENT: (
            async_handle_trigger_plugin_event_service,
            TRIGGER_PLUGIN_EVENT_SERVICE_SCHEMA,
        ),
        SERVICE_SET_GLOBAL_SETTING: (
            async_handle_set_global_setting_service,
            SET_GLOBAL_SETTING_SERVICE_SCHEMA,
        ),
        SERVICE_RELOAD_GLOBAL_SETTINGS: (
            async_handle_reload_global_settings_service,
            RELOAD_GLOBAL_SETTINGS_SERVICE_SCHEMA,
        ),
        SERVICE_RESTORE_SELECT_BACKUP_TYPE: (
            async_handle_restore_select_backup_type_service,
            RESTORE_SELECT_BACKUP_TYPE_SERVICE_SCHEMA,
        ),
    }

    async def service_wrapper(call: ServiceCall, handler):
        """Wrap service calls to handle exceptions."""
        _LOGGER.debug(
            "Service call '%s.%s' received, dispatching to %s.",
            call.domain,
            call.service,
            handler.__name__,
        )
        try:
            await handler(call, hass)
        except (ServiceValidationError, HomeAssistantError) as e:
            _LOGGER.error(
                "Error handling service call %s.%s: %s", call.domain, call.service, e
            )
            raise
        except Exception as e:
            _LOGGER.exception(
                "Unexpected error handling service call %s.%s",
                call.domain,
                call.service,
            )
            raise HomeAssistantError(
                f"Unexpected error executing service {call.domain}.{call.service}: {e}"
            ) from e

    for service_name, (handler, schema) in service_map.items():
        if not hass.services.has_service(DOMAIN, service_name):
            hass.services.async_register(
                DOMAIN,
                service_name,
                lambda call, h=handler: service_wrapper(call, h),
                schema=schema,
            )
            _LOGGER.debug("Registered service: %s.%s", DOMAIN, service_name)


async def async_remove_services(hass: HomeAssistant) -> None:
    """
    Remove all services for the Bedrock Server Manager integration.
    This is called when the last config entry is unloaded.
    """
    _LOGGER.info("Removing all BSM services.")
    services_to_remove = [
        SERVICE_SEND_COMMAND,
        SERVICE_PRUNE_DOWNLOADS,
        SERVICE_TRIGGER_BACKUP,
        SERVICE_RESTORE_BACKUP,
        SERVICE_RESTORE_LATEST_ALL,
        SERVICE_INSTALL_SERVER,
        SERVICE_DELETE_SERVER,
        SERVICE_ADD_TO_ALLOWLIST,
        SERVICE_REMOVE_FROM_ALLOWLIST,
        SERVICE_SET_PERMISSIONS,
        SERVICE_UPDATE_PROPERTIES,
        SERVICE_INSTALL_WORLD,
        SERVICE_INSTALL_ADDON,
        SERVICE_CONFIGURE_OS_SERVICE,
        SERVICE_ADD_GLOBAL_PLAYERS,
        SERVICE_SET_PLUGIN_ENABLED,
        SERVICE_TRIGGER_PLUGIN_EVENT,
        SERVICE_SET_GLOBAL_SETTING,
        SERVICE_RELOAD_GLOBAL_SETTINGS,
        SERVICE_RESTORE_SELECT_BACKUP_TYPE,
    ]
    for service_name in services_to_remove:
        if hass.services.has_service(DOMAIN, service_name):
            _LOGGER.debug("Removing service: %s.%s", DOMAIN, service_name)
            hass.services.async_remove(DOMAIN, service_name)
