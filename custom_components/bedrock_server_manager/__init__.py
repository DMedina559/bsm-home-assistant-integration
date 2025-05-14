# custom_components/bedrock_server_manager/__init__.py
"""The Bedrock Server Manager integration."""

import asyncio
import logging
from datetime import timedelta

# import traceback # No longer explicitly needed for formatting if exc_info is used correctly

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
from homeassistant.helpers import device_registry as dr
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,  # Not directly used for raising in this file
)

from pybedrock_server_manager import (
    BedrockServerManagerApi,
    AuthError,
    CannotConnectError,
    APIError,
)

from .frontend import BsmFrontendRegistration
from .const import (
    DOMAIN,
    CONF_SERVER_NAMES,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    PLATFORMS,
)
from .coordinator import MinecraftBedrockCoordinator, ManagerDataCoordinator
from . import services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {})

    frontend_registrar = BsmFrontendRegistration(hass)
    try:
        await frontend_registrar.async_register()
        hass.data[DOMAIN][entry.entry_id]["frontend_registrar"] = frontend_registrar
    except Exception as e:
        _LOGGER.error(
            "Failed during frontend module registration: %s", e, exc_info=True
        )

    host = entry.data[CONF_HOST]
    port = int(entry.data[CONF_PORT])
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    selected_servers = entry.options.get(CONF_SERVER_NAMES, [])
    manager_scan_interval_options_key = "manager_scan_interval"
    server_scan_interval_options_key = "scan_interval"
    manager_scan_interval = entry.options.get(manager_scan_interval_options_key, 600)
    server_scan_interval = entry.options.get(
        server_scan_interval_options_key, DEFAULT_SCAN_INTERVAL_SECONDS
    )

    session = async_get_clientsession(hass)
    api_client = BedrockServerManagerApi(host, port, username, password, session)
    hass.data[DOMAIN][entry.entry_id]["api"] = api_client

    manager_coordinator = ManagerDataCoordinator(
        hass=hass, api_client=api_client, scan_interval=manager_scan_interval
    )
    try:
        await manager_coordinator.async_config_entry_first_refresh()
    except AuthError as err:
        _LOGGER.error("Authentication failed for ManagerDataCoordinator: %s", err)
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
    except (CannotConnectError, APIError) as err:
        _LOGGER.error("Failed initial refresh for ManagerDataCoordinator: %s", err)
        raise ConfigEntryNotReady(
            f"Failed to initialize manager data coordinator: {err}"
        ) from err
    except Exception as err:  # Catch any other unexpected errors
        _LOGGER.exception(
            "Unexpected error during ManagerDataCoordinator initial refresh"
        )
        raise ConfigEntryNotReady(
            f"Unexpected error initializing manager data: {err}"
        ) from err

    manager_os_type = "Unknown"
    manager_app_version = "Unknown"
    global_players_list_data_initial = []  # Renamed to clarify it's initial
    if manager_coordinator.last_update_success and manager_coordinator.data:
        manager_info_data = manager_coordinator.data.get("info")
        if isinstance(manager_info_data, dict):
            manager_os_type = manager_info_data.get("os_type", "Unknown").lower()
            manager_app_version = manager_info_data.get("app_version", "Unknown")
        # Global players data will be accessed directly from coordinator by platforms
        global_players_data_from_coord = manager_coordinator.data.get("global_players")
        if isinstance(global_players_data_from_coord, list):
            global_players_list_data_initial = global_players_data_from_coord
        _LOGGER.debug(
            "Manager Info: OS=%s, Version=%s, Global Players (initial count)=%d",
            manager_os_type,
            manager_app_version,
            len(global_players_list_data_initial),
        )
    else:
        _LOGGER.warning(
            "ManagerDataCoordinator initial update failed or returned no data. Manager-level entities might be affected."
        )

    manager_host_port_id = f"{host}:{port}"
    manager_identifier = (DOMAIN, manager_host_port_id)
    device_registry_instance = dr.async_get(hass)
    manager_device = device_registry_instance.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={manager_identifier},
        name=f"BSM @ {host}",
        manufacturer="Bedrock Server Manager",
        model=f"BSM-{manager_os_type.upper() if manager_os_type else 'UNKNOWN'}",
        sw_version=manager_app_version,
        configuration_url=f"http://{host}:{port}",
    )
    _LOGGER.debug("Ensured manager device exists: ID=%s", manager_device.id)

    hass.data[DOMAIN][entry.entry_id].update(
        {
            "manager_identifier": manager_identifier,
            "manager_coordinator": manager_coordinator,
            "manager_os_type": manager_os_type,  # For services.py logic, might be useful
            "manager_app_version": manager_app_version,  # For device info
            # "global_players_list": global_players_list_data_initial, # Platforms should use coordinator.data
            "servers": {},  # Will be populated with successful server coordinators
        }
    )

    if not selected_servers:
        _LOGGER.warning(
            "No Minecraft servers selected in options for manager %s.",
            manager_host_port_id,
        )
    else:
        _LOGGER.info(
            "Attempting to set up server coordinators for: %s", selected_servers
        )
        setup_tasks = [
            _async_setup_server_coordinator(
                hass, entry, api_client, server_name, server_scan_interval
            )
            for server_name in selected_servers
        ]
        results = await asyncio.gather(*setup_tasks, return_exceptions=True)
        successful_setups = 0
        for i, result in enumerate(results):
            server_name = selected_servers[i]
            if isinstance(result, Exception):
                # Log specific errors for each failed server
                # AuthError for a specific server is unlikely if manager auth passed, but log if it occurs
                if isinstance(result, AuthError):
                    _LOGGER.error(
                        "Authentication error during setup for server '%s': %s. "
                        "This is unexpected if manager authentication succeeded.",
                        server_name,
                        result,
                        exc_info=result,
                    )
                elif isinstance(result, (CannotConnectError, APIError)):
                    _LOGGER.error(
                        "API or Connection error setting up coordinator for server '%s': %s",
                        server_name,
                        result,
                        exc_info=result,  # exc_info=result provides full traceback
                    )
                elif isinstance(
                    result, ConfigEntryNotReady
                ):  # Can be raised by coordinator's own refresh
                    _LOGGER.error(
                        "Coordinator for server '%s' reported not ready: %s",
                        server_name,
                        result,
                        exc_info=result,
                    )
                else:  # Other unexpected errors
                    _LOGGER.error(
                        "Unexpected error setting up coordinator for server '%s'",
                        server_name,
                        exc_info=result,  # Provides full traceback of the original exception
                    )
                # Ensure failed server's partial data (if any) is cleaned up
                if server_name in hass.data[DOMAIN][entry.entry_id].get("servers", {}):
                    del hass.data[DOMAIN][entry.entry_id]["servers"][server_name]
            else:
                successful_setups += 1

        # If all *selected* servers failed to set up, log an error.
        # However, DO NOT raise ConfigEntryNotReady here if ManagerDataCoordinator is okay.
        # The manager part of the integration should still load.
        if selected_servers and successful_setups == 0:
            _LOGGER.error(
                "All selected Minecraft server coordinator setups failed for manager %s. "
                "The manager device and its global entities should still load if the manager is reachable. "
                "Server-specific entities will not be available. "
                "Check Minecraft server configurations on the BSM host or update integration options in Home Assistant.",
                manager_host_port_id,
            )
        elif selected_servers and successful_setups < len(selected_servers):
            _LOGGER.warning(
                "%d of %d selected Minecraft server coordinators failed to set up for manager %s. "
                "Problematic servers will not have entities.",
                len(selected_servers) - successful_setups,
                len(selected_servers),
                manager_host_port_id,
            )

    # Proceed to load platforms. Platforms will check for available coordinators.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    if not hass.data[DOMAIN].get("_services_registered"):
        await services.async_register_services(hass)
        hass.data[DOMAIN]["_services_registered"] = True

    return True


