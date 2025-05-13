# custom_components/bedrock_server_manager/services.py
"""Service handlers for the Bedrock Server Manager integration."""

import asyncio
import logging
from typing import cast, Dict, Optional, List, Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    entity_registry as er,
    device_registry as dr,
    config_validation as cv,
)

# --- IMPORT FROM CONSTANTS ---
from .const import (
    DOMAIN,
    SERVICE_ADD_GLOBAL_PLAYERS,
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

# --- IMPORT FROM THE NEW LIBRARY ---
from pybedrock_server_manager import (
    BedrockServerManagerApi,
    APIError,
    AuthError,
    CannotConnectError,
    ServerNotRunningError,
    # ServerNotFoundError might be useful if a helper specifically needs to catch it
)

# --- END IMPORT FROM NEW LIBRARY ---

# --- IMPORT FROM LOCAL MODULES ---
from .coordinator import ManagerDataCoordinator

_LOGGER = logging.getLogger(__name__)

# --- Service Schema Definitions ---
SEND_COMMAND_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_COMMAND): cv.string,
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
    }
)
PRUNE_DOWNLOADS_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_DIRECTORY): cv.string,
        vol.Optional(FIELD_KEEP): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)
TRIGGER_BACKUP_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_BACKUP_TYPE): vol.In(["all", "world", "config"]),
        vol.Optional(FIELD_FILE_TO_BACKUP): cv.string,
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
    }
)
RESTORE_BACKUP_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_RESTORE_TYPE): vol.In(["world", "config"]),
        vol.Required(FIELD_BACKUP_FILE): cv.string,
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
    }
)
RESTORE_LATEST_ALL_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
    }
)
INSTALL_SERVER_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_SERVER_NAME): cv.string,
        vol.Required(FIELD_SERVER_VERSION): cv.string,
        vol.Optional(FIELD_OVERWRITE, default=False): cv.boolean,
    }
)
DELETE_SERVER_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_CONFIRM_DELETE): True,
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
    }
)
ADD_TO_ALLOWLIST_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PLAYERS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(FIELD_IGNORE_PLAYER_LIMIT, default=False): cv.boolean,
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
    }
)
REMOVE_FROM_ALLOWLIST_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PLAYER_NAME): cv.string,
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
    }
)
SET_PERMISSIONS_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PERMISSIONS): vol.Schema({cv.string: cv.string}),
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
    }
)
UPDATE_PROPERTIES_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PROPERTIES): vol.Schema(
            {cv.string: vol.Any(cv.string, cv.positive_int, cv.boolean)}
        ),
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
    }
)
INSTALL_WORLD_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_FILENAME): cv.string,
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
    }
)
INSTALL_ADDON_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_FILENAME): cv.string,
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
    }
)
CONFIGURE_OS_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_AUTOUPDATE): cv.boolean,
        vol.Optional(FIELD_AUTOSTART): cv.boolean,
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
    }
)
ADD_GLOBAL_PLAYERS_SERVICE_SCHEMA = vol.Schema(
    {vol.Required(FIELD_PLAYERS): vol.All(cv.ensure_list, [cv.string])}
)


# --- Service Handler Helper Functions ---
async def _base_api_call_handler(
    api_call_coro, error_message_prefix: str, server_name_for_log: Optional[str] = None
):
    """Generic helper to make an API call and handle common exceptions."""
    log_context = f"for server '{server_name_for_log}'" if server_name_for_log else ""
    try:
        response = await api_call_coro
        _LOGGER.debug(
            "Successfully executed API call %s. Response: %s", log_context, response
        )
        return response  # Return response for handlers that need it
    except ServerNotRunningError as err:
        _LOGGER.error(
            "%s %s: Server not running - %s", error_message_prefix, log_context, err
        )
        raise HomeAssistantError(
            f"{error_message_prefix}: Server is not running."
        ) from err
    except (APIError, AuthError, CannotConnectError) as err:
        _LOGGER.error(
            "%s %s: API/Connection Error - %s", error_message_prefix, log_context, err
        )
        raise HomeAssistantError(f"{error_message_prefix}: {err}") from err
    except ValueError as err:  # For client-side validation errors from library methods
        _LOGGER.error(
            "%s %s: Invalid input - %s", error_message_prefix, log_context, err
        )
        raise HomeAssistantError(
            f"{error_message_prefix}: Invalid input - {err}"
        ) from err
    except Exception as err:
        _LOGGER.exception(
            "%s %s: Unexpected error - %s", error_message_prefix, log_context, err
        )
        raise HomeAssistantError(
            f"{error_message_prefix}: Unexpected error - {err}"
        ) from err


