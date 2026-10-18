"""Native numeric settings backed by the manager settings coordinator."""

from bsm_api_client import APIError
from bsm_api_client.models import SettingItemResponse
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .attributes import VOLATILE_ATTRIBUTES, entity_attributes
from .const import DOMAIN
from .coordinator import ManagerDataCoordinator
from .reconcile import refresh_after_action

SETTINGS = {
    "monitoring.app_metrics_interval_sec": ("Application metrics interval", 1, 3600),
    "monitoring.bedrock_metrics_interval_sec": ("Bedrock metrics interval", 1, 3600),
    "lifecycle.startup_timeout_seconds": ("Startup timeout", 0.000001, 600),
    "lifecycle.shutdown_timeout_seconds": ("Shutdown timeout", 0.000001, 600),
    "lifecycle.task_drain_timeout_seconds": ("Task drain timeout", 0.000001, 600),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Register numeric configuration on the existing manager device."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SettingNumber(data["manager_coordinator"], data["manager_identifier"], key)
            for key in SETTINGS
        ]
    )


class SettingNumber(CoordinatorEntity[ManagerDataCoordinator], NumberEntity):
    """Read confirmed values and preserve backend validation for writes."""

    _unrecorded_attributes = VOLATILE_ATTRIBUTES
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX

    def __init__(
        self, coordinator: ManagerDataCoordinator, identifier: tuple[str, str], key: str
    ) -> None:
        super().__init__(coordinator)
        self.key = key
        self._attr_name, self._attr_native_min_value, self._attr_native_max_value = (
            SETTINGS[key]
        )
        self._attr_native_step = 1 if key.startswith("monitoring.") else 0.1
        self._attr_unique_id = f"{DOMAIN}_{identifier[1]}_{key}".lower().replace(
            ":", "_"
        )
        self._attr_device_info = DeviceInfo(identifiers={identifier})
        self._attr_extra_state_attributes = {
            "bsm_role": "manager",
            "bsm_key": key,
            "bsm_manager_url": identifier[1],
        }

    @property
    def extra_state_attributes(self) -> dict:
        """Expose stable identity and resource freshness during outages."""
        return entity_attributes(
            "manager",
            self._attr_extra_state_attributes["bsm_key"],
            self._attr_extra_state_attributes["bsm_manager_url"],
            metadata=self.coordinator.resource_metadata("application_settings"),
        )

    @property
    def native_value(self) -> float | None:
        value = (self.coordinator.data or {}).get("application_settings", {})
        for part in self.key.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        return float(value) if type(value) in (int, float) else None

    @property
    def available(self) -> bool:
        return (
            super().available
            and "application_settings" not in self.coordinator.unavailable_resources
            and self.native_value is not None
        )

    async def async_set_native_value(self, value: float) -> None:
        """Persist a numeric JSON value and refresh the authoritative settings."""
        try:
            await self.coordinator.api.application.async_set_setting(
                SettingItemResponse(key=self.key, value=value)
            )
        except (APIError, ValueError) as error:
            raise HomeAssistantError(str(error)) from error
        refresh_after_action(self.coordinator, None)
