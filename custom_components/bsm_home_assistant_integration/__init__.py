"""The Minecraft Bedrock Server Manager integration."""

import asyncio
import logging
from datetime import timedelta
import traceback # For more detailed error logging during setup loop

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import device_registry as dr # Import device registry
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, HomeAssistantError

# Import API definitions used by coordinator/setup logic (AuthError etc)
from .api import (
    MinecraftBedrockApi,
    AuthError,
    CannotConnectError,
    APIError, # Import other errors if needed by helper
)
# Import local constants
from .const import (
    DOMAIN,
    CONF_SERVER_NAMES, # Import the constant for the list
    DEFAULT_SCAN_INTERVAL_SECONDS,
    PLATFORMS,
)
# Import the specific Coordinator class
from .coordinator import MinecraftBedrockCoordinator
# Import the services module for registration/removal
from . import services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Minecraft Bedrock Server Manager from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {}) # Prepare entry-specific data store

    # --- Get configuration data ---
    host = entry.data[CONF_HOST]
    port = int(entry.data[CONF_PORT]) # Ensure int cast
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    # --- Get options ---
    # Server list comes from options now
    selected_servers = entry.options.get(CONF_SERVER_NAMES, [])
    # Polling interval also comes from options (or default)
    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL_SECONDS)

    # --- Initialize Shared API Client ---
    session = async_get_clientsession(hass)
    api_client = MinecraftBedrockApi(host, port, username, password, session)

    # --- Create the Central "Manager" Device ---
    # This device represents the BSM API endpoint itself
    manager_host_port_id = f"{host}:{port}" # Logical identifier value (string)
    # Create the identifier tuple using the domain and the logical ID string
    manager_identifier = (DOMAIN, manager_host_port_id)
    device_registry = dr.async_get(hass)
    manager_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={manager_identifier}, # Pass the identifier tuple in a set
        name=f"BSM @ {host}",
        manufacturer="Minecraft Bedrock Manager", # Or your specific branding
        model="Server Manager API",
        # sw_version=? # Can add manager version if API provides it
        configuration_url=f"http://{host}:{port}", # Link to the manager UI
    )
    _LOGGER.debug("Ensured manager device exists: ID=%s, Identifier=%s", manager_device.id, manager_identifier)

    # --- Store API Client and Manager Identifier ---
    # Store the identifier tuple for platforms to use for linking (via_device)
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api_client,
        "manager_identifier": manager_identifier, # Store identifier tuple
        "servers": {}, # Dictionary to hold data for each server instance
    }

    # --- Create Coordinators for Selected Servers ---
    if not selected_servers:
        _LOGGER.warning("No servers selected for manager %s. Integration will load but monitor no servers.", manager_host_port_id)
    else:
        _LOGGER.info("Setting up coordinators for servers: %s", selected_servers)
        setup_tasks = []
        for server_name in selected_servers:
            # Create a separate setup task for each server's coordinator
            setup_tasks.append(
                _async_setup_server_coordinator(hass, entry, api_client, server_name, scan_interval)
            )

        # Run coordinator setups concurrently
        results = await asyncio.gather(*setup_tasks, return_exceptions=True)

        # Check for errors during individual coordinator setups
        successful_setups = 0
        for i, result in enumerate(results):
            # Use the original list order to match results to server names
            server_name = selected_servers[i]
            if isinstance(result, Exception):
                log_msg = f"Failed to set up coordinator for server '{server_name}': {result}"
                # Log full traceback only for truly unexpected errors
                if not isinstance(result, (ConfigEntryAuthFailed, ConfigEntryNotReady, HomeAssistantError, APIError)):
                     _LOGGER.error(log_msg + "\n%s", traceback.format_exc(), exc_info=False)
                else:
                     _LOGGER.error(log_msg, exc_info=False)
                # Remove failed server entry from hass.data so platforms don't try to use it
                if server_name in hass.data[DOMAIN][entry.entry_id]["servers"]:
                    del hass.data[DOMAIN][entry.entry_id]["servers"][server_name]
            else:
                 successful_setups += 1

        # If ALL coordinator setups failed (and servers were selected), raise ConfigEntryNotReady
        if successful_setups == 0 and selected_servers:
             _LOGGER.error("All server coordinator setups failed for manager %s.", manager_host_port_id)
             raise ConfigEntryNotReady(f"Could not establish connection or initial update for any selected server on manager {manager_host_port_id}")

    # --- Forward Setup to Platforms ---
    # Platforms will now look into hass.data[DOMAIN][entry.entry_id]["servers"]
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # --- Add listener for options flow updates ---
    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    # --- Register Services (only once per domain) ---
    await services.async_register_services(hass)

    return True

async def _async_setup_server_coordinator(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api_client: MinecraftBedrockApi,
    server_name: str,
    scan_interval: int
):
    """Helper function to set up coordinator for a single server."""
    _LOGGER.debug("Setting up coordinator for server: %s", server_name)
    coordinator = MinecraftBedrockCoordinator(
        hass=hass,
        api_client=api_client,
        server_name=server_name,
        scan_interval=scan_interval,
    )
    # Perform initial refresh *for this specific coordinator*
    # This might raise ConfigEntryAuthFailed or UpdateFailed (-> ConfigEntryNotReady)
    # Let the exception propagate up to the gather call in async_setup_entry
    await coordinator.async_config_entry_first_refresh()

    # Store the successful coordinator in hass.data
    # Ensure the "servers" dict exists before trying to add to it
    hass.data[DOMAIN][entry.entry_id].setdefault("servers", {})
    hass.data[DOMAIN][entry.entry_id]["servers"][server_name] = {
        "coordinator": coordinator,
        # Static info will be fetched by platforms now if needed
    }
    _LOGGER.debug("Successfully set up coordinator for server: %s", server_name)


async def options_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    _LOGGER.debug("Options updated for %s, reloading entry to apply changes.", entry.entry_id)
    # Reload the integration entry. This will trigger async_unload_entry and then async_setup_entry again.
    # async_setup_entry will read the updated server list from entry.options.
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    manager_host = entry.data.get(CONF_HOST, entry.entry_id)
    _LOGGER.info("Unloading Minecraft Manager entry for manager '%s'", manager_host)

    # Unload platforms first
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # --- Clean up hass.data ---
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, None) # Remove entry's data safely

        if entry_data:
             _LOGGER.debug("Successfully removed data for entry %s (%s)", entry.entry_id, manager_host)
        else:
             _LOGGER.debug("No data found in hass.data for entry %s (%s) during unload.", entry.entry_id, manager_host)

        # --- Remove services if this was the last entry ---
        # Check if the domain key itself is now empty or gone
        if not hass.data.get(DOMAIN):
             await services.async_remove_services(hass)
        else:
             _LOGGER.debug("Other entries still loaded for domain %s, keeping services", DOMAIN)

    return unload_ok