async def _async_handle_send_command(
    api: BedrockServerManagerApi, server: str, command: str
):
    await _base_api_call_handler(
        api.async_send_server_command(server, command), "Send command failed", server
    )


async def _async_handle_prune_downloads(
    api: BedrockServerManagerApi, directory: str, keep: Optional[int]
):
    await _base_api_call_handler(
        api.async_prune_downloads(directory=directory, keep=keep),
        "Prune downloads failed",
    )


async def _async_handle_trigger_backup(
    api: BedrockServerManagerApi,
    server: str,
    backup_type: str,
    file_to_backup: Optional[str],
):
    await _base_api_call_handler(
        api.async_trigger_server_backup(
            server_name=server, backup_type=backup_type, file_to_backup=file_to_backup
        ),
        "Trigger backup failed",
        server,
    )


async def _async_handle_restore_backup(
    api: BedrockServerManagerApi, server: str, restore_type: str, backup_file: str
):
    await _base_api_call_handler(
        api.async_restore_server_backup(
            server_name=server, restore_type=restore_type, backup_file=backup_file
        ),
        "Restore backup failed",
        server,
    )


async def _async_handle_restore_latest_all(api: BedrockServerManagerApi, server: str):
    await _base_api_call_handler(
        api.async_restore_server_latest_all(server_name=server),
        "Restore latest all failed",
        server,
    )


async def _async_handle_install_server(
    api: BedrockServerManagerApi, server_name: str, server_version: str, overwrite: bool
):
    try:
        response = await api.async_install_new_server(
            server_name=server_name, server_version=server_version, overwrite=overwrite
        )
        if response.get("status") == "confirm_needed":
            _LOGGER.warning(
                "Server '%s' already exists and overwrite was false.", server_name
            )
            raise HomeAssistantError(
                f"Server '{server_name}' already exists. Set 'overwrite: true' to replace it."
            )
        _LOGGER.info(
            "Successfully requested install for server '%s' (Version: %s, Overwrite: %s). API Message: %s",
            server_name,
            server_version,
            overwrite,
            response.get("message", "N/A"),
        )
    except (APIError, AuthError, CannotConnectError) as err:
        _LOGGER.error(
            f"Install server failed for '{server_name}': API/Connection Error - {err}"
        )
        raise HomeAssistantError(f"Install server failed: {err}") from err
    except (
        Exception
    ) as err:  # Catches HomeAssistantError from above or other unexpected
        _LOGGER.exception(
            f"Install server failed for '{server_name}': Unexpected problem - {err}"
        )
        if not isinstance(err, HomeAssistantError):  # Avoid double-wrapping
            raise HomeAssistantError(
                f"Install server failed: Unexpected error - {err}"
            ) from err
        raise  # Re-raise HomeAssistantError


async def _async_handle_delete_server(
    hass: HomeAssistant, api: BedrockServerManagerApi, server: str, config_entry_id: str
):
    _LOGGER.critical("EXECUTING IRREVERSIBLE DELETE for server '%s'", server)
    device_removed = False
    try:
        response = await api.async_delete_server(server_name=server)
        if response and response.get("status") == "success":
            _LOGGER.info(
                "Manager API confirmed deletion of '%s'. Removing from HA.", server
            )
            device_registry_instance = dr.async_get(hass)
            device_identifier = (DOMAIN, server)
            device_to_remove = device_registry_instance.async_get_device(
                identifiers={device_identifier}
            )
            if device_to_remove:
                _LOGGER.debug(
                    "Removing device %s (%s) from registry.",
                    device_to_remove.name_by_user or device_to_remove.name,
                    device_to_remove.id,
                )
                device_registry_instance.async_remove_device(device_to_remove.id)
                device_removed = True
            else:
                _LOGGER.warning(
                    "Could not find device %s in registry after API delete.",
                    device_identifier,
                )
        else:
            _LOGGER.error(
                "Manager API did not confirm deletion for '%s'. Response: %s.",
                server,
                response,
            )
            raise HomeAssistantError(
                f"Manager API did not confirm deletion for {server}."
            )
    except (APIError, AuthError, CannotConnectError) as err:
        _LOGGER.error(
            f"Delete server failed for '{server}': API/Connection Error - {err}"
        )
        raise HomeAssistantError(f"Delete server failed: {err}") from err
    except Exception as err:
        _LOGGER.exception(
            f"Delete server failed for '{server}': Unexpected error - {err}"
        )
        if not isinstance(err, HomeAssistantError):
            raise HomeAssistantError(
                f"Delete server failed: Unexpected error - {err}"
            ) from err
        raise
    return device_removed


