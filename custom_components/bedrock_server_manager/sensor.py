# custom_components/bedrock_server_manager/sensor.py
"""Sensor platform for Bedrock Server Manager."""

import asyncio
import logging
from typing import Optional, Dict, Any, List, Tuple

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers import device_registry as dr


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
    SensorEntityDescription(
        key="status",
        name="Status",  # From en.json
        icon="mdi:minecraft",
    ),
    SensorEntityDescription(
        key=ATTR_CPU_PERCENT,
        name="CPU Usage",  # From en.json
        icon="mdi:cpu-64-bit",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_MEMORY_MB,
        name="Memory Usage",  # From en.json
        icon="mdi:memory",
        native_unit_of_measurement="MiB",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATA_SIZE,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=KEY_SERVER_PERMISSIONS_COUNT,
        name="Permissioned Players",  # From en.json
        icon="mdi:account-key",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=KEY_WORLD_BACKUPS_COUNT,
        name="World Backups",  # From en.json
        icon="mdi:earth-box",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=KEY_CONFIG_BACKUPS_COUNT,
        name="Config Backups",  # From en.json
        icon="mdi:file-cog",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=KEY_LEVEL_NAME, name="Level Name", icon="mdi:map-legend"  # From en.json
    ),
    SensorEntityDescription(
        key=KEY_ALLOWLIST_COUNT,
        name="Allowlist Count",  # From en.json
        icon="mdi:format-list-checks",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)
MANAGER_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=KEY_GLOBAL_PLAYERS,  # This is a key for a count sensor
        name="Global Players",
        icon="mdi:account-group",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=KEY_AVAILABLE_WORLDS_COUNT,
        name="Available Worlds",  # From en.json
        icon="mdi:earth-box",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=KEY_AVAILABLE_ADDONS_COUNT,
        name="Available Addons",  # From en.json
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
        manager_identifier: Tuple[str, str] = entry_data["manager_identifier"]
        manager_coordinator: ManagerDataCoordinator = entry_data["manager_coordinator"]
        api_client: BedrockServerManagerApi = entry_data["api"]
    except KeyError as e:
        _LOGGER.error(
            "Missing expected data for entry %s (Key: %s). Cannot set up sensors.",
            entry.entry_id,
            e,
        )
        return

    entities_to_add = []

    _LOGGER.debug(
        "Setting up manager sensors for entry %s (Manager ID: %s)",
        entry.entry_id,
        manager_identifier[1],
    )
    if manager_coordinator.last_update_success and manager_coordinator.data:
        for description in MANAGER_SENSOR_DESCRIPTIONS:
            entities_to_add.append(
                ManagerInfoSensor(
                    coordinator=manager_coordinator,
                    description=description,
                    manager_identifier=manager_identifier,
                )
            )
    else:
        _LOGGER.warning(
            "Manager coordinator for %s (Manager ID: %s) has no data or last update failed; skipping manager sensors.",
            entry.title,
            manager_identifier[1],
        )

    if not servers_data:
        _LOGGER.info(
            "No server coordinators found for %s (Manager ID: %s), no server sensors will be created.",
            entry.title,
            manager_identifier[1],
        )

    for server_name, server_specific_data_dict in servers_data.items():
        server_coordinator = server_specific_data_dict.get("coordinator")
        if not server_coordinator:
            _LOGGER.warning(
                "Coordinator missing for server '%s' (Manager ID: %s). Skipping its sensors.",
                server_name,
                manager_identifier[1],
            )
            continue

        world_name = server_specific_data_dict.get(ATTR_WORLD_NAME)
        installed_version = server_specific_data_dict.get(ATTR_INSTALLED_VERSION)

        if world_name is None or installed_version is None:
            _LOGGER.debug(
                "Attempting initial fetch of static info for server '%s' (Manager ID: %s).",
                server_name,
                manager_identifier[1],
            )
            try:
                # This fetch is a fallback. Ideally, coordinator handles this.
                results = await asyncio.gather(
                    api_client.async_get_server_world_name(server_name),
                    api_client.async_get_server_version(server_name),
                    return_exceptions=True,
                )
                world_name_res, version_res = results

                world_name = (
                    world_name_res
                    if not isinstance(world_name_res, Exception)
                    else world_name
                )
                installed_version = (
                    version_res
                    if not isinstance(version_res, Exception)
                    else installed_version
                )

                if isinstance(world_name_res, Exception):
                    _LOGGER.warning(
                        "Failed to fetch world name for '%s': %s",
                        server_name,
                        world_name_res,
                    )
                if isinstance(version_res, Exception):
                    _LOGGER.warning(
                        "Failed to fetch version for '%s': %s", server_name, version_res
                    )

                server_specific_data_dict[ATTR_WORLD_NAME] = world_name
                server_specific_data_dict[ATTR_INSTALLED_VERSION] = installed_version
            except Exception as e:
                _LOGGER.exception(
                    "Unexpected error fetching static info for server %s: %s",
                    server_name,
                    e,
                )

        if server_coordinator.last_update_success and server_coordinator.data:
            for description in SERVER_SENSOR_DESCRIPTIONS:
                entities_to_add.append(
                    MinecraftServerSensor(
                        coordinator=server_coordinator,
                        description=description,
                        server_name=server_name,
                        manager_identifier=manager_identifier,
                        installed_version_static=installed_version,
                        world_name_static=world_name,
                    )
                )
        else:
            _LOGGER.warning(
                "Server coordinator for '%s' (Manager ID: %s) has no data or last update failed; skipping its sensors.",
                server_name,
                manager_identifier[1],
            )

    if entities_to_add:
        _LOGGER.info(
            "Adding %d sensor entities for entry %s (%s)",
            len(entities_to_add),
            entry.title,
            entry.entry_id,
        )
        async_add_entities(entities_to_add)
    else:
        _LOGGER.debug(
            "No sensor entities to add for BSM integration %s (%s)",
            entry.title,
            entry.entry_id,
        )


