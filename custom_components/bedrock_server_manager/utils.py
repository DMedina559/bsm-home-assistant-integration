"""Device registry compatibility helpers for supported Home Assistant versions."""

from collections.abc import Mapping
from typing import Any


def device_config_entry_ids(device: Any) -> set[str]:
    """Read modern ownership, including legacy composite and pre-2026.8 devices."""
    if hasattr(device, "config_entry_id") and not getattr(
        device, "is_composite_device", False
    ):
        return {device.config_entry_id} if device.config_entry_id else set()
    return set(device.config_entries)


def registry_devices(registry: Any):
    """Iterate new collections or old mappings without deprecated mapping reads."""
    devices = registry.devices
    return devices.values() if isinstance(devices, Mapping) else devices