async def _async_handle_add_to_allowlist(
    api: BedrockServerManagerApi, server: str, players: List[str], ignore_limit: bool
):
    await _base_api_call_handler(
        api.async_add_server_allowlist(
            server_name=server, players=players, ignores_player_limit=ignore_limit
        ),
        "Add to allowlist failed",
        server,
    )


async def _async_handle_remove_from_allowlist(
    api: BedrockServerManagerApi, server: str, player_name: str
):
    await _base_api_call_handler(
        api.async_remove_server_allowlist_player(
            server_name=server, player_name=player_name
        ),
        "Remove from allowlist failed",
        server,
    )


async def _async_handle_set_permissions(
    api: BedrockServerManagerApi, server: str, permissions_dict: Dict[str, str]
):
    await _base_api_call_handler(
        api.async_set_server_permissions(
            server_name=server, permissions_dict=permissions_dict
        ),
        "Set permissions failed",
        server,
    )


async def _async_handle_update_properties(
    api: BedrockServerManagerApi, server: str, properties_dict: Dict[str, Any]
):
    await _base_api_call_handler(
        api.async_update_server_properties(
            server_name=server, properties_dict=properties_dict
        ),
        "Update properties failed",
        server,
    )


async def _async_handle_install_world(
    api: BedrockServerManagerApi, server: str, filename: str
):
    await _base_api_call_handler(
        api.async_install_server_world(server_name=server, filename=filename),
        "Install world failed",
        server,
    )


async def _async_handle_install_addon(
    api: BedrockServerManagerApi, server: str, filename: str
):
    await _base_api_call_handler(
        api.async_install_server_addon(server_name=server, filename=filename),
        "Install addon failed",
        server,
    )


async def _async_handle_configure_os_service(
    api: BedrockServerManagerApi, server: str, payload: Dict[str, bool]
):
    await _base_api_call_handler(
        api.async_configure_server_os_service(server_name=server, payload=payload),
        "Configure OS service failed",
        server,
    )


async def _async_handle_add_global_players(
    api: BedrockServerManagerApi, players_data: List[str]
):
    await _base_api_call_handler(
        api.async_add_players(players_data=players_data), "Add global players failed"
    )


