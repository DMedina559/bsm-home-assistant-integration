"""Service handlers for the Bedrock Server Manager integration."""

import asyncio
import logging
from typing import cast, Dict, Optional, List, Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
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

ADD_TO_ALLOWLIST_SERVICE_SCHEMA = vol.Schema(
    {
        # Players field: Expect a list of strings
        vol.Required(FIELD_PLAYERS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(FIELD_IGNORE_PLAYER_LIMIT, default=False): bool,
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
    }
)

REMOVE_FROM_ALLOWLIST_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PLAYER_NAME): str,
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
        # Allow any string key, value can be string, int, or bool (API handles specific validation)
        vol.Required(FIELD_PROPERTIES): vol.Schema(
            {cv.string: vol.Any(cv.string, cv.positive_int, cv.boolean)}
        ),
        # Add target keys workaround if needed
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
    }
)

INSTALL_WORLD_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_FILENAME): str,
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
    }
)

INSTALL_ADDON_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_FILENAME): str,
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
    }
)

CONFIGURE_OS_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_AUTOUPDATE): bool,
        vol.Optional(FIELD_AUTOSTART): bool,
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


async def _async_handle_delete_server(
    hass: HomeAssistant, api: BedrockServerManagerApi, server: str, config_entry_id: str
):
    """Helper coroutine to call API and remove device for delete_server."""
    _LOGGER.critical("EXECUTING IRREVERSIBLE DELETE for server '%s'", server)
    device_removed = False
    try:
        # Call the API to delete on the manager side
        response = await api.async_delete_server(server_name=server)

        # Check if API reported success before removing from HA
        if response and response.get("status") == "success":
            _LOGGER.info(
                "Manager API confirmed successful deletion of server '%s'. Removing from Home Assistant.",
                server,
            )

            # --- Remove Device from HA Registry ---
            device_registry = dr.async_get(hass)
            # Find the device using its unique identifier for THIS server
            device_identifier = (DOMAIN, server)
            device_to_remove = device_registry.async_get_device(
                identifiers={device_identifier}
            )

            if device_to_remove:
                _LOGGER.debug(
                    "Removing device %s (%s) from registry.",
                    device_to_remove.name_by_user or device_to_remove.name,
                    device_to_remove.id,
                )
                # This removes the device and implicitly its entities from this config entry
                # Note: If device shared by other entries (shouldn't happen here), it only removes association
                device_registry.async_remove_device(device_to_remove.id)
                device_removed = True  # Mark as removed for logging/notification
            else:
                _LOGGER.warning(
                    "Could not find device with identifier %s in registry to remove after successful API deletion.",
                    device_identifier,
                )
            # --- End Remove Device ---

        else:
            # API did not confirm success (might have returned 200 OK but status!=success, or non-2xx)
            _LOGGER.error(
                "Manager API did not confirm successful deletion for server '%s'. Response: %s. Device not removed from HA.",
                server,
                response,
            )
            # Re-raise as an error so the gather call logs it
            raise HomeAssistantError(
                f"Manager API did not confirm successful deletion for {server}. Check manager logs."
            )

    except APIError as err:
        _LOGGER.error("API Error deleting server '%s': %s", server, err)
        raise HomeAssistantError(f"API Error deleting server: {err}") from err
    except Exception as err:
        _LOGGER.exception("Unexpected error deleting server '%s': %s", server, err)
        raise HomeAssistantError(f"Unexpected error deleting server: {err}") from err

    return device_removed  # Return status


async def _async_handle_add_to_allowlist(
    api: BedrockServerManagerApi, server: str, players: List[str], ignore_limit: bool
):
    """Helper for add_to_allowlist service."""
    try:
        await api.async_add_to_allowlist(
            server_name=server, players=players, ignores_player_limit=ignore_limit
        )
        _LOGGER.info(
            "Successfully requested add players %s to allowlist for server '%s'",
            players,
            server,
        )
    except APIError as err:
        _LOGGER.error("API Error adding to allowlist for '%s': %s", server, err)
        raise HomeAssistantError(f"API Error adding to allowlist: {err}") from err
    except Exception as err:
        _LOGGER.exception(
            "Unexpected error adding to allowlist for '%s': %s", server, err
        )
        raise HomeAssistantError(
            f"Unexpected error adding to allowlist: {err}"
        ) from err


