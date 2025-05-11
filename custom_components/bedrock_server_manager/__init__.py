"""The Bedrock Server Manager integration."""

import asyncio
import logging
from datetime import timedelta
import traceback  # For more detailed error logging during setup loop

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    Platform,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import device_registry as dr  # Import device registry
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)

# Import API definitions used by coordinator/setup logic (AuthError etc)
from .api import (
    BedrockServerManagerApi,
    AuthError,
    CannotConnectError,
    APIError,  # Import other errors if needed by helper
)

# Import local constants
from .frontend import BsmFrontendRegistration
from .const import (
    DOMAIN,
    CONF_SERVER_NAMES,  # Import the constant for the list
    DEFAULT_SCAN_INTERVAL_SECONDS,
    PLATFORMS,
)

# Import the specific Coordinator class
from .coordinator import MinecraftBedrockCoordinator, ManagerDataCoordinator

# Import the services module for registration/removal
from . import services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bedrock Server Manager from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(
        entry.entry_id, {}
    )  # Prepare entry-specific data store

    # --- Frontend Registration ---
    frontend_registrar = BsmFrontendRegistration(hass)
    try:
        await frontend_registrar.async_register()
        # Store registrar instance for unload if needed, or just let it run
        hass.data[DOMAIN][entry.entry_id]["frontend_registrar"] = frontend_registrar
    except Exception as e:
        # Log error but don't necessarily prevent rest of setup
        _LOGGER.error(
            "Failed during frontend module registration: %s", e, exc_info=True
        )
    # --- End Frontend Registration ---

    # --- Get configuration data ---
    host = entry.data[CONF_HOST]
    port = int(entry.data[CONF_PORT])  # Ensure int cast
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    # --- Get options ---
    selected_servers = entry.options.get(CONF_SERVER_NAMES, [])
    # Use different scan intervals for manager data vs server data
    manager_scan_interval_options_key = (
        "manager_scan_interval"  # Potentially add to const.py
    )
    server_scan_interval_options_key = (
        "scan_interval"  # Existing options key for servers
    )

    # Default for manager coordinator (e.g., less frequent)
    manager_scan_interval = entry.options.get(
        manager_scan_interval_options_key, 600
    )  # Default 10 minutes
    # Default for server coordinators (e.g., more frequent)
    server_scan_interval = entry.options.get(
        server_scan_interval_options_key, DEFAULT_SCAN_INTERVAL_SECONDS
    )

    # --- Initialize Shared API Client ---
    session = async_get_clientsession(hass)
    # Ensure you use the correct class name from your api.py
    api_client = BedrockServerManagerApi(host, port, username, password, session)

    # --- Create and Refresh ManagerDataCoordinator FIRST ---
    # This fetches /api/info and /api/players/get
    manager_coordinator = ManagerDataCoordinator(
        hass=hass, api_client=api_client, scan_interval=manager_scan_interval
    )
    try:
        await manager_coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:  # Let specific auth errors propagate for reauth flow
        raise
    except Exception as err:  # Catch other errors during first refresh
        _LOGGER.error("Failed initial refresh for ManagerDataCoordinator: %s", err)
        raise ConfigEntryNotReady(
            f"Failed to initialize manager data coordinator: {err}"
        ) from err

    # --- Get manager OS/Version and Global Players from the ManagerDataCoordinator ---
    manager_os_type = "Unknown"
    manager_app_version = "Unknown"
    global_players_list_data = []  # Default to empty list

    if manager_coordinator.last_update_success and manager_coordinator.data:
        manager_info_data = manager_coordinator.data.get("info")
        if isinstance(manager_info_data, dict):
            manager_os_type = manager_info_data.get("os_type", "Unknown").lower()
            manager_app_version = manager_info_data.get("app_version", "Unknown")

        global_players_data_from_coord = manager_coordinator.data.get("global_players")
        if isinstance(global_players_data_from_coord, list):
            global_players_list_data = global_players_data_from_coord
        _LOGGER.debug(
            "Manager Info from Coordinator: OS=%s, Version=%s, Global Players=%d",
            manager_os_type,
            manager_app_version,
            len(global_players_list_data),
        )
    else:
        _LOGGER.warning(
            "ManagerDataCoordinator initial update failed or returned no data. Using defaults for manager info."
        )

    # --- Create the Central "Manager" Device ---
    manager_host_port_id = f"{host}:{port}"
    manager_identifier = (DOMAIN, manager_host_port_id)
    device_registry = dr.async_get(hass)
    manager_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={manager_identifier},
        name=f"BSM @ {host}",
        manufacturer="Bedrock Server Manager",
        model=f"BSM-{manager_os_type.upper()}",
        sw_version=manager_app_version,
        configuration_url=f"http://{host}:{port}",
    )
    _LOGGER.debug(
        "Ensured manager device exists: ID=%s, Identifier=%s",
        manager_device.id,
        manager_identifier,
    )

    # --- Store API Client, Manager Coordinator, and other essential data ---
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api_client,
        "manager_identifier": manager_identifier,
        "manager_coordinator": manager_coordinator,  # Store the manager coordinator
        "manager_os_type": manager_os_type,
        "manager_app_version": manager_app_version,
        "global_players_list": global_players_list_data,  # Initial list for sensor setup
        "servers": {},  # For server-specific coordinators
    }

    # --- Create Server-Specific Coordinators ---
    if not selected_servers:
        _LOGGER.warning(
            "No servers selected for manager %s. Integration will load but monitor no individual servers.",
            manager_host_port_id,
        )
    else:
        _LOGGER.info("Setting up server coordinators for: %s", selected_servers)
        setup_tasks = []
        for server_name in selected_servers:
            setup_tasks.append(
                _async_setup_server_coordinator(
                    hass, entry, api_client, server_name, server_scan_interval
                )
            )
        results = await asyncio.gather(*setup_tasks, return_exceptions=True)

        successful_setups = 0
        for i, result in enumerate(results):
            server_name = selected_servers[i]
            if isinstance(result, Exception):
                log_msg = (
                    f"Failed to set up coordinator for server '{server_name}': {result}"
                )
                if not isinstance(
                    result,
                    (
                        ConfigEntryAuthFailed,
                        ConfigEntryNotReady,
                        HomeAssistantError,
                        APIError,
                    ),
                ):
                    _LOGGER.error(
                        log_msg + "\n%s", traceback.format_exc(), exc_info=False
                    )
                else:
                    _LOGGER.error(log_msg, exc_info=False)
                if server_name in hass.data[DOMAIN][entry.entry_id]["servers"]:
                    del hass.data[DOMAIN][entry.entry_id]["servers"][server_name]
            else:
                successful_setups += 1

        if successful_setups == 0 and selected_servers:
            _LOGGER.error(
                "All server coordinator setups failed for manager %s.",
                manager_host_port_id,
            )
            # Do not pop hass.data[DOMAIN][entry.entry_id] here, as manager_coordinator might be valid
            raise ConfigEntryNotReady(
                f"Could not initialize any selected server for manager {manager_host_port_id}"
            )

    # --- Forward Setup to Platforms ---
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # --- Add listener for options flow updates ---
    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    # --- Register Services (only once per domain) ---
    await services.async_register_services(hass)

    return True


