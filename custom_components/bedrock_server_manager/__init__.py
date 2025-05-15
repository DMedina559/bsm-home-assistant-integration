# custom_components/bedrock_server_manager/__init__.py
"""The Bedrock Server Manager integration."""

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    Platform,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import device_registry as dr
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
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
    CONF_USE_SSL,
)
from .coordinator import MinecraftBedrockCoordinator, ManagerDataCoordinator
from . import services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bedrock Server Manager from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {})

    # Frontend Registration
    frontend_registrar = BsmFrontendRegistration(hass)
    try:
        await frontend_registrar.async_register()
        hass.data[DOMAIN][entry.entry_id]["frontend_registrar"] = frontend_registrar
        _LOGGER.debug("BSM Frontend module registered.")
    except Exception as e:  # pylint: disable=broad-except
        _LOGGER.error(
            "Failed during frontend module registration: %s", e, exc_info=True
        )
        # Continue setup even if frontend registration fails, as core functionality might still work

    # API Client Setup
    host = entry.data[CONF_HOST]
    port = int(entry.data[CONF_PORT])  # Ensure port is int
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    use_ssl = entry.data.get(CONF_USE_SSL, False)  # Get use_ssl, default to False

    session = async_get_clientsession(hass)
    api_client = BedrockServerManagerApi(
        host=host,
        port=port,
        username=username,
        password=password,
        session=session,  # Pass HA-managed session
        use_ssl=use_ssl,  # Pass SSL preference
    )
    hass.data[DOMAIN][entry.entry_id]["api"] = api_client
    _LOGGER.debug(
        "BedrockServerManagerApi client initialized for %s:%s (SSL: %s)",
        host,
        port,
        use_ssl,
    )

    # Manager Data Coordinator Setup
    manager_scan_interval = entry.options.get(
        "manager_scan_interval", 600  # Default to 10 minutes for manager-level data
    )
    manager_coordinator = ManagerDataCoordinator(
        hass=hass, api_client=api_client, scan_interval=manager_scan_interval
    )

    try:
        await manager_coordinator.async_config_entry_first_refresh()
    except AuthError as err:
        _LOGGER.error("Authentication failed for ManagerDataCoordinator: %s", err)
        # Optionally, include more detail from err.api_message or err.api_errors if available
        raise ConfigEntryAuthFailed(
            f"Authentication failed: {err.api_message or err}"
        ) from err
    except (
        CannotConnectError,
        APIError,
    ) as err:  # APIError will catch its children like APIServerSideError
        _LOGGER.error("Initial refresh failed for ManagerDataCoordinator: %s", err)
        raise ConfigEntryNotReady(
            f"Failed to initialize manager data coordinator: {err.api_message or err}"
        ) from err
    except Exception as err:  # Catch any other unexpected errors during initial setup
        _LOGGER.exception(  # Use .exception for full traceback automatically
            "Unexpected error during ManagerDataCoordinator initial refresh"
        )
        raise ConfigEntryNotReady(
            f"Unexpected error initializing manager data: {err}"
        ) from err

    # Extract manager info for device registration
    manager_os_type = "Unknown"
    manager_app_version = "Unknown"
    if manager_coordinator.last_update_success and manager_coordinator.data:
        # into self.data['info']
        manager_info_payload = manager_coordinator.data.get("info")
        if isinstance(manager_info_payload, dict):
            manager_os_type = manager_info_payload.get("os_type", "Unknown").lower()
            manager_app_version = manager_info_payload.get("app_version", "Unknown")

        # Log global players count from coordinator for debugging
        # global_players_from_coord = manager_coordinator.data.get("global_players", [])
        # _LOGGER.debug(
        #     "Manager Info: OS=%s, Version=%s, Global Players (from coord count)=%d",
        #     manager_os_type,
        #     manager_app_version,
        #     len(global_players_from_coord),
        # )
    else:
        _LOGGER.warning(
            "ManagerDataCoordinator initial update failed or returned no data. "
            "Manager-level entities and device info might be incomplete."
        )

    # Manager Device Registration
    manager_host_port_id = f"{host}:{port}"  # Unique ID for this BSM instance
    manager_identifier_tuple = (
        DOMAIN,
        manager_host_port_id,
    )  # Identifiers for HA device registry

    device_registry = dr.async_get(hass)
    manager_device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={manager_identifier_tuple},  # Must be a set of tuples
        name=f"Bedrock Server Manager @ {host}",  # User-friendly name
        manufacturer="Bedrock Server Manager",
        model=f"{manager_os_type.capitalize() if manager_os_type != 'unknown' else 'Unknown OS'}",
        sw_version=manager_app_version,
        configuration_url=f"{'https' if use_ssl else 'http'}://{host}:{port}",  # Link to BSM UI
    )
    _LOGGER.debug("Ensured manager device exists: ID=%s", manager_device_entry.id)

    # Store common data for platforms
    hass.data[DOMAIN][entry.entry_id].update(
        {
            "manager_identifier": manager_identifier_tuple,  # For entities to link to this device
            "manager_coordinator": manager_coordinator,
            "manager_os_type": manager_os_type,
            "manager_app_version": manager_app_version,
            "servers": {},  # To be populated by successful server coordinators
        }
    )

    # Server Coordinators Setup
    selected_servers = entry.options.get(CONF_SERVER_NAMES, [])
    server_scan_interval = entry.options.get(
        "scan_interval",
        DEFAULT_SCAN_INTERVAL_SECONDS,  # 'scan_interval' is for server-specific entities
    )

    if not selected_servers:
        _LOGGER.info(
            "No Minecraft servers selected in options for manager %s. Only manager-level entities will be created.",
            manager_host_port_id,
        )
    else:
        _LOGGER.info(
            "Attempting to set up server coordinators for selected servers: %s",
            selected_servers,
        )
        setup_tasks = [
            _async_setup_server_coordinator(
                hass, entry, api_client, server_name, server_scan_interval
            )
            for server_name in selected_servers
        ]
        # Gather results, allowing individual server setups to fail without stopping others
        results = await asyncio.gather(*setup_tasks, return_exceptions=True)

        successful_setups = 0
        for i, result in enumerate(results):
            server_name = selected_servers[i]
            if isinstance(result, Exception):
                # Detailed logging for each failed server setup
                if isinstance(
                    result, ConfigEntryAuthFailed
                ):  # Should not happen if manager auth passed
                    _LOGGER.error(
                        "Auth error setting up server '%s': %s",
                        server_name,
                        result,
                        exc_info=result,
                    )
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
                # Ensure failed server's partial data (if any) is cleaned up from hass.data
                # This check is important if _async_setup_server_coordinator might partially add data before failing
                if server_name in hass.data[DOMAIN][entry.entry_id].get("servers", {}):
                    del hass.data[DOMAIN][entry.entry_id]["servers"][server_name]
            else:  # No exception means success for this server
                successful_setups += 1

        if selected_servers and successful_setups < len(selected_servers):
            failed_count = len(selected_servers) - successful_setups
            _LOGGER.warning(
                "%d of %d selected Minecraft server coordinator(s) failed to set up for manager %s. "
                "Problematic server(s) will not have entities.",
                failed_count,
                len(selected_servers),
                manager_host_port_id,
            )
        elif not selected_servers:  # This case is already handled by the info log above
            pass
        else:  # All selected servers set up successfully
            _LOGGER.info(
                "All %d selected server coordinators set up successfully for manager %s.",
                successful_setups,
                manager_host_port_id,
            )

    # Forward entry setup to platforms (binary_sensor, sensor, switch, etc.)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Add update listener for options flow
    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    # Register services (idempotently)
    if not hass.data[DOMAIN].get("_services_registered"):
        await services.async_register_services(hass)
        hass.data[DOMAIN]["_services_registered"] = True
        _LOGGER.debug("Integration services registered.")

    return True


