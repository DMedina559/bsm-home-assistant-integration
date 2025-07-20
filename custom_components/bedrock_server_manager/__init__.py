# custom_components/bedrock_server_manager/__init__.py
"""The Bedrock Server Manager integration."""

import asyncio
import logging
from typing import Optional  # Added for type hinting

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
)

from bsm_api_client import (
    BedrockServerManagerApi,
    AuthError,
    CannotConnectError,
    APIError,
)

from .frontend import BsmFrontendRegistration
from .utils import sanitize_host_port_string
from .const import (
    DOMAIN,
    CONF_SERVER_NAMES,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    PLATFORMS,
    CONF_USE_SSL,
    CONF_VERIFY_SSL,
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
    except Exception as e:
        _LOGGER.error(
            "Failed during frontend module registration: %s", e, exc_info=True
        )
        # Continue setup even if frontend registration fails

    # --- API Client Setup ---
    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    use_ssl = entry.data.get(CONF_USE_SSL, False)
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, True)

    # Safely get and process the port
    port_from_config_entry = entry.data.get(CONF_PORT)
    processed_port: Optional[int] = None

    if port_from_config_entry is not None:
        port_input_str = str(
            port_from_config_entry
        ).strip()  # Ensure it's a string and stripped
        if port_input_str:  # Check if it's not an empty string
            try:
                # Attempt to convert to float first to handle inputs like "123.0"
                port_float = float(port_input_str)
                # Check if the float is actually an integer (e.g., 123.0, not 123.5)
                if port_float == int(
                    port_float
                ):  # Note: int(123.5) is 123. 123.5 == 123 is False.
                    port_val = int(port_float)  # Convert the whole number float to int
                    if not (1 <= port_val <= 65535):
                        _LOGGER.error(
                            "Invalid port value '%s' (resolved to %d) in config entry for %s. Port must be between 1 and 65535. "
                            "Please reconfigure the integration.",
                            port_input_str,
                            port_val,
                            host,
                        )
                        raise ConfigEntryNotReady(
                            f"Invalid port {port_val} in configuration for {host}."
                        )
                    processed_port = port_val
                else:
                    # Input was a float but not a whole number, e.g., "123.5"
                    _LOGGER.error(
                        "Invalid port value '%s' in config entry for %s. Port must be a whole number. "
                        "Please reconfigure the integration.",
                        port_input_str,
                        host,
                    )
                    raise ConfigEntryNotReady(
                        f"Port value '{port_input_str}' must be a whole number in configuration for {host}."
                    )
            except ValueError:
                # This will catch cases where float() fails (e.g., "abc")
                # or int(port_float) fails if float was inf/nan
                _LOGGER.error(
                    "Invalid port value '%s' in config entry for %s. It's not a valid number. "
                    "Please reconfigure the integration.",
                    port_input_str,
                    host,
                )
                raise ConfigEntryNotReady(
                    f"Invalid port value '{port_input_str}' in configuration for {host}."
                )

    api_client = BedrockServerManagerApi(
        host=host,
        port=processed_port,
        username=username,
        password=password,
        use_ssl=use_ssl,
        verify_ssl=verify_ssl,
    )
    hass.data[DOMAIN][entry.entry_id]["api"] = api_client
    _LOGGER.debug(
        "BedrockServerManagerApi client initialized for %s (Port: %s, SSL: %s, Verify SSL: %s)",
        host,
        processed_port if processed_port is not None else "derived/omitted",
        use_ssl,
        verify_ssl,
    )
    # --- End of API Client Setup Modification ---

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

    manager_os_type = "Unknown"
    manager_app_version = "Unknown"
    if manager_coordinator.last_update_success and manager_coordinator.data:
        manager_info_payload = manager_coordinator.data.get("info")
        if isinstance(manager_info_payload, dict):
            manager_os_type = manager_info_payload.get("os_type", "Unknown").lower()
            manager_app_version = manager_info_payload.get("app_version", "Unknown")
    else:
        _LOGGER.warning(
            "ManagerDataCoordinator initial update failed or returned no data. "
            "Manager-level entities and device info might be incomplete."
        )

    # --- Manager Device Registration ---
    display_port_str = f":{processed_port}" if processed_port is not None else ""

    # Construct RAW manager_host_port_id for unique identification
    raw_manager_host_port_id: str
    if ":" in host and processed_port is None:
        # If host already contains a port (e.g., "domain.com:1234") and no explicit port was configured,
        # use the host string as is for the ID.
        raw_manager_host_port_id = host
    else:
        # If host is "domain.com" and processed_port is 8080 => "domain.com:8080"
        # If host is "domain.com" and processed_port is None => "domain.com"
        raw_manager_host_port_id = f"{host}{display_port_str}"

    # Sanitize the constructed ID string
    manager_host_port_id = sanitize_host_port_string(raw_manager_host_port_id)

    if manager_host_port_id != raw_manager_host_port_id:
        _LOGGER.info(
            "Sanitized main manager identifier string from '%s' to '%s' for entry %s",
            raw_manager_host_port_id,
            manager_host_port_id,  # Log the sanitized version
            entry.entry_id,
        )

    # manager_identifier_tuple will now use the sanitized manager_host_port_id
    manager_identifier_tuple = (DOMAIN, manager_host_port_id)

    device_registry = dr.async_get(hass)
    # Determine configuration URL parts
    protocol_for_url = "https" if use_ssl else "http"
    # For the URL, we use the original host and processed_port, not the potentially sanitized ID string parts,
    # unless the ID string itself is meant to be the direct address.
    # If host is IPv6 and needs brackets for URL when port is present:
    url_host_part = host
    if (
        ":" in host
        and not host.startswith("[")
        and host.count(":") >= 2
        and processed_port is not None
    ):
        url_host_part = f"[{host}]"

    configuration_url_for_device = (
        f"{protocol_for_url}://{url_host_part}{display_port_str}"
    )

    manager_device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={manager_identifier_tuple},  # Uses sanitized ID in tuple
        name=f"BSM @ {manager_host_port_id}",  # Display name can use the sanitized ID
        manufacturer="DMedina559",
        model=f"{manager_os_type.capitalize() if manager_os_type != 'unknown' else 'Unknown OS'}",
        sw_version=manager_app_version,
        configuration_url=configuration_url_for_device,  # Use the carefully constructed URL
    )
    _LOGGER.debug(
        "Ensured manager device exists: ID=%s for identifier %s",
        manager_device_entry.id,
        manager_host_port_id,  # Log the sanitized version
    )
    # --- End of Manager Device Registration Modification ---

    hass.data[DOMAIN][entry.entry_id].update(
        {
            "manager_identifier": manager_identifier_tuple,
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
            manager_host_port_id,
        )
    else:
        _LOGGER.info(
            "Attempting to set up server coordinators for manager %s, selected servers: %s",
            manager_host_port_id,
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
                if server_name in hass.data[DOMAIN][entry.entry_id].get("servers", {}):
                    del hass.data[DOMAIN][entry.entry_id]["servers"][server_name]
            else:
                successful_setups += 1

        if selected_servers and successful_setups == 0 and len(selected_servers) > 0:
            _LOGGER.warning(
                "All %d selected Minecraft server coordinator(s) failed to set up for manager %s. "
                "Problematic server(s) will not have entities.",
                len(selected_servers),
                manager_host_port_id,
            )
        elif selected_servers and successful_setups < len(selected_servers):
            failed_count = len(selected_servers) - successful_setups
            _LOGGER.warning(
                "%d of %d selected Minecraft server coordinator(s) failed to set up for manager %s. "
                "Problematic server(s) will not have entities.",
                failed_count,
                len(selected_servers),
                manager_host_port_id,
            )
        elif selected_servers and successful_setups == len(
            selected_servers
        ):  # All selected servers set up successfully
            _LOGGER.info(
                "All %d selected server coordinators set up successfully for manager %s.",
                successful_setups,
                manager_host_port_id,
            )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(options_update_listener))

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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Safely construct manager_host_port_id for logging
    host_for_unload = entry.data.get(CONF_HOST, "UnknownHost")
    port_for_unload_input = entry.data.get(CONF_PORT)  # Could be None or empty string
    port_for_unload_str = ""
    if port_for_unload_input is not None:
        temp_port_str = str(port_for_unload_input).strip()
        if temp_port_str:  # Ensure it's not an empty string before assigning
            port_for_unload_str = temp_port_str

    display_port_unload_str = f":{port_for_unload_str}" if port_for_unload_str else ""

    # Construct unique ID string for logging, similar to async_setup_entry
    if ":" in host_for_unload and not port_for_unload_str:
        manager_host_port_id_unload = host_for_unload
    else:
        manager_host_port_id_unload = f"{host_for_unload}{display_port_unload_str}"

    _LOGGER.info(
        "Unloading Bedrock Server Manager entry for manager '%s' (Entry ID: %s)",
        manager_host_port_id_unload,
        entry.entry_id,
    )

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        domain_data = hass.data.get(DOMAIN)
        entry_specific_data_popped = None
        if domain_data:
            entry_specific_data_popped = domain_data.pop(entry.entry_id, None)

        if entry_specific_data_popped:
            _LOGGER.debug(
                "Successfully removed data for entry %s (%s) from hass.data.%s",
                entry.entry_id,
                manager_host_port_id_unload,
                DOMAIN,
            )
            frontend_registrar = entry_specific_data_popped.get("frontend_registrar")
            if frontend_registrar:
                try:
                    await frontend_registrar.async_unregister()
                    _LOGGER.debug(
                        "BSM Frontend module unregistered for %s.",
                        manager_host_port_id_unload,
                    )
                except Exception as e:
                    _LOGGER.error(
                        "Error during frontend unregistration for %s: %s",
                        manager_host_port_id_unload,
                        e,
                        exc_info=True,
                    )

            # Closing the API client from hass.data is generally not needed if ClientBase
            # is used correctly with HA's shared session or if it's managed by coordinators.
            # If ClientBase created its own session (not typical for runtime), it should be closed by its owner.
            # api_client_instance = entry_specific_data_popped.get("api")
            # if api_client_instance and hasattr(api_client_instance, "close"):
            #     await api_client_instance.close() # ClientBase.close() is safe for shared sessions.

        else:
            _LOGGER.debug(
                "No specific data found in hass.data.%s for entry %s to pop.",
                DOMAIN,
                entry.entry_id,
            )

        current_domain_data = hass.data.get(DOMAIN)
        active_bsm_config_entries_count = 0
        if current_domain_data:
            active_bsm_config_entries_count = sum(
                1 for key in current_domain_data if key != "_services_registered"
            )

        if active_bsm_config_entries_count == 0:
            _LOGGER.info(
                "No active BSM config entries remain after unloading %s. Proceeding to remove services and domain data.",
                entry.entry_id,
            )
            if current_domain_data and current_domain_data.get("_services_registered"):
                await services.async_remove_services(hass)
                current_domain_data.pop("_services_registered", None)
            if (
                current_domain_data and not current_domain_data
            ):  # Checks if dict is empty after pop
                _LOGGER.debug("Popping empty %s dictionary from hass.data.", DOMAIN)
                hass.data.pop(DOMAIN, None)
            elif (
                not current_domain_data
            ):  # Domain data was already gone or never created
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
    else:
        _LOGGER.error(
            "Failed to unload platforms for BSM entry %s. Data and services will not be fully cleaned up.",
            entry.entry_id,
        )

    return unload_ok