# --- Main Service Handlers ---
async def _resolve_server_targets(
    service: ServiceCall, hass: HomeAssistant
) -> Dict[str, str]:
    """Resolves service targets to a dict of {config_entry_id: server_name}."""
    servers_to_target: Dict[str, str] = {}
    entity_registry_instance = er.async_get(hass)
    device_registry_instance = dr.async_get(hass)

    target_entity_ids = service.data.get(ATTR_ENTITY_ID, [])
    target_device_ids = service.data.get(ATTR_DEVICE_ID, [])

    if isinstance(target_entity_ids, str):
        target_entity_ids = [target_entity_ids]
    if isinstance(target_device_ids, str):
        target_device_ids = [target_device_ids]

    # Resolve Entities
    for entity_id_str in target_entity_ids:
        entity_entry = entity_registry_instance.async_get(entity_id_str)
        if (
            entity_entry
            and entity_entry.platform == DOMAIN
            and entity_entry.config_entry_id
        ):
            # Assuming unique_id format: DOMAIN_server-name_entitykey
            parts = entity_entry.unique_id.split("_", 2)  # Split max 2 times
            if len(parts) == 3 and parts[0] == DOMAIN:
                server_name = parts[1]  # Middle part is server name
                if entity_entry.config_entry_id not in servers_to_target:
                    servers_to_target[entity_entry.config_entry_id] = server_name
                elif servers_to_target[entity_entry.config_entry_id] != server_name:
                    _LOGGER.warning(
                        "Config entry %s targeted via entities with different server names ('%s' vs '%s'). Using first found.",
                        entity_entry.config_entry_id,
                        servers_to_target[entity_entry.config_entry_id],
                        server_name,
                    )
            else:
                _LOGGER.warning(
                    "Could not determine server name from unique ID '%s' for entity %s",
                    entity_entry.unique_id,
                    entity_id_str,
                )

    # Resolve Devices
    for device_id_str in target_device_ids:
        device_entry = device_registry_instance.async_get(device_id_str)
        if device_entry:
            our_entry_id = None
            for entry_id_for_dev in device_entry.config_entries:
                config_entry = hass.config_entries.async_get_entry(entry_id_for_dev)
                if config_entry and config_entry.domain == DOMAIN:
                    our_entry_id = entry_id_for_dev
                    break
            if our_entry_id:
                server_name_from_dev = None
                for (
                    identifier
                ) in device_entry.identifiers:  # identifiers is a set of tuples
                    if (
                        len(identifier) == 2
                        and identifier[0] == DOMAIN
                        and ":" not in identifier[1]
                    ):  # Avoid manager device
                        server_name_from_dev = identifier[1]
                        break
                if server_name_from_dev:
                    if our_entry_id not in servers_to_target:
                        servers_to_target[our_entry_id] = server_name_from_dev
                    elif servers_to_target[our_entry_id] != server_name_from_dev:
                        _LOGGER.warning(
                            "Config entry %s targeted via device/entity with different server names ('%s' vs '%s'). Using first.",
                            our_entry_id,
                            servers_to_target[our_entry_id],
                            server_name_from_dev,
                        )
                else:
                    _LOGGER.debug(
                        "Targeted device %s is likely manager or has unexpected identifiers.",
                        device_id_str,
                    )

    if not servers_to_target:
        _LOGGER.error(
            "Service call for '%s.%s' did not resolve to any valid server targets.",
            service.domain,
            service.service,
        )
        raise HomeAssistantError(
            f"Service {service.domain}.{service.service} requires targeting specific server devices or entities from the {DOMAIN} integration."
        )
    return servers_to_target


async def _execute_targeted_service(
    service_call: ServiceCall, hass: HomeAssistant, handler_coro, *handler_args
):
    """Generic executor for services that target servers."""
    resolved_targets = await _resolve_server_targets(service_call, hass)
    tasks = []
    for config_entry_id, target_server_name in resolved_targets.items():
        if config_entry_id not in hass.data.get(DOMAIN, {}):
            _LOGGER.warning(
                "Config entry %s for server %s not loaded. Skipping.",
                config_entry_id,
                target_server_name,
            )
            continue
        try:
            api_client: BedrockServerManagerApi = hass.data[DOMAIN][config_entry_id][
                "api"
            ]
            # Prepend api_client and target_server_name to the handler_args
            full_handler_args = (api_client, target_server_name) + handler_args
            tasks.append(handler_coro(*full_handler_args))
        except KeyError as e:
            _LOGGER.error(
                "Missing 'api' for config entry %s. Service call for %s failed. Error: %s",
                config_entry_id,
                target_server_name,
                e,
            )
        except Exception as e:  # Catch any other error during task creation
            _LOGGER.exception(
                "Error queueing service call for server %s: %s", target_server_name, e
            )

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):  # Basic error logging from gather
            if isinstance(result, Exception):
                # More context could be added here if needed (e.g., which server failed)
                _LOGGER.error(
                    "An error occurred executing a batched service call: %s", result
                )
    elif not resolved_targets:  # Should be caught by _resolve_server_targets
        _LOGGER.error(
            "Service %s.%s did not resolve any targets.",
            service_call.domain,
            service_call.service,
        )


