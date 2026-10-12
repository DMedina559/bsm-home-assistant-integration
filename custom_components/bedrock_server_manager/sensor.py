# custom_components/bedrock_server_manager/sensor.py
"""Sensor platform for Bedrock Server Manager."""

import logging
from typing import Any, Dict, Optional, Tuple

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ALLOWLIST_BACKUPS_LIST,
    ATTR_ALLOWLISTED_PLAYERS,
    ATTR_AVAILABLE_ADDONS_LIST,
    ATTR_AVAILABLE_WORLDS_LIST,
    ATTR_CPU_PERCENT,
    ATTR_GLOBAL_PLAYERS_LIST,
    ATTR_INSTALLED_VERSION,
    ATTR_MANAGER_OS_TYPE,
    ATTR_MEMORY_MB,
    ATTR_PERMISSIONS_BACKUPS_LIST,
    ATTR_PID,
    ATTR_PLUGINS_DATA,
    ATTR_PROPERTIES_BACKUPS_LIST,
    ATTR_SERVER_ADDONS_LIST,
    ATTR_SERVER_PERMISSIONS_LIST,
    ATTR_SERVER_PROPERTIES,
    ATTR_UPTIME,
    ATTR_WORLD_BACKUPS_LIST,
    ATTR_WORLD_NAME,
    CONF_BASE_URL,
    DOMAIN,
    KEY_ALLOWLIST_BACKUPS_COUNT,
    KEY_ALLOWLIST_COUNT,
    KEY_AVAILABLE_ADDONS_COUNT,
    KEY_AVAILABLE_WORLDS_COUNT,
    KEY_GLOBAL_PLAYERS_COUNT,
    KEY_LEVEL_NAME,
    KEY_MANAGER_APP_VERSION,
    KEY_ONLINE_PLAYERS_COUNT,
    KEY_PERMISSIONS_BACKUPS_COUNT,
    KEY_PLUGIN_STATUSES,
    KEY_PROPERTIES_BACKUPS_COUNT,
    KEY_SERVER_ADDONS_COUNT,
    KEY_SERVER_BANS_COUNT,
    KEY_SERVER_PERMISSIONS_COUNT,
    KEY_WORLD_BACKUPS_COUNT,
)

# --- IMPORT FROM LOCAL MODULES ---
from .coordinator import ManagerDataCoordinator, MinecraftBedrockCoordinator
from .metrics import METRIC_DESCRIPTIONS, ApplicationMetricSensor

_LOGGER = logging.getLogger(__name__)

