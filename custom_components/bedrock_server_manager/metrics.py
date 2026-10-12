"""Native HA metrics with units, statistics, and bounded state attributes."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ApplicationMonitorCoordinator


@dataclass(frozen=True, kw_only=True)
class MetricDescription(SensorEntityDescription):
    """Describe a field in the latest metrics or health resource."""

    resource: str = "metrics"
    field: str


def metric(
    field: str,
    name: str,
    unit: str | None = None,
    device_class: SensorDeviceClass | None = None,
    enabled: bool = True,
) -> MetricDescription:
    """Build consistent measurement metadata for recorder statistics."""
    return MetricDescription(
        key=field,
        field=field,
        name=name,
        native_unit_of_measurement=unit,
        device_class=device_class,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1 if unit else 0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=enabled,
    )


METRIC_DESCRIPTIONS = (
    metric("app_cpu_percent", "Application CPU", "%"),
    metric("app_ram_mb", "Application memory", "MiB", SensorDeviceClass.DATA_SIZE),
    metric("asyncio_task_count", "Application asyncio tasks", enabled=False),
    metric("background_task_count", "Application background tasks"),
    metric(
        "loop_lag_ms",
        "Application event loop lag",
        "ms",
        SensorDeviceClass.DURATION,
        False,
    ),
    metric("thread_count", "Application threads", enabled=False),
    metric("uptime_seconds", "Application uptime", "s", SensorDeviceClass.DURATION),
    metric("sys_cpu_percent", "System CPU", "%"),
    metric("sys_ram_percent", "System memory usage", "%"),
    metric(
        "sys_ram_mb", "System memory used", "MiB", SensorDeviceClass.DATA_SIZE, False
    ),
    metric(
        "sys_ram_total_mb",
        "System memory total",
        "MiB",
        SensorDeviceClass.DATA_SIZE,
        False,
    ),
    metric(
        "disk_read_kib_s",
        "System disk read",
        "KiB/s",
        SensorDeviceClass.DATA_RATE,
        False,
    ),
    metric(
        "disk_write_kib_s",
        "System disk write",
        "KiB/s",
        SensorDeviceClass.DATA_RATE,
        False,
    ),
    metric(
        "net_rx_kib_s",
        "System network receive",
        "KiB/s",
        SensorDeviceClass.DATA_RATE,
        False,
    ),
    metric(
        "net_tx_kib_s",
        "System network send",
        "KiB/s",
        SensorDeviceClass.DATA_RATE,
        False,
    ),
    MetricDescription(
        key="metrics_sampled_at",
        field="timestamp",
        name="Metrics sampled at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


class ApplicationMetricSensor(
    CoordinatorEntity[ApplicationMonitorCoordinator], SensorEntity
):
    """Expose one metric, leaving historic samples to Home Assistant's recorder."""

    _unrecorded_attributes = frozenset({"bsm_updated_at", "bsm_last_error"})
    entity_description: MetricDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ApplicationMonitorCoordinator,
        description: MetricDescription,
        manager_identifier: tuple[str, str],
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self.manager_url = manager_identifier[1]
        self._attr_extra_state_attributes = {
            "bsm_role": "manager",
            "bsm_key": description.key,
        }
        self._attr_unique_id = (
            f"{DOMAIN}_{manager_identifier[1]}_{description.key}".lower().replace(
                ":", "_"
            )
        )
        self._attr_device_info = DeviceInfo(identifiers={manager_identifier})

    @property
    def extra_state_attributes(self) -> dict:
        return {
            **self._attr_extra_state_attributes,
            "bsm_manager_url": self.manager_url,
            **self.coordinator.resource_metadata(self.entity_description.resource),
        }

    @property
    def available(self) -> bool:
        description = self.entity_description
        return (
            super().available
            and description.resource not in self.coordinator.unavailable_resources
            and description.resource not in self.coordinator.unsupported_resources
            and self.native_value is not None
        )

    @property
    def native_value(self) -> Any:
        description = self.entity_description
        value = (
            (self.coordinator.data or {})
            .get(description.resource, {})
            .get(description.field)
        )
        if (
            value is not None
            and description.device_class == SensorDeviceClass.TIMESTAMP
        ):
            return datetime.fromtimestamp(value, timezone.utc)
        return value
