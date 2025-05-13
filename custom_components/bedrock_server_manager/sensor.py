# custom_components/bedrock_server_manager/sensor.py
"""Sensor platform for Bedrock Server Manager."""

import asyncio
import logging
from typing import Optional, Dict, Any, List

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

# --- IMPORT FROM LOCAL MODULES ---
from .coordinator import MinecraftBedrockCoordinator, ManagerDataCoordinator
from .const import (
    DOMAIN,
    ATTR_CPU_PERCENT,
    ATTR_MEMORY_MB,
    ATTR_PID,
    ATTR_UPTIME,
    ATTR_WORLD_NAME,
    ATTR_INSTALLED_VERSION,
    ATTR_ALLOWLISTED_PLAYERS,
    ATTR_SERVER_PROPERTIES,
    ATTR_CONFIG_BACKUPS_LIST,
    ATTR_WORLD_BACKUPS_LIST,
    ATTR_AVAILABLE_ADDONS_LIST,
    ATTR_AVAILABLE_WORLDS_LIST,
    KEY_GLOBAL_PLAYERS,
    KEY_LEVEL_NAME,
    KEY_ALLOWLIST_COUNT,
    KEY_SERVER_PERMISSIONS_COUNT,
    KEY_CONFIG_BACKUPS_COUNT,
    KEY_WORLD_BACKUPS_COUNT,
    KEY_AVAILABLE_ADDONS_COUNT,
    KEY_AVAILABLE_WORLDS_COUNT,
    ATTR_GLOBAL_PLAYERS_LIST,
    ATTR_SERVER_PERMISSIONS_LIST,
)


from pybedrock_server_manager import (
    BedrockServerManagerApi,
    APIError,
    AuthError,
    CannotConnectError,
    ServerNotFoundError,
)


_LOGGER = logging.getLogger(__name__)

# --- Sensor Descriptions ---
SERVER_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(key="status", name="Status", icon="mdi:minecraft"),
    SensorEntityDescription(
        key=ATTR_CPU_PERCENT,
        name="CPU Usage",
        icon="mdi:cpu-64-bit",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key=ATTR_MEMORY_MB,
        name="Memory Usage",
        icon="mdi:memory",
        native_unit_of_measurement="MiB",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE,
        suggested_unit_of_measurement="MiB",
    ),
    SensorEntityDescription(
        key=KEY_SERVER_PERMISSIONS_COUNT,
        name="Permissioned Players",
        icon="mdi:account-key",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=KEY_WORLD_BACKUPS_COUNT,
        name="World Backups",
        icon="mdi:earth-box",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=KEY_CONFIG_BACKUPS_COUNT,
        name="Config Backups",
        icon="mdi:file-cog",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=KEY_LEVEL_NAME, name="Level Name", icon="mdi:map-legend"
    ),
    SensorEntityDescription(
        key=KEY_ALLOWLIST_COUNT,
        name="Allowlist Count",
        icon="mdi:format-list-checks",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)
MANAGER_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=KEY_GLOBAL_PLAYERS,
        name="Global Players",
        icon="mdi:account-group",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=KEY_AVAILABLE_WORLDS_COUNT,
        name="Available Worlds",
        icon="mdi:earth-box",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=KEY_AVAILABLE_ADDONS_COUNT,
        name="Available Addons",
        icon="mdi:puzzle-outline",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


