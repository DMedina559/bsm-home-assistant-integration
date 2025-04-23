"""Service handlers for the Minecraft Bedrock Server Manager integration."""

import asyncio
import logging
from typing import cast

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
)
from .api import (
    MinecraftBedrockApi,
    APIError,
    ServerNotRunningError,
)

_LOGGER = logging.getLogger(__name__)

# --- Service Schema Definition (Experimental) ---
SEND_COMMAND_SERVICE_SCHEMA = vol.Schema(
    {
        # Keep the required command field
        vol.Required(FIELD_COMMAND): vol.All(vol.Coerce(str), vol.Length(min=1)),

        # --- Experiment: Explicitly allow targeting keys as Optional ---
        vol.Optional(ATTR_ENTITY_ID): object,
        vol.Optional(ATTR_DEVICE_ID): object,
        vol.Optional(ATTR_AREA_ID): object,
        # --- End Experiment ---
    }
)

# --- Service Handler Helper Function ---
async def _async_handle_send_command(api: MinecraftBedrockApi, server: str, command: str):
    """Helper coroutine to call API and handle errors for send_command."""
    try:
        await api.async_send_command(server, command)
        _LOGGER.debug("Successfully sent command '%s' to server '%s'", command, server)
    except ServerNotRunningError as err:
        _LOGGER.error("Failed to send command to '%s': %s", server, err)
        # Raise specific HA error users might catch in automations
        raise HomeAssistantError(f"Cannot send command to {server}: Server is not running.") from err
    except APIError as err:
        _LOGGER.error("API Error sending command to '%s': %s", server, err)
        raise HomeAssistantError(f"API Error sending command to {server}: {err}") from err
    except Exception as err:
        _LOGGER.exception("Unexpected error sending command to '%s': %s", server, err)
        raise HomeAssistantError(f"Unexpected error sending command to {server}: {err}") from err


# --- Main Service Handler Function (Using Revised Target Resolution) ---
async def async_handle_send_command_service(service: ServiceCall, hass: HomeAssistant):
    """Handle the send_command service call. Maps targets to config entries."""
    try:
         command_to_send = service.data[FIELD_COMMAND]
    except KeyError:
         _LOGGER.error("Internal error: '%s' key missing from service data after validation.", FIELD_COMMAND)
         raise HomeAssistantError(f"Missing required field: {FIELD_COMMAND}")

    tasks = {}

    # --- Resolve targets specified in service call ---
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)
    targeted_config_entry_ids = set()

    # Get target IDs from the service call data (HA populates these based on target selector)
    # Use .get() with default empty list to handle cases where one type isn't targeted
    target_entity_ids = service.data.get(ATTR_ENTITY_ID, [])
    target_device_ids = service.data.get(ATTR_DEVICE_ID, [])
    # target_area_ids = service.data.get(ATTR_AREA_ID, []) # Add if needed

    # If specific entities were targeted, find their config entries
    if target_entity_ids:
        # Ensure it's a list if only one was provided
        if isinstance(target_entity_ids, str): target_entity_ids = [target_entity_ids]
        for entity_id in target_entity_ids:
            entity_entry = entity_reg.async_get(entity_id)
            # Ensure entity exists and belongs to our domain
            if entity_entry and entity_entry.platform == DOMAIN and entity_entry.config_entry_id:
                targeted_config_entry_ids.add(entity_entry.config_entry_id)
            else:
                 _LOGGER.debug("Targeted entity %s not found or not part of %s domain", entity_id, DOMAIN)

    # If specific devices were targeted, find their config entries
    if target_device_ids:
        # Ensure it's a list if only one was provided
        if isinstance(target_device_ids, str): target_device_ids = [target_device_ids]
        for device_id in target_device_ids:
            device_entry = device_reg.async_get(device_id)
            # Ensure device exists and belongs to our integration (check config entries)
            if device_entry:
                 # A device can have multiple config entries, add all relevant ones
                 for entry_id in device_entry.config_entries:
                      # Check if this config entry belongs to our domain
                      config_entry = hass.config_entries.async_get_entry(entry_id)
                      if config_entry and config_entry.domain == DOMAIN:
                          targeted_config_entry_ids.add(entry_id)
            else:
                 _LOGGER.debug("Targeted device %s not found", device_id)

    # Add area resolution here if needed

    if not targeted_config_entry_ids:
         _LOGGER.error(
             "Service '%s.%s' called without valid targets. "
             "Please target devices or entities belonging to the '%s' integration.",
             service.domain, service.service, DOMAIN
         )
         raise HomeAssistantError(
             f"Service {service.domain}.{service.service} requires targeting specific "
             f"devices or entities from the {DOMAIN} integration."
         )


    # --- Queue tasks for unique, valid config entries ---
    for config_entry_id in targeted_config_entry_ids:
        # Check if the resolved config entry ID has data loaded for our domain
        if config_entry_id not in hass.data.get(DOMAIN, {}):
            _LOGGER.warning(
                "Targeted config entry %s (via device/entity) is not loaded or has no data for domain %s.",
                 config_entry_id, DOMAIN
            )
            continue

        # Queue the task using the config_entry_id as the key (already unique)
        try:
            entry_data = hass.data[DOMAIN][config_entry_id]
            target_api: MinecraftBedrockApi = entry_data["api"]
            target_server_name: str = entry_data["server_name"]

            _LOGGER.info(
                "Queueing command '%s' for server '%s' (config entry %s)",
                command_to_send, target_server_name, config_entry_id
            )
            # Store the task, keyed by config entry ID
            tasks[config_entry_id] = _async_handle_send_command(
                 target_api, target_server_name, command_to_send
            )
        except KeyError as e:
            _LOGGER.error(
                "Missing expected data ('%s') for config entry %s when queueing service call.",
                 e, config_entry_id
            )
        except Exception as e:
             _LOGGER.exception(
                 "Unexpected error processing target entry %s for service call.",
                 config_entry_id
             )


    # Execute all unique tasks concurrently
    if tasks:
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        # Check results for exceptions and log them
        processed_errors = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                 processed_errors += 1
                 failed_entry_id = list(tasks.keys())[i]
                 _LOGGER.error(
                     "Error executing send_command for config entry %s: %s",
                     failed_entry_id, result
                 )


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
            service_wrapper, # Use the wrapper function
            schema=SEND_COMMAND_SERVICE_SCHEMA, # Use the modified schema
        )

# --- Service Removal Function ---
async def async_remove_services(hass: HomeAssistant):
    """Remove the custom services for the integration."""
    if not hass.data.get(DOMAIN):
        if hass.services.has_service(DOMAIN, SERVICE_SEND_COMMAND):
            _LOGGER.debug("Removing service: %s.%s", DOMAIN, SERVICE_SEND_COMMAND)
            hass.services.async_remove(DOMAIN, SERVICE_SEND_COMMAND)