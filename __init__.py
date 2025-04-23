"""The Minecraft Bedrock Server Manager integration."""

import asyncio
import logging
from datetime import timedelta

import async_timeout # Required by coordinator logic, keep if coordinator uses it implicitly? No, likely not needed here anymore. Remove if coordinator handles its own.
# import voluptuous as vol # No longer needed here if schema is in services.py
import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform # Use Platform enum if HA >= 2024.7
from homeassistant.core import HomeAssistant # ServiceCall no longer needed here
# from homeassistant.helpers import entity_registry as er # No longer needed here
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, HomeAssistantError

# Import API definitions used by coordinator/setup logic (AuthError etc)
from .api import (
    MinecraftBedrockApi,
    AuthError,
    CannotConnectError,
    # APIError, # Not directly handled here anymore
    # ServerNotFoundError, # Handled by coordinator
    # ServerNotRunningError, # Handled by coordinator
)
from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SERVER_NAME,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    PLATFORMS,
    # Constants related to services are no longer needed here
)
from .coordinator import MinecraftBedrockCoordinator
# Import the new services module
from . import services

_LOGGER = logging.getLogger(__name__)

# --- Service Schema and Handlers are REMOVED from here ---


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Minecraft Bedrock Server Manager from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # --- Get configuration data ---
    host = entry.data[CONF_HOST]
    port = int(entry.data[CONF_PORT]) # Keep int cast
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    server_name = entry.data[CONF_SERVER_NAME]
    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL_SECONDS)

    # --- Initialize API Client and Coordinator ---
    session = async_get_clientsession(hass)
    api_client = MinecraftBedrockApi(host, port, username, password, session)

    coordinator = MinecraftBedrockCoordinator(
        hass=hass,
        api_client=api_client,
        server_name=server_name,
        scan_interval=scan_interval,
    )

    # --- Perform Initial Coordinator Refresh ---
    # This will raise ConfigEntryNotReady if it fails (e.g., cannot connect, initial auth fails)
    await coordinator.async_config_entry_first_refresh()

    # --- Store coordinator and API client in hass.data ---
    # API client is stored here mainly for easier access during service calls routed back here,
    # or potentially other future logic. Platforms primarily use the coordinator.
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api_client,
        "server_name": server_name,
    }

    # --- Forward Setup to Platforms ---
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # --- Add listener for options flow updates ---
    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    # --- Register Services via the services module ---
    # This function handles checking if registration is needed
    await services.async_register_services(hass)

    return True


async def options_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    _LOGGER.debug("Options updated for %s, reloading entry", entry.entry_id)
    # Reload the integration entry to apply the new options (e.g., scan_interval)
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    server_name = entry.data.get(CONF_SERVER_NAME, entry.entry_id)
    _LOGGER.info("Unloading Minecraft Manager entry for server '%s'", server_name)

    # Unload platforms (sensor, switch, button) linked to this entry
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Remove this entry's data from hass.data
        if entry.entry_id in hass.data.get(DOMAIN, {}): # Check domain exists before pop
            hass.data[DOMAIN].pop(entry.entry_id)
            _LOGGER.debug("Successfully removed data for entry %s (%s)", entry.entry_id, server_name)

        # Check if the domain data dictionary is now empty to remove services
        # This check must happen *after* popping the entry data
        if not hass.data.get(DOMAIN):
             # Call the removal function from the services module
             await services.async_remove_services(hass)
        else:
             _LOGGER.debug("Other entries still loaded for domain %s, keeping services", DOMAIN)

    return unload_ok