# --- Setup Entry Function ---
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    try:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        servers_data: dict = entry_data.get("servers", {})
        manager_identifier: tuple = entry_data["manager_identifier"]
        manager_coordinator: ManagerDataCoordinator = entry_data["manager_coordinator"]
        api_client: BedrockServerManagerApi = entry_data["api"]
    except KeyError as e:
        _LOGGER.error(
            "Missing expected data for entry %s (%s). Cannot set up sensors.",
            entry.entry_id,
            e,
        )
        return

    entities_to_add = []

    _LOGGER.debug("Setting up manager sensors for entry %s", entry.entry_id)
    for description in MANAGER_SENSOR_DESCRIPTIONS:
        entities_to_add.append(
            ManagerInfoSensor(
                coordinator=manager_coordinator,
                description=description,
                manager_identifier=manager_identifier,
                entry_id=entry.entry_id,
            )
        )

    if servers_data:
        _LOGGER.debug(
            "Setting up server sensors for servers: %s", list(servers_data.keys())
        )
        for server_name, server_specific_data in servers_data.items():
            server_coordinator = server_specific_data.get("coordinator")
            if not server_coordinator:
                _LOGGER.warning(
                    "Coordinator missing for server '%s'. Skipping sensors.",
                    server_name,
                )
                continue

            world_name = server_specific_data.get("world_name")
            installed_version = server_specific_data.get("installed_version")

            if world_name is None or installed_version is None:
                _LOGGER.debug(
                    "Attempting initial fetch of static info for server '%s'.",
                    server_name,
                )
                try:
                    # --- UPDATED METHOD CALLS ---
                    results = await asyncio.gather(
                        api_client.async_get_server_world_name(server_name),  # Renamed
                        api_client.async_get_server_version(server_name),  # Renamed
                        return_exceptions=True,
                    )
                    # --- END UPDATED METHOD CALLS ---
                    world_name_res, version_res = results

                    if isinstance(world_name_res, Exception):
                        _LOGGER.warning(
                            "Failed to fetch initial world name for '%s': %s",
                            server_name,
                            world_name_res,
                        )
                        world_name = None
                    else:
                        world_name = world_name_res

                    if isinstance(version_res, Exception):
                        _LOGGER.warning(
                            "Failed to fetch initial version for '%s': %s",
                            server_name,
                            version_res,
                        )
                        installed_version = None
                    else:
                        installed_version = version_res

                    server_specific_data["world_name"] = world_name
                    server_specific_data["installed_version"] = installed_version
                except (
                    AuthError,
                    CannotConnectError,
                    APIError,
                    ServerNotFoundError,
                ) as e:
                    _LOGGER.warning(
                        "API error fetching static info for server %s: %s.",
                        server_name,
                        e,
                    )
                except Exception as e:
                    _LOGGER.exception(
                        "Unexpected error fetching static info for server %s: %s",
                        server_name,
                        e,
                    )

            for description in SERVER_SENSOR_DESCRIPTIONS:
                entities_to_add.append(
                    MinecraftServerSensor(
                        coordinator=server_coordinator,
                        description=description,
                        entry=entry,
                        server_name=server_name,
                        manager_identifier=manager_identifier,
                        installed_version=installed_version,
                        world_name=world_name,
                    )
                )

    if entities_to_add:
        _LOGGER.info(
            "Adding %d sensor entities for entry %s (%s)",
            len(entities_to_add),
            entry.title,
            entry.entry_id,
        )
        async_add_entities(entities_to_add)


