# custom_components/bedrock_server_manager/switch.py
"""Switch platform for Bedrock Server Manager."""

import logging
from typing import Any, Optional, Tuple

from bsm_api_client import (
    APIError,
    ServerNotRunningError,
)
from bsm_api_client.models import PluginStatusSetPayload, ServerSettingItemPayload
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .action_common import _base_api_call_handler
from .const import ATTR_INSTALLED_VERSION, CONF_BASE_URL, DOMAIN
from .coordinator import ManagerDataCoordinator, MinecraftBedrockCoordinator
from .reconcile import refresh_after_action

_LOGGER = logging.getLogger(__name__)


# Descriptions for the server control switch
SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="server_control",  # This key is primarily for internal use if you had multiple switch types
    name="Server",  # This will be the entity's friendly name suffix
    icon="mdi:minecraft",
)

AUTOUPDATE_SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="autoupdate",
    name="Autoupdate",
    icon="mdi:update",
)

AUTOSTART_SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="autostart",
    name="Autostart",
    icon="mdi:play-circle-outline",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create stable controls for selected servers and discover plugin switches."""
    data = hass.data[DOMAIN][entry.entry_id]
    identifier = data["manager_identifier"]
    manager = data["manager_coordinator"]
    os_type = (manager.data or {}).get("info", {}).get("os_type", "Unknown")
    entities: list[SwitchEntity] = []
    for name, server in data["servers"].items():
        coordinator = server["coordinator"]
        entities.append(
            MinecraftServerSwitch(
                coordinator=coordinator,
                description=SWITCH_DESCRIPTION,
                server_name=name,
                manager_identifier=identifier,
                installed_version_static=server.get(ATTR_INSTALLED_VERSION),
                bsm_os_type=os_type,
                base_url=entry.data[CONF_BASE_URL],
            )
        )
        for description in (
            AUTOUPDATE_SWITCH_DESCRIPTION,
            AUTOSTART_SWITCH_DESCRIPTION,
        ):
            entities.append(
                MinecraftServerSettingSwitch(
                    coordinator=coordinator,
                    description=description,
                    manager_identifier=identifier,
                    server_name=name,
                    base_url=entry.data[CONF_BASE_URL],
                    bsm_os_type=os_type,
                    setting_key=description.key,
                )
            )
    async_add_entities(entities)
    _watch_plugins(entry, manager, identifier, async_add_entities)


def _watch_plugins(
    entry: ConfigEntry,
    coordinator: ManagerDataCoordinator,
    identifier: tuple[str, str],
    add_entities: AddEntitiesCallback,
) -> None:
    """Discover plugins after reload and retain unavailable entities after removal."""
    known_plugins: set[str] = set()

    @callback
    def add_plugin_switches() -> None:
        plugins = (coordinator.data or {}).get("plugins_status") or {}
        added = [
            PluginEnabledSwitch(coordinator, identifier, name)
            for name in sorted(set(plugins) - known_plugins)
        ]
        known_plugins.update(plugins)
        if added:
            add_entities(added)

    entry.async_on_unload(coordinator.async_add_listener(add_plugin_switches))
    add_plugin_switches()


class MinecraftServerSwitch(
    CoordinatorEntity[MinecraftBedrockCoordinator], SwitchEntity
):
    """Represents a switch to control a Minecraft Bedrock server."""

    _attr_device_info: dr.DeviceInfo
    _attr_has_entity_name = True  # Name will be "Device Name Switch Name" (e.g. "Server MyServer Server Power")

    def __init__(
        self,
        coordinator: MinecraftBedrockCoordinator,
        description: SwitchEntityDescription,  # Make sure this is SwitchEntityDescription
        server_name: str,  # The configured name of the server (e.g., "s1", "my_world")
        manager_identifier: Tuple[str, str],  # (DOMAIN, manager_host_port_id string)
        installed_version_static: Optional[
            str
        ],  # Can be None, used as fallback for sw_version
        bsm_os_type: Optional[str],
        base_url: str = "",
    ) -> None:
        """Initialize the server switch."""
        super().__init__(coordinator)  # Initialize CoordinatorEntity
        self.entity_description = description
        self._attr_extra_state_attributes = {
            "bsm_role": "server",
            "bsm_key": description.key,
        }
        self._server_name = server_name
        self._manager_host_port_id = manager_identifier[1]
        self._attr_installed_version_static = installed_version_static
        self._bsm_os_type = bsm_os_type

        # Construct unique_id for the switch entity itself
        self._attr_unique_id = (
            f"{DOMAIN}_{self._manager_host_port_id}_{self._server_name}_{description.key}".lower()
            .replace(":", "_")
            .replace(".", "_")
        )  # Make it a safe string for an entity ID

        _LOGGER.debug(
            "Init ServerSwitch '%s' for server '%s' (Manager ID: %s), UniqueID: %s",
            description.key,  # Log the key for dev clarity, UI name will be entity_description.name
            self._server_name,
            self._manager_host_port_id,
            self._attr_unique_id,
        )

        config_entry_data = (
            coordinator.config_entry.data
            if coordinator.config_entry
            else {CONF_BASE_URL: manager_identifier[1]}
        )
        safe_config_url = config_entry_data.get(CONF_BASE_URL)

        # Construct the model string
        base_model_name = "Minecraft Bedrock Server"
        model_name_with_os = base_model_name
        uninformative_os_types = ["Unknown", None, ""]
        if self._bsm_os_type and self._bsm_os_type not in uninformative_os_types:
            model_name_with_os = f"{base_model_name} ({self._bsm_os_type})"
        else:
            _LOGGER.debug(
                "BSM OS type for server switch device '%s' is '%s' (or uninformative), using base model name: '%s'.",
                self._server_name,
                self._bsm_os_type,
                base_model_name,
            )

        # Define the device for this specific Minecraft server.
        safe_config_url = base_url
        if not safe_config_url.startswith("http://") and not safe_config_url.startswith(
            "https://"
        ):
            safe_config_url = f"http://{safe_config_url}"

        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, f"{self._manager_host_port_id}_{self._server_name}")},
            name=f"{self._server_name} ({self._manager_host_port_id})",  # Use the configured server name
            manufacturer="Bedrock Server Manager",
            model=model_name_with_os,
            # Try to get dynamic version from coordinator, then static, then Unknown
            sw_version=(
                self.coordinator.data.get("version") if self.coordinator.data else None
            )
            or installed_version_static
            or "Unknown",
            **(
                {"via_device_id": coordinator.manager_device_id}
                if coordinator.manager_device_id
                else {}
            ),
            configuration_url=safe_config_url,
        )

    @property
    def available(self) -> bool:
        """Return True if coordinator is available and has data."""
        # last_update_success is checked by super().available
        return (
            super().available
            and self.coordinator.data is not None
            and "process_info" not in self.coordinator.unavailable_resources
        )

    @property
    def is_on(self) -> bool:
        """Return true if the server is considered running."""
        # Ensure coordinator data is valid before accessing
        if not self.available:  # Relies on the refined available property
            _LOGGER.debug(
                "Switch %s unavailable, reporting is_on as False.", self.unique_id
            )
            return False  # Or self._attr_is_on to retain last known state if preferred

        server_status = self.coordinator.data.get("server_status", "UNKNOWN")
        # Server is 'on' if server_status is RUNNING (fallback to checking process_info if status isn't available)
        if server_status != "UNKNOWN":
            current_state_is_on = str(server_status).upper() == "RUNNING"
        else:
            process_info = self.coordinator.data.get("process_info")
            current_state_is_on = isinstance(process_info, dict)

        return current_state_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Request start and reconcile confirmed process and status state."""
        await _base_api_call_handler(
            self.coordinator.api.servers.async_start_server(self._server_name),
            "Start server",
            self._server_name,
        )
        refresh_after_action(self.coordinator, {"process_info", "summary"})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Request an idempotent stop and reconcile confirmed process state."""
        try:
            await _base_api_call_handler(
                self.coordinator.api.servers.async_stop_server(self._server_name),
                "Stop server",
                self._server_name,
            )
        except HomeAssistantError as error:
            if not isinstance(error.__cause__, ServerNotRunningError):
                raise
        refresh_after_action(self.coordinator, {"process_info", "summary"})

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator and update device sw_version if applicable."""
        if (
            self.coordinator.last_update_success
            and isinstance(self.coordinator.data, dict)
            and self._attr_device_info
        ):  # Ensure device_info was set

            # Dynamic SW Version update logic
            dynamic_version_from_coord = self.coordinator.data.get(
                "version"
            )  # Must match key in coordinator data

            current_device_sw_version = self._attr_device_info.get("sw_version")

            if (
                dynamic_version_from_coord
                and dynamic_version_from_coord != "Unknown"
                and dynamic_version_from_coord != current_device_sw_version
            ):

                _LOGGER.debug(
                    "Switch for server '%s': version '%s' from coordinator differs from device SW version '%s'. Updating device.",
                    self._server_name,
                    dynamic_version_from_coord,
                    current_device_sw_version,
                )
                device_registry = dr.async_get(self.hass)
                device_entry = device_registry.async_get_device(
                    identifiers=self._attr_device_info["identifiers"]
                )

                if device_entry:
                    device_registry.async_update_device(
                        device_entry.id, sw_version=dynamic_version_from_coord
                    )
                    self._attr_device_info["sw_version"] = (
                        dynamic_version_from_coord  # Update local cache
                    )
                    self._attr_installed_version_static = (
                        dynamic_version_from_coord  # Update static cache
                    )

        super()._handle_coordinator_update()  # This calls self.async_write_ha_state()


