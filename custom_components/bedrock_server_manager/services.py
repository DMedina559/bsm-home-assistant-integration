# custom_components/bedrock_server_manager/services.py
"""Service handlers for the Bedrock Server Manager integration."""

import asyncio
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
)

from pybedrock_server_manager import (
    BedrockServerManagerApi,
    APIError,
    AuthError,
    CannotConnectError,
    ServerNotRunningError,
    InvalidInputError,
    ServerNotFoundError,
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
        vol.Required(FIELD_RESTORE_TYPE): vol.In(["world", "config"]),
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
        vol.Required(FIELD_PERMISSIONS): vol.Schema(
            {cv.string: vol.In(["visitor", "member", "operator"])}
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


# --- Service Handler Helper Functions ---
async def _base_api_call_handler(
    api_call_coro: Coroutine[Any, Any, Any],
    error_message_prefix: str,
    log_context_identifier: Optional[str] = None,
) -> Any:
    context_msg = f" for '{log_context_identifier}'" if log_context_identifier else ""
    try:
        response = await api_call_coro
        _LOGGER.debug(
            "API call %s successful%s. Response: %s",
            error_message_prefix,
            context_msg,
            response,
        )
        return response
    except ServerNotRunningError as err:
        msg = f"{error_message_prefix}{context_msg}: Server is not running. (API: {err.api_message or err})"
        _LOGGER.error(msg)
        raise HomeAssistantError(msg) from err
    except ServerNotFoundError as err:
        msg = f"{error_message_prefix}{context_msg}: Target server not found by API. (API: {err.api_message or err})"
        _LOGGER.error(msg)
        raise HomeAssistantError(msg) from err
    except InvalidInputError as err:
        msg = f"{error_message_prefix}{context_msg}: Invalid input provided. (API: {err.api_message or err})"
        _LOGGER.error(msg)
        raise ServiceValidationError(
            description=msg,  # Fallback description
            translation_domain=DOMAIN,
            translation_key="service_invalid_input_api",  # Key for strings.json (under config.error)
            translation_placeholders={"details": err.api_message or str(err)},
        ) from err
    except AuthError as err:
        msg = f"{error_message_prefix}{context_msg}: Authentication failed. (API: {err.api_message or err})"
        _LOGGER.error(msg)
        raise HomeAssistantError(msg) from err
    except CannotConnectError as err:
        msg = f"{error_message_prefix}{context_msg}: Cannot connect to BSM API. ({err.args[0] if err.args else err})"
        _LOGGER.error(msg)
        raise HomeAssistantError(msg) from err
    except APIError as err:
        msg = f"{error_message_prefix}{context_msg}: BSM API Error (Status: {err.status_code}). (API: {err.api_message or err})"
        _LOGGER.error(msg)
        raise HomeAssistantError(msg) from err
    except ValueError as err:  # From client's internal validation
        msg = f"{error_message_prefix}{context_msg}: Invalid input value provided. ({err})"
        _LOGGER.error(msg)
        raise ServiceValidationError(
            description=msg,  # Fallback
            translation_domain=DOMAIN,
            translation_key="service_invalid_value_client",  # Key for strings.json
            translation_placeholders={"details": str(err)},
        ) from err
    except Exception as err:
        _LOGGER.exception("%s%s: Unexpected error.", error_message_prefix, context_msg)
        raise HomeAssistantError(
            f"{error_message_prefix}{context_msg}: Unexpected error - {type(err).__name__}"
        ) from err


# Simplified handlers
async def _async_handle_send_command(
    api: BedrockServerManagerApi, server: str, command: str
):
    return await _base_api_call_handler(
        api.async_send_server_command(server, command), "Send command", server
    )


async def _async_handle_prune_downloads(
    api: BedrockServerManagerApi, directory: str, keep: Optional[int], manager_id: str
):
    return await _base_api_call_handler(
        api.async_prune_downloads(directory=directory, keep=keep),
        "Prune downloads",
        manager_id,
    )


async def _async_handle_trigger_backup(
    api: BedrockServerManagerApi,
    server: str,
    backup_type: str,
    file_to_backup: Optional[str],
):
    return await _base_api_call_handler(
        api.async_trigger_server_backup(server, backup_type, file_to_backup),
        "Trigger backup",
        server,
    )


async def _async_handle_restore_backup(
    api: BedrockServerManagerApi, server: str, restore_type: str, backup_file: str
):
    return await _base_api_call_handler(
        api.async_restore_server_backup(server, restore_type, backup_file),
        "Restore backup",
        server,
    )


async def _async_handle_restore_latest_all(api: BedrockServerManagerApi, server: str):
    return await _base_api_call_handler(
        api.async_restore_server_latest_all(server), "Restore latest all", server
    )


async def _async_handle_add_to_allowlist(
    api: BedrockServerManagerApi, server: str, players: List[str], ignore_limit: bool
):
    return await _base_api_call_handler(
        api.async_add_server_allowlist(server, players, ignore_limit),
        "Add to allowlist",
        server,
    )


async def _async_handle_remove_from_allowlist(
    api: BedrockServerManagerApi, server: str, player_name: str
):
    return await _base_api_call_handler(
        api.async_remove_server_allowlist_player(server, player_name),
        "Remove from allowlist",
        server,
    )


async def _async_handle_set_permissions(
    api: BedrockServerManagerApi, server: str, permissions_dict: Dict[str, str]
):
    return await _base_api_call_handler(
        api.async_set_server_permissions(server, permissions_dict),
        "Set permissions",
        server,
    )


async def _async_handle_update_properties(
    api: BedrockServerManagerApi, server: str, properties_dict: Dict[str, Any]
):
    return await _base_api_call_handler(
        api.async_update_server_properties(server, properties_dict),
        "Update properties",
        server,
    )


async def _async_handle_install_world(
    api: BedrockServerManagerApi, server: str, filename: str
):
    return await _base_api_call_handler(
        api.async_install_server_world(server, filename), "Install world", server
    )


async def _async_handle_install_addon(
    api: BedrockServerManagerApi, server: str, filename: str
):
    return await _base_api_call_handler(
        api.async_install_server_addon(server, filename), "Install addon", server
    )


async def _async_handle_configure_os_service(
    api: BedrockServerManagerApi, server: str, payload: Dict[str, bool], manager_id: str
):
    return await _base_api_call_handler(
        api.async_configure_server_os_service(server, payload),
        "Configure OS service",
        f"{server} on manager '{manager_id}'",
    )


async def _async_handle_add_global_players(
    api: BedrockServerManagerApi, players_data: List[str], manager_id: str
):
    return await _base_api_call_handler(
        api.async_add_players(players_data), "Add global players", manager_id
    )


async def _async_handle_scan_players(api: BedrockServerManagerApi, manager_id: str):
    return await _base_api_call_handler(
        api.async_scan_players(), "Scan players", manager_id
    )


async def _async_handle_install_server(
    api: BedrockServerManagerApi,
    server_name_to_install: str,
    server_version: str,
    overwrite: bool,
    manager_id: str,
):
    log_context = f"for server '{server_name_to_install}' on manager '{manager_id}'"
    try:
        response = await api.async_install_new_server(
            server_name_to_install, server_version, overwrite
        )
        if response.get("status") == "confirm_needed":
            msg = f"Install server {log_context}: Server already exists and overwrite was false. Set 'overwrite: true' to replace it or use the 'delete_server' service first."
            _LOGGER.warning(msg)
            raise ServiceValidationError(
                description=msg,
                translation_domain=DOMAIN,
                translation_key="service_install_server_confirm_needed",  # Updated key
                translation_placeholders={"server_name": server_name_to_install},
            )
        _LOGGER.info(
            "Successfully requested install %s. API Message: %s",
            log_context,
            response.get("message", "N/A"),
        )
        return response
    except (
        AuthError,
        CannotConnectError,
        APIError,
        ValueError,
        InvalidInputError,
    ) as err:
        error_prefix = f"Install server {log_context}"
        err_msg = (
            err.api_message
            if hasattr(err, "api_message") and err.api_message
            else str(err)
        )
        status_code_msg = (
            f"(Status: {err.status_code})"
            if hasattr(err, "status_code") and err.status_code
            else ""
        )
        full_error_msg = (
            f"{error_prefix}: {type(err).__name__} {status_code_msg} - {err_msg}"
        )
        _LOGGER.error(full_error_msg)
        if isinstance(err, (ValueError, InvalidInputError)):
            raise ServiceValidationError(description=full_error_msg) from err
        raise HomeAssistantError(full_error_msg) from err
    except Exception as err:
        _LOGGER.exception("Install server %s: Unexpected error.", log_context)
        raise HomeAssistantError(
            f"Install server {log_context}: Unexpected error - {type(err).__name__}"
        ) from err


async def _async_handle_delete_server(
    hass: HomeAssistant,
    api: BedrockServerManagerApi,
    server_to_delete: str,
    manager_host_port_id: str,
):
    log_context = f"for server '{server_to_delete}' on manager '{manager_host_port_id}'"
    _LOGGER.critical("EXECUTING IRREVERSIBLE DELETE %s", log_context)
    device_removed_from_ha = False
    try:
        response = await api.async_delete_server(server_name=server_to_delete)
        if response and response.get("status") == "success":
            _LOGGER.info(
                "Manager API confirmed deletion of server '%s'. Attempting HA device removal.",
                server_to_delete,
            )
            device_registry_instance = dr.async_get(hass)
            server_device_unique_value = f"{manager_host_port_id}_{server_to_delete}"
            device_identifier_tuple = (DOMAIN, server_device_unique_value)
            device_to_remove = device_registry_instance.async_get_device(
                identifiers={device_identifier_tuple}
            )
            if device_to_remove:
                _LOGGER.debug(
                    "Removing device '%s' (ID: %s) from HA registry.",
                    device_to_remove.name or device_to_remove.id,
                    device_to_remove.id,
                )
                device_registry_instance.async_remove_device(device_to_remove.id)
                device_removed_from_ha = True
            else:
                _LOGGER.warning(
                    "Could not find HA device for server '%s' (identifier: %s) to remove from registry after API deletion.",
                    server_to_delete,
                    device_identifier_tuple,
                )
            return {
                "status": "success",
                "message": response.get("message"),
                "ha_device_removed": device_removed_from_ha,
            }
        else:
            msg = f"Manager API did not confirm deletion {log_context}. Response: {response}"
            _LOGGER.error(msg)
            raise HomeAssistantError(msg)
    except (
        AuthError,
        CannotConnectError,
        APIError,
        ValueError,
        InvalidInputError,
    ) as err:
        error_prefix = f"Delete server {log_context}"
        err_msg = (
            err.api_message
            if hasattr(err, "api_message") and err.api_message
            else str(err)
        )
        status_code_msg = (
            f"(Status: {err.status_code})"
            if hasattr(err, "status_code") and err.status_code
            else ""
        )
        full_error_msg = (
            f"{error_prefix}: {type(err).__name__} {status_code_msg} - {err_msg}"
        )
        _LOGGER.error(full_error_msg)
        if isinstance(
            err, (ValueError, InvalidInputError)
        ):  # Could be client-side validation if any was added to delete_server
            raise ServiceValidationError(description=full_error_msg) from err
        raise HomeAssistantError(full_error_msg) from err
    except Exception as err:
        _LOGGER.exception("Delete server %s: Unexpected error.", log_context)
        raise HomeAssistantError(
            f"Delete server {log_context}: Unexpected error - {type(err).__name__}"
        ) from err


# --- Target Resolvers and Executors ---
async def _resolve_server_targets(
    service: ServiceCall, hass: HomeAssistant
) -> Dict[str, str]:
    servers_to_target: Dict[str, str] = {}
    entity_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    def process_device_for_server_target(
        device_entry: dr.DeviceEntry, config_entry_id_context: str
    ):
        nonlocal servers_to_target
        try:
            manager_data = hass.data[DOMAIN][config_entry_id_context]
            manager_host_port_id = manager_data["manager_identifier"][1]
        except (KeyError, TypeError, IndexError):
            _LOGGER.warning(
                "Could not get manager_identifier for config entry %s when processing device %s.",
                config_entry_id_context,
                device_entry.id,
            )
            return

        parsed_server_name = None
        for identifier_domain, identifier_value in device_entry.identifiers:
            if identifier_domain == DOMAIN:
                expected_prefix = manager_host_port_id + "_"
                if identifier_value.startswith(expected_prefix):
                    prefix_len = len(expected_prefix)
                    if (
                        len(identifier_value) > prefix_len
                    ):  # Ensure there's something after the prefix
                        parsed_server_name = identifier_value[prefix_len:]
                        break

        if parsed_server_name:
            if config_entry_id_context not in servers_to_target:
                servers_to_target[config_entry_id_context] = parsed_server_name
                _LOGGER.debug(
                    "Targeted server '%s' via device %s for config entry %s",
                    parsed_server_name,
                    device_entry.id,
                    config_entry_id_context,
                )
            elif servers_to_target[config_entry_id_context] != parsed_server_name:
                _LOGGER.warning(
                    "Config entry %s targeted via multiple entities/devices resolving to different servers ('%s' vs '%s'). Using first resolved: '%s'.",
                    config_entry_id_context,
                    servers_to_target[config_entry_id_context],
                    parsed_server_name,
                    servers_to_target[config_entry_id_context],
                )
        elif _LOGGER.isEnabledFor(logging.DEBUG):
            is_manager_device = any(
                val == manager_host_port_id
                for dom, val in device_entry.identifiers
                if dom == DOMAIN
            )
            if not is_manager_device:
                _LOGGER.debug(
                    "Device %s (identifiers: %s) for config entry %s is not a recognized BSM server sub-device.",
                    device_entry.id,
                    device_entry.identifiers,
                    config_entry_id_context,
                )

    target_entity_ids: List[str] = cv.ensure_list(service.data.get(ATTR_ENTITY_ID, []))
    target_device_ids: List[str] = cv.ensure_list(service.data.get(ATTR_DEVICE_ID, []))
    target_area_ids: List[str] = cv.ensure_list(service.data.get(ATTR_AREA_ID, []))

    for entity_id in target_entity_ids:
        entity_entry = entity_reg.async_get(entity_id)
        if (
            entity_entry
            and entity_entry.platform == DOMAIN
            and entity_entry.config_entry_id
            and entity_entry.device_id
        ):
            if entity_entry.config_entry_id in hass.data.get(DOMAIN, {}):
                device_of_entity = dev_reg.async_get(entity_entry.device_id)
                if device_of_entity:
                    process_device_for_server_target(
                        device_of_entity, entity_entry.config_entry_id
                    )

    for device_id in target_device_ids:
        device_entry = dev_reg.async_get(device_id)
        if device_entry:
            for ce_id in device_entry.config_entries:
                if ce_id in hass.data.get(DOMAIN, {}):
                    process_device_for_server_target(device_entry, ce_id)
                    break

    if target_area_ids:
        all_devices = list(dev_reg.devices.values())
        for device_entry in all_devices:
            if device_entry.area_id in target_area_ids:
                for ce_id in device_entry.config_entries:
                    if ce_id in hass.data.get(DOMAIN, {}):
                        process_device_for_server_target(device_entry, ce_id)
                        break

    if not servers_to_target:
        error_message = f"Service {service.domain}.{service.service} requires targeting specific BSM server devices or their entities."
        key_for_translation = "service_no_target_provided"
        if not any([target_entity_ids, target_device_ids, target_area_ids]):
            error_message = f"No target (device, entity, or area) was provided for service {service.domain}.{service.service}."
        _LOGGER.error(
            error_message + " Targets provided: Entities=%s, Devices=%s, Areas=%s",
            target_entity_ids,
            target_device_ids,
            target_area_ids,
        )
        if not any([target_entity_ids, target_device_ids, target_area_ids]):
            raise ServiceValidationError(
                description=error_message,
                translation_domain=DOMAIN,
                translation_key=key_for_translation,
            )
        raise HomeAssistantError(error_message)

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
    config_entry_ids_to_target: Set[str] = set()
    entity_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    target_entity_ids: List[str] = cv.ensure_list(service.data.get(ATTR_ENTITY_ID, []))
    target_device_ids: List[str] = cv.ensure_list(service.data.get(ATTR_DEVICE_ID, []))
    target_area_ids: List[str] = cv.ensure_list(service.data.get(ATTR_AREA_ID, []))

    for entity_id in target_entity_ids:
        entity_entry = entity_reg.async_get(entity_id)
        if (
            entity_entry
            and entity_entry.domain == DOMAIN
            and entity_entry.config_entry_id
        ):
            if entity_entry.config_entry_id in hass.data.get(DOMAIN, {}):
                config_entry_ids_to_target.add(entity_entry.config_entry_id)

    for device_id in target_device_ids:
        device_entry = dev_reg.async_get(device_id)
        if device_entry:
            for ce_id in device_entry.config_entries:
                config_entry = hass.config_entries.async_get_entry(ce_id)
                if (
                    config_entry
                    and config_entry.domain == DOMAIN
                    and ce_id in hass.data.get(DOMAIN, {})
                ):
                    config_entry_ids_to_target.add(ce_id)

    if target_area_ids:
        all_devices = list(dev_reg.devices.values())
        for device_entry in all_devices:
            if device_entry.area_id in target_area_ids:
                for ce_id in device_entry.config_entries:
                    config_entry = hass.config_entries.async_get_entry(ce_id)
                    if (
                        config_entry
                        and config_entry.domain == DOMAIN
                        and ce_id in hass.data.get(DOMAIN, {})
                    ):
                        config_entry_ids_to_target.add(ce_id)

    if not config_entry_ids_to_target:
        error_message = f"Service {service.domain}.{service.service} requires targeting a BSM manager instance."
        key_for_translation = "service_no_target_provided_manager"
        if not any([target_entity_ids, target_device_ids, target_area_ids]):
            error_message += " No target was provided."
        else:
            error_message += (
                " Provided targets did not resolve to any loaded BSM manager instances."
            )
        _LOGGER.error(
            error_message + " Targets: E=%s, D=%s, A=%s",
            target_entity_ids,
            target_device_ids,
            target_area_ids,
        )
        if not any([target_entity_ids, target_device_ids, target_area_ids]):
            raise ServiceValidationError(
                description=error_message,
                translation_domain=DOMAIN,
                translation_key=key_for_translation,
            )
        raise HomeAssistantError(error_message)

    _LOGGER.debug(
        "Resolved manager targets for service %s.%s: %s",
        service.domain,
        service.service,
        list(config_entry_ids_to_target),
    )
    return list(config_entry_ids_to_target)


async def _execute_targeted_service(
    service_call: ServiceCall,
    hass: HomeAssistant,
    handler_coro: Coroutine,
    *handler_args: Any,
):
    try:
        resolved_targets = await _resolve_server_targets(service_call, hass)
    except (HomeAssistantError, ServiceValidationError) as e:
        _LOGGER.error(
            "Failed to resolve targets for service %s.%s: %s",
            service_call.domain,
            service_call.service,
            e,
        )
        raise

    tasks = []
    processed_targets_info = []

    for config_entry_id, target_server_name in resolved_targets.items():
        try:
            entry_data = hass.data[DOMAIN][config_entry_id]
            api_client: BedrockServerManagerApi = entry_data["api"]
            manager_host_port_id = entry_data["manager_identifier"][1]

            current_handler_args = [api_client, target_server_name]
            # Special argument handling for _async_handle_delete_server
            if handler_coro.__name__ == "_async_handle_delete_server":
                current_handler_args = [
                    hass,
                    api_client,
                    target_server_name,
                    manager_host_port_id,
                ]
            else:  # For other handlers, just extend with common args
                current_handler_args.extend(handler_args)

            tasks.append(handler_coro(*current_handler_args))
            processed_targets_info.append(
                {
                    "cid": config_entry_id,
                    "sname": target_server_name,
                    "manager_id": manager_host_port_id,
                }
            )
        except KeyError:
            _LOGGER.error(
                "Data missing for config entry %s (server %s). Skipping service.",
                config_entry_id,
                target_server_name,
            )
        except Exception:
            _LOGGER.exception(
                "Error queueing service for server %s (entry %s)",
                target_server_name,
                config_entry_id,
            )

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result_or_exc in enumerate(results):
            target_info = processed_targets_info[i]
            if isinstance(result_or_exc, Exception):
                _LOGGER.debug(
                    "Service execution for server '%s' (manager '%s') resulted in an exception (already logged by handler): %s",
                    target_info["sname"],
                    target_info["manager_id"],
                    type(result_or_exc).__name__,
                )


async def _execute_manager_targeted_service(
    service_call: ServiceCall,
    hass: HomeAssistant,
    handler_coro: Coroutine,
    *handler_args: Any,
):
    try:
        resolved_config_entry_ids = await _resolve_manager_instance_targets(
            service_call, hass
        )
    except (HomeAssistantError, ServiceValidationError) as e:
        _LOGGER.error(
            "Failed to resolve manager targets for service %s.%s: %s",
            service_call.domain,
            service_call.service,
            e,
        )
        raise

    tasks = []
    coordinators_to_refresh: List[ManagerDataCoordinator] = []
    processed_targets_info = []

    for config_entry_id in resolved_config_entry_ids:
        try:
            entry_data = hass.data[DOMAIN][config_entry_id]
            api_client: BedrockServerManagerApi = entry_data["api"]
            manager_host_port_id = entry_data["manager_identifier"][1]

            current_handler_args = [api_client]
            current_handler_args.extend(handler_args)
            # Pass manager_host_port_id as the last arg for handlers that need it for context/logging
            if handler_coro.__name__ in [
                "_async_handle_prune_downloads",
                "_async_handle_install_server",
                "_async_handle_add_global_players",
                "_async_handle_scan_players",
            ]:
                current_handler_args.append(manager_host_port_id)

            tasks.append(handler_coro(*current_handler_args))
            processed_targets_info.append(
                {"cid": config_entry_id, "manager_id": manager_host_port_id}
            )

            if handler_coro.__name__ in [
                "_async_handle_add_global_players",
                "_async_handle_scan_players",
                "_async_handle_install_server",
            ]:
                coordinator: Optional[ManagerDataCoordinator] = entry_data.get(
                    "manager_coordinator"
                )
                if coordinator and coordinator not in coordinators_to_refresh:
                    coordinators_to_refresh.append(coordinator)
        except KeyError:
            _LOGGER.error(
                "Data missing for config entry %s. Skipping manager service.",
                config_entry_id,
            )
        except Exception:
            _LOGGER.exception(
                "Error queueing manager service for entry %s", config_entry_id
            )

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result_or_exc in enumerate(results):
            target_info = processed_targets_info[i]
            if isinstance(result_or_exc, Exception):
                _LOGGER.debug(
                    "Manager service execution for instance '%s' (entry %s) resulted in an exception (already logged by handler): %s",
                    target_info["manager_id"],
                    target_info["cid"],
                    type(result_or_exc).__name__,
                )

        unique_coordinators_to_refresh = list(set(coordinators_to_refresh))
        for coordinator in unique_coordinators_to_refresh:
            _LOGGER.debug(
                "Requesting refresh of ManagerDataCoordinator for BSM '%s' after service.",
                coordinator.name,
            )
            await coordinator.async_request_refresh()


# --- Main Service Handlers ---
async def async_handle_send_command_service(service: ServiceCall, hass: HomeAssistant):
    await _execute_targeted_service(
        service, hass, _async_handle_send_command, service.data[FIELD_COMMAND]
    )


async def async_handle_prune_downloads_service(
    service: ServiceCall, hass: HomeAssistant
):
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
    if service.data[FIELD_BACKUP_TYPE] == "config" and not service.data.get(
        FIELD_FILE_TO_BACKUP
    ):
        raise ServiceValidationError(
            description=f"'{FIELD_FILE_TO_BACKUP}' is required when '{FIELD_BACKUP_TYPE}' is 'config'.",
            translation_domain=DOMAIN,
            translation_key="service_backup_config_file_required",
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
    await _execute_targeted_service(service, hass, _async_handle_restore_latest_all)


async def async_handle_install_server_service(
    service: ServiceCall, hass: HomeAssistant
):
    await _execute_manager_targeted_service(
        service,
        hass,
        _async_handle_install_server,
        service.data[FIELD_SERVER_NAME],
        service.data[FIELD_SERVER_VERSION],
        service.data[FIELD_OVERWRITE],
    )


async def async_handle_scan_players_service(service: ServiceCall, hass: HomeAssistant):
    await _execute_manager_targeted_service(service, hass, _async_handle_scan_players)


async def async_handle_delete_server_service(service: ServiceCall, hass: HomeAssistant):
    _LOGGER.warning(
        "Executing delete_server service call. User confirmation was: %s",
        service.data[FIELD_CONFIRM_DELETE],
    )

    try:
        resolved_targets = await _resolve_server_targets(service, hass)
    except (HomeAssistantError, ServiceValidationError) as e:
        _LOGGER.error("Failed to resolve targets for delete_server service: %s", e)
        raise

    tasks = []
    processed_targets_for_notification: List[Dict[str, Any]] = []

    for config_entry_id, server_name_to_delete in resolved_targets.items():
        try:
            entry_data = hass.data[DOMAIN][config_entry_id]
            api_client: BedrockServerManagerApi = entry_data["api"]
            manager_host_port_id = entry_data["manager_identifier"][1]

            tasks.append(
                _async_handle_delete_server(
                    hass, api_client, server_name_to_delete, manager_host_port_id
                )
            )
            processed_targets_for_notification.append(
                {
                    "server_name": server_name_to_delete,
                    "manager_id": manager_host_port_id,
                    "config_entry_id": config_entry_id,
                }
            )
        except KeyError:
            _LOGGER.error(
                "Data missing for config entry %s (server %s) for delete_server service. Skipping.",
                config_entry_id,
                server_name_to_delete,
            )
            processed_targets_for_notification.append(
                {
                    "server_name": server_name_to_delete,
                    "error_queuing": "Missing entry data",
                    "manager_id": "Unknown",
                }
            )
        except Exception:
            _LOGGER.exception(
                "Error queueing delete_server for server %s (entry %s)",
                server_name_to_delete,
                config_entry_id,
            )
            processed_targets_for_notification.append(
                {
                    "server_name": server_name_to_delete,
                    "error_queuing": "Exception during queueing",
                    "manager_id": "Unknown",
                }
            )

    if not tasks and resolved_targets:
        async_create(
            hass,
            "Could not queue deletion for any targeted servers due to setup issues. Check logs.",
            "Minecraft Server Deletion Problem",
            f"bsm_delete_{service.context.id}_queue_fail",
        )
        return
    if not tasks:
        return

    results = await asyncio.gather(*tasks, return_exceptions=True)

    success_messages: List[str] = []
    failure_messages: List[str] = []

    for i, result_or_exc in enumerate(results):
        target_info = processed_targets_for_notification[i]
        sname = target_info["server_name"]

        if target_info.get("error_queuing"):
            failure_messages.append(
                f"'{sname}': Failed to queue for deletion ({target_info['error_queuing']})."
            )
            continue

        if isinstance(result_or_exc, Exception):
            err_msg = (
                result_or_exc.args[0] if result_or_exc.args else str(result_or_exc)
            )
            failure_messages.append(
                f"'{sname}': Failed ({type(result_or_exc).__name__} - {err_msg})."
            )
            # Error already logged by _async_handle_delete_server or _base_api_call_handler
        elif (
            isinstance(result_or_exc, dict) and result_or_exc.get("status") == "success"
        ):
            msg = f"'{sname}': API deletion successful."
            if result_or_exc.get("ha_device_removed"):
                msg += " HA device removed."
            else:
                msg += " HA device not found or not removed from HA."
            success_messages.append(msg)
        else:
            failure_messages.append(
                f"'{sname}': API deletion status unclear or failed (Result: {result_or_exc})."
            )

    final_notification_parts = []
    if success_messages:
        final_notification_parts.append(f"Successes: {'; '.join(success_messages)}")
    if failure_messages:
        final_notification_parts.append(f"Failures: {'; '.join(failure_messages)}")

    if not final_notification_parts:
        final_notification_parts.append(
            "No deletion actions were completed or status is unclear. Check logs for details."
        )

    async_create(
        hass=hass,
        message=" ".join(final_notification_parts),
        title="Minecraft Server Deletion Results",
        notification_id=f"bsm_delete_results_{service.context.id}",
    )


async def async_handle_add_to_allowlist_service(
    service: ServiceCall, hass: HomeAssistant
):
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
    await _execute_targeted_service(
        service,
        hass,
        _async_handle_remove_from_allowlist,
        service.data[FIELD_PLAYER_NAME],
    )


async def async_handle_set_permissions_service(
    service: ServiceCall, hass: HomeAssistant
):
    await _execute_targeted_service(
        service, hass, _async_handle_set_permissions, service.data[FIELD_PERMISSIONS]
    )


async def async_handle_update_properties_service(
    service: ServiceCall, hass: HomeAssistant
):
    await _execute_targeted_service(
        service, hass, _async_handle_update_properties, service.data[FIELD_PROPERTIES]
    )


async def async_handle_install_world_service(service: ServiceCall, hass: HomeAssistant):
    await _execute_targeted_service(
        service, hass, _async_handle_install_world, service.data[FIELD_FILENAME]
    )


async def async_handle_install_addon_service(service: ServiceCall, hass: HomeAssistant):
    await _execute_targeted_service(
        service, hass, _async_handle_install_addon, service.data[FIELD_FILENAME]
    )


async def async_handle_configure_os_service_service(
    service: ServiceCall, hass: HomeAssistant
):
    autoupdate_val = service.data[FIELD_AUTOUPDATE]
    autostart_val = service.data.get(FIELD_AUTOSTART)

    try:
        resolved_targets = await _resolve_server_targets(service, hass)
    except (HomeAssistantError, ServiceValidationError) as e:
        _LOGGER.error("Failed to resolve targets for configure_os_service: %s", e)
        raise

    tasks = []
    processed_targets_info = []
    for config_entry_id, server_name in resolved_targets.items():
        try:
            entry_data = hass.data[DOMAIN][config_entry_id]
            api_client: BedrockServerManagerApi = entry_data["api"]
            manager_host_port_id = entry_data["manager_identifier"][1]
            manager_os_type = entry_data.get("manager_os_type", "unknown").lower()

            payload: Dict[str, bool] = {FIELD_AUTOUPDATE: autoupdate_val}
            if autostart_val is not None:
                if manager_os_type == "linux":
                    payload[FIELD_AUTOSTART] = autostart_val
                else:
                    _LOGGER.warning(
                        "Autostart config for server '%s' (manager '%s') ignored as manager OS '%s' is not Linux, but %s was provided.",
                        server_name,
                        manager_host_port_id,
                        manager_os_type,
                        FIELD_AUTOSTART,
                    )

            tasks.append(
                _async_handle_configure_os_service(
                    api_client, server_name, payload, manager_host_port_id
                )
            )
            processed_targets_info.append(
                {
                    "cid": config_entry_id,
                    "sname": server_name,
                    "manager_id": manager_host_port_id,
                }
            )
        except KeyError:
            _LOGGER.error(
                "Data missing for config entry %s (server %s) for OS service config. Skipping.",
                config_entry_id,
                server_name,
            )
        except Exception:
            _LOGGER.exception(
                "Error queueing configure_os_service for server %s (entry %s)",
                server_name,
                config_entry_id,
            )

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            target_info = processed_targets_info[i]
            if isinstance(result, Exception):  # Check if result is an exception
                _LOGGER.debug(
                    "OS Service config for server '%s' (manager '%s') resulted in an exception (already logged by handler): %s",
                    target_info["sname"],
                    target_info["manager_id"],
                    type(result).__name__,
                )


async def async_handle_add_global_players_service(
    service: ServiceCall, hass: HomeAssistant
):
    await _execute_manager_targeted_service(
        service, hass, _async_handle_add_global_players, service.data[FIELD_PLAYERS]
    )


# --- Service Registration/Removal ---
async def async_register_services(hass: HomeAssistant) -> None:
    """Register services with Home Assistant."""
    service_mapping = {
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
        SERVICE_SCAN_PLAYERS: (
            async_handle_scan_players_service,
            SCAN_PLAYERS_SERVICE_SCHEMA,
        ),
    }

    for service_name, (handler, schema) in service_mapping.items():
        if not hass.services.has_service(DOMAIN, service_name):

            async def service_wrapper_closure(
                call: ServiceCall, captured_handler=handler
            ):
                _LOGGER.debug(
                    "Service call '%s.%s' received, dispatching to %s.",
                    call.domain,
                    call.service,
                    captured_handler.__name__,
                )
                try:
                    await captured_handler(call, hass)
                except ServiceValidationError as sve:
                    _LOGGER.warning(
                        "Service validation error in %s for %s.%s: %s",
                        captured_handler.__name__,
                        call.domain,
                        call.service,
                        sve,
                    )
                    raise
                except HomeAssistantError as hae:
                    _LOGGER.error(
                        "HomeAssistantError in %s for %s.%s: %s",
                        captured_handler.__name__,
                        call.domain,
                        call.service,
                        hae,
                    )
                    raise
                except Exception as exc:
                    _LOGGER.exception(
                        "Unexpected error in service handler %s for %s.%s",
                        captured_handler.__name__,
                        call.domain,
                        call.service,
                    )
                    # Raise a generic HomeAssistantError to provide some feedback to the user
                    raise HomeAssistantError(
                        f"Unexpected error executing service {call.domain}.{call.service}: {type(exc).__name__} - {exc}"
                    ) from exc

            hass.services.async_register(
                DOMAIN, service_name, service_wrapper_closure, schema=schema
            )
            _LOGGER.debug("Registered service: %s.%s", DOMAIN, service_name)


async def async_remove_services(hass: HomeAssistant) -> None:
    """Remove previously registered services."""
    domain_data = hass.data.get(DOMAIN)
    is_last_entry = True
    if domain_data:
        is_last_entry = not any(
            entry_id != "_services_registered" for entry_id in domain_data
        )

    if is_last_entry:
        _LOGGER.info(
            "Last BSM config entry unloaded or no entries active. Removing all BSM services."
        )
        services_to_unregister = [
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
            SERVICE_SCAN_PLAYERS,
        ]
        for service_name in services_to_unregister:
            if hass.services.has_service(DOMAIN, service_name):
                _LOGGER.debug("Removing service: %s.%s", DOMAIN, service_name)
                hass.services.async_remove(DOMAIN, service_name)

        if domain_data:  # Check again as it might have been modified by another process
            domain_data.pop("_services_registered", None)
            if not domain_data:
                hass.data.pop(DOMAIN, None)
    else:
        _LOGGER.debug(
            "Other BSM config entries still loaded. Services will not be removed."
        )