# --- Server Sensor Class (Logic Unchanged from previous provided version) ---
class MinecraftServerSensor(
    CoordinatorEntity[MinecraftBedrockCoordinator], SensorEntity
):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MinecraftBedrockCoordinator,
        description: SensorEntityDescription,
        entry: ConfigEntry,
        server_name: str,
        manager_identifier: tuple,
        installed_version: Optional[str],
        world_name: Optional[str],
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._server_name = server_name
        self._world_name = world_name
        self._installed_version = installed_version
        self._attr_unique_id = f"{DOMAIN}_{self._server_name}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._server_name)},
            name=f"bsm-{self._server_name}",
            manufacturer="Bedrock Server Manager",
            model="Minecraft Bedrock Server",
            sw_version=self._installed_version or "Unknown",
            via_device=manager_identifier,
            configuration_url=f"http://{entry.data[CONF_HOST]}:{int(entry.data[CONF_PORT])}",
        )

    @property
    def native_value(self) -> Any:
        if not self.available:
            return None
        coordinator_data = self.coordinator.data
        if not isinstance(coordinator_data, dict):
            _LOGGER.warning("Coordinator data invalid for %s.", self.unique_id)
            return None
        sensor_key = self.entity_description.key
        process_info = coordinator_data.get("process_info")
        if sensor_key == "status":
            return "Running" if isinstance(process_info, dict) else "Stopped"
        if sensor_key == ATTR_CPU_PERCENT:
            return (
                process_info.get(ATTR_CPU_PERCENT)
                if isinstance(process_info, dict)
                else None
            )
        if sensor_key == ATTR_MEMORY_MB:
            return (
                process_info.get(ATTR_MEMORY_MB)
                if isinstance(process_info, dict)
                else None
            )
        count_map = {
            KEY_SERVER_PERMISSIONS_COUNT: "server_permissions",
            KEY_WORLD_BACKUPS_COUNT: "world_backups",
            KEY_CONFIG_BACKUPS_COUNT: "config_backups",
            KEY_ALLOWLIST_COUNT: "allowlist",
        }
        if sensor_key in count_map:
            data_list = coordinator_data.get(count_map[sensor_key], [])
            return len(data_list if isinstance(data_list, list) else [])
        if sensor_key == KEY_LEVEL_NAME:
            server_props = coordinator_data.get("properties", {})
            return (
                server_props.get("level-name", "Unknown")
                if isinstance(server_props, dict)
                else "Unknown"
            )
        _LOGGER.debug(
            "Sensor state not handled for key %s in %s", sensor_key, self.unique_id
        )
        return None

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        if not self.available or not isinstance(self.coordinator.data, dict):
            return None
        coordinator_data = self.coordinator.data
        attrs = {}
        sensor_key = self.entity_description.key
        if sensor_key == "status":
            if self._world_name:
                attrs[ATTR_WORLD_NAME] = self._world_name
            if self._installed_version:
                attrs[ATTR_INSTALLED_VERSION] = self._installed_version
        elif sensor_key == ATTR_CPU_PERCENT:
            process_info = coordinator_data.get("process_info")
            if isinstance(process_info, dict):
                attrs[ATTR_PID] = process_info.get("pid")
                attrs[ATTR_UPTIME] = process_info.get("uptime")
        elif sensor_key == KEY_SERVER_PERMISSIONS_COUNT:
            attrs[ATTR_SERVER_PERMISSIONS_LIST] = coordinator_data.get(
                "server_permissions", []
            )
        elif sensor_key == KEY_WORLD_BACKUPS_COUNT:
            attrs[ATTR_WORLD_BACKUPS_LIST] = coordinator_data.get("world_backups", [])
        elif sensor_key == KEY_CONFIG_BACKUPS_COUNT:
            attrs[ATTR_CONFIG_BACKUPS_LIST] = coordinator_data.get("config_backups", [])
        elif sensor_key == KEY_ALLOWLIST_COUNT:
            allowlist = coordinator_data.get("allowlist", [])
            attrs[ATTR_ALLOWLISTED_PLAYERS] = (
                [p.get("name") for p in allowlist if isinstance(p, dict)]
                if isinstance(allowlist, list)
                else []
            )
        elif sensor_key == KEY_LEVEL_NAME:
            attrs[ATTR_SERVER_PROPERTIES] = coordinator_data.get("properties", {})
        return attrs if attrs else None


# --- Manager Sensor Class (Logic Unchanged from previous provided version) ---
class ManagerInfoSensor(CoordinatorEntity[ManagerDataCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ManagerDataCoordinator,
        description: SensorEntityDescription,
        manager_identifier: tuple,
        entry_id: str,
    ):
        super().__init__(coordinator)
        self.entity_description = description
        self._manager_identifier = manager_identifier
        self._attr_unique_id = f"{DOMAIN}_{manager_identifier[1]}_{description.key}"
        self._attr_device_info = DeviceInfo(identifiers={self._manager_identifier})

    @property
    def native_value(self) -> Optional[int]:
        if not self.available or not isinstance(self.coordinator.data, dict):
            return None
        coordinator_data = self.coordinator.data
        sensor_key = self.entity_description.key
        data_list = []
        if sensor_key == KEY_GLOBAL_PLAYERS:
            data_list = coordinator_data.get("global_players", [])
        elif sensor_key == KEY_AVAILABLE_WORLDS_COUNT:
            data_list = coordinator_data.get("available_worlds", [])
        elif sensor_key == KEY_AVAILABLE_ADDONS_COUNT:
            data_list = coordinator_data.get("available_addons", [])
        else:
            _LOGGER.warning("Unhandled manager sensor key for value: %s", sensor_key)
            return None
        return len(data_list if isinstance(data_list, list) else [])

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        if not self.available or not isinstance(self.coordinator.data, dict):
            return None
        coordinator_data = self.coordinator.data
        sensor_key = self.entity_description.key
        attrs = {}
        if sensor_key == KEY_GLOBAL_PLAYERS:
            attrs[ATTR_GLOBAL_PLAYERS_LIST] = coordinator_data.get("global_players", [])
        elif sensor_key == KEY_AVAILABLE_WORLDS_COUNT:
            attrs[ATTR_AVAILABLE_WORLDS_LIST] = coordinator_data.get(
                "available_worlds", []
            )
        elif sensor_key == KEY_AVAILABLE_ADDONS_COUNT:
            attrs[ATTR_AVAILABLE_ADDONS_LIST] = coordinator_data.get(
                "available_addons", []
            )
        return attrs if attrs else None
