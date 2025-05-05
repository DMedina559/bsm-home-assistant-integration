"""Service handlers for the Bedrock Server Manager integration."""

import asyncio
import logging
from typing import cast, Dict, Optional

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr

from .const import (
    DOMAIN,
    SERVICE_SEND_COMMAND,
    SERVICE_PRUNE_DOWNLOADS,
    SERVICE_RESTORE_BACKUP,
    SERVICE_TRIGGER_BACKUP,
    SERVICE_RESTORE_LATEST_ALL,
    SERVICE_INSTALL_SERVER,
    SERVICE_DELETE_SERVER,
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
)
from .api import (
    BedrockServerManagerApi,
    APIError,
    ServerNotRunningError,
)

_LOGGER = logging.getLogger(__name__)

# --- Service Schema Definition ---
SEND_COMMAND_SERVICE_SCHEMA = vol.Schema(
    {
        # Keep the required command field
        vol.Required(FIELD_COMMAND): vol.All(vol.Coerce(str), vol.Length(min=1)),
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
    }
)

PRUNE_DOWNLOADS_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_DIRECTORY): str,
        vol.Optional(FIELD_KEEP): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)

TRIGGER_BACKUP_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_BACKUP_TYPE): vol.In(
            ["all", "world", "config"]
        ),  # Validate type
        vol.Optional(
            FIELD_FILE_TO_BACKUP
        ): str,  # String, required only if type is config (API validates)
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
    }
)

RESTORE_BACKUP_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_RESTORE_TYPE): vol.In(["world", "config"]),
        vol.Required(FIELD_BACKUP_FILE): str,
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
        vol.Required(FIELD_SERVER_NAME): str,
        vol.Required(FIELD_SERVER_VERSION): str,
        vol.Optional(FIELD_OVERWRITE, default=False): bool,
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


# --- Service Handler Helper Function ---
async def _async_handle_send_command(
    api: BedrockServerManagerApi, server: str, command: str
):
    """Helper coroutine to call API and handle errors for send_command."""
    try:
        await api.async_send_command(server, command)
        _LOGGER.debug("Successfully sent command '%s' to server '%s'", command, server)
    except ServerNotRunningError as err:
        _LOGGER.error("Failed to send command to '%s': %s", server, err)
        # Raise specific HA error users might catch in automations
        raise HomeAssistantError(
            f"Cannot send command to {server}: Server is not running."
        ) from err
    except APIError as err:
        _LOGGER.error("API Error sending command to '%s': %s", server, err)
        raise HomeAssistantError(
            f"API Error sending command to {server}: {err}"
        ) from err
    except Exception as err:
        _LOGGER.exception("Unexpected error sending command to '%s': %s", server, err)
        raise HomeAssistantError(
            f"Unexpected error sending command to {server}: {err}"
        ) from err


async def _async_handle_prune_downloads(
    api: BedrockServerManagerApi, directory: str, keep: Optional[int]
):
    """Helper coroutine to call API for prune_download_cache."""
    try:
        await api.async_prune_download_cache(directory=directory, keep=keep)
        _LOGGER.info(
            "Successfully requested prune download cache for directory: %s", directory
        )
    except APIError as err:
        _LOGGER.error("API Error pruning download cache for '%s': %s", directory, err)
        raise HomeAssistantError(f"API Error pruning download cache: {err}") from err
    except Exception as err:
        _LOGGER.exception(
            "Unexpected error pruning download cache for '%s': %s", directory, err
        )
        raise HomeAssistantError(
            f"Unexpected error pruning download cache: {err}"
        ) from err