# --- Main Service Handlers ---
async def async_handle_send_command_service(service: ServiceCall, hass: HomeAssistant):
    command_to_send = service.data[FIELD_COMMAND]
    await _execute_targeted_service(
        service, hass, _async_handle_send_command, command_to_send
    )


async def async_handle_prune_downloads_service(
    service: ServiceCall, hass: HomeAssistant
):
    directory = service.data[FIELD_DIRECTORY]
    keep = service.data.get(FIELD_KEEP)
    api_client: Optional[BedrockServerManagerApi] = None
    if hass.data.get(DOMAIN):
        first_entry_id = next(iter(hass.data[DOMAIN]), None)
        if first_entry_id and hass.data[DOMAIN][first_entry_id].get("api"):
            api_client = hass.data[DOMAIN][first_entry_id]["api"]
        else:
            raise HomeAssistantError("BSM API client missing.")
    else:
        raise HomeAssistantError("BSM integration not loaded.")
    await _async_handle_prune_downloads(api=api_client, directory=directory, keep=keep)


async def async_handle_trigger_backup_service(
    service: ServiceCall, hass: HomeAssistant
):
    backup_type = service.data[FIELD_BACKUP_TYPE]
    file_to_backup = service.data.get(FIELD_FILE_TO_BACKUP)
    if backup_type == "config" and not file_to_backup:
        raise vol.Invalid(f"'{FIELD_FILE_TO_BACKUP}' required for 'config' backup.")
    await _execute_targeted_service(
        service, hass, _async_handle_trigger_backup, backup_type, file_to_backup
    )


async def async_handle_restore_backup_service(
    service: ServiceCall, hass: HomeAssistant
):
    restore_type = service.data[FIELD_RESTORE_TYPE]
    backup_file = service.data[FIELD_BACKUP_FILE]
    await _execute_targeted_service(
        service, hass, _async_handle_restore_backup, restore_type, backup_file
    )


async def async_handle_restore_latest_all_service(
    service: ServiceCall, hass: HomeAssistant
):
    await _execute_targeted_service(service, hass, _async_handle_restore_latest_all)


async def async_handle_install_server_service(
    service: ServiceCall, hass: HomeAssistant
):
    sname = service.data[FIELD_SERVER_NAME]
    sversion = service.data[FIELD_SERVER_VERSION]
    overwrite = service.data[FIELD_OVERWRITE]
    api_client: Optional[BedrockServerManagerApi] = None
    if hass.data.get(DOMAIN):
        fid = next(iter(hass.data[DOMAIN]), None)
        if fid and hass.data[DOMAIN][fid].get("api"):
            api_client = hass.data[DOMAIN][fid]["api"]
        else:
            raise HomeAssistantError("BSM API client missing.")
    else:
        raise HomeAssistantError("BSM not loaded.")
    await _async_handle_install_server(
        api=api_client, server_name=sname, server_version=sversion, overwrite=overwrite
    )


async def async_handle_delete_server_service(service: ServiceCall, hass: HomeAssistant):
    _LOGGER.warning("Executing delete_server service. CONFIRMATION PROVIDED!")
    resolved_targets = await _resolve_server_targets(service, hass)
    tasks = []
    for cid, sname in resolved_targets.items():
        if cid not in hass.data.get(DOMAIN, {}):
            continue
        try:
            tasks.append(
                _async_handle_delete_server(
                    hass, hass.data[DOMAIN][cid]["api"], sname, cid
                )
            )
        except Exception as e:
            _LOGGER.exception("Error queueing delete_server for %s: %s", sname, e)
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        removed, failed_api = [], []
        for i, res in enumerate(results):
            sname_proc = resolved_targets.get(
                list(resolved_targets.keys())[i], "unknown"
            )
            if isinstance(res, Exception):
                failed_api.append(sname_proc)
            elif res is True:
                removed.append(sname_proc)
        msg_parts = []
        if removed:
            msg_parts.append(f"Removed from HA: {', '.join(removed)}.")
        if failed_api:
            msg_parts.append(f"Failed API delete: {', '.join(failed_api)}.")
        if not msg_parts:
            msg_parts.append("Deletion status unclear.")
        hass.components.persistent_notification.async_create(
            " ".join(msg_parts),
            title="BSM Deletion Results",
            notification_id=f"bsm_delete_{service.context.id}",
        )