async def _async_handle_remove_from_allowlist(
    api: BedrockServerManagerApi, server: str, player_name: str
):
    """Helper for remove_from_allowlist service."""
    try:
        await api.async_remove_from_allowlist(
            server_name=server, player_name=player_name
        )
        _LOGGER.info(
            "Successfully requested remove player '%s' from allowlist for server '%s'",
            player_name,
            server,
        )
    except APIError as err:
        _LOGGER.error("API Error removing from allowlist for '%s': %s", server, err)
        raise HomeAssistantError(f"API Error removing from allowlist: {err}") from err
    except Exception as err:
        _LOGGER.exception(
            "Unexpected error removing from allowlist for '%s': %s", server, err
        )
        raise HomeAssistantError(
            f"Unexpected error removing from allowlist: {err}"
        ) from err


async def _async_handle_set_permissions(
    api: BedrockServerManagerApi, server: str, permissions_dict: Dict[str, str]
):
    """Helper coroutine to call API for set_permissions."""
    try:
        await api.async_set_permissions(
            server_name=server, permissions_dict=permissions_dict
        )
        _LOGGER.info("Successfully requested set permissions for server '%s'", server)
    except APIError as err:
        # Check if the error response contains detailed validation errors
        error_details = ""
        if isinstance(getattr(err, "message", None), dict) and "errors" in err.message:
            error_details = f" Details: {err.message['errors']}"
        elif isinstance(getattr(err, "message", None), str):
            error_details = f" Message: {err.message}"

        _LOGGER.error(
            "API Error setting permissions for '%s': %s%s", server, err, error_details
        )
        # Include details in the HA error if possible
        raise HomeAssistantError(
            f"API Error setting permissions: {err}{error_details}"
        ) from err
    except Exception as err:
        _LOGGER.exception(
            "Unexpected error setting permissions for '%s': %s", server, err
        )
        raise HomeAssistantError(
            f"Unexpected error setting permissions: {err}"
        ) from err


async def _async_handle_update_properties(
    api: BedrockServerManagerApi, server: str, properties_dict: Dict[str, Any]
):
    """Helper coroutine to call API for update_properties."""
    try:
        await api.async_update_properties(
            server_name=server, properties_dict=properties_dict
        )
        _LOGGER.info("Successfully requested property updates for server '%s'", server)
    except APIError as err:
        # Check for detailed validation errors from API
        error_details = ""
        if isinstance(getattr(err, "message", None), dict) and "errors" in err.message:
            error_details = f" Details: {err.message['errors']}"
        elif isinstance(getattr(err, "message", None), str):
            error_details = f" Message: {err.message}"

        _LOGGER.error(
            "API Error updating properties for '%s': %s%s", server, err, error_details
        )
        raise HomeAssistantError(
            f"API Error updating properties: {err}{error_details}"
        ) from err
    except Exception as err:
        _LOGGER.exception(
            "Unexpected error updating properties for '%s': %s", server, err
        )
        raise HomeAssistantError(
            f"Unexpected error updating properties: {err}"
        ) from err


async def _async_handle_install_world(
    api: BedrockServerManagerApi, server: str, filename: str
):
    """Helper coroutine to call API for install_world."""
    try:
        await api.async_install_world(server_name=server, filename=filename)
        _LOGGER.info(
            "Successfully requested world install from '%s' for server '%s'",
            filename,
            server,
        )
    except APIError as err:
        _LOGGER.error("API Error installing world for '%s': %s", server, err)
        raise HomeAssistantError(f"API Error installing world: {err}") from err
    except Exception as err:
        _LOGGER.exception("Unexpected error installing world for '%s': %s", server, err)
        raise HomeAssistantError(f"Unexpected error installing world: {err}") from err


