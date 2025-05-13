# custom_components/bedrock_server_manager/__init__.py
"""The Bedrock Server Manager integration."""

import asyncio
import logging
from datetime import timedelta
import traceback

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
    HomeAssistantError,
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
    except Exception as err:
        _LOGGER.exception(
            "Unexpected error during ManagerDataCoordinator initial refresh"
        )
        raise ConfigEntryNotReady(
            f"Unexpected error initializing manager data: {err}"
        ) from err

    manager_os_type = "Unknown"
    manager_app_version = "Unknown"
    global_players_list_data = []
    if manager_coordinator.last_update_success and manager_coordinator.data:
        manager_info_data = manager_coordinator.data.get("info")
        if isinstance(manager_info_data, dict):
            manager_os_type = manager_info_data.get("os_type", "Unknown").lower()
            manager_app_version = manager_info_data.get("app_version", "Unknown")
        global_players_data_from_coord = manager_coordinator.data.get("global_players")
        if isinstance(global_players_data_from_coord, list):
            global_players_list_data = global_players_data_from_coord
        _LOGGER.debug(
            "Manager Info: OS=%s, Version=%s, Global Players=%d",
            manager_os_type,
            manager_app_version,
            len(global_players_list_data),
        )
    else:
        _LOGGER.warning(
            "ManagerDataCoordinator initial update failed or returned no data."
        )

    manager_host_port_id = f"{host}:{port}"
    manager_identifier = (DOMAIN, manager_host_port_id)
    device_registry_instance = dr.async_get(hass)  # Renamed variable
    manager_device = device_registry_instance.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={manager_identifier},
        name=f"BSM @ {host}",
        manufacturer="Bedrock Server Manager",
        model=f"BSM-{manager_os_type.upper()}",
        sw_version=manager_app_version,
        configuration_url=f"http://{host}:{port}",
    )
    _LOGGER.debug("Ensured manager device exists: ID=%s", manager_device.id)

    hass.data[DOMAIN][entry.entry_id].update(
        {
            "manager_identifier": manager_identifier,
            "manager_coordinator": manager_coordinator,
            "manager_os_type": manager_os_type,
            "manager_app_version": manager_app_version,
            "global_players_list": global_players_list_data,
            "servers": {},
        }
    )

    if not selected_servers:
        _LOGGER.warning("No servers selected for manager %s.", manager_host_port_id)
    else:
        _LOGGER.info("Setting up server coordinators for: %s", selected_servers)
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
                if isinstance(result, AuthError):
                    _LOGGER.error(
                        "Auth failed setting up server '%s': %s", server_name, result
                    )
                    raise ConfigEntryAuthFailed(
                        f"Auth failed for server '{server_name}': {result}"
                    ) from result
                elif isinstance(
                    result, (CannotConnectError, APIError, ConfigEntryNotReady)
                ):
                    _LOGGER.error(
                        "Failed to set up coordinator for server '%s': %s",
                        server_name,
                        result,
                    )
                else:
                    _LOGGER.error(
                        "Unexpected error for server '%s': %s\n%s",
                        server_name,
                        result,
                        traceback.format_exc(),
                        exc_info=False,
                    )
                if server_name in hass.data[DOMAIN][entry.entry_id].get("servers", {}):
                    del hass.data[DOMAIN][entry.entry_id]["servers"][server_name]
            else:
                successful_setups += 1
        if successful_setups == 0 and selected_servers:
            _LOGGER.error(
                "All selected server coordinator setups failed for manager %s.",
                manager_host_port_id,
            )
            raise ConfigEntryNotReady(
                f"Could not initialize any selected server for manager {manager_host_port_id}"
            )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    # Simplified service registration check
    if not hass.data[DOMAIN].get("_services_registered"):
        await services.async_register_services(hass)
        hass.data[DOMAIN]["_services_registered"] = True  # Mark as registered

    return True


async def _async_setup_server_coordinator(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api_client: BedrockServerManagerApi,
    server_name: str,
    scan_interval: int,
):
    _LOGGER.debug("Setting up server coordinator for: %s", server_name)
    coordinator = MinecraftBedrockCoordinator(
        hass=hass,
        api_client=api_client,
        server_name=server_name,
        scan_interval=scan_interval,
    )
    try:
        await coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id].setdefault("servers", {})
        hass.data[DOMAIN][entry.entry_id]["servers"][server_name] = {
            "coordinator": coordinator
        }
        _LOGGER.debug("Successfully set up server coordinator for: %s", server_name)
    except Exception as err:
        _LOGGER.error(
            "Error during initial refresh for server '%s': %s", server_name, err
        )
        raise


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
        else:
            _LOGGER.debug(
                "No data found for entry %s (%s) during unload.",
                entry.entry_id,
                manager_host,
            )

        # Simplified service removal check
        if not any(
            hass.data[DOMAIN].get(eid)
            for eid in hass.data[DOMAIN]
            if eid != "_services_registered"
        ):
            await services.async_remove_services(hass)
            hass.data[DOMAIN].pop("_services_registered", None)  # Clear flag
        else:
            _LOGGER.debug(
                "Other entries still loaded for domain %s, keeping services.", DOMAIN
            )
    return unload_ok