async def _async_setup_server_coordinator(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api_client: BedrockServerManagerApi,
    server_name: str,
    scan_interval: int,
) -> None:  # Return None on success, raise exception on failure
    """Helper to set up and refresh a coordinator for a single Minecraft server."""
    _LOGGER.debug("Setting up MinecraftBedrockCoordinator for server: %s", server_name)
    coordinator = MinecraftBedrockCoordinator(
        hass=hass,
        api_client=api_client,
        server_name=server_name,
        scan_interval=scan_interval,  # This is the server-specific scan interval
    )
    try:
        # Perform the first refresh. This can raise exceptions.
        await coordinator.async_config_entry_first_refresh()

        # If successful, store the coordinator.
        # Ensure "servers" dict exists before trying to add to it.
        hass.data[DOMAIN][entry.entry_id].setdefault("servers", {})
        hass.data[DOMAIN][entry.entry_id]["servers"][server_name] = {
            "coordinator": coordinator
            # You might add other server-specific static info here if needed by platforms
        }
        _LOGGER.info(  # Changed to info for successful setup
            "Successfully set up and refreshed coordinator for server: %s", server_name
        )
    except Exception as err:
        # Log at debug level as the caller (async_setup_entry) will log the error with more context.
        _LOGGER.debug(
            "Initial refresh failed for server '%s' coordinator: %s (%s)",
            server_name,
            type(err).__name__,
            err,
        )
        raise  # Re-raise to be caught by asyncio.gather in async_setup_entry


