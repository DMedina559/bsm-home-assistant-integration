# custom_components/bedrock_server_manager/__init__.py
"""The Bedrock Server Manager integration."""

import asyncio
import logging
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from bsm_api_client import (
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
    CONF_VERIFY_SSL,
    CONF_BASE_URL,
)
from .coordinator import MinecraftBedrockCoordinator, ManagerDataCoordinator
from . import services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Set up Bedrock Server Manager from a config entry.

    This function initializes the API client, sets up data coordinators for the
    manager and selected servers, registers devices, and forwards the setup to
    the relevant platforms (sensor, switch, etc.).
    """
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    # Register frontend modules
    frontend_registrar = BsmFrontendRegistration(hass)
    try:
        await frontend_registrar.async_register()
        hass.data[DOMAIN][entry.entry_id]["frontend_registrar"] = frontend_registrar
        _LOGGER.debug("BSM Frontend module registered.")
    except Exception as e:
        _LOGGER.error(
            "Failed during frontend module registration: %s", e, exc_info=True
        )

    # --- API Client Setup ---
    url = entry.data[CONF_BASE_URL]
    api_client = BedrockServerManagerApi(
        base_url=url,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, True),
    )
    hass.data[DOMAIN][entry.entry_id]["api"] = api_client
    _LOGGER.debug("BedrockServerManagerApi client initialized for %s", url)

    # --- Manager Data Coordinator Setup ---
    manager_scan_interval = entry.options.get("manager_scan_interval", 600)
    manager_coordinator = ManagerDataCoordinator(
        hass=hass, api_client=api_client, scan_interval=manager_scan_interval
    )
    try:
        await manager_coordinator.async_config_entry_first_refresh()
    except AuthError as err:
        _LOGGER.error("Authentication failed for ManagerDataCoordinator: %s", err)
        raise ConfigEntryAuthFailed(
            f"Authentication failed: {err.api_message or err}"
        ) from err
    except (CannotConnectError, APIError) as err:
        _LOGGER.error("Initial refresh failed for ManagerDataCoordinator: %s", err)
        raise ConfigEntryNotReady(
            f"Failed to initialize manager data coordinator: {err.api_message or err}"
        ) from err

    # Extract manager info for device registration
    manager_os_type = "Unknown"
    manager_app_version = "Unknown"
    if manager_coordinator.last_update_success and manager_coordinator.data:
        info = manager_coordinator.data.get("info", {})
        manager_os_type = info.get("os_type", "Unknown").lower()
        manager_app_version = info.get("app_version", "Unknown")
    else:
        _LOGGER.warning(
            "ManagerDataCoordinator initial update failed; device info may be incomplete."
        )

    # --- Manager Device Registration ---
    manager_identifier = (DOMAIN, url)
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={manager_identifier},
        name=f"BSM @ {url}",
        manufacturer="DMedina559",
        model=f"{manager_os_type.capitalize() if manager_os_type != 'unknown' else 'Unknown OS'}",
        sw_version=manager_app_version,
        configuration_url=url,
    )

    hass.data[DOMAIN][entry.entry_id].update(
        {
            "manager_identifier": manager_identifier,
            "manager_coordinator": manager_coordinator,
            "manager_os_type": manager_os_type,
            "servers": {},
        }
    )

    # --- Server-Specific Setup ---
    selected_servers = entry.options.get(CONF_SERVER_NAMES, [])
    if selected_servers:
        await _async_setup_servers(hass, entry, api_client, selected_servers)

    # --- Finalize Setup ---
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    if not hass.data[DOMAIN].get("_services_registered"):
        await services.async_register_services(hass)
        hass.data[DOMAIN]["_services_registered"] = True
        _LOGGER.debug("Integration services registered.")

    return True


async def _async_setup_servers(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api_client: BedrockServerManagerApi,
    server_names: list[str],
):
    """Set up coordinators and static data for each selected server."""
    _LOGGER.info("Setting up coordinators for servers: %s", server_names)
    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL_SECONDS)

    setup_tasks = [
        _async_setup_server_coordinator(hass, entry, api_client, name, scan_interval)
        for name in server_names
    ]
    results = await asyncio.gather(*setup_tasks, return_exceptions=True)

    successful_setups = 0
    for i, result in enumerate(results):
        server_name = server_names[i]
        if isinstance(result, Exception):
            _LOGGER.error(
                "Failed to set up coordinator for server '%s': %s",
                server_name,
                result,
                exc_info=result,
            )
            # Clean up partially created data if setup fails
            if server_name in hass.data[DOMAIN][entry.entry_id].get("servers", {}):
                del hass.data[DOMAIN][entry.entry_id]["servers"][server_name]
        else:
            successful_setups += 1

    if successful_setups < len(server_names):
        failed_count = len(server_names) - successful_setups
        _LOGGER.warning(
            "%d of %d server coordinator(s) failed to set up.",
            failed_count,
            len(server_names),
        )


async def _async_setup_server_coordinator(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api_client: BedrockServerManagerApi,
    server_name: str,
    scan_interval: int,
) -> None:
    """Helper to set up and refresh a coordinator for a single Minecraft server."""
    _LOGGER.debug("Setting up MinecraftBedrockCoordinator for server: %s", server_name)
    coordinator = MinecraftBedrockCoordinator(
        hass=hass,
        api_client=api_client,
        server_name=server_name,
        scan_interval=scan_interval,
    )
    try:
        await coordinator.async_config_entry_first_refresh()

        # Fetch static data once and store it
        version_res = await api_client.async_get_server_version(server_name)
        properties_res = await api_client.async_get_server_properties(server_name)

        server_data = {
            "coordinator": coordinator,
            "installed_version": (
                version_res.data.get("version")
                if hasattr(version_res, "data") and version_res.data
                else None
            ),
            "world_name": (
                properties_res.properties.get("level-name")
                if hasattr(properties_res, "properties") and properties_res.properties
                else None
            ),
        }

        hass.data[DOMAIN][entry.entry_id].setdefault("servers", {})
        hass.data[DOMAIN][entry.entry_id]["servers"][server_name] = server_data
        _LOGGER.info("Successfully set up coordinator for server: %s", server_name)
    except Exception as err:
        _LOGGER.warning(
            "Initial refresh failed for server '%s' coordinator, it will be ignored: %s",
            server_name,
            err,
        )
        raise


async def options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading the integration."""
    _LOGGER.debug(
        "Options updated for entry %s, reloading integration.", entry.entry_id
    )
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Unload a config entry.

    This function unloads the integration's platforms, cleans up hass.data,
    unregisters frontend modules, and removes services if it's the last entry.
    """
    url_for_unload = entry.data.get(CONF_BASE_URL, "Unknown")
    _LOGGER.info("Unloading BSM entry for manager '%s'", url_for_unload)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if entry_data:
            # Unregister frontend resources
            if frontend_registrar := entry_data.get("frontend_registrar"):
                try:
                    await frontend_registrar.async_unregister()
                    _LOGGER.debug(
                        "BSM Frontend module unregistered for %s.", url_for_unload
                    )
                except Exception as e:
                    _LOGGER.error(
                        "Error during frontend unregistration: %s", e, exc_info=True
                    )

        # Check if this is the last BSM entry being unloaded
        active_bsm_entries = [
            e for e in hass.data.get(DOMAIN, {}) if e != "_services_registered"
        ]
        if not active_bsm_entries:
            _LOGGER.info("No active BSM config entries remain. Removing services.")
            if hass.data.get(DOMAIN, {}).get("_services_registered"):
                await services.async_remove_services(hass)
            hass.data.pop(DOMAIN, None)
        else:
            _LOGGER.debug(
                "%d BSM config entries still loaded. Services will be kept.",
                len(active_bsm_entries),
            )

    return unload_ok
