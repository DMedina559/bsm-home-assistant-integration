# custom_components/bedrock_server_manager/diagnostics.py
"""Diagnostics support for Bedrock Server Manager."""

from __future__ import annotations  # Ensures all type hints are forward references

import logging
from typing import (
    Any,
    Dict,
    List,
    Optional,
    cast,
)  # Added cast for type hinting clarity

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME  # Standard HA constants
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.device_registry import (
    async_entries_for_config_entry as dr_async_entries_for_config_entry,
)
from homeassistant.helpers.entity_registry import (
    async_entries_for_device as er_async_entries_for_device,
)
from homeassistant.helpers.device_registry import async_get as dr_async_get
from homeassistant.helpers.entity_registry import async_get as er_async_get
from homeassistant.components.diagnostics.util import async_redact_data

# --- IMPORT FROM LOCAL MODULES ---
from .const import DOMAIN  # CONF_SERVER_NAMES is not directly used here
from .coordinator import (
    MinecraftBedrockCoordinator,
    ManagerDataCoordinator,
)

from pybedrock_server_manager import BedrockServerManagerApi  # For type hinting

_LOGGER = logging.getLogger(__name__)

# Keys to redact from the config entry's 'data' field in diagnostics
TO_REDACT_CONFIG = {
    CONF_PASSWORD,
    CONF_USERNAME,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> Dict[str, Any]:
    """Return diagnostics for a config entry."""
    _LOGGER.debug("Gathering diagnostics for config entry: %s", entry.entry_id)
    diagnostics_data: Dict[str, Any] = {
        "entry_details": {
            "title": entry.title,
            "entry_id": entry.entry_id,
            "data": async_redact_data(entry.data, TO_REDACT_CONFIG),
            "options": dict(entry.options),  # Include current options
            "source": entry.source,
            "version": entry.version,
            "disabled_by": entry.disabled_by,
        }
    }

    # Attempt to retrieve integration-specific data stored in hass.data
    try:
        # Ensure DOMAIN and entry.entry_id exist before further access
        if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
            raise KeyError(
                f"Data for {DOMAIN} or entry {entry.entry_id} not found in hass.data"
            )

        entry_specific_data = hass.data[DOMAIN][entry.entry_id]

        api_client = cast(BedrockServerManagerApi, entry_specific_data.get("api"))
        manager_identifier_tuple = cast(
            tuple, entry_specific_data.get("manager_identifier")
        )
        manager_os: str = entry_specific_data.get("manager_os_type", "Unknown")
        manager_version: str = entry_specific_data.get("manager_app_version", "Unknown")
        servers_dict: Dict[str, Dict[str, Any]] = entry_specific_data.get("servers", {})
        manager_coordinator = cast(
            Optional[ManagerDataCoordinator],
            entry_specific_data.get("manager_coordinator"),
        )

        if not api_client or not manager_identifier_tuple:
            raise ValueError(
                "API client or manager_identifier missing from entry data."
            )

    except (KeyError, ValueError) as err:
        _LOGGER.warning(
            "Required integration data missing for diagnostics of entry %s: %s",
            entry.entry_id,
            err,
        )
        diagnostics_data["error"] = (
            f"Integration data partially missing in hass.data for entry {entry.entry_id}: {err}"
        )
        # Still return what we have, like entry_details
        return diagnostics_data
    except Exception as e:  # Catch any other unexpected error during data retrieval
        _LOGGER.error(
            "Unexpected error accessing integration data for diagnostics of entry %s: %s",
            entry.entry_id,
            e,
            exc_info=True,
        )
        diagnostics_data["error"] = (
            f"Unexpected error accessing integration data: {type(e).__name__} - {e}"
        )
        return diagnostics_data

    # Add API client and manager information
    diagnostics_data["bsm_manager_connection"] = {
        "identifier_tuple": manager_identifier_tuple,
        "detected_os_type": manager_os,
        "detected_app_version": manager_version,
        "api_base_url": getattr(
            api_client,
            "_base_url",
            "Unknown (client not fully initialized or attribute missing)",
        ),
        "has_auth_token": hasattr(api_client, "_jwt_token")
        and api_client._jwt_token is not None,
    }

    # Add Manager Coordinator diagnostics
    if manager_coordinator:
        diagnostics_data["manager_data_coordinator"] = {
            "name": manager_coordinator.name,
            "last_update_success": manager_coordinator.last_update_success,
            "data": async_redact_data(manager_coordinator.data, TO_REDACT_CONFIG),
            "listeners_count": len(manager_coordinator._listeners),
            "update_interval_seconds": (
                manager_coordinator.update_interval.total_seconds()
                if manager_coordinator.update_interval
                else "N/A"
            ),
        }
    else:
        diagnostics_data["manager_data_coordinator"] = "Not available or setup failed."

    # Add Server Coordinators diagnostics
    diagnostics_data["monitored_server_coordinators"] = {}
    for server_name, server_data_from_hass in servers_dict.items():
        coordinator = cast(
            Optional[MinecraftBedrockCoordinator],
            server_data_from_hass.get("coordinator"),
        )
        if coordinator:
            diagnostics_data["monitored_server_coordinators"][server_name] = {
                "coordinator_name": coordinator.name,
                "last_update_success": coordinator.last_update_success,
                "data": async_redact_data(coordinator.data, TO_REDACT_CONFIG),
                "listeners_count": len(coordinator._listeners),
                "update_interval_seconds": (
                    coordinator.update_interval.total_seconds()
                    if coordinator.update_interval
                    else "N/A"
                ),
                # These seem like static data stored during setup, not from coordinator directly
                "world_name_at_setup": server_data_from_hass.get("world_name"),
                "version_at_setup": server_data_from_hass.get("installed_version"),
            }
        else:
            diagnostics_data["monitored_server_coordinators"][server_name] = {
                "status": "Coordinator not found or its setup failed."
            }

    # Add Device and Entity Registry information
    device_registry = dr_async_get(hass)
    entity_registry = er_async_get(hass)

    devices_payload: List[Dict[str, Any]] = []
    # Get devices linked to this specific config entry
    hass_devices_for_entry = dr_async_entries_for_config_entry(
        device_registry, entry.entry_id
    )

    for device_entry in hass_devices_for_entry:
        entities_payload: List[Dict[str, Any]] = []
        # Get entities linked to this specific device
        hass_entities_for_device = er_async_entries_for_device(
            entity_registry, device_entry.id, include_disabled_entities=True
        )
        for entity_entry in hass_entities_for_device:
            state = hass.states.get(entity_entry.entity_id)
            state_dict_redacted = None
            if state:
                state_dict_redacted = async_redact_data(
                    state.as_dict(), {}
                )  # No redaction by default here
                state_dict_redacted.pop("context", None)
                state_dict_redacted.pop("last_changed", None)
                state_dict_redacted.pop("last_updated", None)

            entities_payload.append(
                {
                    "entity_id": entity_entry.entity_id,
                    "unique_id": entity_entry.unique_id,
                    "name": entity_entry.name
                    or entity_entry.original_name,  # Prefer user-set name
                    "platform": entity_entry.platform,
                    "disabled_by": (
                        str(entity_entry.disabled_by)
                        if entity_entry.disabled_by
                        else None
                    ),
                    "current_state": state_dict_redacted,
                }
            )

        devices_payload.append(
            {
                "ha_device_id": device_entry.id,
                "name": device_entry.name_by_user or device_entry.name,
                "model": device_entry.model,
                "sw_version": device_entry.sw_version,
                "manufacturer": device_entry.manufacturer,
                "identifiers": list(
                    device_entry.identifiers
                ),  # Convert set to list for JSON
                "config_entries": list(device_entry.config_entries),
                "via_device_id": device_entry.via_device_id,
                "linked_entities": entities_payload,
            }
        )
    diagnostics_data["home_assistant_devices_and_entities"] = devices_payload
    _LOGGER.debug("Finished gathering config entry diagnostics for: %s", entry.entry_id)
    return diagnostics_data


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> Dict[str, Any]:
    """Return diagnostics for a device entry."""
    _LOGGER.debug(
        "Gathering device diagnostics for device ID: %s (Entry: %s)",
        device.id,
        entry.entry_id,
    )
    # Get comprehensive config entry diagnostics first
    config_entry_diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    device_specific_diagnostics: Dict[str, Any] = {
        "device_registry_info": {
            "ha_device_id": device.id,
            "name": device.name_by_user or device.name,
            "model": device.model,
            "sw_version": device.sw_version,
            "manufacturer": device.manufacturer,
            "identifiers": list(device.identifiers),
            "via_device_id": device.via_device_id,
            "config_entries_linked": list(device.config_entries),
            "disabled_by": str(device.disabled_by) if device.disabled_by else None,
        },
        "related_config_entry_title": entry.title,
    }

    # Attempt to link this device back to specific data in the config_entry_diagnostics
    device_primary_id_value = None
    # Find the identifier that belongs to our DOMAIN to identify if it's a manager or server device
    for identifier_tuple in device.identifiers:
        if identifier_tuple[0] == DOMAIN:
            device_primary_id_value = identifier_tuple[
                1
            ]  # This is e.g., "host:port" or "servername_host:port"
            break

    if device_primary_id_value:
        # Check if it's one of the monitored server devices
        server_coordinator_diag = config_entry_diagnostics.get(
            "monitored_server_coordinators", {}
        ).get(device_primary_id_value)
        if server_coordinator_diag:
            device_specific_diagnostics["associated_server_coordinator_data"] = (
                server_coordinator_diag
            )
        else:
            # Check if it's the manager device
            manager_info_diag = config_entry_diagnostics.get(
                "bsm_manager_connection", {}
            )
            if (
                manager_info_diag.get("identifier_tuple", (None, None))[1]
                == device_primary_id_value
            ):
                device_specific_diagnostics["associated_manager_info"] = (
                    manager_info_diag
                )
                if "manager_data_coordinator" in config_entry_diagnostics:
                    device_specific_diagnostics[
                        "associated_manager_coordinator_data"
                    ] = config_entry_diagnostics["manager_data_coordinator"]
            else:
                _LOGGER.debug(
                    "Device %s (ID: %s) could not be matched to manager or server coordinator data.",
                    device_primary_id_value,
                    device.id,
                )
    else:
        _LOGGER.warning(
            "Device %s (ID: %s) has no primary %s domain identifier.",
            device.name,
            device.id,
            DOMAIN,
        )

    # Add entities for this specific device
    entity_registry = er_async_get(hass)
    entities_payload_for_device: List[Dict[str, Any]] = []
    hass_entities_for_this_device = er_async_entries_for_device(
        entity_registry, device.id, include_disabled_entities=True
    )
    for entity_entry in hass_entities_for_this_device:
        state = hass.states.get(entity_entry.entity_id)
        state_dict_redacted = None
        if state:
            state_dict_redacted = async_redact_data(
                state.as_dict(), {}
            )  # No redaction by default here
            state_dict_redacted.pop("context", None)
            state_dict_redacted.pop("last_changed", None)
            state_dict_redacted.pop("last_updated", None)

        entities_payload_for_device.append(
            {
                "entity_id": entity_entry.entity_id,
                "unique_id": entity_entry.unique_id,
                "name": entity_entry.name or entity_entry.original_name,
                "platform": entity_entry.platform,
                "disabled_by": (
                    str(entity_entry.disabled_by) if entity_entry.disabled_by else None
                ),
                "current_state": state_dict_redacted,
            }
        )
    device_specific_diagnostics["linked_entities_states"] = entities_payload_for_device

    _LOGGER.debug("Finished gathering device diagnostics for: %s", device.id)
    return device_specific_diagnostics