async def _async_handle_install_addon(
    api: BedrockServerManagerApi, server: str, filename: str
):
    """Helper coroutine to call API for install_addon."""
    try:
        await api.async_install_addon(server_name=server, filename=filename)
        _LOGGER.info(
            "Successfully requested addon install from '%s' for server '%s'",
            filename,
            server,
        )
    except APIError as err:
        _LOGGER.error("API Error installing addon for '%s': %s", server, err)
        raise HomeAssistantError(f"API Error installing addon: {err}") from err
    except Exception as err:
        _LOGGER.exception("Unexpected error installing addon for '%s': %s", server, err)
        raise HomeAssistantError(f"Unexpected error installing addon: {err}") from err


async def _async_handle_configure_os_service(
    api: BedrockServerManagerApi,
    server: str,
    payload: Dict[str, bool],  # Payload is already OS-specific
):
    """Helper coroutine to call API for configure_os_service."""
    try:
        await api.async_configure_os_service(server_name=server, payload=payload)
        _LOGGER.info(
            "Successfully requested OS service configuration for server '%s' with %s",
            server,
            payload,
        )
    except APIError as err:
        _LOGGER.error("API Error configuring OS service for '%s': %s", server, err)
        raise HomeAssistantError(f"API Error configuring OS service: {err}") from err
    except Exception as err:
        _LOGGER.exception(
            "Unexpected error configuring OS service for '%s': %s", server, err
        )
        raise HomeAssistantError(
            f"Unexpected error configuring OS service: {err}"
        ) from err


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
    # Schema validation already confirmed FIELD_CONFIRM_DELETE is True

    _LOGGER.warning(
        "Executing delete_server service for target(s) specified in call %s. "
        "Confirmation provided. THIS IS DESTRUCTIVE!",
        service.context.id,
    )

    try:
        resolved_targets = await _resolve_server_targets(service, hass)
    except HomeAssistantError as e:
        _LOGGER.error("Cannot execute delete_server: Failed to resolve targets - %s", e)
        raise
    except Exception as e:
        _LOGGER.exception("Unexpected error resolving targets for delete_server.")
        raise HomeAssistantError("Unexpected error resolving service targets.") from e

    tasks = []
    servers_attempted = {}  # Store {config_entry_id: server_name} for notification

    for config_entry_id, target_server_name in resolved_targets.items():
        if config_entry_id not in hass.data.get(DOMAIN, {}):
            continue
        try:
            entry_data = hass.data[DOMAIN][config_entry_id]
            target_api: BedrockServerManagerApi = entry_data["api"]
            _LOGGER.warning(
                "Queueing IRREVERSIBLE delete for server '%s' (config entry %s)",
                target_server_name,
                config_entry_id,
            )
            # Pass hass and config_entry_id to the helper now
            tasks.append(
                _async_handle_delete_server(
                    hass, target_api, target_server_name, config_entry_id
                )
            )
            servers_attempted[config_entry_id] = target_server_name  # Track attempt
        except Exception as e:
            _LOGGER.exception(
                "Error queueing delete_server for %s: %s", target_server_name, e
            )

    if tasks:
        _LOGGER.warning(
            "Proceeding with delete API calls for %d server(s).", len(tasks)
        )
        # Results now contain True (if device removed) or an Exception
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_errors = 0
        servers_removed_from_ha = []
        servers_failed_api = []

        for i, result in enumerate(results):
            # Map result back to entry ID and resolved server name
            entry_id_processed = list(resolved_targets.keys())[
                i
            ]  # Assumes gather preserves order
            server_name_processed = resolved_targets.get(entry_id_processed, "unknown")

            if isinstance(result, Exception):
                processed_errors += 1
                servers_failed_api.append(server_name_processed)
                _LOGGER.error(
                    "Error executing delete_server for server '%s' (entry %s): %s",
                    server_name_processed,
                    entry_id_processed,
                    result,
                )
            elif (
                result is True
            ):  # Helper returned True indicating HA device removal success
                servers_removed_from_ha.append(server_name_processed)
            # else: result is False or None (shouldn't happen with current helper logic)

        # Create persistent notification
        if servers_attempted:
            message_parts = []
            if servers_removed_from_ha:
                message_parts.append(
                    f"Successfully deleted and removed from HA: {', '.join(servers_removed_from_ha)}."
                )
            if servers_failed_api:
                message_parts.append(
                    f"Failed API deletion (check logs): {', '.join(servers_failed_api)}."
                )
            if not message_parts:
                message_parts.append(
                    "Deletion attempted but status unclear (check logs)."
                )

            hass.components.persistent_notification.async_create(
                " ".join(message_parts),
                title="Minecraft Server Deletion Results",
                notification_id=f"bsm_delete_{service.context.id}",
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


async def async_handle_add_to_allowlist_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle add_to_allowlist service call."""
    players = service.data[FIELD_PLAYERS]
    ignore_limit = service.data[
        FIELD_IGNORE_PLAYER_LIMIT
    ]  # Uses default=False from schema

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
                "Queueing add players %s to allowlist for server '%s'",
                players,
                target_server_name,
            )
            tasks.append(
                _async_handle_add_to_allowlist(
                    target_api, target_server_name, players, ignore_limit
                )
            )
        except Exception as e:
            _LOGGER.exception(
                "Error queueing add_to_allowlist for %s: %s", target_server_name, e
            )
    if tasks:
        await asyncio.gather(
            *tasks, return_exceptions=True
        )  # Log errors within gather if needed


async def async_handle_remove_from_allowlist_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle remove_from_allowlist service call."""
    player_name = service.data[FIELD_PLAYER_NAME]

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
                "Queueing remove player '%s' from allowlist for server '%s'",
                player_name,
                target_server_name,
            )
            tasks.append(
                _async_handle_remove_from_allowlist(
                    target_api, target_server_name, player_name
                )
            )
        except Exception as e:
            _LOGGER.exception(
                "Error queueing remove_from_allowlist for %s: %s", target_server_name, e
            )
    if tasks:
        await asyncio.gather(
            *tasks, return_exceptions=True
        )  # Log errors within gather if needed


