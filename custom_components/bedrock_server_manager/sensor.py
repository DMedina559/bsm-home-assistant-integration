# custom_components/bedrock_server_manager/sensor.py
"""Sensor platform for Bedrock Server Manager."""

import asyncio
import logging
from typing import Optional, Dict, Any, List, Tuple, cast

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT  # Used for configuration_url
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers import device_registry as dr


# --- IMPORT FROM LOCAL MODULES ---
from .coordinator import MinecraftBedrockCoordinator, ManagerDataCoordinator
from .const import (
    DOMAIN,
    CONF_USE_SSL,
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
    KEY_GLOBAL_PLAYERS_COUNT,
    KEY_LEVEL_NAME,
    KEY_ALLOWLIST_COUNT,
    KEY_SERVER_PERMISSIONS_COUNT,
    KEY_CONFIG_BACKUPS_COUNT,
    KEY_WORLD_BACKUPS_COUNT,
    KEY_AVAILABLE_ADDONS_COUNT,
    KEY_AVAILABLE_WORLDS_COUNT,
    ATTR_GLOBAL_PLAYERS_LIST,
    ATTR_SERVER_PERMISSIONS_LIST,
    KEY_MANAGER_APP_VERSION,
    ATTR_MANAGER_OS_TYPE,
)

from pybedrock_server_manager import BedrockServerManagerApi


_LOGGER = logging.getLogger(__name__)

# --- Sensor Descriptions ---
SERVER_SENSOR_DESCRIPTIONS: Tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="status", name="Status", icon="mdi:minecraft"
    ),  # Main status: Running/Stopped
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
        native_unit_of_measurement="MB",
        device_class=SensorDeviceClass.DATA_SIZE,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
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
        key=KEY_CONFIG_BACKUPS_COUNT,
        name="Config Backups",
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
    SensorEntityDescription(  # New sensor for Manager App Version
        key=KEY_MANAGER_APP_VERSION,
        name="Manager App Version",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
)