async def options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug(
        "Options updated for entry %s, reloading integration.", entry.entry_id
    )
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    manager_host_port_id = (
        f"{entry.data.get(CONF_HOST, 'UnknownHost')}:{entry.data.get(CONF_PORT, '0')}"
    )
    _LOGGER.info(
        "Unloading Bedrock Server Manager entry for manager '%s' (Entry ID: %s)",
        manager_host_port_id,
        entry.entry_id,
    )

    # Unload platforms (entities, etc.) linked to this config entry
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Remove this entry's specific data from hass.data[DOMAIN]
        domain_data = hass.data.get(DOMAIN)  # Get the domain's data dictionary
        entry_specific_data_popped = None
        if domain_data:
            entry_specific_data_popped = domain_data.pop(entry.entry_id, None)

        if entry_specific_data_popped:
            _LOGGER.debug(
                "Successfully removed data for entry %s (%s) from hass.data.%s",
                entry.entry_id,
                manager_host_port_id,
                DOMAIN,
            )
            # Unregister frontend if it was registered for this entry
            frontend_registrar = entry_specific_data_popped.get("frontend_registrar")
            if frontend_registrar:
                try:
                    await frontend_registrar.async_unregister()
                    _LOGGER.debug(
                        "BSM Frontend module unregistered for %s.", manager_host_port_id
                    )
                except Exception as e:  # pylint: disable=broad-except
                    _LOGGER.error(
                        "Error during frontend unregistration for %s: %s",
                        manager_host_port_id,
                        e,
                        exc_info=True,
                    )

            # Close the API client session if it was created by this entry and is managed
            # This assumes the api_client has a close method and was stored.
            # api_client_instance = entry_specific_data_popped.get("api")
            # if api_client_instance and hasattr(api_client_instance, "close"):
            # try:
            # await api_client_instance.close() # ClientBase already handles _close_session logic
            # _LOGGER.debug("Closed API client session for unloaded entry %s.", entry.entry_id)
            # except Exception as e:
            # _LOGGER.error("Error closing API client for entry %s: %s", entry.entry_id, e)
            # Note: If using HA's shared session, HA manages its lifecycle.
            # The client's close() method checks if it should close the session.

        else:  # entry_specific_data_popped was None
            _LOGGER.debug(
                "No specific data found in hass.data.%s for entry %s to pop. It might have been already cleaned up.",
                DOMAIN,
                entry.entry_id,
            )

        # Now, check if the DOMAIN key itself should be removed from hass.data
        # (i.e., if this was the last BSM entry)
        # Re-fetch domain_data as it might have been modified by the pop above
        current_domain_data = hass.data.get(DOMAIN)

        # Count remaining actual config entries (excluding internal keys like '_services_registered')
        active_bsm_config_entries_count = 0
        if current_domain_data:
            active_bsm_config_entries_count = sum(
                1 for key in current_domain_data if key != "_services_registered"
            )

        if active_bsm_config_entries_count == 0:
            _LOGGER.info(
                "No active BSM config entries remain after unloading %s. "
                "Proceeding to remove services and domain data.",
                entry.entry_id,
            )
            # Remove services only if they were registered and no other entries exist
            if current_domain_data and current_domain_data.get("_services_registered"):
                await services.async_remove_services(
                    hass
                )  # This function should also be robust
                current_domain_data.pop(
                    "_services_registered", None
                )  # Clean up the flag

            # If the domain_data dictionary is now empty (only had _services_registered or nothing), remove it.
            if (
                current_domain_data and not current_domain_data
            ):  # Checks if dict is empty
                _LOGGER.debug("Popping empty %s dictionary from hass.data.", DOMAIN)
                hass.data.pop(DOMAIN, None)
            elif not current_domain_data:  # Domain data was already gone
                _LOGGER.debug(
                    "%s dictionary already removed from hass.data or was never created.",
                    DOMAIN,
                )

        else:
            _LOGGER.debug(
                "%d BSM config entries still loaded for domain %s. Services will be kept.",
                active_bsm_config_entries_count,
                DOMAIN,
            )
    else:  # unload_ok is False
        _LOGGER.error(
            "Failed to unload platforms for BSM entry %s. Data and services will not be fully cleaned up.",
            entry.entry_id,
        )

    return unload_ok
