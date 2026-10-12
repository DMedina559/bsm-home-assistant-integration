"""Connection and dependency health entities for automation and diagnostics."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ApplicationMonitorCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Replace individual checks with one health entity and connection indicators."""
    data = hass.data[DOMAIN][entry.entry_id]
    registry = er.async_get(hass)
    for domain, keys in (
        ("binary_sensor", ("lifecycle", "database", "state", "metrics")),
        ("sensor", ("application_lifecycle", "health_checked_at")),
    ):
        for key in keys:
            unique_id = (
                f"{DOMAIN}_{data['manager_identifier'][1]}_{key}".lower().replace(
                    ":", "_"
                )
            )
            entity_id = registry.async_get_entity_id(domain, DOMAIN, unique_id)
            if entity_id is not None:
                registry.async_remove(entity_id)
    async_add_entities(
        [
            ApplicationHealthSensor(
                data["monitor_coordinator"], data["manager_identifier"], key
            )
            for key in ("connection", "websocket", "health")
        ]
    )


class ApplicationHealthSensor(
    CoordinatorEntity[ApplicationMonitorCoordinator], BinarySensorEntity
):
    """Distinguish reachable APIs, live WebSockets, and dependency problems."""

    _unrecorded_attributes = frozenset(
        {
            "checks",
            "failed_checks",
            "checked_at",
            "message",
            "bsm_updated_at",
            "bsm_last_error",
        }
    )
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: ApplicationMonitorCoordinator,
        manager_identifier: tuple[str, str],
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self.key = key
        self.manager_url = manager_identifier[1]
        self._attr_unique_id = (
            f"{DOMAIN}_{manager_identifier[1]}_{key}".lower().replace(":", "_")
        )
        self._attr_device_info = DeviceInfo(identifiers={manager_identifier})
        self._attr_name = {
            "connection": "API connection",
            "websocket": "WebSocket connection",
            "health": "Application health problem",
        }.get(key, f"{key.capitalize()} health problem")
        self._attr_device_class = (
            BinarySensorDeviceClass.CONNECTIVITY
            if key in {"connection", "websocket"}
            else BinarySensorDeviceClass.PROBLEM
        )
        self._attr_entity_registry_enabled_default = key in {
            "connection",
            "websocket",
            "health",
        }

    @property
    def available(self) -> bool:
        if self.key in {"connection", "websocket"}:
            return True
        health = (self.coordinator.data or {}).get("health") or {}
        return (
            super().available
            and "health" not in self.coordinator.unavailable_resources
            and "health" not in self.coordinator.unsupported_resources
            and bool(health)
        )

    @property
    def is_on(self) -> bool:
        if self.key == "connection":
            return self.coordinator.http_connected
        if self.key == "websocket":
            return self.coordinator.websocket_connected
        health = (self.coordinator.data or {}).get("health") or {}
        return health.get("health") == "degraded"

    @property
    def extra_state_attributes(self) -> dict | None:
        metadata = {
            "bsm_role": "manager",
            "bsm_key": self.key,
            "bsm_manager_url": self.manager_url,
            **self.coordinator.resource_metadata(
                "health" if self.key not in {"connection", "websocket"} else None
            ),
        }
        if self.key == "health":
            health = (self.coordinator.data or {}).get("health") or {}
            checks = health.get("checks") or {}
            return {
                **metadata,
                "checks": checks,
                "failed_checks": [
                    name
                    for name, check in checks.items()
                    if not check.get("healthy", False)
                ],
                "lifecycle": health.get("lifecycle"),
                "checked_at": health.get("checked_at"),
            }
        return metadata