# --- Setup Entry Function ---
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities based on a config entry."""
    _LOGGER.debug("Setting up sensor platform for BSM entry: %s", entry.entry_id)
    try:
        # Retrieve data stored by __init__.py
        entry_data = hass.data[DOMAIN][entry.entry_id]
        api_client = cast(
            BedrockServerManagerApi, entry_data["api"]
        )  # Cast for type checker
        manager_identifier = cast(Tuple[str, str], entry_data["manager_identifier"])
        manager_coordinator = cast(
            ManagerDataCoordinator, entry_data["manager_coordinator"]
        )
        servers_config_data: Dict[str, Dict[str, Any]] = entry_data.get(
            "servers", {}
        )  # Server specific static data and coordinator
    except KeyError as e:
        _LOGGER.error(
            "Sensor setup failed for entry %s: Missing expected data (Key: %s). "
            "This might happen if __init__.py did not complete successfully.",
            entry.entry_id,
            e,
        )
        return

    entities_to_add: List[SensorEntity] = []

    # --- Setup Manager Sensors ---
    _LOGGER.debug("Setting up manager-level sensors for BSM: %s", manager_identifier[1])
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
            "ManagerDataCoordinator for BSM '%s' has no data or last update failed; "
            "skipping manager-level sensors.",
            entry.title,
        )

    # --- Setup Server-Specific Sensors ---
    if not servers_config_data:
        _LOGGER.info(
            "No servers configured or found for BSM '%s'; no server-specific sensors will be created.",
            entry.title,
        )

    for server_name, server_entry_data in servers_config_data.items():
        server_coordinator = cast(
            Optional[MinecraftBedrockCoordinator], server_entry_data.get("coordinator")
        )
        if not server_coordinator:
            _LOGGER.warning(
                "Coordinator missing for server '%s' under BSM '%s'. Skipping its sensors.",
                server_name,
                entry.title,
            )
            continue

        world_name_static = server_entry_data.get(ATTR_WORLD_NAME)
        version_static = server_entry_data.get(ATTR_INSTALLED_VERSION)

        if world_name_static is None or version_static is None:
            _LOGGER.debug(
                "Attempting to fetch initial static info (world/version) for server '%s' during sensor setup.",
                server_name,
            )
            try:
                async with asyncio.timeout(10):
                    results = await asyncio.gather(
                        api_client.async_get_server_world_name(server_name),
                        api_client.async_get_server_version(server_name),
                        return_exceptions=True,
                    )
                world_name_res, version_res = results

                if isinstance(world_name_res, Exception):
                    _LOGGER.warning(
                        "Failed to fetch initial world name for '%s': %s",
                        server_name,
                        world_name_res,
                    )
                elif isinstance(world_name_res, str):
                    world_name_static = world_name_res

                if isinstance(version_res, Exception):
                    _LOGGER.warning(
                        "Failed to fetch initial version for '%s': %s",
                        server_name,
                        version_res,
                    )
                elif isinstance(version_res, str):
                    version_static = version_res

                server_entry_data[ATTR_WORLD_NAME] = world_name_static
                server_entry_data[ATTR_INSTALLED_VERSION] = version_static

            except TimeoutError:
                _LOGGER.warning(
                    "Timeout fetching initial static info for server '%s'.", server_name
                )
            except Exception as e:
                _LOGGER.error(
                    "Unexpected error fetching initial static info for server '%s': %s",
                    server_name,
                    e,
                    exc_info=True,
                )

        if server_coordinator.last_update_success and server_coordinator.data:
            for description in SERVER_SENSOR_DESCRIPTIONS:
                entities_to_add.append(
                    MinecraftServerSensor(
                        coordinator=server_coordinator,
                        description=description,
                        server_name=server_name,
                        manager_identifier=manager_identifier,
                        installed_version_static=version_static,
                        world_name_static=world_name_static,  # Still pass for DeviceInfo name consistency
                    )
                )
        else:
            _LOGGER.warning(
                "MinecraftBedrockCoordinator for server '%s' (BSM '%s') has no data or "
                "last update failed; skipping its sensors.",
                server_name,
                entry.title,
            )

    if entities_to_add:
        _LOGGER.info(
            "Adding %d BSM sensor entities for BSM '%s'.",
            len(entities_to_add),
            entry.title,
        )
        async_add_entities(entities_to_add)
    else:
        _LOGGER.info("No sensor entities were added for BSM '%s'.", entry.title)


class MinecraftServerSensor(
    CoordinatorEntity[MinecraftBedrockCoordinator], SensorEntity
):
    """Representation of a Minecraft Bedrock Server sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MinecraftBedrockCoordinator,
        description: SensorEntityDescription,
        server_name: str,
        manager_identifier: Tuple[str, str],
        installed_version_static: Optional[str],
        world_name_static: Optional[str],  # Used for device name
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._server_name = server_name
        self._manager_host_port_id = manager_identifier[1]

        # _world_name_static is primarily used for the DeviceInfo name now,
        # and as a fallback for Level Name sensor if properties aren't available.
        self._world_name_static = world_name_static
        self._installed_version_static = installed_version_static  # Used for sw_version

        self._attr_unique_id = f"{DOMAIN}_{self._manager_host_port_id}_{self._server_name}_{description.key}".lower().replace(
            ":", "_"
        )

        server_device_id_value = f"{self._manager_host_port_id}_{self._server_name}"

        config_data = coordinator.config_entry.data
        host_val = config_data[CONF_HOST]
        try:
            port_val = int(float(config_data[CONF_PORT]))
        except (ValueError, TypeError) as e:
            _LOGGER.error(
                "Invalid port value '%s' for sensor on server '%s', device configuration_url. Defaulting to 0. Error: %s",
                config_data.get(CONF_PORT),
                self._server_name,
                e,
            )
            port_val = 0

        protocol = "https" if config_data.get(CONF_USE_SSL, False) else "http"
        safe_config_url = f"{protocol}://{host_val}:{port_val}"

        # Device name uses server_name and host_val for clarity.
        # World name is not part of the device name anymore, as a server can change worlds.
        device_name = f"{self._server_name} ({host_val})"

        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, server_device_id_value)},
            name=device_name,
            manufacturer="Bedrock Server Manager",
            model="Minecraft Bedrock Server",
            sw_version=self._installed_version_static or "Unknown",
            via_device=manager_identifier,
            configuration_url=safe_config_url,
        )

    @property
    def available(self) -> bool:
        """Return True if coordinator has data and entity is enabled."""
        return (
            super().available
            and self.coordinator.last_update_success
            and bool(self.coordinator.data)
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if not self.available or not isinstance(self.coordinator.data, dict):
            return None

        data = self.coordinator.data
        key = self.entity_description.key
        process_info = data.get("process_info")

        if key == "status":
            return "Running" if isinstance(process_info, dict) else "Stopped"

        if isinstance(process_info, dict):
            if key == ATTR_CPU_PERCENT:
                return process_info.get(ATTR_CPU_PERCENT)
            if key == ATTR_MEMORY_MB:
                return process_info.get(ATTR_MEMORY_MB)

        if key == KEY_SERVER_PERMISSIONS_COUNT:
            return len(data.get("server_permissions", []))
        if key == KEY_WORLD_BACKUPS_COUNT:
            return len(data.get("world_backups", []))
        if key == KEY_CONFIG_BACKUPS_COUNT:
            return len(data.get("config_backups", []))
        if key == KEY_ALLOWLIST_COUNT:
            return len(data.get("allowlist", []))

        if key == KEY_LEVEL_NAME:
            server_properties = data.get("properties", {})
            dynamic_level_name = server_properties.get("level-name")
            # Fallback to static world name if dynamic one is not available or server is stopped
            return (
                dynamic_level_name
                if dynamic_level_name is not None
                else (self._world_name_static or "Unknown")
            )

        _LOGGER.warning(
            "Unhandled sensor key '%s' for native_value in %s", key, self.unique_id
        )
        return None

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return additional state attributes."""
        if not self.available or not isinstance(self.coordinator.data, dict):
            return None

        data = self.coordinator.data
        attrs: Dict[str, Any] = {}
        key = self.entity_description.key
        process_info = data.get("process_info")  # Dict if running, else None

        if key == "status":
            # Only general info that doesn't fit better elsewhere
            if self._installed_version_static:  # The current installed version
                attrs[ATTR_INSTALLED_VERSION] = self._installed_version_static
            # PID and Uptime moved to CPU/Memory sensors
            # World name is handled by the Level Name sensor

        elif key in [ATTR_CPU_PERCENT, ATTR_MEMORY_MB]:
            # Process-specific info for CPU and Memory sensors
            if isinstance(process_info, dict):
                if process_info.get(ATTR_PID) is not None:
                    attrs[ATTR_PID] = process_info[ATTR_PID]
                if process_info.get(ATTR_UPTIME) is not None:
                    attrs[ATTR_UPTIME] = process_info[ATTR_UPTIME]

        elif key == KEY_SERVER_PERMISSIONS_COUNT:
            attrs[ATTR_SERVER_PERMISSIONS_LIST] = data.get("server_permissions", [])
        elif key == KEY_WORLD_BACKUPS_COUNT:
            attrs[ATTR_WORLD_BACKUPS_LIST] = data.get("world_backups", [])
        elif key == KEY_CONFIG_BACKUPS_COUNT:
            attrs[ATTR_CONFIG_BACKUPS_LIST] = data.get("config_backups", [])
        elif key == KEY_ALLOWLIST_COUNT:
            allowlist_data = data.get("allowlist", [])
            attrs[ATTR_ALLOWLISTED_PLAYERS] = [
                p.get("name") for p in allowlist_data if isinstance(p, dict)
            ]
        elif key == KEY_LEVEL_NAME:
            # The Level Name sensor's state is the current level name.
            # Attributes include the full server properties dictionary.
            attrs[ATTR_SERVER_PROPERTIES] = data.get("properties", {})
            # ATTR_INSTALLED_VERSION is on the 'status' sensor.
            # Static world name is not needed here as an attribute.

        return attrs if attrs else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (
            self.coordinator.last_update_success
            and isinstance(self.coordinator.data, dict)
            and self._attr_device_info
        ):
            dynamic_version_from_coord = self.coordinator.data.get(
                "current_installed_version"
            )
            current_device_sw_version = self._attr_device_info.get("sw_version")

            if (
                dynamic_version_from_coord
                and dynamic_version_from_coord != "Unknown"
                and dynamic_version_from_coord != current_device_sw_version
            ):
                _LOGGER.debug(
                    "Server '%s' version '%s' from coordinator differs from device SW version '%s'. Updating device.",
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
                    self._attr_device_info["sw_version"] = dynamic_version_from_coord
                    self._installed_version_static = dynamic_version_from_coord
        super()._handle_coordinator_update()


class ManagerInfoSensor(CoordinatorEntity[ManagerDataCoordinator], SensorEntity):
    """Representation of a BSM Manager sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ManagerDataCoordinator,
        description: SensorEntityDescription,
        manager_identifier: Tuple[str, str],
    ):
        """Initialize the manager sensor."""
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
        """Return True if coordinator has data."""
        return (
            super().available
            and self.coordinator.last_update_success
            and bool(self.coordinator.data)
        )

    @property
    def native_value(self) -> Optional[Any]:  # Can be int or str now
        """Return the state of the sensor."""
        if not self.available or not isinstance(self.coordinator.data, dict):
            return None

        data = self.coordinator.data
        key = self.entity_description.key

        if key == KEY_GLOBAL_PLAYERS_COUNT:
            return len(data.get("global_players", []))
        elif key == KEY_AVAILABLE_WORLDS_COUNT:
            return len(data.get("available_worlds", []))
        elif key == KEY_AVAILABLE_ADDONS_COUNT:
            return len(data.get("available_addons", []))
        elif key == KEY_MANAGER_APP_VERSION:  # New sensor's state
            manager_info_payload = data.get("info", {})
            if isinstance(manager_info_payload, dict):
                return manager_info_payload.get("app_version", "Unknown")
            return "Unknown"  # Fallback if 'info' is not a dict

        _LOGGER.warning(
            "Unhandled manager sensor key '%s' for native_value in %s",
            key,
            self.unique_id,
        )
        return None

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return additional state attributes."""
        if not self.available or not isinstance(self.coordinator.data, dict):
            return None

        data = self.coordinator.data
        key = self.entity_description.key
        attrs: Dict[str, Any] = {}

        if key == KEY_GLOBAL_PLAYERS_COUNT:
            attrs[ATTR_GLOBAL_PLAYERS_LIST] = data.get("global_players", [])
        elif key == KEY_AVAILABLE_WORLDS_COUNT:
            attrs[ATTR_AVAILABLE_WORLDS_LIST] = data.get("available_worlds", [])
        elif key == KEY_AVAILABLE_ADDONS_COUNT:
            attrs[ATTR_AVAILABLE_ADDONS_LIST] = data.get("available_addons", [])
        elif key == KEY_MANAGER_APP_VERSION:
            manager_info_payload = data.get("info", {})
            if isinstance(manager_info_payload, dict):
                attrs[ATTR_MANAGER_OS_TYPE] = manager_info_payload.get(
                    "os_type", "Unknown"
                )
            else:
                attrs[ATTR_MANAGER_OS_TYPE] = "Unknown"

        return attrs if attrs else None
