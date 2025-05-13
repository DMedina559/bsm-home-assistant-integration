# custom_components/bedrock_server_manager/diaognostics.py
"""Diagnostics support for Bedrock Server Manager."""

from __future__ import annotations

import logging  # Added
from typing import Any, Dict, List, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.device_registry import async_entries_for_config_entry
from homeassistant.helpers.entity_registry import async_entries_for_device
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.components.diagnostics.util import async_redact_data

# --- IMPORT FROM LOCAL MODULES ---
from .const import DOMAIN, CONF_SERVER_NAMES  # CONF_SERVER_NAMES not used, but fine
from .coordinator import (
    MinecraftBedrockCoordinator,
    ManagerDataCoordinator,
)  # Added ManagerDataCoordinator

# --- IMPORT FROM THE NEW LIBRARY ---
from pybedrock_server_manager import BedrockServerManagerApi

# --- END IMPORT FROM NEW LIBRARY ---

_LOGGER = logging.getLogger(__name__)  # Added

TO_REDACT_CONFIG = {
    CONF_PASSWORD,
    CONF_USERNAME,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> Dict[str, Any]:
    """Return diagnostics for a config entry."""
    diagnostics_data: Dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "entry_id": entry.entry_id,
            "data": async_redact_data(entry.data, TO_REDACT_CONFIG),
            "options": dict(entry.options),
        }
    }

    try:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        api_client: BedrockServerManagerApi = entry_data["api"]
        manager_identifier_tuple: tuple = entry_data["manager_identifier"]
        manager_os: str = entry_data.get("manager_os_type", "Unknown")
        manager_version: str = entry_data.get("manager_app_version", "Unknown")
        servers_dict: Dict[str, Dict[str, Any]] = entry_data.get("servers", {})
        manager_coordinator: Optional[ManagerDataCoordinator] = entry_data.get(
            "manager_coordinator"
        )
    except KeyError:
        diagnostics_data["error"] = (
            f"Integration data not found in hass.data[{DOMAIN}][{entry.entry_id}]."
        )
        return diagnostics_data
    except Exception as e:
        _LOGGER.error(
            "Error accessing integration data for diagnostics: %s", e, exc_info=True
        )
        diagnostics_data["error"] = f"Error accessing integration data: {e}"
        return diagnostics_data

    diagnostics_data["manager_info"] = {
        "identifier": manager_identifier_tuple,
        "os_type": manager_os,
        "app_version": manager_version,
        "base_url": getattr(api_client, "_base_url", "Unknown"),
    }

    if manager_coordinator:
        diagnostics_data["manager_coordinator"] = {
            "name": manager_coordinator.name,
            "last_update_success": manager_coordinator.last_update_success,
            "data": manager_coordinator.data,
            "listeners": len(manager_coordinator._listeners),
            "update_interval_seconds": (
                manager_coordinator.update_interval.total_seconds()
                if manager_coordinator.update_interval
                else None
            ),
        }
    else:
        diagnostics_data["manager_coordinator"] = "Not available or setup failed."

    diagnostics_data["monitored_servers"] = {}
    for server_name, server_specific_data in servers_dict.items():
        coordinator: Optional[MinecraftBedrockCoordinator] = server_specific_data.get(
            "coordinator"
        )
        if coordinator:
            diagnostics_data["monitored_servers"][server_name] = {
                "coordinator_name": coordinator.name,
                "last_update_success": coordinator.last_update_success,
                "data": coordinator.data,
                "listeners": len(coordinator._listeners),
                "update_interval_seconds": (
                    coordinator.update_interval.total_seconds()
                    if coordinator.update_interval
                    else None
                ),
                "world_name_static": server_specific_data.get("world_name"),
                "version_static": server_specific_data.get("installed_version"),
            }
        else:
            diagnostics_data["monitored_servers"][server_name] = {
                "status": "Coordinator not found or setup failed."
            }

    device_registry = async_get_device_registry(hass)
    entity_registry = async_get_entity_registry(hass)
    devices_info: List[Dict[str, Any]] = []
    hass_devices = async_entries_for_config_entry(device_registry, entry.entry_id)

    for device_entry in hass_devices:
        entities_info: List[Dict[str, Any]] = []
        hass_entities = async_entries_for_device(
            entity_registry, device_entry.id, include_disabled_entities=True
        )
        for entity_entry in hass_entities:
            state = hass.states.get(entity_entry.entity_id)
            state_dict = None
            if state:
                state_dict = dict(state.as_dict())
                state_dict.pop("context", None)
                state_dict.pop("last_changed", None)
                state_dict.pop("last_updated", None)
            entities_info.append(
                {
                    "entity_id": entity_entry.entity_id,
                    "unique_id": entity_entry.unique_id,
                    "name": entity_entry.name or entity_entry.original_name,
                    "platform": entity_entry.platform,
                    "disabled_by": entity_entry.disabled_by,
                    "state": state_dict,
                }
            )
        devices_info.append(
            {
                "id": device_entry.id,
                "name": device_entry.name_by_user or device_entry.name,
                "model": device_entry.model,
                "sw_version": device_entry.sw_version,
                "manufacturer": device_entry.manufacturer,
                "identifiers": list(device_entry.identifiers),
                "via_device_id": device_entry.via_device_id,
                "entities": entities_info,
            }
        )
    diagnostics_data["devices"] = devices_info
    return diagnostics_data


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    config_entry_diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    device_specific_diagnostics: Dict[str, Any] = {
        "device_info_from_registry": {
            "id": device.id,
            "name": device.name_by_user or device.name,
            "model": device.model,
            "sw_version": device.sw_version,
            "manufacturer": device.manufacturer,
            "identifiers": list(device.identifiers),
            "via_device_id": device.via_device_id,
            "config_entries": list(device.config_entries),
        },
        "config_entry_title": entry.title,
    }
    device_primary_identifier_value = None
    for identifier_tuple in device.identifiers:
        if identifier_tuple[0] == DOMAIN:
            device_primary_identifier_value = identifier_tuple[1]
            break
    if device_primary_identifier_value:
        if device_primary_identifier_value in config_entry_diagnostics.get(
            "monitored_servers", {}
        ):
            device_specific_diagnostics["server_coordinator_data"] = (
                config_entry_diagnostics["monitored_servers"][
                    device_primary_identifier_value
                ]
            )
        elif (
            config_entry_diagnostics.get("manager_info", {}).get(
                "identifier", (None, None)
            )[1]
            == device_primary_identifier_value
        ):
            device_specific_diagnostics["manager_info_from_diagnostics"] = (
                config_entry_diagnostics["manager_info"]
            )
            if "manager_coordinator" in config_entry_diagnostics:
                device_specific_diagnostics["manager_coordinator_data"] = (
                    config_entry_diagnostics["manager_coordinator"]
                )
    entity_registry = async_get_entity_registry(hass)
    entities_info: List[Dict[str, Any]] = []
    hass_entities = async_entries_for_device(
        entity_registry, device.id, include_disabled_entities=True
    )
    for entity_entry in hass_entities:
        state = hass.states.get(entity_entry.entity_id)
        state_dict = None
        if state:
            state_dict = dict(state.as_dict())
            state_dict.pop("context", None)
            state_dict.pop("last_changed", None)
            state_dict.pop("last_updated", None)
        entities_info.append(
            {
                "entity_id": entity_entry.entity_id,
                "unique_id": entity_entry.unique_id,
                "name": entity_entry.name or entity_entry.original_name,
                "platform": entity_entry.platform,
                "state": state_dict,
            }
        )
    device_specific_diagnostics["entities_for_this_device"] = entities_info
    return device_specific_diagnostics
