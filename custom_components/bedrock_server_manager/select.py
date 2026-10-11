"""Native selection of common server update channels."""

from bsm_api_client import APIError
from bsm_api_client.models import ServerSettingItemPayload
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MinecraftBedrockCoordinator
from .reconcile import refresh_after_action


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add optional update-channel selections beside the exact-version text entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            UpdateChannelSelect(server["coordinator"], data["manager_identifier"])
            for server in data["servers"].values()
        ]
    )


class UpdateChannelSelect(CoordinatorEntity[MinecraftBedrockCoordinator], SelectEntity):
    """Offer standard channels and retain any configured exact version as an option."""

    _attr_has_entity_name = True
    _attr_name = "Update channel"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: MinecraftBedrockCoordinator, identifier: tuple[str, str]
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{identifier[1]}_{coordinator.server_name}_update_channel".lower().replace(
            ":", "_"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{identifier[1]}_{coordinator.server_name}")}
        )
        self._attr_extra_state_attributes = {
            "bsm_role": "server",
            "bsm_key": "update_channel",
            "bsm_manager_url": identifier[1],
            "bsm_server_name": coordinator.server_name,
        }

    @property
    def extra_state_attributes(self) -> dict:
        """Keep identity and resource freshness available during outages."""
        return {
            **self._attr_extra_state_attributes,
            **self.coordinator.resource_metadata("server_settings"),
        }

    @property
    def current_option(self) -> str | None:
        value = (
            (self.coordinator.data or {})
            .get("server_settings", {})
            .get("settings", {})
            .get("target_version")
        )
        return value if isinstance(value, str) and value else None

    @property
    def options(self) -> list[str]:
        return list(
            dict.fromkeys(
                [
                    "LATEST",
                    "PREVIEW",
                    *([self.current_option] if self.current_option else []),
                ]
            )
        )

    @property
    def available(self) -> bool:
        return (
            super().available
            and "server_settings" not in self.coordinator.unavailable_resources
            and self.current_option is not None
        )

    async def async_select_option(self, option: str) -> None:
        """Set the target channel through the same typed setting as exact versions."""
        if option not in self.options:
            raise HomeAssistantError("Choose a supported update channel")
        try:
            await self.coordinator.api.servers.async_set_server_setting(
                self.coordinator.server_name,
                ServerSettingItemPayload(key="settings.target_version", value=option),
            )
        except (APIError, ValueError) as error:
            raise HomeAssistantError(str(error)) from error
        refresh_after_action(self.coordinator, {"server_settings", "summary"})
