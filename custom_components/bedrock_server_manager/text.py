"""Editable server configuration using typed backend setting contracts."""

from bsm_api_client import APIError
from bsm_api_client.models import ServerSettingItemPayload
from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MinecraftBedrockCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Expose the target version for every selected server."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            TargetVersionText(server["coordinator"], data["manager_identifier"])
            for server in data["servers"].values()
        ]
    )


class TargetVersionText(CoordinatorEntity[MinecraftBedrockCoordinator], TextEntity):
    """Edit and synchronize the desired Bedrock version without optimistic state."""

    _attr_has_entity_name = True
    _attr_name = "Target version"
    _attr_icon = "mdi:update"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_max = 100
    _attr_native_min = 1

    def __init__(
        self,
        coordinator: MinecraftBedrockCoordinator,
        manager_identifier: tuple[str, str],
    ) -> None:
        super().__init__(coordinator)
        self._attr_extra_state_attributes = {
            "bsm_role": "server",
            "bsm_key": "target_version",
        }
        self._attr_unique_id = f"{DOMAIN}_{manager_identifier[1]}_{coordinator.server_name}_target_version".lower().replace(
            ":", "_"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{manager_identifier[1]}_{coordinator.server_name}")}
        )

    @property
    def available(self) -> bool:
        return (
            super().available
            and "server_settings" not in self.coordinator.unavailable_resources
            and self.native_value is not None
        )

    @property
    def native_value(self) -> str | None:
        settings = (self.coordinator.data or {}).get("server_settings") or {}
        value = settings.get("settings", {}).get("target_version")
        return value if isinstance(value, str) else None

    async def async_set_value(self, value: str) -> None:
        """Persist the typed setting and reconcile with the backend response."""
        try:
            await self.coordinator.api.servers.async_set_server_setting(
                self.coordinator.server_name,
                ServerSettingItemPayload(key="settings.target_version", value=value),
            )
        except APIError as error:
            raise HomeAssistantError(str(error)) from error
        self.coordinator.invalidate({})
        await self.coordinator.async_request_refresh()
