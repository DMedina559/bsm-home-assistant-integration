"""Service handlers for the Minecraft Bedrock Server Manager integration."""

import asyncio
import logging
from typing import cast, Dict

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_AREA_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr

from .const import (
    DOMAIN,
    SERVICE_SEND_COMMAND,
    FIELD_COMMAND,
    FIELD_DIRECTORY,
    FIELD_KEEP,
)
from .api import (
    MinecraftBedrockApi,
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


# --- Service Handler Helper Function ---
async def _async_handle_send_command(
    api: MinecraftBedrockApi, server: str, command: str
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
    api: MinecraftBedrockApi, directory: str, keep: Optional[int]
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


# --- Main Service Handlers ---
# async_handle_send_command_service remains the same


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
    api_client: Optional[MinecraftBedrockApi] = None
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


# --- Main Service Handler Function ---
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
            target_api: MinecraftBedrockApi = entry_data["api"]
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


# --- Service Registration Function ---
async def async_register_services(hass: HomeAssistant):
    """Register the custom services for the integration."""

    # Define a wrapper function that passes hass to the handler
    async def service_wrapper(service_call: ServiceCall):
        """Wrapper to pass hass to the service handler."""
        await async_handle_send_command_service(service_call, hass)

    # Register the service if it doesn't exist for this domain yet
    if not hass.services.has_service(DOMAIN, SERVICE_SEND_COMMAND):
        _LOGGER.debug("Registering service: %s.%s", DOMAIN, SERVICE_SEND_COMMAND)
        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_COMMAND,
            service_wrapper,  # Use the wrapper function
            schema=SEND_COMMAND_SERVICE_SCHEMA,  # Use the modified schema
        )

    async def prune_downloads_wrapper(service_call: ServiceCall):
        await async_handle_prune_downloads_service(service_call, hass)

    if not hass.services.has_service(DOMAIN, SERVICE_PRUNE_DOWNLOADS):
        _LOGGER.debug("Registering service: %s.%s", DOMAIN, SERVICE_PRUNE_DOWNLOADS)
        hass.services.async_register(
            DOMAIN,
            SERVICE_PRUNE_DOWNLOADS,
            prune_downloads_wrapper,
            schema=PRUNE_DOWNLOADS_SERVICE_SCHEMA,
        )


# --- Service Removal Function ---
async def async_remove_services(hass: HomeAssistant):
    """Remove the custom services for the integration."""
    if not hass.data.get(DOMAIN):
        if hass.services.has_service(DOMAIN, SERVICE_SEND_COMMAND):
            _LOGGER.debug("Removing service: %s.%s", DOMAIN, SERVICE_SEND_COMMAND)
            hass.services.async_remove(DOMAIN, SERVICE_SEND_COMMAND)