async def async_handle_set_permissions_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the set_permissions service call."""
    # Schema ensures 'permissions' is a dict[str, str]
    permissions_dict = service.data[FIELD_PERMISSIONS]

    _LOGGER.info("Executing set_permissions service for target(s)")

    resolved_targets = await _resolve_server_targets(service, hass)  # Reuse resolver
    tasks = []
    servers_processed = []

    for config_entry_id, target_server_name in resolved_targets.items():
        if config_entry_id not in hass.data.get(DOMAIN, {}):
            continue
        try:
            target_api: BedrockServerManagerApi = hass.data[DOMAIN][config_entry_id][
                "api"
            ]
            _LOGGER.info(
                "Queueing set_permissions for server '%s' (config entry %s)",
                target_server_name,
                config_entry_id,
            )
            tasks.append(
                _async_handle_set_permissions(
                    target_api, target_server_name, permissions_dict
                )
            )
            servers_processed.append(target_server_name)
        except Exception as e:
            _LOGGER.exception(
                "Error queueing set_permissions for %s: %s", target_server_name, e
            )

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Log errors (already handled by helper raising HomeAssistantError)
        processed_errors = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_errors += 1
                failed_entry_id = list(resolved_targets.keys())[i]
                failed_server_name = resolved_targets.get(failed_entry_id, "unknown")
                _LOGGER.error(
                    "Error executing set_permissions for server '%s' (entry %s): %s",
                    failed_server_name,
                    failed_entry_id,
                    result,
                )


async def async_handle_update_properties_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the update_properties service call."""
    # Schema ensures 'properties' exists and is a dict[str, Any]
    properties_dict = service.data[FIELD_PROPERTIES]

    _LOGGER.info("Executing update_properties service for target(s)")

    resolved_targets = await _resolve_server_targets(service, hass)  # Reuse resolver
    tasks = []

    for config_entry_id, target_server_name in resolved_targets.items():
        if config_entry_id not in hass.data.get(DOMAIN, {}):
            continue
        try:
            target_api: BedrockServerManagerApi = hass.data[DOMAIN][config_entry_id][
                "api"
            ]
            _LOGGER.info(
                "Queueing property updates for server '%s' (config entry %s): %s",
                target_server_name,
                config_entry_id,
                properties_dict,
            )
            tasks.append(
                _async_handle_update_properties(
                    target_api, target_server_name, properties_dict
                )
            )
        except Exception as e:
            _LOGGER.exception(
                "Error queueing update_properties for %s: %s", target_server_name, e
            )

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Log errors (already handled by helper raising HomeAssistantError)
        processed_errors = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_errors += 1
                failed_entry_id = list(resolved_targets.keys())[i]
                failed_server_name = resolved_targets.get(failed_entry_id, "unknown")
                _LOGGER.error(
                    "Error executing update_properties for server '%s' (entry %s): %s",
                    failed_server_name,
                    failed_entry_id,
                    result,
                )


