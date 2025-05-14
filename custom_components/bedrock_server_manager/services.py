# custom_components/bedrock_server_manager/services.py
"""Service handlers for the Bedrock Server Manager integration."""

import asyncio
import logging
from typing import cast, Dict, Optional, List, Any, Set

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.components.persistent_notification import async_create
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


from pybedrock_server_manager import (
    BedrockServerManagerApi,
    APIError,
    AuthError,
    CannotConnectError,
    ServerNotRunningError,
)


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
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
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
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
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
    {
        vol.Required(FIELD_PLAYERS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
    }
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
        return response
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
    except ValueError as err:
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
        "Prune downloads failed",  # No server name here, it's a manager-level op
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
    # This function already has its own error handling, not using _base_api_call_handler
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
            "Successfully requested install for server '%s' (Version: %s, Overwrite: %s) on manager. API Message: %s",
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
    except Exception as err:
        _LOGGER.exception(
            f"Install server failed for '{server_name}': Unexpected problem - {err}"
        )
        if not isinstance(err, HomeAssistantError):
            raise HomeAssistantError(
                f"Install server failed: Unexpected error - {err}"
            ) from err
        raise


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
        api.async_add_players(players_data=players_data),
        "Add global players failed",
        # No server name here, it's a manager-level op
    )


# --- Target Resolvers and Executors ---