async def _async_setup_server_coordinator(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api_client: BedrockServerManagerApi,
    server_name: str,
    scan_interval: int,
):
    """Helper function to set up coordinator for a single server."""
    _LOGGER.debug("Setting up server coordinator for: %s", server_name)
    # Use the renamed MinecraftBedrockServerCoordinator
    coordinator = MinecraftBedrockCoordinator(
        hass=hass,
        api_client=api_client,
        server_name=server_name,
        scan_interval=scan_interval,
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id].setdefault("servers", {})
    hass.data[DOMAIN][entry.entry_id]["servers"][server_name] = {
        "coordinator": coordinator,
        # Static info can be stored here by platforms if needed after first fetch
        # "world_name": None, "installed_version": None
    }
    _LOGGER.debug("Successfully set up server coordinator for: %s", server_name)


async def options_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    _LOGGER.debug(
        "Options updated for %s, reloading entry to apply changes.", entry.entry_id
    )
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
        entry_data = hass.data[DOMAIN].pop(
            entry.entry_id, None
        )  # Remove entry's data safely

        # --- Unregister Frontend ---
        if entry_data and "frontend_registrar" in entry_data:
            registrar: BsmFrontendRegistration = entry_data["frontend_registrar"]
            try:
                await registrar.async_unregister()
            except Exception as e:
                _LOGGER.error(
                    "Failed during frontend module unregistration: %s", e, exc_info=True
                )
        # --- End Unregister ---

        if entry_data:
            _LOGGER.debug(
                "Successfully removed data for entry %s (%s)",
                entry.entry_id,
                manager_host,
            )
        else:
            _LOGGER.debug(
                "No data found in hass.data for entry %s (%s) during unload.",
                entry.entry_id,
                manager_host,
            )

        # --- Remove services if this was the last entry ---
        # Check if the domain key itself is now empty or gone
        if not hass.data.get(DOMAIN):
            await services.async_remove_services(hass)
        else:
            _LOGGER.debug(
                "Other entries still loaded for domain %s, keeping services", DOMAIN
            )

    return unload_ok
