# custom_components/bedrock_server_manager/__init__.py
"""The Bedrock Server Manager integration."""

import asyncio
import logging
from typing import Any

from bsm_api_client import (
    APIError,
    AuthError,
    BedrockServerManagerApi,
    CannotConnectError,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import services
from .const import (
    CONF_BASE_URL,
    CONF_SERVER_NAMES,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import (
    ApplicationMonitorCoordinator,
    ManagerDataCoordinator,
    MinecraftBedrockCoordinator,
)
from .frontend import BsmFrontendRegistration
from .websocket import MANAGER_EVENTS, SERVER_EVENTS, BsmWebSocketManager

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an entry and release owned resources if any setup stage fails."""
    try:
        return await _async_setup_entry(hass, entry)
    except (Exception, asyncio.CancelledError):
        entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
        if entry_data.get("platforms_started"):
            try:
                await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
            except Exception:
                _LOGGER.exception("Error unloading partially set up BSM platforms")
        await _async_cleanup_entry(hass, entry)
        raise


async def _async_setup_entry(  # noqa: C901
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up Bedrock Server Manager from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {})

    # Frontend Registration
    frontend_registrar = hass.data.setdefault(
        f"{DOMAIN}_frontend", BsmFrontendRegistration(hass)
    )
    try:
        await frontend_registrar.async_register()
        hass.data[DOMAIN][entry.entry_id]["frontend_registrar"] = frontend_registrar
        _LOGGER.debug("BSM Frontend module registered.")
    except Exception as e:
        _LOGGER.error(
            "Failed during frontend module registration: %s", e, exc_info=True
        )
        # Continue setup even if frontend registration fails

    # --- API Client Setup ---
    url = entry.data[CONF_BASE_URL]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, True)

    api_client = BedrockServerManagerApi(
        base_url=url,
        username=username,
        password=password,
        verify_ssl=verify_ssl,
        session=async_get_clientsession(hass, verify_ssl=verify_ssl),
    )
    hass.data[DOMAIN][entry.entry_id]["api"] = api_client
    _LOGGER.debug(
        "BedrockServerManagerApi client initialized for %s (Verify SSL: %s)",
        url,
        verify_ssl,
    )
    # --- End of API Client Setup Modification ---

    # Manager Data Coordinator Setup
    manager_scan_interval = entry.options.get(
        "manager_scan_interval", 600  # Default to 10 minutes for manager-level data
    )
    manager_coordinator = ManagerDataCoordinator(
        hass=hass,
        api_client=api_client,
        scan_interval=manager_scan_interval,
        config_entry=entry,
    )

    hass.data[DOMAIN][entry.entry_id]["manager_coordinator"] = manager_coordinator
    try:
        await manager_coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        raise
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
    except Exception as err:
        _LOGGER.exception(
            "Unexpected error during ManagerDataCoordinator initial refresh"
        )
        raise ConfigEntryNotReady(
            f"Unexpected error initializing manager data: {err}"
        ) from err

    monitor_coordinator = ApplicationMonitorCoordinator(
        hass,
        api_client,
        entry.options.get("monitor_scan_interval", 30),
        config_entry=entry,
    )
    hass.data[DOMAIN][entry.entry_id]["monitor_coordinator"] = monitor_coordinator
    await monitor_coordinator.async_config_entry_first_refresh()

    manager_os_type = "Unknown"
    manager_app_version = "Unknown"
    if manager_coordinator.last_update_success and manager_coordinator.data:
        manager_info_payload = manager_coordinator.data.get("info")
        if isinstance(manager_info_payload, dict):
            manager_os_type = str(
                manager_info_payload.get("os_type") or "Unknown"
            ).lower()
            manager_app_version = manager_info_payload.get("app_version", "Unknown")
    else:
        _LOGGER.warning(
            "ManagerDataCoordinator initial update failed or returned no data. "
            "Manager-level entities and device info might be incomplete."
        )

    # --- Manager Device Registration ---
    manager_identifier_tuple = (DOMAIN, url)

    device_registry = dr.async_get(hass)
    configuration_url_for_device = url

    manager_device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={manager_identifier_tuple},  # Uses sanitized ID in tuple
        name=f"BSM @ {url}",  # Display name can use the sanitized ID
        manufacturer="DMedina559",
        model=f"{manager_os_type.capitalize() if manager_os_type != 'unknown' else 'Unknown OS'}",
        sw_version=manager_app_version,
        configuration_url=configuration_url_for_device,  # Use the carefully constructed URL
    )
    _LOGGER.debug(
        "Ensured manager device exists: ID=%s for identifier %s",
        manager_device_entry.id,
        url,  # Log the sanitized version
    )
    # --- End of Manager Device Registration Modification ---

    hass.data[DOMAIN][entry.entry_id].update(
        {
            "manager_identifier": manager_identifier_tuple,
            "manager_device_id": manager_device_entry.id,
            "manager_coordinator": manager_coordinator,
            "manager_os_type": manager_os_type,
            "manager_app_version": manager_app_version,
            "servers": {},
        }
    )

    selected_servers = entry.options.get(CONF_SERVER_NAMES, [])
    server_scan_interval = entry.options.get(
        "scan_interval", DEFAULT_SCAN_INTERVAL_SECONDS
    )

    if not selected_servers:
        _LOGGER.info(
            "No Minecraft servers selected for manager %s. Only manager-level entities will be created.",
            url,
        )
    else:
        _LOGGER.info(
            "Attempting to set up server coordinators for manager %s, selected servers: %s",
            url,
            selected_servers,
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
                if isinstance(result, ConfigEntryAuthFailed):
                    raise result
                elif isinstance(result, AuthError):
                    raise ConfigEntryAuthFailed(str(result)) from result
                elif isinstance(result, ConfigEntryNotReady):
                    _LOGGER.error(
                        "Coordinator for server '%s' not ready: %s",
                        server_name,
                        result,
                        exc_info=result,
                    )
                elif isinstance(result, (AuthError, CannotConnectError, APIError)):
                    _LOGGER.error(
                        "API/Connection error setting up coordinator for server '%s': %s",
                        server_name,
                        result,
                        exc_info=result,
                    )
                else:
                    _LOGGER.error(
                        "Unexpected error setting up coordinator for server '%s': %s",
                        server_name,
                        result,
                        exc_info=result,
                    )
            else:
                successful_setups += 1

        if selected_servers and successful_setups == 0 and len(selected_servers) > 0:
            _LOGGER.warning(
                "All %d selected Minecraft server coordinator(s) failed to set up for manager %s. "
                "Problematic server(s) will not have entities.",
                len(selected_servers),
                url,
            )
        elif selected_servers and successful_setups < len(selected_servers):
            failed_count = len(selected_servers) - successful_setups
            _LOGGER.warning(
                "%d of %d selected Minecraft server coordinator(s) failed to set up for manager %s. "
                "Problematic server(s) will not have entities.",
                failed_count,
                len(selected_servers),
                url,
            )
        elif selected_servers and successful_setups == len(
            selected_servers
        ):  # All selected servers set up successfully
            _LOGGER.info(
                "All %d selected server coordinators set up successfully for manager %s.",
                successful_setups,
                url,
            )

    def _ws_refresh(topic, data):
        """Invalidate affected resources and coalesce refreshes through coordinators."""
        entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if not entry_data:
            return
        event = topic.removeprefix("event:")
        all_servers = topic == "reconnect" or topic.startswith("task:")
        if all_servers or event == "after_setting_update":
            if monitor_coordinator.invalidate(data):
                hass.async_create_task(monitor_coordinator.async_request_refresh())
        if all_servers or event in MANAGER_EVENTS:
            if manager_coordinator.invalidate(data):
                hass.async_create_task(manager_coordinator.async_request_refresh())
        if all_servers or event in SERVER_EVENTS:
            result = data.get("result") or {}
            name = data.get("server_name") or (
                result.get("server_name") if isinstance(result, dict) else None
            )
            for server_name, server_data in entry_data["servers"].items():
                if all_servers or name == server_name:
                    coordinator = server_data["coordinator"]
                    if coordinator.invalidate(data):
                        hass.async_create_task(coordinator.async_request_refresh())

    def _ws_process(server_name, payload):
        """Apply process snapshots to their selected server only."""
        entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
        server_data = entry_data.get("servers", {}).get(server_name)
        if server_data:
            server_data["coordinator"].update_process_info(payload)

    ws_manager = BsmWebSocketManager(
        hass,
        api_client,
        _ws_refresh,
        _ws_process,
        selected_servers,
        url,
        monitor_coordinator.update_metrics,
        monitor_coordinator.set_websocket_connected,
    )
    hass.data[DOMAIN][entry.entry_id]["ws_manager"] = ws_manager

    hass.data[DOMAIN][entry.entry_id]["platforms_started"] = True
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    if not hass.data[DOMAIN].get("_services_registered"):
        await services.async_register_services(hass)
        hass.data[DOMAIN]["_services_registered"] = True
        _LOGGER.debug("Integration services registered.")

    await ws_manager.async_start()
    return True


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
        config_entry=entry,
    )
    hass.data[DOMAIN][entry.entry_id].setdefault("servers", {})[server_name] = {
        "coordinator": coordinator
    }
    try:
        await coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id].setdefault("servers", {})
        hass.data[DOMAIN][entry.entry_id]["servers"][server_name] = {
            "coordinator": coordinator
        }
        _LOGGER.info(
            "Successfully set up and refreshed coordinator for server: %s", server_name
        )
    except Exception as err:
        _LOGGER.debug(
            "Initial refresh failed for server '%s' coordinator: %s (%s)",
            server_name,
            type(err).__name__,
            err,
        )
        raise


async def options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug(
        "Options updated for entry %s, reloading integration.", entry.entry_id
    )
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_cleanup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Release runtime resources without removing shared dashboard modules."""
    domain_data = hass.data.get(DOMAIN, {})
    entry_data = domain_data.get(entry.entry_id, {})
    start_task = entry_data.get("ws_start_task")
    if start_task:
        start_task.cancel()
        await asyncio.gather(start_task, return_exceptions=True)
    cleanup_calls = []
    if ws_manager := entry_data.get("ws_manager"):
        cleanup_calls.append(ws_manager.async_stop())
    coordinators = [
        entry_data.get("manager_coordinator"),
        entry_data.get("monitor_coordinator"),
    ]
    coordinators.extend(
        server.get("coordinator") for server in entry_data.get("servers", {}).values()
    )
    for coordinator in coordinators:
        if coordinator is not None:
            cleanup_calls.append(coordinator.async_shutdown())
    # Stop the WebSocket before closing the API that it uses.
    await _async_finish_cleanup(cleanup_calls)
    if api := entry_data.get("api"):
        try:
            await api.close()
        except Exception:
            _LOGGER.exception("Error closing BSM API client")
    await _async_remove_entry_resources(hass, entry, domain_data)


async def _async_finish_cleanup(cleanup_calls) -> None:
    """Await all owned workers while keeping cleanup failures isolated."""
    results = await asyncio.gather(*cleanup_calls, return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            _LOGGER.warning("Error cleaning up BSM runtime: %s", result)


async def _async_remove_entry_resources(
    hass: HomeAssistant, entry: ConfigEntry, domain_data: dict[str, Any]
) -> None:
    """Remove entry bookkeeping and release shared services after the last entry."""
    domain_data.pop(entry.entry_id, None)
    if not any(not key.startswith("_") for key in domain_data):
        if domain_data.get("_services_registered"):
            await services.async_remove_services(hass)
        hass.data.pop(DOMAIN, None)
        if frontend := hass.data.get(f"{DOMAIN}_frontend"):
            await frontend.async_unregister()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload platforms before releasing the entry's runtime resources."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await _async_cleanup_entry(hass, entry)
    return True