async def _async_setup_server_coordinator(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api_client: BedrockServerManagerApi,
    server_name: str,
    scan_interval: int,
):
    _LOGGER.debug("Setting up MinecraftBedrockCoordinator for server: %s", server_name)
    coordinator = MinecraftBedrockCoordinator(
        hass=hass,
        api_client=api_client,
        server_name=server_name,
        scan_interval=scan_interval,
    )
    try:
        # This first refresh can fail if server is deleted (APIError) or other issues
        await coordinator.async_config_entry_first_refresh()
        # Only add to hass.data if refresh was successful
        hass.data[DOMAIN][entry.entry_id].setdefault("servers", {})
        hass.data[DOMAIN][entry.entry_id]["servers"][server_name] = {
            "coordinator": coordinator
        }
        _LOGGER.debug(
            "Successfully set up and refreshed coordinator for server: %s", server_name
        )
    except Exception as err:
        # Do not log here as error, it will be logged by the caller with more context
        _LOGGER.debug(  # Changed to debug as caller will log the error
            "Initial refresh failed for server '%s' coordinator: %s", server_name, err
        )
        raise  # Re-raise to be caught by asyncio.gather in async_setup_entry


async def options_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.debug("Options updated for %s, reloading entry.", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    manager_host = entry.data.get(CONF_HOST, entry.entry_id)
    _LOGGER.info("Unloading Minecraft Manager entry for manager '%s'", manager_host)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if entry_data and "frontend_registrar" in entry_data:
            try:
                await entry_data["frontend_registrar"].async_unregister()
            except Exception as e:
                _LOGGER.error("Failed frontend unregistration: %s", e, exc_info=True)
        if entry_data:
            _LOGGER.debug(
                "Successfully removed data for entry %s (%s)",
                entry.entry_id,
                manager_host,
            )
        # Service removal logic remains the same
        active_bsm_entries = False
        for eid, data_val in hass.data[DOMAIN].items():
            if (
                eid != "_services_registered" and data_val
            ):  # Check if data_val is not empty
                active_bsm_entries = True
                break

        if not active_bsm_entries:
            _LOGGER.info("No active BSM entries remain, removing services.")
            await services.async_remove_services(hass)
            hass.data[DOMAIN].pop("_services_registered", None)
        else:
            _LOGGER.debug(
                "Other BSM entries still loaded for domain %s, keeping services.",
                DOMAIN,
            )

    return unload_ok