async def _resolve_server_targets(
    service: ServiceCall, hass: HomeAssistant
) -> Dict[str, str]:
    """Resolves service targets to a dict of {config_entry_id: server_name}."""
    servers_to_target: Dict[str, str] = {}
    entity_registry_instance = er.async_get(hass)
    device_registry_instance = dr.async_get(hass)

    target_entity_ids = service.data.get(ATTR_ENTITY_ID, [])
    target_device_ids = service.data.get(ATTR_DEVICE_ID, [])
    target_area_ids = service.data.get(ATTR_AREA_ID, [])

    if isinstance(target_entity_ids, str):
        target_entity_ids = [target_entity_ids]
    if isinstance(target_device_ids, str):
        target_device_ids = [target_device_ids]
    if isinstance(target_area_ids, str):
        target_area_ids = [target_area_ids]

    # --- Resolve Entities ---
    for entity_id_str in target_entity_ids:
        entity_entry = entity_registry_instance.async_get(entity_id_str)
        if (
            entity_entry
            and entity_entry.platform == DOMAIN
            and entity_entry.config_entry_id
            # Ensure the entity's device is a server device, not the manager device
            # Entity unique ID typically: DOMAIN_managerhost:port_servername_entitykey
        ):
            # Assuming unique_id format for server entities: DOMAIN_managerid_servername_entitykey
            # or if managerid part isn't in unique_id, rely on device info.
            # A safer bet is to get the device of the entity and check its identifiers.
            if entity_entry.device_id:
                device_of_entity = device_registry_instance.async_get(
                    entity_entry.device_id
                )
                if device_of_entity:
                    # Check if this device_of_entity is a server device
                    manager_id_from_entry = hass.data[DOMAIN][
                        entity_entry.config_entry_id
                    ]["manager_identifier"][1]
                    server_name_from_entity_device = None
                    for identifier in device_of_entity.identifiers:
                        if identifier[0] == DOMAIN and identifier[1].startswith(
                            manager_id_from_entry + "_"
                        ):
                            server_name_from_entity_device = identifier[1].split(
                                "_", 1
                            )[1]
                            break
                    if server_name_from_entity_device:
                        if entity_entry.config_entry_id not in servers_to_target:
                            servers_to_target[entity_entry.config_entry_id] = (
                                server_name_from_entity_device
                            )
                        elif (
                            servers_to_target[entity_entry.config_entry_id]
                            != server_name_from_entity_device
                        ):
                            _LOGGER.warning(
                                "Config entry %s targeted via entities with different server names ('%s' vs '%s'). Using first.",
                                entity_entry.config_entry_id,
                                servers_to_target[entity_entry.config_entry_id],
                                server_name_from_entity_device,
                            )
                    else:
                        _LOGGER.debug(
                            "Entity %s is linked to device %s which is not a recognized server device for this manager.",
                            entity_id_str,
                            entity_entry.device_id,
                        )
            else:  # Fallback to parsing entity unique_id if no device_id (less robust)
                parts = entity_entry.unique_id.split("_", 2)
                if (
                    len(parts) == 3
                    and parts[0] == DOMAIN
                    and ":" in parts[1]
                    and "_" in parts[1]
                ):  # basic check for manager_server format
                    # This parsing is fragile. Example: DOMAIN_host:port_servername_sensor
                    manager_and_server_part = parts[1]
                    # We need to ensure manager_and_server_part corresponds to the current config entry's manager
                    config_entry_manager_id = hass.data[DOMAIN][
                        entity_entry.config_entry_id
                    ]["manager_identifier"][1]
                    if manager_and_server_part.startswith(
                        config_entry_manager_id + "_"
                    ):
                        server_name = manager_and_server_part.split("_", 1)[1]
                        if entity_entry.config_entry_id not in servers_to_target:
                            servers_to_target[entity_entry.config_entry_id] = (
                                server_name
                            )
                        # ... (conflict warning) ...
                else:
                    _LOGGER.warning(
                        "Could not reliably determine server name from unique ID '%s' for entity %s",
                        entity_entry.unique_id,
                        entity_id_str,
                    )

    # --- Resolve Devices ---
    for device_id_str in target_device_ids:
        device_entry = device_registry_instance.async_get(device_id_str)
        if device_entry:
            our_entry_id = None
            # Find which of our config entries this device belongs to
            for entry_id_for_dev in device_entry.config_entries:
                if entry_id_for_dev in hass.data.get(
                    DOMAIN, {}
                ):  # Check if it's one of ours and loaded
                    our_entry_id = entry_id_for_dev
                    break

            if our_entry_id:
                server_name_from_dev = None
                # Get the manager_id for this specific config entry
                # This is crucial for correctly parsing server device identifiers
                manager_id_for_this_config_entry = hass.data[DOMAIN][our_entry_id][
                    "manager_identifier"
                ][1]

                for identifier in device_entry.identifiers:
                    if identifier[0] == DOMAIN:
                        # Expected server device identifier value: f"{manager_id_for_this_config_entry}_{actual_server_name}"
                        if identifier[1].startswith(
                            manager_id_for_this_config_entry + "_"
                        ):
                            try:
                                server_name_from_dev = identifier[1].split("_", 1)[
                                    1
                                ]  # Get part after first underscore
                                _LOGGER.debug(
                                    "Resolved server device: ID Value '%s', Extracted Server Name: '%s'",
                                    identifier[1],
                                    server_name_from_dev,
                                )
                                break
                            except IndexError:  # Should not happen if format is correct
                                _LOGGER.warning(
                                    "Malformed server device identifier for parsing: %s",
                                    identifier[1],
                                )

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
                        "Targeted device %s (identifiers: %s) is not a recognized BSM server device for manager %s, or is the manager device itself.",
                        device_id_str,
                        device_entry.identifiers,
                        manager_id_for_this_config_entry,
                    )
            else:
                _LOGGER.debug(
                    "Targeted device %s is not associated with any loaded %s config entry.",
                    device_id_str,
                    DOMAIN,
                )

    # --- Resolve Areas ---
    if target_area_ids:
        all_devices_in_ha = list(device_registry_instance.devices.values())
        for area_id_str in target_area_ids:
            for device_entry_from_area in all_devices_in_ha:
                if device_entry_from_area.area_id == area_id_str:
                    # Now, process this device_entry_from_area like in the ATTR_DEVICE_ID section
                    our_entry_id_area = None
                    for entry_id_for_dev_area in device_entry_from_area.config_entries:
                        if entry_id_for_dev_area in hass.data.get(DOMAIN, {}):
                            our_entry_id_area = entry_id_for_dev_area
                            break
                    if our_entry_id_area:
                        server_name_from_area_dev = None
                        manager_id_for_area_config_entry = hass.data[DOMAIN][
                            our_entry_id_area
                        ]["manager_identifier"][1]
                        for identifier in device_entry_from_area.identifiers:
                            if identifier[0] == DOMAIN and identifier[1].startswith(
                                manager_id_for_area_config_entry + "_"
                            ):
                                try:
                                    server_name_from_area_dev = identifier[1].split(
                                        "_", 1
                                    )[1]
                                    break
                                except IndexError:
                                    _LOGGER.warning(
                                        "Malformed server device identifier from area device: %s",
                                        identifier[1],
                                    )

                        if server_name_from_area_dev:
                            if our_entry_id_area not in servers_to_target:
                                servers_to_target[our_entry_id_area] = (
                                    server_name_from_area_dev
                                )
                            elif (
                                servers_to_target[our_entry_id_area]
                                != server_name_from_area_dev
                            ):
                                _LOGGER.warning(
                                    "Config entry %s targeted via area/device/entity with different server names ('%s' vs '%s'). Using first.",
                                    our_entry_id_area,
                                    servers_to_target[our_entry_id_area],
                                    server_name_from_area_dev,
                                )

    if not servers_to_target:
        _LOGGER.error(
            "Service call for '%s.%s' with targets %s, %s, %s did not resolve to any valid BSM server sub-devices.",
            service.domain,
            service.service,
            target_entity_ids,
            target_device_ids,
            target_area_ids,
        )
        # Provide more specific error based on what was targeted
        error_message = f"Service {service.domain}.{service.service} requires targeting specific BSM server devices or entities."
        if not any([target_entity_ids, target_device_ids, target_area_ids]):
            error_message = f"Service {service.domain}.{service.service} requires a target (device, entity, or area) but none was provided."

        raise HomeAssistantError(error_message)

    _LOGGER.debug(
        "Resolved targets for service %s.%s: %s",
        service.domain,
        service.service,
        servers_to_target,
    )
    return servers_to_target