async def async_handle_install_world_service(service: ServiceCall, hass: HomeAssistant):
    """Handle the install_world service call."""
    filename = service.data[FIELD_FILENAME]

    _LOGGER.info(
        "Executing install_world service for target(s) with file: %s", filename
    )

    resolved_targets = await _resolve_server_targets(service, hass)  # Reuse resolver
    tasks = []

    for config_entry_id, target_server_name in resolved_targets.items():
        if config_entry_id not in hass.data.get(DOMAIN, {}):
            continue
        try:
            target_api: MinecraftBedrockApi = hass.data[DOMAIN][config_entry_id]["api"]
            _LOGGER.info(
                "Queueing world install from '%s' for server '%s' (config entry %s)",
                filename,
                target_server_name,
                config_entry_id,
            )
            tasks.append(
                _async_handle_install_world(target_api, target_server_name, filename)
            )
        except Exception as e:
            _LOGGER.exception(
                "Error queueing install_world for %s: %s", target_server_name, e
            )

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Log errors
        processed_errors = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_errors += 1
                failed_entry_id = list(resolved_targets.keys())[i]
                failed_server_name = resolved_targets.get(failed_entry_id, "unknown")
                _LOGGER.error(
                    "Error executing install_world for server '%s' (entry %s): %s",
                    failed_server_name,
                    failed_entry_id,
                    result,
                )


async def async_handle_install_addon_service(service: ServiceCall, hass: HomeAssistant):
    """Handle the install_addon service call."""
    filename = service.data[FIELD_FILENAME]

    _LOGGER.info(
        "Executing install_addon service for target(s) with file: %s", filename
    )

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
                "Queueing addon install from '%s' for server '%s' (config entry %s)",
                filename,
                target_server_name,
                config_entry_id,
            )
            tasks.append(
                _async_handle_install_addon(target_api, target_server_name, filename)
            )
        except Exception as e:
            _LOGGER.exception(
                "Error queueing install_addon for %s: %s", target_server_name, e
            )

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Log errors
        processed_errors = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_errors += 1
                failed_entry_id = list(resolved_targets.keys())[i]
                failed_server_name = resolved_targets.get(failed_entry_id, "unknown")
                _LOGGER.error(
                    "Error executing install_addon for server '%s' (entry %s): %s",
                    failed_server_name,
                    failed_entry_id,
                    result,
                )


