"""Diagnostics support for Bedrock Server Manager."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME  # For redaction
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    DeviceEntry,
    async_entries_for_config_entry,
)
from homeassistant.helpers.entity_registry import async_entries_for_device
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.components.diagnostics.util import async_redact_data

from .const import DOMAIN, CONF_SERVER_NAMES
from .coordinator import MinecraftBedrockCoordinator  # Import your specific coordinator
from .api import BedrockServerManagerApi  # Import your API class for type hinting

# Keys to redact from config_entry.data
TO_REDACT_CONFIG = {
    CONF_PASSWORD,
    CONF_USERNAME,
}  # Add any other sensitive keys from entry.data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> Dict[str, Any]:
    """Return diagnostics for a config entry."""
    diagnostics_data: Dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "entry_id": entry.entry_id,
            "data": async_redact_data(entry.data, TO_REDACT_CONFIG),
            "options": dict(entry.options),  # Options are generally not sensitive
        }
    }

    # Get the stored data for this config entry
    try:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        api_client: BedrockServerManagerApi = entry_data[
            "api"
        ]  # For type hinting, not direct use here
        manager_identifier_tuple: tuple = entry_data["manager_identifier"]
        manager_os: str = entry_data.get("manager_os_type", "Unknown")
        manager_version: str = entry_data.get("manager_app_version", "Unknown")
        servers_dict: Dict[str, Dict[str, Any]] = entry_data.get("servers", {})
    except KeyError:
        diagnostics_data["error"] = (
            "Integration data not found in hass.data. Setup might be incomplete."
        )
        return diagnostics_data

    diagnostics_data["manager_info"] = {
        "identifier": manager_identifier_tuple,
        "os_type": manager_os,
        "app_version": manager_version,
        "base_url": api_client._base_url,  # Expose base URL for connectivity checks
    }

    diagnostics_data["monitored_servers"] = {}
    for server_name, server_specific_data in servers_dict.items():
        coordinator: Optional[MinecraftBedrockCoordinator] = server_specific_data.get(
            "coordinator"
        )
        if coordinator:
            diagnostics_data["monitored_servers"][server_name] = {
                "coordinator_name": coordinator.name,
                "last_update_success": coordinator.last_update_success,
                "data": coordinator.data,  # This is the raw data from the last successful API poll
                "listeners": len(coordinator._listeners),
                "update_interval_seconds": (
                    coordinator.update_interval.total_seconds()
                    if coordinator.update_interval
                    else None
                ),
                # Include static info fetched during setup if available
                "world_name_static": server_specific_data.get("world_name"),
                "version_static": server_specific_data.get("installed_version"),
            }
        else:
            diagnostics_data["monitored_servers"][server_name] = {
                "status": "Coordinator not found or setup failed."
            }

    # Add device and entity information
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
                # Remove context to keep diagnostics smaller and cleaner
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
    """Return diagnostics for a device entry."""
    # Get all config entry diagnostics first
    config_entry_diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    # Filter to include only data relevant to the specific device
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
        "config_entry_title": entry.title,  # Add some context from the entry
    }

    # Find the server name or manager ID from the device identifiers
    device_primary_identifier_value = None
    for identifier_tuple in device.identifiers:
        if identifier_tuple[0] == DOMAIN:
            device_primary_identifier_value = identifier_tuple[1]
            break

    if device_primary_identifier_value:
        # Check if it's a server device
        if device_primary_identifier_value in config_entry_diagnostics.get(
            "monitored_servers", {}
        ):
            device_specific_diagnostics["server_coordinator_data"] = (
                config_entry_diagnostics["monitored_servers"][
                    device_primary_identifier_value
                ]
            )
        # Check if it's the manager device
        elif (
            config_entry_diagnostics.get("manager_info", {}).get(
                "identifier", (None, None)
            )[1]
            == device_primary_identifier_value
        ):
            device_specific_diagnostics["manager_info_from_diagnostics"] = (
                config_entry_diagnostics["manager_info"]
            )

    # Include entities for this specific device
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