class MinecraftServerSettingSwitch(
    CoordinatorEntity[MinecraftBedrockCoordinator], SwitchEntity
):
    """Switch for managing a specific server setting via BSM."""

    def __init__(
        self,
        coordinator: MinecraftBedrockCoordinator,
        description: SwitchEntityDescription,
        manager_identifier: Tuple[str, str],
        server_name: str,
        base_url: str,
        bsm_os_type: str,
        setting_key: str,
    ) -> None:
        """Initialize the setting switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_extra_state_attributes = {
            "bsm_role": "server",
            "bsm_key": description.key,
        }
        self._server_name = server_name
        self._manager_host_port_id = manager_identifier[1]
        self._setting_key = setting_key

        self._attr_unique_id = (
            f"{self._manager_host_port_id}_{server_name}_{setting_key}"
        )
        self._attr_has_entity_name = True

        safe_config_url = base_url
        if not safe_config_url.startswith("http://") and not safe_config_url.startswith(
            "https://"
        ):
            safe_config_url = f"http://{safe_config_url}"

        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, f"{self._manager_host_port_id}_{self._server_name}")},
            name=f"{self._server_name} ({self._manager_host_port_id})",
            manufacturer="Bedrock Server Manager",
            model=f"Minecraft Server ({bsm_os_type.capitalize()})",
            **(
                {"via_device_id": coordinator.manager_device_id}
                if coordinator.manager_device_id
                else {}
            ),
            configuration_url=safe_config_url,
        )

    @property
    def available(self) -> bool:
        """Return True if coordinator is available and has data."""
        return (
            super().available
            and self.coordinator.data is not None
            and "server_settings" not in self.coordinator.unavailable_resources
        )

    @property
    def is_on(self) -> bool:
        """Return true if the setting is true."""
        if not self.available:
            return False

        server_settings = self.coordinator.data.get("server_settings", {})
        if not server_settings:
            return False

        # Check in the nested 'settings' dict where autostart/autoupdate live
        inner_settings = server_settings.get("settings", {})
        if self._setting_key in inner_settings:
            return bool(inner_settings.get(self._setting_key, False))

        return bool(server_settings.get(self._setting_key, False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the setting on."""
        await self._set_setting(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the setting off."""
        await self._set_setting(False)

    async def _set_setting(self, state: bool) -> None:
        """Persist a typed setting and share mutation invalidation with actions."""
        await _base_api_call_handler(
            self.coordinator.api.servers.async_set_server_setting(
                self._server_name,
                ServerSettingItemPayload(
                    key=f"settings.{self._setting_key}", value=state
                ),
            ),
            "Set server setting",
            self._server_name,
        )
        refresh_after_action(self.coordinator, {"server_settings", "summary"})


class PluginEnabledSwitch(CoordinatorEntity[ManagerDataCoordinator], SwitchEntity):
    """A plugin enable control that remains consistent with live backend changes."""

    _attr_device_info: dr.DeviceInfo
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:puzzle"

    def __init__(
        self,
        coordinator: ManagerDataCoordinator,
        manager_identifier: tuple[str, str],
        plugin_name: str,
    ) -> None:
        super().__init__(coordinator)
        self.plugin_name = plugin_name
        self._attr_extra_state_attributes = {
            "bsm_role": "manager",
            "bsm_key": f"plugin:{plugin_name}",
        }
        self._attr_name = f"Plugin {plugin_name}"
        self._attr_unique_id = (
            f"{DOMAIN}_{manager_identifier[1]}_plugin_{plugin_name}".lower().replace(
                ":", "_"
            )
        )
        self._attr_device_info = dr.DeviceInfo(identifiers={manager_identifier})

    @property
    def available(self) -> bool:
        return (
            super().available
            and "plugins_status" not in self.coordinator.unavailable_resources
            and self.plugin_name
            in ((self.coordinator.data or {}).get("plugins_status") or {})
        )

    @property
    def is_on(self) -> bool:
        plugin = ((self.coordinator.data or {}).get("plugins_status") or {}).get(
            self.plugin_name, {}
        )
        return bool(plugin.get("enabled"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_enabled(False)

    async def _set_enabled(self, enabled: bool) -> None:
        """Persist plugin status, then obtain the authoritative backend state."""
        try:
            await self.coordinator.api.plugins.async_set_plugin_status(
                self.plugin_name, PluginStatusSetPayload(enabled=enabled)
            )
        except APIError as error:
            raise HomeAssistantError(str(error)) from error
        refresh_after_action(self.coordinator)
