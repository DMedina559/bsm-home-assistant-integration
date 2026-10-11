"""Resolve HA entity, device and area targets without losing selected servers."""

import logging
from typing import List, Set

from homeassistant.const import ATTR_AREA_ID, ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .utils import device_config_entry_ids, registry_devices

_LOGGER = logging.getLogger(__name__)


async def resolve_server_targets(  # noqa: C901
    service: ServiceCall, hass: HomeAssistant
) -> list[tuple[str, str]]:
    servers_to_target: set[tuple[str, str]] = set()
    entity_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    def process_device_for_server_target(
        device_entry: dr.DeviceEntry | dr.ChildDeviceEntry, config_entry_id_context: str
    ):
        try:
            manager_data = hass.data[DOMAIN][config_entry_id_context]
            manager_host_port_id = manager_data["manager_identifier"][1]
        except (KeyError, TypeError, IndexError):
            _LOGGER.warning(
                "Could not get manager_identifier for config entry %s when processing device %s.",
                config_entry_id_context,
                device_entry.id,
            )
            return

        parsed_server_name = None
        for identifier_domain, identifier_value in device_entry.identifiers:
            if identifier_domain == DOMAIN:
                expected_prefix = manager_host_port_id + "_"
                if identifier_value.startswith(expected_prefix):
                    prefix_len = len(expected_prefix)
                    if len(identifier_value) > prefix_len:
                        parsed_server_name = identifier_value[prefix_len:]
                        break

        if parsed_server_name:
            if parsed_server_name in manager_data.get("servers", {}):
                servers_to_target.add((config_entry_id_context, parsed_server_name))
        elif _LOGGER.isEnabledFor(logging.DEBUG):
            is_manager_device = any(
                val == manager_host_port_id
                for dom, val in device_entry.identifiers
                if dom == DOMAIN
            )
            if not is_manager_device:
                _LOGGER.debug(
                    "Device %s (identifiers: %s) for config entry %s is not a recognized BSM server sub-device.",
                    device_entry.id,
                    device_entry.identifiers,
                    config_entry_id_context,
                )

    target_entity_ids: List[str] = cv.ensure_list(service.data.get(ATTR_ENTITY_ID, []))
    target_device_ids: List[str] = cv.ensure_list(service.data.get(ATTR_DEVICE_ID, []))
    target_area_ids: List[str] = cv.ensure_list(service.data.get(ATTR_AREA_ID, []))

    for entity_id in target_entity_ids:
        entity_entry = entity_reg.async_get(entity_id)
        if (
            entity_entry
            and entity_entry.platform == DOMAIN
            and entity_entry.config_entry_id
            and entity_entry.device_id
        ):
            if entity_entry.config_entry_id in hass.data.get(DOMAIN, {}):
                device_of_entity = dev_reg.async_get(entity_entry.device_id)
                if device_of_entity:
                    process_device_for_server_target(
                        device_of_entity, entity_entry.config_entry_id
                    )

    for device_id in target_device_ids:
        device_entry = dev_reg.async_get(device_id)
        if device_entry:
            for ce_id in device_config_entry_ids(device_entry):
                if ce_id in hass.data.get(DOMAIN, {}):
                    process_device_for_server_target(device_entry, ce_id)
                    break

    if target_area_ids:
        all_devices = list(registry_devices(dev_reg))
        for device_entry in all_devices:
            if device_entry.area_id in target_area_ids:
                for ce_id in device_config_entry_ids(device_entry):
                    if ce_id in hass.data.get(DOMAIN, {}):
                        process_device_for_server_target(device_entry, ce_id)
                        break

    if not servers_to_target:
        error_message = f"Service {service.domain}.{service.service} requires targeting specific BSM server devices or their entities."
        if not any([target_entity_ids, target_device_ids, target_area_ids]):
            error_message = f"No target (device, entity, or area) was provided for service {service.domain}.{service.service}."
        _LOGGER.error(
            error_message + " Targets provided: Entities=%s, Devices=%s, Areas=%s",
            target_entity_ids,
            target_device_ids,
            target_area_ids,
        )
        if not any([target_entity_ids, target_device_ids, target_area_ids]):
            raise ServiceValidationError(error_message)
        raise HomeAssistantError(error_message)

    _LOGGER.debug(
        "Resolved server targets for service %s.%s: %s",
        service.domain,
        service.service,
        servers_to_target,
    )
    return sorted(servers_to_target)


async def resolve_manager_targets(  # noqa: C901
    service: ServiceCall, hass: HomeAssistant
) -> List[str]:
    config_entry_ids_to_target: Set[str] = set()
    entity_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    target_entity_ids: List[str] = cv.ensure_list(service.data.get(ATTR_ENTITY_ID, []))
    target_device_ids: List[str] = cv.ensure_list(service.data.get(ATTR_DEVICE_ID, []))
    target_area_ids: List[str] = cv.ensure_list(service.data.get(ATTR_AREA_ID, []))

    for entity_id in target_entity_ids:
        entity_entry = entity_reg.async_get(entity_id)
        if (
            entity_entry
            and entity_entry.platform == DOMAIN
            and entity_entry.config_entry_id
        ):
            if entity_entry.config_entry_id in hass.data.get(DOMAIN, {}):
                config_entry_ids_to_target.add(entity_entry.config_entry_id)

    for device_id in target_device_ids:
        device_entry = dev_reg.async_get(device_id)
        if device_entry:
            for ce_id in device_config_entry_ids(device_entry):
                config_entry = hass.config_entries.async_get_entry(ce_id)
                if (
                    config_entry
                    and config_entry.domain == DOMAIN
                    and ce_id in hass.data.get(DOMAIN, {})
                ):
                    config_entry_ids_to_target.add(ce_id)

    if target_area_ids:
        all_devices = list(registry_devices(dev_reg))
        for device_entry in all_devices:
            if device_entry.area_id in target_area_ids:
                for ce_id in device_config_entry_ids(device_entry):
                    config_entry = hass.config_entries.async_get_entry(ce_id)
                    if (
                        config_entry
                        and config_entry.domain == DOMAIN
                        and ce_id in hass.data.get(DOMAIN, {})
                    ):
                        config_entry_ids_to_target.add(ce_id)

    if not config_entry_ids_to_target:
        error_message = f"Service {service.domain}.{service.service} requires targeting a BSM manager instance."
        if not any([target_entity_ids, target_device_ids, target_area_ids]):
            error_message += " No target was provided."
        else:
            error_message += (
                " Provided targets did not resolve to any loaded BSM manager instances."
            )
        _LOGGER.error(
            error_message + " Targets: E=%s, D=%s, A=%s",
            target_entity_ids,
            target_device_ids,
            target_area_ids,
        )
        if not any([target_entity_ids, target_device_ids, target_area_ids]):
            raise ServiceValidationError(error_message)
        raise HomeAssistantError(error_message)

    _LOGGER.debug(
        "Resolved manager targets for service %s.%s: %s",
        service.domain,
        service.service,
        list(config_entry_ids_to_target),
    )
    return list(config_entry_ids_to_target)