# --- Sensor Descriptions ---
SERVER_SENSOR_DESCRIPTIONS: Tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="uptime_seconds",
        name="Uptime",
        native_unit_of_measurement="s",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(key="status", name="Status", icon="mdi:minecraft"),
    SensorEntityDescription(
        key=ATTR_CPU_PERCENT,
        name="CPU Usage",
        icon="mdi:cpu-64-bit",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_MEMORY_MB,
        name="Memory Usage",
        icon="mdi:memory",
        native_unit_of_measurement="MiB",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=KEY_SERVER_ADDONS_COUNT,
        name="Installed Addons",
        icon="mdi:puzzle",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=KEY_SERVER_PERMISSIONS_COUNT,
        name="Permissioned Players",
        icon="mdi:account-key-outline",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=KEY_WORLD_BACKUPS_COUNT,
        name="World Backups",
        icon="mdi:archive-arrow-down-outline",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=KEY_ALLOWLIST_BACKUPS_COUNT,
        name="Allowlist Backups",
        icon="mdi:file-settings-outline",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=KEY_PROPERTIES_BACKUPS_COUNT,
        name="Properties Backups",
        icon="mdi:file-settings-outline",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=KEY_PERMISSIONS_BACKUPS_COUNT,
        name="Permissions Backups",
        icon="mdi:file-settings-outline",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=KEY_LEVEL_NAME, name="Level Name", icon="mdi:map-legend"
    ),
    SensorEntityDescription(
        key=KEY_ALLOWLIST_COUNT,
        name="Allowlist Players",
        icon="mdi:format-list-checks",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=KEY_ONLINE_PLAYERS_COUNT,
        name="Online Players",
        icon="mdi:account-group",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=KEY_SERVER_BANS_COUNT,
        name="Server Bans",
        icon="mdi:account-cancel",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

MANAGER_SENSOR_DESCRIPTIONS: Tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=KEY_GLOBAL_PLAYERS_COUNT,
        name="Global Known Players",
        icon="mdi:account-group-outline",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=KEY_AVAILABLE_WORLDS_COUNT,
        name="Available Worlds",
        icon="mdi:earth-box",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=KEY_AVAILABLE_ADDONS_COUNT,
        name="Available Addons",
        icon="mdi:puzzle-edit-outline",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=KEY_MANAGER_APP_VERSION,
        name="Manager App Version",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key=KEY_PLUGIN_STATUSES,
        name="Plugin Statuses",
        icon="mdi:puzzle-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create stable entities from coordinator snapshots without duplicate HTTP calls."""
    data = hass.data[DOMAIN][entry.entry_id]
    identifier = data["manager_identifier"]
    manager = data["manager_coordinator"]
    os_type = (manager.data or {}).get("info", {}).get("os_type", "Unknown")
    entities: list[SensorEntity] = [
        ApplicationMetricSensor(data["monitor_coordinator"], description, identifier)
        for description in METRIC_DESCRIPTIONS
    ]
    entities.extend(
        ManagerInfoSensor(manager, description, identifier)
        for description in MANAGER_SENSOR_DESCRIPTIONS
    )
    for name, server in data["servers"].items():
        coordinator = server["coordinator"]
        snapshot = coordinator.data or {}
        version = snapshot.get("version")
        world = snapshot.get("properties", {}).get("level-name")
        server[ATTR_INSTALLED_VERSION] = version
        server[ATTR_WORLD_NAME] = world
        entities.extend(
            MinecraftServerSensor(
                coordinator=coordinator,
                description=description,
                server_name=name,
                manager_identifier=identifier,
                installed_version_static=version,
                world_name_static=world,
                bsm_os_type=os_type,
            )
            for description in SERVER_SENSOR_DESCRIPTIONS
        )
    async_add_entities(entities)


class MinecraftServerSensor(
    CoordinatorEntity[MinecraftBedrockCoordinator], SensorEntity
):
    _unrecorded_attributes = frozenset(
        {
            "server_properties",
            "server_permissions",
            "server_addons_list",
            "world_backups_list",
            "allowlist_backups_list",
            "properties_backups_list",
            "permissions_backups_list",
            "allowed_players",
            "online_players",
            "server_bans",
            "global_players_list",
            "available_worlds_list",
            "available_addons_list",
            "plugins_data",
            "pid",
            "uptime",
            "bsm_settings_revision",
            "bsm_updated_at",
            "bsm_last_error",
        }
    )
    _attr_device_info: dr.DeviceInfo
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MinecraftBedrockCoordinator,
        description: SensorEntityDescription,
        server_name: str,
        manager_identifier: Tuple[str, str],
        installed_version_static: Optional[str],
        world_name_static: Optional[str],
        bsm_os_type: Optional[str],
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        if description.key == "status":
            # Dynamic flattened settings belong to live state, not recorder history.
            self._unrecorded_attributes = frozenset({"*"})
        self._server_name = server_name
        self._manager_host_port_id = manager_identifier[1]
        self._bsm_os_type = bsm_os_type

        # Explicitly log what's being set
        _LOGGER.debug(
            "MinecraftServerSensor __init__ for %s: Setting _installed_version_static to: %s",
            server_name,
            installed_version_static,
        )
        self._installed_version_static = installed_version_static

        _LOGGER.debug(
            "MinecraftServerSensor __init__ for %s: Setting _world_name_static to: %s",
            server_name,
            world_name_static,
        )
        self._world_name_static = world_name_static

        self._attr_unique_id = (
            f"{DOMAIN}_{self._manager_host_port_id}_{self._server_name}_{description.key}".lower()
            .replace(":", "_")
            .replace(".", "_")
        )
        # Use self.name which falls back to entity_description.name if _attr_name is not set.
        # This ensures we log the actual name that will be used if has_entity_name is True and name isn't overridden.
        entity_name_for_log = (
            self.name or description.name
        )  # Prefer self.name if available
        _LOGGER.debug(
            "Init ServerSensor '%s' for server '%s', UniqueID: %s",
            entity_name_for_log,
            self._server_name,
            self._attr_unique_id,
        )

        config_entry_data = (
            coordinator.config_entry.data
            if coordinator.config_entry
            else {CONF_BASE_URL: manager_identifier[1]}
        )
        safe_config_url = config_entry_data.get(CONF_BASE_URL)

        dynamic_sw_version = None
        if self.coordinator.data:
            dynamic_sw_version = self.coordinator.data.get("version")

        # Construct the model string
        base_model_name = "Minecraft Bedrock Server"
        model_name_with_os = base_model_name
        # Define uninformative OS types that shouldn't alter the base model name
        uninformative_os_types = ["Unknown", None, ""]
        if self._bsm_os_type and self._bsm_os_type not in uninformative_os_types:
            model_name_with_os = f"{base_model_name} ({self._bsm_os_type})"
        else:
            _LOGGER.debug(
                "BSM OS type for server '%s' is '%s' (or uninformative), using base model name: '%s'.",
                server_name,
                self._bsm_os_type,
                base_model_name,
            )

        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, f"{self._manager_host_port_id}_{self._server_name}")},
            name=f"{self._server_name} ({self._manager_host_port_id})",
            manufacturer="Bedrock Server Manager",
            model=model_name_with_os,
            sw_version=dynamic_sw_version
            or self._installed_version_static
            or "Unknown",
            **(
                {"via_device_id": coordinator.manager_device_id}
                if coordinator.manager_device_id
                else {}
            ),
            configuration_url=safe_config_url,
        )

    @property
    def resource(self) -> str | None:
        return {
            "status": "summary",
            ATTR_CPU_PERCENT: "process_info",
            ATTR_MEMORY_MB: "process_info",
            "uptime_seconds": "process_info",
            KEY_SERVER_ADDONS_COUNT: "server_addons",
            KEY_SERVER_PERMISSIONS_COUNT: "server_permissions",
            KEY_WORLD_BACKUPS_COUNT: "world_backups",
            KEY_ALLOWLIST_BACKUPS_COUNT: "allowlist_backups",
            KEY_PROPERTIES_BACKUPS_COUNT: "properties_backups",
            KEY_PERMISSIONS_BACKUPS_COUNT: "permissions_backups",
            KEY_LEVEL_NAME: "properties",
            KEY_ALLOWLIST_COUNT: "allowlist",
            KEY_ONLINE_PLAYERS_COUNT: "summary",
            KEY_SERVER_BANS_COUNT: "server_bans",
        }.get(self.entity_description.key)

    @property
    def available(self) -> bool:
        resource = self.resource
        if (
            resource in self.coordinator.unavailable_resources
            or resource in self.coordinator.unsupported_resources
        ):
            return False
        if resource == "process_info" and not (self.coordinator.data or {}).get(
            "process_info"
        ):
            return False
        return super().available and bool(self.coordinator.data)

    @property
    def native_value(self) -> Any:  # noqa: C901
        if not self.available or not isinstance(self.coordinator.data, dict):
            return None
        data = self.coordinator.data
        key = self.entity_description.key
        process_info = data.get("process_info")

        if key == "uptime_seconds":
            return uptime_seconds((process_info or {}).get("uptime"))
        if key == "status":
            server_status = data.get("server_status", "UNKNOWN")
            if server_status:
                return str(server_status).capitalize()
            return "Unknown"
        if key == ATTR_CPU_PERCENT:
            return (
                process_info.get("cpu_percent")
                if isinstance(process_info, dict)
                else None
            )
        if key == ATTR_MEMORY_MB:
            return (
                process_info.get("memory_mb")
                if isinstance(process_info, dict)
                else None
            )
        if key == KEY_SERVER_PERMISSIONS_COUNT:
            return len(data.get("server_permissions", []))
        if key == KEY_SERVER_ADDONS_COUNT:
            addons = data.get("server_addons")
            if addons:
                return len((addons.get("behavior_packs") or [])) + len(
                    (addons.get("resource_packs") or [])
                )
            return 0
        if key == KEY_WORLD_BACKUPS_COUNT:
            return len(data.get("world_backups", []))
        if key == KEY_ALLOWLIST_BACKUPS_COUNT:
            return len(data.get("allowlist_backups", []))
        if key == KEY_PERMISSIONS_BACKUPS_COUNT:
            return len(data.get("permissions_backups", []))
        if key == KEY_PROPERTIES_BACKUPS_COUNT:
            return len(data.get("properties_backups", []))
        if key == KEY_ALLOWLIST_COUNT:
            return len(data.get("allowlist", []))
        if key == KEY_ONLINE_PLAYERS_COUNT:
            # Prefer player_count from summary if available, fallback to len of online_players
            player_count = data.get("player_count")
            if player_count is not None:
                return player_count
            return len(data.get("online_players", []))
        if key == KEY_SERVER_BANS_COUNT:
            return len(data.get("server_bans", []))
        if key == KEY_LEVEL_NAME:
            props = data.get("properties", {})
            dyn_lvl_name = props.get("level-name")
            return (
                dyn_lvl_name
                if dyn_lvl_name is not None
                else (self._world_name_static or "Unknown")
            )

        _LOGGER.warning(
            "Unhandled sensor key '%s' for native_value in %s", key, self.unique_id
        )
        return None

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:  # noqa: C901
        data = self.coordinator.data or {}
        attrs: Dict[str, Any] = {
            "bsm_role": "server",
            "bsm_key": self.entity_description.key,
            "bsm_server_name": self._server_name,
            "bsm_manager_url": self._manager_host_port_id,
            **self.coordinator.resource_metadata(self.resource),
        }
        if not self.available:
            return attrs
        key = self.entity_description.key
        process_info = data.get("process_info")

        if key == "status":
            attrs["bsm_settings_revision"] = self.coordinator.state.generation
            if self._installed_version_static:  # This should now be safe
                attrs[ATTR_INSTALLED_VERSION] = self._installed_version_static

            # Add all settings from coordinator to the status sensor
            server_settings = data.get("server_settings", {})
            if isinstance(server_settings, dict):
                server_info = server_settings.get("server_info", {})
                inner_settings = server_settings.get("settings", {})
                custom_settings = server_settings.get("custom", {})

                # Flatten the settings cleanly
                for k, v in server_info.items():
                    attrs[f"server_info_{k}"] = v
                for k, v in inner_settings.items():
                    attrs[f"settings_{k}"] = v
                for k, v in custom_settings.items():
                    attrs[f"custom_{k}"] = v

                # Ensure direct keys that aren't nested aren't skipped
                for k, v in server_settings.items():
                    if k not in ["server_info", "settings", "custom"]:
                        attrs[k] = v
        elif key in [ATTR_CPU_PERCENT, ATTR_MEMORY_MB]:
            if isinstance(process_info, dict):
                if process_info.get(ATTR_PID) is not None:
                    attrs[ATTR_PID] = process_info[ATTR_PID]
                if process_info.get(ATTR_UPTIME) is not None:
                    attrs[ATTR_UPTIME] = process_info[ATTR_UPTIME]
        elif key == KEY_SERVER_PERMISSIONS_COUNT:
            attrs[ATTR_SERVER_PERMISSIONS_LIST] = data.get("server_permissions", [])
        elif key == KEY_SERVER_ADDONS_COUNT:
            addons = data.get("server_addons")
            attrs[ATTR_SERVER_ADDONS_LIST] = addons or {}
        elif key == KEY_WORLD_BACKUPS_COUNT:
            attrs[ATTR_WORLD_BACKUPS_LIST] = data.get("world_backups", [])
        elif key == KEY_ALLOWLIST_BACKUPS_COUNT:
            attrs[ATTR_ALLOWLIST_BACKUPS_LIST] = data.get("allowlist_backups", [])
        elif key == KEY_PROPERTIES_BACKUPS_COUNT:
            attrs[ATTR_PROPERTIES_BACKUPS_LIST] = data.get("properties_backups", [])
        elif key == KEY_PERMISSIONS_BACKUPS_COUNT:
            attrs[ATTR_PERMISSIONS_BACKUPS_LIST] = data.get("permissions_backups", [])
        elif key == KEY_ALLOWLIST_COUNT:
            attrs[ATTR_ALLOWLISTED_PLAYERS] = [
                p.get("name") for p in data.get("allowlist", []) if isinstance(p, dict)
            ]
        elif key == KEY_ONLINE_PLAYERS_COUNT:
            attrs["online_players"] = data.get("online_players", [])
        elif key == KEY_SERVER_BANS_COUNT:
            attrs["server_bans"] = data.get("server_bans", [])
        elif key == KEY_LEVEL_NAME:
            attrs[ATTR_SERVER_PROPERTIES] = data.get("properties", {})
        return attrs if attrs else None

    @callback
    def _handle_coordinator_update(self) -> None:
        if (
            self.coordinator.last_update_success
            and isinstance(self.coordinator.data, dict)
            and self._attr_device_info
        ):
            dynamic_version_from_coord = self.coordinator.data.get("version")
            new_sw_version = (
                dynamic_version_from_coord
                or self._installed_version_static
                or "Unknown"
            )
            current_device_sw_version = self._attr_device_info.get("sw_version")

            if (
                new_sw_version != "Unknown"
                and new_sw_version != current_device_sw_version
            ):
                _LOGGER.debug(
                    "Server '%s' SW version update: from '%s' to '%s'.",
                    self._server_name,
                    current_device_sw_version,
                    new_sw_version,
                )
                device_registry = dr.async_get(self.hass)
                device_entry = device_registry.async_get_device(
                    identifiers=self._attr_device_info["identifiers"]
                )
                if device_entry:
                    device_registry.async_update_device(
                        device_entry.id, sw_version=new_sw_version
                    )
                    self._attr_device_info["sw_version"] = new_sw_version
                    if (
                        dynamic_version_from_coord
                        and dynamic_version_from_coord != "Unknown"
                    ):
                        self._installed_version_static = dynamic_version_from_coord
        super()._handle_coordinator_update()