async def async_handle_configure_os_service_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Handle the configure_os_service service call."""
    # Schema validation ensures these fields exist if required, or provides defaults
    autoupdate_val = service.data[FIELD_AUTOUPDATE]
    # autostart_val is optional, .get() will return None if not provided by user
    # and no default is set in the schema directly that would make it always present.
    autostart_val = service.data.get(FIELD_AUTOSTART)  # Will be None if not provided

    _LOGGER.info(
        "Executing configure_os_service for target(s). User input - Autoupdate: %s, Autostart: %s",
        autoupdate_val,
        autostart_val if autostart_val is not None else "(not provided)",
    )

    # Resolve which server(s) were targeted
    try:
        resolved_targets = await _resolve_server_targets(service, hass)
    except HomeAssistantError as e:
        _LOGGER.error(
            "Cannot execute configure_os_service: Failed to resolve targets - %s", e
        )
        raise  # Re-raise to let HA handle and report the error
    except Exception as e:
        _LOGGER.exception(
            "Unexpected error resolving targets for configure_os_service."
        )
        raise HomeAssistantError("Unexpected error resolving service targets.") from e

    tasks = []
    servers_processed_info = []  # For potential summary notification

    for config_entry_id, target_server_name in resolved_targets.items():
        # Ensure entry data is loaded
        if config_entry_id not in hass.data.get(DOMAIN, {}):
            _LOGGER.warning(
                "Config entry %s (for server %s) not loaded or has no data. Skipping OS service config.",
                config_entry_id,
                target_server_name,
            )
            continue

        try:
            entry_data = hass.data[DOMAIN][config_entry_id]
            target_api: BedrockServerManagerApi = entry_data["api"]
            # Get the stored OS type for the manager associated with this config entry
            manager_os_type: str = entry_data.get("manager_os_type", "unknown").lower()

            # --- Build OS-specific payload for the API ---
            payload_for_api: Dict[str, bool] = {"autoupdate": autoupdate_val}

            if manager_os_type == "linux":
                if (
                    autostart_val is not None
                ):  # Only include autostart if user explicitly provided a value
                    payload_for_api["autostart"] = autostart_val
                # If autostart_val is None (user didn't touch the optional field),
                # we don't send 'autostart' to the API for Linux, letting API/manager use defaults or ignore.
            elif manager_os_type == "windows":
                # For Windows, 'autostart' is not applicable via this API endpoint.
                # Log if user tried to set it.
                if autostart_val is not None:
                    _LOGGER.warning(
                        "Autostart field was provided for server '%s' (manager OS: Windows), "
                        "but it's not applicable. 'autostart' will be omitted from API call.",
                        target_server_name,
                    )
            else:  # Unknown or other OS types
                if autostart_val is not None:
                    _LOGGER.warning(
                        "Autostart field provided for server '%s' (manager OS: '%s'), "
                        "but OS specific behavior is unknown. 'autostart' will be omitted.",
                        target_server_name,
                        manager_os_type,
                    )
            # --- End Build Payload ---

            _LOGGER.info(
                "Queueing OS service config for server '%s' (Manager OS: %s) with API payload: %s",
                target_server_name,
                manager_os_type,
                payload_for_api,
            )
            tasks.append(
                _async_handle_configure_os_service(
                    target_api, target_server_name, payload_for_api
                )
            )
            servers_processed_info.append(
                {"name": target_server_name, "payload": payload_for_api}
            )

        except KeyError as e:
            _LOGGER.error(
                "Missing expected data ('%s') for config entry %s when queueing configure_os_service for server '%s'.",
                e,
                config_entry_id,
                target_server_name,
            )
        except Exception as e:
            _LOGGER.exception(
                "Unexpected error queueing configure_os_service for server '%s': %s",
                target_server_name,
                e,
            )

    if tasks:
        _LOGGER.info(
            "Proceeding with configure_os_service API calls for %d server(s).",
            len(tasks),
        )
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any errors that occurred during the API calls
        processed_errors = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_errors += 1
                # Get corresponding server name for better logging
                failed_server_info = (
                    servers_processed_info[i]
                    if i < len(servers_processed_info)
                    else {"name": "unknown"}
                )
                _LOGGER.error(
                    "Error executing configure_os_service for server '%s': %s",
                    failed_server_info["name"],
                    result,
                )
                # HomeAssistantError raised by helper will be handled by HA's service layer

        if servers_processed_info:
            status_summary = (
                f"OS service configuration attempt finished for {len(servers_processed_info)} server(s). "
                f"{processed_errors} error(s) occurred (check logs for details)."
            )
            _LOGGER.info(status_summary)

    elif not resolved_targets:
        # This case should have been caught by the _resolve_server_targets check raising an error
        _LOGGER.error(
            "Configure OS service handler reached but no valid targets were resolved (this should not happen)."
        )
    else:
        # No tasks were queued, likely due to errors finding API client or other data issues
        _LOGGER.error(
            "Configure OS service handler did not queue any tasks despite resolved targets. Check previous logs for errors."
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

    # Add to Allowlist
    if not hass.services.has_service(DOMAIN, SERVICE_ADD_TO_ALLOWLIST):

        async def add_allowlist_wrapper(call: ServiceCall):
            await async_handle_add_to_allowlist_service(call, hass)

        _LOGGER.debug("Registering service: %s.%s", DOMAIN, SERVICE_ADD_TO_ALLOWLIST)
        hass.services.async_register(
            DOMAIN,
            SERVICE_ADD_TO_ALLOWLIST,
            add_allowlist_wrapper,
            schema=ADD_TO_ALLOWLIST_SERVICE_SCHEMA,
        )

    # Remove from Allowlist
    if not hass.services.has_service(DOMAIN, SERVICE_REMOVE_FROM_ALLOWLIST):

        async def remove_allowlist_wrapper(call: ServiceCall):
            await async_handle_remove_from_allowlist_service(call, hass)

        _LOGGER.debug(
            "Registering service: %s.%s", DOMAIN, SERVICE_REMOVE_FROM_ALLOWLIST
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_REMOVE_FROM_ALLOWLIST,
            remove_allowlist_wrapper,
            schema=REMOVE_FROM_ALLOWLIST_SERVICE_SCHEMA,
        )

    # Set Permissions
    if not hass.services.has_service(DOMAIN, SERVICE_SET_PERMISSIONS):

        async def set_permissions_wrapper(call: ServiceCall):
            await async_handle_set_permissions_service(call, hass)

        _LOGGER.debug("Registering service: %s.%s", DOMAIN, SERVICE_SET_PERMISSIONS)
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_PERMISSIONS,
            set_permissions_wrapper,
            schema=SET_PERMISSIONS_SERVICE_SCHEMA,
        )

    # Update Properties
    if not hass.services.has_service(DOMAIN, SERVICE_UPDATE_PROPERTIES):

        async def update_properties_wrapper(call: ServiceCall):
            await async_handle_update_properties_service(call, hass)

        _LOGGER.debug("Registering service: %s.%s", DOMAIN, SERVICE_UPDATE_PROPERTIES)
        hass.services.async_register(
            DOMAIN,
            SERVICE_UPDATE_PROPERTIES,
            update_properties_wrapper,
            schema=UPDATE_PROPERTIES_SERVICE_SCHEMA,
        )

    # Install World
    if not hass.services.has_service(DOMAIN, SERVICE_INSTALL_WORLD):

        async def install_world_wrapper(call: ServiceCall):
            await async_handle_install_world_service(call, hass)

        _LOGGER.debug("Registering service: %s.%s", DOMAIN, SERVICE_INSTALL_WORLD)
        hass.services.async_register(
            DOMAIN,
            SERVICE_INSTALL_WORLD,
            install_world_wrapper,
            schema=INSTALL_WORLD_SERVICE_SCHEMA,
        )

    # Install Addon
    if not hass.services.has_service(DOMAIN, SERVICE_INSTALL_ADDON):

        async def install_addon_wrapper(call: ServiceCall):
            await async_handle_install_addon_service(call, hass)

        _LOGGER.debug("Registering service: %s.%s", DOMAIN, SERVICE_INSTALL_ADDON)
        hass.services.async_register(
            DOMAIN,
            SERVICE_INSTALL_ADDON,
            install_addon_wrapper,
            schema=INSTALL_ADDON_SERVICE_SCHEMA,
        )

    # Configure OS Service
    if not hass.services.has_service(DOMAIN, SERVICE_CONFIGURE_OS_SERVICE):

        async def configure_os_service_wrapper(call: ServiceCall):
            await async_handle_configure_os_service_service(call, hass)

        _LOGGER.debug(
            "Registering service: %s.%s", DOMAIN, SERVICE_CONFIGURE_OS_SERVICE
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_CONFIGURE_OS_SERVICE,
            configure_os_service_wrapper,
            schema=CONFIGURE_OS_SERVICE_SCHEMA,
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
            SERVICE_ADD_TO_ALLOWLIST,
            SERVICE_REMOVE_FROM_ALLOWLIST,
            SERVICE_SET_PERMISSIONS,
            SERVICE_UPDATE_PROPERTIES,
            SERVICE_INSTALL_WORLD,
            SERVICE_INSTALL_ADDON,
            SERVICE_CONFIGURE_OS_SERVICE,
        ]
        for service_name in services_to_remove:
            if hass.services.has_service(DOMAIN, service_name):
                _LOGGER.debug("Removing service: %s.%s", DOMAIN, service_name)
                hass.services.async_remove(DOMAIN, service_name)