async def _async_handle_trigger_backup(
    api: BedrockServerManagerApi,
    server: str,
    backup_type: str,
    file_to_backup: Optional[str],
):
    """Helper for trigger_backup service."""
    try:
        # API method already handles logic based on type
        await api.async_trigger_backup(
            server_name=server, backup_type=backup_type, file_to_backup=file_to_backup
        )
        _LOGGER.info(
            "Successfully requested '%s' backup for server '%s'", backup_type, server
        )
    except APIError as err:
        _LOGGER.error(
            "API Error triggering '%s' backup for '%s': %s", backup_type, server, err
        )
        raise HomeAssistantError(f"API Error triggering backup: {err}") from err
    except ValueError as err:  # Catch potential error from API method validation
        _LOGGER.error(
            "Invalid input for trigger_backup service for server '%s': %s", server, err
        )
        raise HomeAssistantError(f"Invalid input for backup: {err}") from err
    except Exception as err:
        _LOGGER.exception(
            "Unexpected error triggering backup for '%s': %s", server, err
        )
        raise HomeAssistantError(f"Unexpected error triggering backup: {err}") from err


async def _async_handle_restore_backup(
    api: BedrockServerManagerApi, server: str, restore_type: str, backup_file: str
):
    """Helper for restore_backup service."""
    try:
        await api.async_restore_backup(
            server_name=server, restore_type=restore_type, backup_file=backup_file
        )
        _LOGGER.info(
            "Successfully requested restore '%s' from '%s' for server '%s'",
            restore_type,
            backup_file,
            server,
        )
    except APIError as err:
        _LOGGER.error("API Error restoring backup for '%s': %s", server, err)
        raise HomeAssistantError(f"API Error restoring backup: {err}") from err
    except Exception as err:
        _LOGGER.exception("Unexpected error restoring backup for '%s': %s", server, err)
        raise HomeAssistantError(f"Unexpected error restoring backup: {err}") from err


async def _async_handle_restore_latest_all(api: BedrockServerManagerApi, server: str):
    """Helper for restore_latest_all service."""
    try:
        await api.async_restore_latest_all(server_name=server)
        _LOGGER.info(
            "Successfully requested restore latest all for server '%s'", server
        )
    except APIError as err:
        _LOGGER.error("API Error restoring latest backup for '%s': %s", server, err)
        raise HomeAssistantError(f"API Error restoring latest backup: {err}") from err
    except Exception as err:
        _LOGGER.exception(
            "Unexpected error restoring latest backup for '%s': %s", server, err
        )
        raise HomeAssistantError(
            f"Unexpected error restoring latest backup: {err}"
        ) from err