async def _resolve_manager_instance_targets(
    service: ServiceCall, hass: HomeAssistant
) -> List[str]:
    """Resolves service targets to a list of config_entry_ids for BSM manager instances."""
    config_entry_ids_to_target: Set[str] = set()
    entity_registry_instance = er.async_get(hass)
    device_registry_instance = dr.async_get(hass)

    target_entity_ids = service.data.get(ATTR_ENTITY_ID, [])
    target_device_ids = service.data.get(ATTR_DEVICE_ID, [])
    target_area_ids = service.data.get(ATTR_AREA_ID, [])

    if isinstance(target_entity_ids, str):
        target_entity_ids = [target_entity_ids]
    if isinstance(target_device_ids, str):
        target_device_ids = [target_device_ids]
    if isinstance(target_area_ids, str):
        target_area_ids = [target_area_ids]

    # Resolve Entities
    for entity_id_str in target_entity_ids:
        entity_entry = entity_registry_instance.async_get(entity_id_str)
        if (
            entity_entry
            and entity_entry.domain == DOMAIN
            and entity_entry.config_entry_id
        ):
            config_entry_ids_to_target.add(entity_entry.config_entry_id)

    # Resolve Devices
    for device_id_str in target_device_ids:
        device_entry = device_registry_instance.async_get(device_id_str)
        if device_entry:
            for entry_id_for_dev in device_entry.config_entries:
                config_entry = hass.config_entries.async_get_entry(entry_id_for_dev)
                if config_entry and config_entry.domain == DOMAIN:
                    config_entry_ids_to_target.add(entry_id_for_dev)

    # Resolve Areas
    if target_area_ids:
        all_devices_in_ha = list(device_registry_instance.devices.values())
        for area_id_str in target_area_ids:
            for device_entry in all_devices_in_ha:
                if device_entry.area_id == area_id_str:
                    for entry_id_for_dev in device_entry.config_entries:
                        config_entry = hass.config_entries.async_get_entry(
                            entry_id_for_dev
                        )
                        if config_entry and config_entry.domain == DOMAIN:
                            config_entry_ids_to_target.add(entry_id_for_dev)

    if not config_entry_ids_to_target:
        has_target_specifiers = bool(
            service.data.get(ATTR_ENTITY_ID)
            or service.data.get(ATTR_DEVICE_ID)
            or service.data.get(ATTR_AREA_ID)
        )
        if has_target_specifiers:
            _LOGGER.error(
                "Service call for '%s.%s' provided targets, but none resolved to a valid BSM manager instance.",
                service.domain,
                service.service,
            )
            raise HomeAssistantError(
                f"Service {service.domain}.{service.service} targets did not match any BSM manager instances."
            )
        else:
            _LOGGER.error(
                "Service call for '%s.%s' requires explicit targeting of a BSM manager instance "
                "(via device, entity, or area) but no targets were provided.",
                service.domain,
                service.service,
            )
            raise HomeAssistantError(
                f"Service {service.domain}.{service.service} requires targeting a BSM manager instance. "
                "Please specify a target device, entity, or area."
            )

    return list(config_entry_ids_to_target)