class MinecraftServerSensor(
    CoordinatorEntity[MinecraftBedrockCoordinator], SensorEntity
):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MinecraftBedrockCoordinator,
        description: SensorEntityDescription,
        server_name: str,
        manager_identifier: Tuple[str, str],
        installed_version_static: Optional[str],
        world_name_static: Optional[str],
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._server_name = server_name
        self._manager_host_port_id = manager_identifier[1]

        self._world_name_static = world_name_static
        self._installed_version_static = installed_version_static

        self._attr_unique_id = f"{DOMAIN}_{self._manager_host_port_id}_{self._server_name}_{description.key}"
        _LOGGER.debug(
            "ServerSensor Unique ID for %s (%s): %s for key %s",
            self._server_name,
            self._manager_host_port_id,
            self._attr_unique_id,
            description.key,
        )

        # --- DEVICE IDENTIFIER ---
        server_device_unique_part = f"{self._manager_host_port_id}_{self._server_name}"
        self._attr_device_info = dr.DeviceInfo(
            identifiers={
                (DOMAIN, server_device_unique_part)
            },  # Globally unique server device ID
            name=f"BSM {self._server_name} ({self._manager_host_port_id})",  # Descriptive device name
            manufacturer="Bedrock Server Manager",  # Your original manufacturer
            model="Minecraft Bedrock Server",  # Your original model
            sw_version=self._installed_version_static or "Unknown",
            via_device=manager_identifier,
            configuration_url=f"http://{coordinator.config_entry.data[CONF_HOST]}:{int(coordinator.config_entry.data[CONF_PORT])}",
        )

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and bool(self.coordinator.data)

    @property
    def native_value(self) -> Any:
        if not self.available:
            return None
        coordinator_data = self.coordinator.data
        if not isinstance(coordinator_data, dict):
            _LOGGER.warning("Coordinator data invalid type for %s.", self.unique_id)
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
            KEY_SERVER_PERMISSIONS_COUNT: "permissions",
            KEY_WORLD_BACKUPS_COUNT: "world_backups",
            KEY_CONFIG_BACKUPS_COUNT: "config_backups",
            KEY_ALLOWLIST_COUNT: "allowlist",
        }
        if sensor_key in count_map:
            data_source_key = count_map[sensor_key]
            data_list_or_dict = coordinator_data.get(data_source_key, [])
            return len(data_list_or_dict)

        if sensor_key == KEY_LEVEL_NAME:
            server_props = coordinator_data.get("properties", {})
            return server_props.get("level-name", self._world_name_static or "Unknown")

        _LOGGER.debug(
            "Sensor state not handled for key %s in %s", sensor_key, self.unique_id
        )
        return None

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        if not self.available or not isinstance(self.coordinator.data, dict):
            return None
        coordinator_data = self.coordinator.data
        attrs: Dict[str, Any] = {}
        sensor_key = self.entity_description.key

        # Add static info to relevant sensors or all sensors if desired
        if self._world_name_static:
            attrs[ATTR_WORLD_NAME] = self._world_name_static
        if self._installed_version_static:
            attrs[ATTR_INSTALLED_VERSION] = self._installed_version_static

        dynamic_version = coordinator_data.get("server_version")
        if dynamic_version:
            attrs["current_server_version"] = dynamic_version

        process_info = coordinator_data.get("process_info")
        if isinstance(
            process_info, dict
        ):  # Only add PID/Uptime if process_info is valid
            if sensor_key == ATTR_CPU_PERCENT or sensor_key == "status":
                if process_info.get(ATTR_PID) is not None:
                    attrs[ATTR_PID] = process_info.get(ATTR_PID)
                if process_info.get(ATTR_UPTIME) is not None:
                    attrs[ATTR_UPTIME] = process_info.get(ATTR_UPTIME)

        # Use the actual list keys from coordinator data for attributes
        if sensor_key == KEY_SERVER_PERMISSIONS_COUNT:
            attrs[ATTR_SERVER_PERMISSIONS_LIST] = coordinator_data.get(
                "permissions", []
            )
        elif sensor_key == KEY_WORLD_BACKUPS_COUNT:
            attrs[ATTR_WORLD_BACKUPS_LIST] = coordinator_data.get("world_backups", [])
        elif sensor_key == KEY_CONFIG_BACKUPS_COUNT:
            attrs[ATTR_CONFIG_BACKUPS_LIST] = coordinator_data.get("config_backups", [])
        elif sensor_key == KEY_ALLOWLIST_COUNT:
            allowlist_objects = coordinator_data.get("allowlist", [])
            attrs[ATTR_ALLOWLISTED_PLAYERS] = [
                p.get("name")
                for p in allowlist_objects
                if isinstance(p, dict) and "name" in p
            ]
        elif sensor_key == KEY_LEVEL_NAME:
            attrs[ATTR_SERVER_PROPERTIES] = coordinator_data.get("properties", {})

        return attrs if attrs else None

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data and self._attr_device_info:
            current_dynamic_version = self.coordinator.data.get("server_version")
            device_sw_version = self._attr_device_info.get("sw_version")
            if current_dynamic_version and current_dynamic_version != device_sw_version:
                device_registry = dr.async_get(self.hass)
                device_identifiers = self._attr_device_info.get("identifiers")
                if device_identifiers:
                    device = device_registry.async_get_device(
                        identifiers=device_identifiers
                    )
                    if device:
                        _LOGGER.debug(
                            "Updating SW version for device %s to %s",
                            device.id,
                            current_dynamic_version,
                        )
                        device_registry.async_update_device(
                            device.id, sw_version=current_dynamic_version
                        )
        super()._handle_coordinator_update()