async def _async_handle_install_server(
    api: BedrockServerManagerApi, server_name: str, server_version: str, overwrite: bool
):
    """Helper coroutine to call API for install_server."""
    try:
        # Call the API method
        response = await api.async_install_server(
            server_name=server_name, server_version=server_version, overwrite=overwrite
        )

        # --- Handle specific API responses ---
        # Check if the API returned the confirmation status (which we treat as user error)
        if response.get("status") == "confirm_needed":
            _LOGGER.warning(
                "Server '%s' already exists and overwrite was false. Installation aborted by API.",
                server_name,
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

    except APIError as err:
        _LOGGER.error("API Error installing server '%s': %s", server_name, err)
        raise HomeAssistantError(f"API Error installing server: {err}") from err
    except Exception as err:
        _LOGGER.exception(
            "Unexpected error installing server '%s': %s", server_name, err
        )
        raise HomeAssistantError(f"Unexpected error installing server: {err}") from err


async def _async_handle_delete_server(api: BedrockServerManagerApi, server: str):
    """Helper coroutine to call API for delete_server."""
    # Add an extra log warning here because this is dangerous
    _LOGGER.critical("EXECUTING IRREVERSIBLE DELETE for server '%s'", server)
    try:
        await api.async_delete_server(server_name=server)
        _LOGGER.info("Successfully requested deletion of server '%s'", server)
    except APIError as err:
        _LOGGER.error("API Error deleting server '%s': %s", server, err)
        raise HomeAssistantError(f"API Error deleting server: {err}") from err
    except Exception as err:
        _LOGGER.exception("Unexpected error deleting server '%s': %s", server, err)
        raise HomeAssistantError(f"Unexpected error deleting server: {err}") from err


# --- Main Service Handlers ---


async def async_handle_prune_downloads_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the prune_download_cache service call."""
    directory = service.data[FIELD_DIRECTORY]
    keep = service.data.get(FIELD_KEEP)  # Optional

    _LOGGER.info(
        "Executing prune_download_cache service for directory: %s, keep: %s",
        directory,
        keep,
    )

    # This is a global action, we need *any* valid API client instance for this manager
    # We can't easily determine *which* entry triggered this if multiple managers are added (unlikely scenario?)
    # Let's find the first available API client for this domain.
    api_client: Optional[BedrockServerManagerApi] = None
    if hass.data.get(DOMAIN):
        # Get the first entry's data (assuming only one manager for global actions for now)
        first_entry_id = next(iter(hass.data[DOMAIN]))
        if first_entry_id and hass.data[DOMAIN][first_entry_id].get("api"):
            api_client = hass.data[DOMAIN][first_entry_id]["api"]
        else:
            _LOGGER.error(
                "Could not find a valid API client instance to execute prune_download_cache."
            )
            raise HomeAssistantError(
                "BSM integration not fully loaded or API client missing."
            )
    else:
        _LOGGER.error("BSM integration data not found.")
        raise HomeAssistantError("BSM integration not loaded.")

    # Call the helper
    await _async_handle_prune_downloads(api=api_client, directory=directory, keep=keep)


async def async_handle_send_command_service(service: ServiceCall, hass: HomeAssistant):
    """Handle the send_command service call. Maps targets to config entries."""
    # Extract the actual command data field
    try:
        command_to_send = service.data[FIELD_COMMAND]
    except KeyError:
        _LOGGER.error(
            "Internal error: '%s' key missing from service data after validation.",
            FIELD_COMMAND,
        )
        raise HomeAssistantError(f"Missing required field: {FIELD_COMMAND}")

    tasks = {}  # Stores tasks keyed by config_entry_id to avoid duplicates
    servers_to_command: Dict[str, str] = {}  # Stores {config_entry_id: server_name}

    # --- Resolve targets specified in service call ---
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)

    # Get target IDs from the service call data (HA populates these based on target selector)
    target_entity_ids = service.data.get(ATTR_ENTITY_ID, [])
    target_device_ids = service.data.get(ATTR_DEVICE_ID, [])
    # Ensure they are lists even if a single string was passed (less common now but safe)
    if isinstance(target_entity_ids, str):
        target_entity_ids = [target_entity_ids]
    if isinstance(target_device_ids, str):
        target_device_ids = [target_device_ids]

    # Resolve Entities to config_entry_id and server_name
    for entity_id in target_entity_ids:
        entity_entry = entity_reg.async_get(entity_id)
        if (
            entity_entry
            and entity_entry.platform == DOMAIN
            and entity_entry.config_entry_id
        ):
            # Extract server_name from entity's unique ID (assuming format domain_servername_key)
            parts = entity_entry.unique_id.split("_")
            # Need at least 3 parts (domain_server_key)
            if len(parts) >= 3 and parts[0] == DOMAIN:
                # Reconstruct server name if it contained underscores originally
                server_name_key = entity_entry.unique_id.replace(
                    f"{DOMAIN}_", "", 1
                ).replace(f"_{parts[-1]}", "", 1)
                server_name = server_name_key  # Simplified assumption for now

                # Check if we already found this entry via another entity/device
                if entity_entry.config_entry_id not in servers_to_command:
                    servers_to_command[entity_entry.config_entry_id] = server_name
                    _LOGGER.debug(
                        "Targeted server '%s' via entity %s", server_name, entity_id
                    )
                elif servers_to_command[entity_entry.config_entry_id] != server_name:
                    # This case should be rare - same config entry linked to entities with different inferred server names? Log warning.
                    _LOGGER.warning(
                        "Config entry %s targeted via multiple entities with different inferred server names ('%s' vs '%s'). Using first found.",
                        entity_entry.config_entry_id,
                        servers_to_command[entity_entry.config_entry_id],
                        server_name,
                    )
            else:
                _LOGGER.warning(
                    "Could not determine server name from unique ID '%s' for entity %s",
                    entity_entry.unique_id,
                    entity_id,
                )
        else:
            _LOGGER.debug(
                "Targeted entity %s not found or not part of %s domain",
                entity_id,
                DOMAIN,
            )

    # Resolve Devices to config_entry_id and server_name
    for device_id in target_device_ids:
        device_entry = device_reg.async_get(device_id)
        if device_entry:
            our_entry_id = None
            for entry_id in device_entry.config_entries:
                config_entry = hass.config_entries.async_get_entry(entry_id)
                if config_entry and config_entry.domain == DOMAIN:
                    our_entry_id = entry_id
                    break  # Found our config entry for this device

            if our_entry_id:
                # Extract server_name from device identifiers (assuming format (DOMAIN, server_name))
                server_name_from_dev = None
                for identifier in device_entry.identifiers:
                    if len(identifier) == 2 and identifier[0] == DOMAIN:
                        # Check if it's likely a server device identifier (not host:port)
                        id_value = identifier[1]
                        if (
                            ":" not in id_value
                        ):  # Basic check: server names shouldn't contain colons like host:port
                            server_name_from_dev = id_value
                            break
                if server_name_from_dev:
                    # Check if we already found this entry
                    if our_entry_id not in servers_to_command:
                        servers_to_command[our_entry_id] = server_name_from_dev
                        _LOGGER.debug(
                            "Targeted server '%s' via device %s",
                            server_name_from_dev,
                            device_id,
                        )
                    elif servers_to_command[our_entry_id] != server_name_from_dev:
                        _LOGGER.warning(
                            "Config entry %s targeted via device and entity with different inferred server names ('%s' vs '%s'). Using first found.",
                            our_entry_id,
                            servers_to_command[our_entry_id],
                            server_name_from_dev,
                        )
                else:
                    _LOGGER.warning(
                        "Targeted device %s is the manager device or has unexpected identifiers for domain %s, cannot send server command via this target.",
                        device_id,
                        DOMAIN,
                    )
            else:
                _LOGGER.debug(
                    "Targeted device %s not associated with config entry for domain %s",
                    device_id,
                    DOMAIN,
                )
        else:
            _LOGGER.debug("Targeted device %s not found", device_id)

    # Check if any valid server targets were found
    if not servers_to_command:
        _LOGGER.error(
            "Service '%s.%s' called without valid targets matching a server instance.",
            service.domain,
            service.service,
        )
        raise HomeAssistantError(
            f"Service {service.domain}.{service.service} requires targeting specific "
            f"server devices or entities from the {DOMAIN} integration."
        )

    # --- Queue tasks using resolved server names ---
    for config_entry_id, target_server_name in servers_to_command.items():
        # Check if the resolved config entry ID has data loaded for our domain
        # Check hass.data structure integrity
        if config_entry_id not in hass.data.get(DOMAIN, {}):
            _LOGGER.warning(
                "Targeted config entry %s is not loaded or has no data.",
                config_entry_id,
            )
            continue

        # Queue task using unique config_entry_id (already handles duplicates via dict keys)
        try:
            entry_data = hass.data[DOMAIN][config_entry_id]
            target_api: BedrockServerManagerApi = entry_data["api"]
            # We now use the specific server name resolved for the API call
            _LOGGER.info(
                "Queueing command '%s' for server '%s' (config entry %s)",
                command_to_send,
                target_server_name,
                config_entry_id,
            )
            tasks[config_entry_id] = _async_handle_send_command(
                target_api,
                target_server_name,
                command_to_send,  # Pass target_server_name
            )
        except KeyError as e:
            _LOGGER.error(
                "Missing expected data ('%s') for config entry %s when queueing service call.",
                e,
                config_entry_id,
            )
        except Exception as e:
            _LOGGER.exception(
                "Unexpected error processing target entry %s for service call.",
                config_entry_id,
            )

    # Execute all unique tasks concurrently
    if tasks:
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        # Check results for exceptions and log them
        processed_errors = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_errors += 1
                # Map result back to entry ID and resolved server name
                failed_entry_id = list(tasks.keys())[i]
                failed_server_name = servers_to_command.get(failed_entry_id, "unknown")
                _LOGGER.error(
                    "Error executing send_command for server '%s' (entry %s): %s",
                    failed_server_name,
                    failed_entry_id,
                    result,
                )
                # Decide if we should raise the first error or just log all
                # if processed_errors == 1:
                #     if isinstance(result, HomeAssistantError): raise result
                #     else: raise HomeAssistantError(f"Failed to send command for {failed_server_name}: {result}") from result


# --- Target Resolution Helper (Generic) ---
# It's useful to have a common way to map targets to server data
async def _resolve_server_targets(
    service: ServiceCall, hass: HomeAssistant
) -> Dict[str, str]:
    """Resolves service targets to a dict of {config_entry_id: server_name}."""
    servers_to_target: Dict[str, str] = {}
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)

    target_entity_ids = service.data.get(ATTR_ENTITY_ID, [])
    target_device_ids = service.data.get(ATTR_DEVICE_ID, [])
    if isinstance(target_entity_ids, str):
        target_entity_ids = [target_entity_ids]
    if isinstance(target_device_ids, str):
        target_device_ids = [target_device_ids]

    # Resolve Entities
    for entity_id in target_entity_ids:
        entity_entry = entity_reg.async_get(entity_id)
        if (
            entity_entry
            and entity_entry.platform == DOMAIN
            and entity_entry.config_entry_id
        ):
            parts = entity_entry.unique_id.split("_")
            if len(parts) >= 3 and parts[0] == DOMAIN:
                server_name = entity_entry.unique_id.replace(
                    f"{DOMAIN}_", "", 1
                ).replace(f"_{parts[-1]}", "", 1)
                if entity_entry.config_entry_id not in servers_to_target:
                    servers_to_target[entity_entry.config_entry_id] = server_name
                elif servers_to_target[entity_entry.config_entry_id] != server_name:
                    _LOGGER.warning(
                        "Config entry %s targeted via entities with different server names ('%s' vs '%s').",
                        entity_entry.config_entry_id,
                        servers_to_target[entity_entry.config_entry_id],
                        server_name,
                    )
            else:
                _LOGGER.warning(
                    "Could not get server name from unique ID '%s'",
                    entity_entry.unique_id,
                )

    # Resolve Devices
    for device_id in target_device_ids:
        device_entry = device_reg.async_get(device_id)
        if device_entry:
            our_entry_id = None
            for entry_id in device_entry.config_entries:
                config_entry = hass.config_entries.async_get_entry(entry_id)
                if config_entry and config_entry.domain == DOMAIN:
                    our_entry_id = entry_id
                    break
            if our_entry_id:
                server_name_from_dev = None
                for identifier in device_entry.identifiers:
                    if (
                        len(identifier) == 2
                        and identifier[0] == DOMAIN
                        and ":" not in identifier[1]
                    ):
                        server_name_from_dev = identifier[1]
                        break
                if server_name_from_dev:
                    if our_entry_id not in servers_to_target:
                        servers_to_target[our_entry_id] = server_name_from_dev
                    elif servers_to_target[our_entry_id] != server_name_from_dev:
                        _LOGGER.warning(
                            "Config entry %s targeted via device/entity with different server names ('%s' vs '%s').",
                            our_entry_id,
                            servers_to_target[our_entry_id],
                            server_name_from_dev,
                        )
                else:
                    _LOGGER.debug(
                        "Targeted device %s is manager or has unexpected identifiers.",
                        device_id,
                    )

    if not servers_to_target:
        _LOGGER.error(
            "Service call for '%s.%s' did not resolve to any valid server targets.",
            service.domain,
            service.service,
        )
        raise HomeAssistantError(
            f"Service {service.domain}.{service.service} requires targeting specific server devices or entities."
        )

    return servers_to_target


async def async_handle_trigger_backup_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle trigger_backup service call."""
    backup_type = service.data[FIELD_BACKUP_TYPE]
    file_to_backup = service.data.get(FIELD_FILE_TO_BACKUP)  # Optional

    if backup_type == "config" and not file_to_backup:
        raise vol.Invalid(
            f"'{FIELD_FILE_TO_BACKUP}' is required when '{FIELD_BACKUP_TYPE}' is 'config'."
        )

    resolved_targets = await _resolve_server_targets(service, hass)
    tasks = []
    for config_entry_id, target_server_name in resolved_targets.items():
        if config_entry_id not in hass.data.get(DOMAIN, {}):
            continue  # Skip unloaded
        try:
            target_api: BedrockServerManagerApi = hass.data[DOMAIN][config_entry_id][
                "api"
            ]
            _LOGGER.info(
                "Queueing '%s' backup for server '%s'", backup_type, target_server_name
            )
            tasks.append(
                _async_handle_trigger_backup(
                    target_api, target_server_name, backup_type, file_to_backup
                )
            )
        except Exception as e:
            _LOGGER.exception(
                "Error queueing trigger_backup for %s: %s", target_server_name, e
            )

    if tasks:
        await asyncio.gather(
            *tasks, return_exceptions=True
        )  # Log errors within gather if needed


async def async_handle_restore_backup_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle restore_backup service call."""
    restore_type = service.data[FIELD_RESTORE_TYPE]
    backup_file = service.data[FIELD_BACKUP_FILE]

    resolved_targets = await _resolve_server_targets(service, hass)
    tasks = []
    for config_entry_id, target_server_name in resolved_targets.items():
        if config_entry_id not in hass.data.get(DOMAIN, {}):
            continue
        try:
            target_api: BedrockServerManagerApi = hass.data[DOMAIN][config_entry_id][
                "api"
            ]
            _LOGGER.info(
                "Queueing '%s' restore from '%s' for server '%s'",
                restore_type,
                backup_file,
                target_server_name,
            )
            tasks.append(
                _async_handle_restore_backup(
                    target_api, target_server_name, restore_type, backup_file
                )
            )
        except Exception as e:
            _LOGGER.exception(
                "Error queueing restore_backup for %s: %s", target_server_name, e
            )

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def async_handle_restore_latest_all_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle restore_latest_all service call."""
    resolved_targets = await _resolve_server_targets(service, hass)
    tasks = []
    for config_entry_id, target_server_name in resolved_targets.items():
        if config_entry_id not in hass.data.get(DOMAIN, {}):
            continue
        try:
            target_api: BedrockServerManagerApi = hass.data[DOMAIN][config_entry_id][
                "api"
            ]
            _LOGGER.info(
                "Queueing restore latest all for server '%s'", target_server_name
            )
            tasks.append(
                _async_handle_restore_latest_all(target_api, target_server_name)
            )
        except Exception as e:
            _LOGGER.exception(
                "Error queueing restore_latest_all for %s: %s", target_server_name, e
            )

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def async_handle_install_server_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the install_server service call."""
    server_name = service.data[FIELD_SERVER_NAME]
    server_version = service.data[FIELD_SERVER_VERSION]
    overwrite = service.data[
        FIELD_OVERWRITE
    ]  # Uses default=False from schema if not provided

    _LOGGER.info(
        "Executing install_server service for: %s, Version: %s, Overwrite: %s",
        server_name,
        server_version,
        overwrite,
    )

    # Find an API client instance (assuming one manager for now)
    api_client: Optional[BedrockServerManagerApi] = None
    if hass.data.get(DOMAIN):
        first_entry_id = next(iter(hass.data[DOMAIN]))
        if first_entry_id and hass.data[DOMAIN][first_entry_id].get("api"):
            api_client = hass.data[DOMAIN][first_entry_id]["api"]
        else:
            _LOGGER.error(
                "Could not find a valid API client instance to execute install_server."
            )
            raise HomeAssistantError(
                "BSM integration not fully loaded or API client missing."
            )
    else:
        _LOGGER.error("BSM integration data not found.")
        raise HomeAssistantError("BSM integration not loaded.")

    # Call the helper
    await _async_handle_install_server(
        api=api_client,
        server_name=server_name,
        server_version=server_version,
        overwrite=overwrite,
    )


async def async_handle_delete_server_service(service: ServiceCall, hass: HomeAssistant):
    """Handle the delete_server service call."""

    _LOGGER.warning(
        "Executing delete_server service for target(s) specified in call %s. "
        "Confirmation provided. THIS IS DESTRUCTIVE!",
        service.context.id,  # Log context ID for tracing
    )

    # Resolve which server(s) were targeted
    try:
        resolved_targets = await _resolve_server_targets(
            service, hass
        )  # Reuse resolver
    except HomeAssistantError as e:
        # If target resolution fails (e.g., no valid targets found), log and stop
        _LOGGER.error("Cannot execute delete_server: Failed to resolve targets - %s", e)
        # Raising here prevents further execution
        raise
    except Exception as e:
        _LOGGER.exception(
            "Unexpected error resolving targets for delete_server service."
        )
        raise HomeAssistantError("Unexpected error resolving service targets.") from e

    tasks = []
    servers_to_delete = []  # Keep track of names for logging/notification

    # Queue deletion tasks for valid targets
    for config_entry_id, target_server_name in resolved_targets.items():
        # Double-check hass data integrity
        if config_entry_id not in hass.data.get(DOMAIN, {}):
            _LOGGER.warning(
                "Config entry %s (resolved target for delete) is not loaded or has no data. Skipping.",
                config_entry_id,
            )
            continue
        try:
            entry_data = hass.data[DOMAIN][config_entry_id]
            target_api: BedrockServerManagerApi = entry_data["api"]
            # Log prominently that deletion is being queued
            _LOGGER.critical(
                "Queueing IRREVERSIBLE delete for server '%s' (config entry %s)",
                target_server_name,
                config_entry_id,
            )
            tasks.append(_async_handle_delete_server(target_api, target_server_name))
            servers_to_delete.append(
                target_server_name
            )  # Add to list for potential summary
        except KeyError as e:
            _LOGGER.error(
                "Missing expected data ('%s') for config entry %s when queueing delete_server.",
                e,
                config_entry_id,
            )
        except Exception as e:
            _LOGGER.exception(
                "Unexpected error queueing delete_server for %s: %s",
                target_server_name,
                e,
            )

    # Execute deletion tasks if any were successfully queued
    if tasks:
        _LOGGER.warning(
            "Proceeding with delete API calls for %d server(s).", len(tasks)
        )
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any errors that occurred during the API calls
        processed_errors = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_errors += 1
                # Try to get the server name corresponding to the failed task
                failed_entry_id = list(resolved_targets.keys())[
                    i
                ]  # Assumes gather preserves order
                failed_server_name = resolved_targets.get(failed_entry_id, "unknown")
                _LOGGER.error(
                    "Error executing delete_server for server '%s' (entry %s): %s",
                    failed_server_name,
                    failed_entry_id,
                    result,
                )
                # Note: The HomeAssistantError raised by the helper will be caught by HA service layer

        # Optionally: Create a persistent notification summarizing the action
        if servers_to_delete:
            message = (
                f"Deletion process executed for server(s): {', '.join(servers_to_delete)}. "
                f"{processed_errors} error(s) occurred during the API calls (check logs). "
                "Associated Home Assistant devices/entities will become unavailable "
                "after restart or next update if deletion was successful on the manager."
            )
            hass.components.persistent_notification.async_create(
                message,
                title="Minecraft Server Deletion Attempted",
                notification_id=f"bsm_delete_{service.context.id}",  # Unique ID for notification
            )

    elif not resolved_targets:
        # This case should have been caught by the _resolve_server_targets check, but double-check
        _LOGGER.error(
            "Delete server handler reached but no valid targets were resolved."
        )
    else:
        # No tasks were queued, likely due to errors finding API client etc.
        _LOGGER.error(
            "Delete server handler did not queue any tasks despite resolved targets. Check previous logs."
        )


# --- Service Registration Function ---
async def async_register_services(hass: HomeAssistant):
    """Register the custom services for the integration."""

    # Send Command
    if not hass.services.has_service(DOMAIN, SERVICE_SEND_COMMAND):

        async def send_command_wrapper(call: ServiceCall):
            await async_handle_send_command_service(call, hass)

        _LOGGER.debug("Registering service: %s.%s", DOMAIN, SERVICE_SEND_COMMAND)
        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_COMMAND,
            send_command_wrapper,
            schema=SEND_COMMAND_SERVICE_SCHEMA,
        )

    # Prune Downloads
    if not hass.services.has_service(DOMAIN, SERVICE_PRUNE_DOWNLOADS):

        async def prune_downloads_wrapper(call: ServiceCall):
            await async_handle_prune_downloads_service(call, hass)

        _LOGGER.debug("Registering service: %s.%s", DOMAIN, SERVICE_PRUNE_DOWNLOADS)
        hass.services.async_register(
            DOMAIN,
            SERVICE_PRUNE_DOWNLOADS,
            prune_downloads_wrapper,
            schema=PRUNE_DOWNLOADS_SERVICE_SCHEMA,
        )

    # Trigger Backup
    if not hass.services.has_service(DOMAIN, SERVICE_TRIGGER_BACKUP):

        async def trigger_backup_wrapper(call: ServiceCall):
            await async_handle_trigger_backup_service(call, hass)

        _LOGGER.debug("Registering service: %s.%s", DOMAIN, SERVICE_TRIGGER_BACKUP)
        hass.services.async_register(
            DOMAIN,
            SERVICE_TRIGGER_BACKUP,
            trigger_backup_wrapper,
            schema=TRIGGER_BACKUP_SERVICE_SCHEMA,
        )

    # Restore Backup
    if not hass.services.has_service(DOMAIN, SERVICE_RESTORE_BACKUP):

        async def restore_backup_wrapper(call: ServiceCall):
            await async_handle_restore_backup_service(call, hass)

        _LOGGER.debug("Registering service: %s.%s", DOMAIN, SERVICE_RESTORE_BACKUP)
        hass.services.async_register(
            DOMAIN,
            SERVICE_RESTORE_BACKUP,
            restore_backup_wrapper,
            schema=RESTORE_BACKUP_SERVICE_SCHEMA,
        )

    # Restore Latest All
    if not hass.services.has_service(DOMAIN, SERVICE_RESTORE_LATEST_ALL):

        async def restore_latest_all_wrapper(call: ServiceCall):
            await async_handle_restore_latest_all_service(call, hass)

        _LOGGER.debug("Registering service: %s.%s", DOMAIN, SERVICE_RESTORE_LATEST_ALL)
        hass.services.async_register(
            DOMAIN,
            SERVICE_RESTORE_LATEST_ALL,
            restore_latest_all_wrapper,
            schema=RESTORE_LATEST_ALL_SERVICE_SCHEMA,
        )

    # Install Server
    if not hass.services.has_service(DOMAIN, SERVICE_INSTALL_SERVER):

        async def install_server_wrapper(call: ServiceCall):
            await async_handle_install_server_service(call, hass)

        _LOGGER.debug("Registering service: %s.%s", DOMAIN, SERVICE_INSTALL_SERVER)
        hass.services.async_register(
            DOMAIN,
            SERVICE_INSTALL_SERVER,
            install_server_wrapper,
            schema=INSTALL_SERVER_SERVICE_SCHEMA,
        )

    # Delete Server
    if not hass.services.has_service(DOMAIN, SERVICE_DELETE_SERVER):

        async def delete_server_wrapper(call: ServiceCall):
            await async_handle_delete_server_service(call, hass)

        _LOGGER.debug("Registering service: %s.%s", DOMAIN, SERVICE_DELETE_SERVER)
        hass.services.async_register(
            DOMAIN,
            SERVICE_DELETE_SERVER,
            delete_server_wrapper,
            schema=DELETE_SERVER_SERVICE_SCHEMA,
        )


# --- Service Removal Function ---
async def async_remove_services(hass: HomeAssistant):
    """Remove the custom services for the integration."""
    if not hass.data.get(DOMAIN):  # Only remove if domain data is gone
        services_to_remove = [
            SERVICE_SEND_COMMAND,
            SERVICE_PRUNE_DOWNLOADS,
            SERVICE_TRIGGER_BACKUP,
            SERVICE_RESTORE_BACKUP,
            SERVICE_RESTORE_LATEST_ALL,
            SERVICE_INSTALL_SERVER,
            SERVICE_DELETE_SERVER,
        ]
        for service_name in services_to_remove:
            if hass.services.has_service(DOMAIN, service_name):
                _LOGGER.debug("Removing service: %s.%s", DOMAIN, service_name)
                hass.services.async_remove(DOMAIN, service_name)
