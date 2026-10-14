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

from .attributes import VOLATILE_ATTRIBUTES, bounded_attributes, entity_attributes
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

    _unrecorded_attributes = VOLATILE_ATTRIBUTES
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
            and health.get("health") in {"healthy", "degraded"}
        )

    @property
    def is_on(self) -> bool | None:
        if self.key == "connection":
            return self.coordinator.http_connected
        if self.key == "websocket":
            return self.coordinator.websocket_connected
        health = (self.coordinator.data or {}).get("health") or {}
        value = health.get("health")
        return value == "degraded" if value in {"healthy", "degraded"} else None

    @property
    def extra_state_attributes(self) -> dict | None:
        metadata = entity_attributes(
            "manager",
            self.key,
            self.manager_url,
            metadata=self.coordinator.resource_metadata(
                "health" if self.key not in {"connection", "websocket"} else None
            ),
        )
        if self.key == "health":
            health = (self.coordinator.data or {}).get("health") or {}
            checks = health.get("checks") or {}
            return bounded_attributes(
                {
                    **metadata,
                    "checks": checks,
                    "failed_checks": [
                        name
                        for name, check in checks.items()
                        if isinstance(check, dict) and check.get("healthy") is False
                    ],
                    "lifecycle": health.get("lifecycle"),
                    "ready": health.get("ready"),
                    "checked_at": health.get("checked_at"),
                }
            )
        return metadata