class ManagerInfoSensor(CoordinatorEntity[ManagerDataCoordinator], SensorEntity):
    _unrecorded_attributes = frozenset(
        {
            "server_properties",
            "server_permissions",
            "server_addons_list",
            "world_backups_list",
            "allowlist_backups_list",
            "properties_backups_list",
            "permissions_backups_list",
            "allowed_players",
            "online_players",
            "server_bans",
            "global_players_list",
            "available_worlds_list",
            "available_addons_list",
            "plugins_data",
            "pid",
            "uptime",
            "bsm_settings_revision",
            "bsm_updated_at",
            "bsm_last_error",
        }
    )
    _attr_device_info: dr.DeviceInfo
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ManagerDataCoordinator,
        description: SensorEntityDescription,
        manager_identifier: Tuple[str, str],
    ):
        super().__init__(coordinator)
        self.entity_description = description
        self._manager_host_port_id = manager_identifier[1]
        self._attr_unique_id = (
            f"{DOMAIN}_{self._manager_host_port_id}_{description.key}".lower().replace(
                ":", "_"
            )
        )
        self._attr_device_info = dr.DeviceInfo(identifiers={manager_identifier})

    @property
    def available(self) -> bool:
        resource = {
            KEY_GLOBAL_PLAYERS_COUNT: "global_players",
            KEY_AVAILABLE_WORLDS_COUNT: "available_worlds",
            KEY_AVAILABLE_ADDONS_COUNT: "available_addons",
            KEY_MANAGER_APP_VERSION: "info",
            KEY_PLUGIN_STATUSES: "plugins_status",
        }.get(self.entity_description.key)
        return (
            super().available
            and resource not in self.coordinator.unavailable_resources
            and bool(self.coordinator.data)
        )

    @property
    def native_value(self) -> Optional[Any]:
        if not self.available or not isinstance(self.coordinator.data, dict):
            return None
        data = self.coordinator.data
        key = self.entity_description.key
        if key == KEY_GLOBAL_PLAYERS_COUNT:
            return len(data.get("global_players", []))
        if key == KEY_AVAILABLE_WORLDS_COUNT:
            return len(data.get("available_worlds", []))
        if key == KEY_AVAILABLE_ADDONS_COUNT:
            return len(data.get("available_addons", []))
        if key == KEY_MANAGER_APP_VERSION:
            info = data.get("info", {})
            return (
                info.get("app_version", "Unknown")
                if isinstance(info, dict)
                else "Unknown"
            )
        if key == KEY_PLUGIN_STATUSES:
            plugins_data = data.get("plugins_status", {})
            if isinstance(plugins_data, dict):
                return len(plugins_data)  # Total number of plugins
            return 0  # Default to 0 if data is not as expected

        _LOGGER.warning(
            "Unhandled manager sensor key '%s' for native_value in %s",
            key,
            self.unique_id,
        )
        return None

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:  # noqa: C901
        data = self.coordinator.data or {}
        key = self.entity_description.key
        resource = {
            KEY_GLOBAL_PLAYERS_COUNT: "global_players",
            KEY_AVAILABLE_WORLDS_COUNT: "available_worlds",
            KEY_AVAILABLE_ADDONS_COUNT: "available_addons",
            KEY_MANAGER_APP_VERSION: "info",
            KEY_PLUGIN_STATUSES: "plugins_status",
        }.get(key)
        attrs: Dict[str, Any] = {
            "bsm_role": "manager",
            "bsm_key": key,
            "bsm_manager_url": self._manager_host_port_id,
            **self.coordinator.resource_metadata(resource),
        }
        if not self.available:
            return attrs
        attrs["bsm_settings_revision"] = self.coordinator.state.generation
        if key == KEY_GLOBAL_PLAYERS_COUNT:
            attrs[ATTR_GLOBAL_PLAYERS_LIST] = data.get("global_players", [])
        if key == KEY_AVAILABLE_WORLDS_COUNT:
            attrs[ATTR_AVAILABLE_WORLDS_LIST] = data.get("available_worlds", [])
        if key == KEY_AVAILABLE_ADDONS_COUNT:
            attrs[ATTR_AVAILABLE_ADDONS_LIST] = data.get("available_addons", [])
        if key == KEY_MANAGER_APP_VERSION:
            info = data.get("info", {})
            attrs[ATTR_MANAGER_OS_TYPE] = (
                info.get("os_type", "Unknown") if isinstance(info, dict) else "Unknown"
            )
        if key == KEY_PLUGIN_STATUSES:
            attrs["bsm_settings_revision"] = self.coordinator.state.generation
            plugins_raw_data = data.get("plugins_status", {})
            if isinstance(plugins_raw_data, dict):
                attrs[ATTR_PLUGINS_DATA] = plugins_raw_data
            else:
                attrs[ATTR_PLUGINS_DATA] = {}

        return attrs if attrs else None


def uptime_seconds(value: str | None) -> float | None:
    """Convert the backend timedelta text into native duration statistics."""
    if not value:
        return None
    try:
        day_part, separator, clock = value.partition(", ")
        days = int(day_part.split()[0]) if separator else 0
        hours, minutes, seconds = (clock if separator else value).split(":")
        return days * 86400 + int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except (ValueError, TypeError):
        return None