class ManagerInfoSensor(CoordinatorEntity[ManagerDataCoordinator], SensorEntity):
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
            f"{DOMAIN}_{self._manager_host_port_id}_{description.key}"
        )
        self._attr_device_info = dr.DeviceInfo(identifiers={manager_identifier})

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and bool(self.coordinator.data)

    @property
    def native_value(self) -> Optional[Any]:
        if not self.available or not isinstance(self.coordinator.data, dict):
            return None
        coordinator_data = self.coordinator.data
        sensor_key = self.entity_description.key

        if sensor_key == KEY_GLOBAL_PLAYERS:
            return len(
                coordinator_data.get(ATTR_GLOBAL_PLAYERS_LIST, [])
            )  # Use ATTR_ for list key
        elif sensor_key == KEY_AVAILABLE_WORLDS_COUNT:
            return len(
                coordinator_data.get(ATTR_AVAILABLE_WORLDS_LIST, [])
            )  # Use ATTR_ for list key
        elif sensor_key == KEY_AVAILABLE_ADDONS_COUNT:
            return len(
                coordinator_data.get(ATTR_AVAILABLE_ADDONS_LIST, [])
            )  # Use ATTR_ for list key
        elif sensor_key == "total_servers_managed":
            return len(coordinator_data.get("servers_summary", []))
        elif sensor_key == "bsm_app_version":
            return coordinator_data.get("info", {}).get("app_version", "Unknown")

        _LOGGER.warning("Unhandled manager sensor key for value: %s", sensor_key)
        return None

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        if not self.available or not isinstance(self.coordinator.data, dict):
            return None
        coordinator_data = self.coordinator.data
        sensor_key = self.entity_description.key
        attrs: Dict[str, Any] = {}

        if sensor_key == KEY_GLOBAL_PLAYERS:
            attrs[ATTR_GLOBAL_PLAYERS_LIST] = coordinator_data.get(
                ATTR_GLOBAL_PLAYERS_LIST, []
            )
        elif sensor_key == KEY_AVAILABLE_WORLDS_COUNT:
            attrs[ATTR_AVAILABLE_WORLDS_LIST] = coordinator_data.get(
                ATTR_AVAILABLE_WORLDS_LIST, []
            )
        elif sensor_key == KEY_AVAILABLE_ADDONS_COUNT:
            attrs[ATTR_AVAILABLE_ADDONS_LIST] = coordinator_data.get(
                ATTR_AVAILABLE_ADDONS_LIST, []
            )

        return attrs if attrs else None