async def async_handle_add_to_allowlist_service(
    service: ServiceCall, hass: HomeAssistant
):
    players = service.data[FIELD_PLAYERS]
    ignore_limit = service.data[FIELD_IGNORE_PLAYER_LIMIT]
    await _execute_targeted_service(
        service, hass, _async_handle_add_to_allowlist, players, ignore_limit
    )


async def async_handle_remove_from_allowlist_service(
    service: ServiceCall, hass: HomeAssistant
):
    player_name = service.data[FIELD_PLAYER_NAME]
    await _execute_targeted_service(
        service, hass, _async_handle_remove_from_allowlist, player_name
    )


async def async_handle_set_permissions_service(
    service: ServiceCall, hass: HomeAssistant
):
    permissions_dict = service.data[FIELD_PERMISSIONS]
    await _execute_targeted_service(
        service, hass, _async_handle_set_permissions, permissions_dict
    )


async def async_handle_update_properties_service(
    service: ServiceCall, hass: HomeAssistant
):
    properties_dict = service.data[FIELD_PROPERTIES]
    await _execute_targeted_service(
        service, hass, _async_handle_update_properties, properties_dict
    )


async def async_handle_install_world_service(service: ServiceCall, hass: HomeAssistant):
    filename = service.data[FIELD_FILENAME]
    await _execute_targeted_service(
        service, hass, _async_handle_install_world, filename
    )


async def async_handle_install_addon_service(service: ServiceCall, hass: HomeAssistant):
    filename = service.data[FIELD_FILENAME]
    await _execute_targeted_service(
        service, hass, _async_handle_install_addon, filename
    )


async def async_handle_configure_os_service_service(
    service: ServiceCall, hass: HomeAssistant
):
    autoupdate_val = service.data[FIELD_AUTOUPDATE]
    autostart_val = service.data.get(FIELD_AUTOSTART)
    resolved_targets = await _resolve_server_targets(service, hass)
    tasks = []
    for cid, sname in resolved_targets.items():
        if cid not in hass.data.get(DOMAIN, {}):
            continue
        try:
            entry_data = hass.data[DOMAIN][cid]
            payload: Dict[str, bool] = {"autoupdate": autoupdate_val}
            if (
                entry_data.get("manager_os_type", "unknown").lower() == "linux"
                and autostart_val is not None
            ):
                payload["autostart"] = autostart_val
            tasks.append(
                _async_handle_configure_os_service(entry_data["api"], sname, payload)
            )
        except Exception as e:
            _LOGGER.exception(
                "Error queueing configure_os_service for %s: %s", sname, e
            )
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def async_handle_add_global_players_service(
    service: ServiceCall, hass: HomeAssistant
):
    players_data_list = service.data[FIELD_PLAYERS]
    api_client: Optional[BedrockServerManagerApi] = None
    manager_coordinator: Optional[ManagerDataCoordinator] = None
    if hass.data.get(DOMAIN):
        for eid_iter, edata_iter in hass.data[DOMAIN].items():
            if edata_iter.get("api") and edata_iter.get("manager_coordinator"):
                api_client = edata_iter["api"]
                manager_coordinator = edata_iter["manager_coordinator"]
                break
    if not api_client:
        raise HomeAssistantError("BSM API client not available.")
    await _async_handle_add_global_players(
        api=api_client, players_data=players_data_list
    )
    if manager_coordinator:
        await manager_coordinator.async_request_refresh()
    else:
        _LOGGER.warning("ManagerDataCoordinator not found. Sensor may not update.")


# --- Service Registration/Removal (Unchanged logic) ---
async def async_register_services(hass: HomeAssistant):
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
    }
    for service_name, (handler, schema) in service_map.items():
        if not hass.services.has_service(DOMAIN, service_name):
            hass.services.async_register(DOMAIN, service_name, handler, schema=schema)


async def async_remove_services(hass: HomeAssistant):
    if not hass.data.get(DOMAIN):
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
        ]
        for service_name in services_to_remove:
            if hass.services.has_service(DOMAIN, service_name):
                hass.services.async_remove(DOMAIN, service_name)