async def _execute_targeted_service(
    service_call: ServiceCall, hass: HomeAssistant, handler_coro, *handler_args
):
    """Generic executor for services that target specific servers."""
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
            full_handler_args = (api_client, target_server_name) + handler_args
            tasks.append(handler_coro(*full_handler_args))
        except KeyError as e:
            _LOGGER.error(
                "Missing 'api' for config entry %s. Service call for %s failed. Error: %s",
                config_entry_id,
                target_server_name,
                e,
            )
        except Exception as e:
            _LOGGER.exception(
                "Error queueing service call for server %s: %s", target_server_name, e
            )

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_target_server_name = list(resolved_targets.values())[i]
                _LOGGER.error(
                    "An error occurred executing service for server '%s': %s",
                    failed_target_server_name,
                    result,
                )
    elif not resolved_targets:
        _LOGGER.error(
            "Service %s.%s did not resolve any targets.",
            service_call.domain,
            service_call.service,
        )


async def _execute_manager_targeted_service(
    service_call: ServiceCall, hass: HomeAssistant, handler_coro, *handler_args
):
    """Generic executor for services that target BSM manager instances."""
    resolved_config_entry_ids = await _resolve_manager_instance_targets(
        service_call, hass
    )
    tasks = []
    coordinators_to_refresh: List[ManagerDataCoordinator] = []

    for config_entry_id in resolved_config_entry_ids:
        if config_entry_id not in hass.data.get(DOMAIN, {}):
            _LOGGER.warning(
                "Config entry %s not loaded. Skipping manager-targeted service.",
                config_entry_id,
            )
            continue
        try:
            entry_data = hass.data[DOMAIN][config_entry_id]
            api_client: BedrockServerManagerApi = entry_data["api"]
            full_handler_args = (api_client,) + handler_args
            tasks.append(handler_coro(*full_handler_args))

            if "manager_coordinator" in entry_data:
                coordinator_instance = entry_data["manager_coordinator"]
                if handler_coro.__name__ == "_async_handle_add_global_players":
                    if coordinator_instance not in coordinators_to_refresh:
                        coordinators_to_refresh.append(coordinator_instance)
        except KeyError as e:
            _LOGGER.error(
                "Missing 'api' or other required data for config entry %s. "
                "Manager-targeted service call failed. Error: %s",
                config_entry_id,
                e,
            )
        except Exception as e:
            _LOGGER.exception(
                "Error queueing manager-targeted service call for config entry %s: %s",
                config_entry_id,
                e,
            )

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_config_entry_id = resolved_config_entry_ids[i]
                _LOGGER.error(
                    "An error occurred executing manager-targeted service for config_entry_id '%s': %s",
                    failed_config_entry_id,
                    result,
                )

        refreshed_coordinator_ce_ids: Set[str] = set()
        for coordinator in coordinators_to_refresh:
            ce_id = (
                coordinator.config_entry.entry_id if coordinator.config_entry else None
            )
            if ce_id and ce_id in refreshed_coordinator_ce_ids:
                continue

            _LOGGER.debug(
                "Requesting refresh of ManagerDataCoordinator for config entry ID '%s' after manager-targeted service.",
                ce_id or "Unknown CE ID",
            )
            await coordinator.async_request_refresh()
            if ce_id:
                refreshed_coordinator_ce_ids.add(ce_id)

    elif not resolved_config_entry_ids:
        _LOGGER.error(
            "Manager-targeted service %s.%s did not resolve any targets.",
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
    await _execute_manager_targeted_service(
        service, hass, _async_handle_prune_downloads, directory, keep
    )


async def async_handle_trigger_backup_service(
    service: ServiceCall, hass: HomeAssistant
):
    backup_type = service.data[FIELD_BACKUP_TYPE]
    file_to_backup = service.data.get(FIELD_FILE_TO_BACKUP)
    if backup_type == "config" and not file_to_backup:
        raise vol.Invalid(
            f"'{FIELD_FILE_TO_BACKUP}' required for 'config' backup type."
        )
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
    await _execute_manager_targeted_service(
        service, hass, _async_handle_install_server, sname, sversion, overwrite
    )


async def async_handle_delete_server_service(service: ServiceCall, hass: HomeAssistant):
    _LOGGER.warning(
        "Executing delete_server service. CONFIRMATION PROVIDED VIA SCHEMA!"
    )
    resolved_targets = await _resolve_server_targets(service, hass)
    tasks = []
    target_info_list = []

    for cid, sname in resolved_targets.items():
        if cid not in hass.data.get(DOMAIN, {}):
            _LOGGER.warning(
                f"Config entry {cid} for server {sname} not loaded. Skipping delete."
            )
            continue
        try:
            api_client = hass.data[DOMAIN][cid]["api"]
            tasks.append(_async_handle_delete_server(hass, api_client, sname, cid))
            target_info_list.append({"cid": cid, "sname": sname})
        except Exception as e:
            _LOGGER.exception("Error queueing delete_server for %s: %s", sname, e)

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        removed_from_ha, api_delete_failed = [], []
        for i, res in enumerate(results):
            sname_proc = target_info_list[i]["sname"]
            if isinstance(res, Exception):
                api_delete_failed.append(sname_proc)
                _LOGGER.error(
                    f"Error during delete_server API call for '{sname_proc}': {res}"
                )
            elif res is True:
                removed_from_ha.append(sname_proc)

        msg_parts = []
        if removed_from_ha:
            msg_parts.append(
                f"Successfully removed from Home Assistant: {', '.join(removed_from_ha)}."
            )
        if api_delete_failed:
            msg_parts.append(
                f"Failed API deletion or subsequent HA removal for: {', '.join(api_delete_failed)}."
            )
        if not msg_parts and resolved_targets:
            msg_parts.append(
                "Deletion attempted, but status unclear. Check logs for details."
            )
        elif not resolved_targets:  # Should be caught by resolver, but defensive.
            msg_parts.append("No servers targeted for deletion.")

        if msg_parts:
            async_create(
                hass=hass,
                message=" ".join(msg_parts),
                title="Minecraft Server Deletion Results",
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
            _LOGGER.warning(
                f"Config entry {cid} for server {sname} not loaded for OS service config. Skipping."
            )
            continue
        try:
            entry_data = hass.data[DOMAIN][cid]
            api_client = entry_data["api"]
            payload: Dict[str, bool] = {"autoupdate": autoupdate_val}
            manager_os_type = entry_data.get("manager_os_type", "unknown").lower()
            if autostart_val is not None:
                if manager_os_type == "linux":
                    payload["autostart"] = autostart_val
                else:
                    _LOGGER.warning(
                        "Autostart configuration is only supported for Linux-based managers. "
                        f"Server '{sname}' manager OS type is '{manager_os_type}'. Ignoring autostart."
                    )
            elif manager_os_type == "linux" and FIELD_AUTOSTART not in service.data:
                _LOGGER.debug(
                    f"Field '{FIELD_AUTOSTART}' not provided for Linux server '{sname}'. Autostart setting will not be changed."
                )
            tasks.append(_async_handle_configure_os_service(api_client, sname, payload))
        except KeyError as e:
            _LOGGER.error(
                f"Missing data for config entry {cid} (server {sname}) for OS service config: {e}"
            )
        except Exception as e:
            _LOGGER.exception(
                "Error queueing configure_os_service for %s: %s", sname, e
            )
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                sname_failed = list(resolved_targets.values())[i]
                _LOGGER.error(
                    f"Error configuring OS service for server '{sname_failed}': {result}"
                )


async def async_handle_add_global_players_service(
    service: ServiceCall, hass: HomeAssistant
):
    players_data_list = service.data[FIELD_PLAYERS]
    await _execute_manager_targeted_service(
        service, hass, _async_handle_add_global_players, players_data_list
    )


# --- Service Registration/Removal ---
async def async_register_services(hass: HomeAssistant):
    """Register services with Home Assistant."""
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
    for service_name, (handler_func_from_map, schema) in service_map.items():
        if not hass.services.has_service(DOMAIN, service_name):

            async def service_wrapper(
                call: ServiceCall, _handler_to_call=handler_func_from_map
            ):
                _LOGGER.debug(
                    "Service wrapper executing for service call to '%s', "
                    "using actual handler: %s",
                    call.service,
                    _handler_to_call.__name__,
                )
                await _handler_to_call(call, hass)

            hass.services.async_register(
                DOMAIN, service_name, service_wrapper, schema=schema
            )


async def async_remove_services(hass: HomeAssistant):
    """Remove services from Home Assistant."""
    if not hass.data.get(DOMAIN) or not any(hass.data[DOMAIN].values()):
        _LOGGER.info(
            "Removing Bedrock Server Manager services as no configurations are loaded."
        )
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
                _LOGGER.debug(f"Removing service: {DOMAIN}.{service_name}")
                hass.services.async_remove(DOMAIN, service_name)
    else:
        _LOGGER.debug(
            "Bedrock Server Manager services not removed as configurations are still loaded."
        )
