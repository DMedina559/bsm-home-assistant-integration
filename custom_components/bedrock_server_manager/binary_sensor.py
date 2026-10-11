"""Connection and dependency health entities for automation and diagnostics."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ApplicationMonitorCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add persistent connection entities and known dependency checks."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ApplicationHealthSensor(
                data["monitor_coordinator"], data["manager_identifier"], key
            )
            for key in (
                "connection",
                "websocket",
                "health",
                "lifecycle",
                "database",
                "state",
                "metrics",
            )
        ]
    )


class ApplicationHealthSensor(
    CoordinatorEntity[ApplicationMonitorCoordinator], BinarySensorEntity
):
    """Distinguish reachable APIs, live WebSockets, and dependency problems."""

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
            and (
                bool(health)
                if self.key == "health"
                else self.key in health.get("checks", {})
            )
        )

    @property
    def is_on(self) -> bool:
        if self.key == "connection":
            return self.coordinator.http_connected
        if self.key == "websocket":
            return self.coordinator.websocket_connected
        health = (self.coordinator.data or {}).get("health") or {}
        if self.key == "health":
            return health.get("health") == "degraded"
        return not health.get("checks", {}).get(self.key, {}).get("healthy", False)

    @property
    def extra_state_attributes(self) -> dict | None:
        metadata = {"bsm_role": "manager", "bsm_key": self.key}
        if self.key in {"connection", "websocket", "health"}:
            return metadata
        check = (
            (self.coordinator.data or {})
            .get("health", {})
            .get("checks", {})
            .get(self.key)
        )
        return {**metadata, "message": check["message"]} if check else metadata
