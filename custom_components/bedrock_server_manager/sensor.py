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
    CONF_USE_SSL,  # For configuration_url
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
    ATTR_GLOBAL_PLAYERS_LIST,  # Full list for attributes
    ATTR_SERVER_PERMISSIONS_LIST,  # Full list for attributes
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

        # Fetch static info if not already populated by __init__.py (e.g., if init failed partially)
        # These are just for initial DeviceInfo, coordinator will provide dynamic updates.
        world_name_static = server_entry_data.get(ATTR_WORLD_NAME)
        version_static = server_entry_data.get(ATTR_INSTALLED_VERSION)

        # This block attempts to fetch static info if it wasn't pre-populated.
        # Useful if __init__.py stored coordinator but failed to get these static details.
        if world_name_static is None or version_static is None:
            _LOGGER.debug(
                "Attempting to fetch initial static info (world/version) for server '%s' during sensor setup.",
                server_name,
            )
            try:
                # Use a timeout for these one-off calls during setup
                async with asyncio.timeout(
                    10
                ):  # 10-second timeout for this setup fetch
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
                elif isinstance(world_name_res, str):  # Client returns Optional[str]
                    world_name_static = world_name_res

                if isinstance(version_res, Exception):
                    _LOGGER.warning(
                        "Failed to fetch initial version for '%s': %s",
                        server_name,
                        version_res,
                    )
                elif isinstance(version_res, str):  # Client returns Optional[str]
                    version_static = version_res

                # Update the stored static info in hass.data if fetched
                server_entry_data[ATTR_WORLD_NAME] = world_name_static
                server_entry_data[ATTR_INSTALLED_VERSION] = version_static

            except TimeoutError:
                _LOGGER.warning(
                    "Timeout fetching initial static info for server '%s'.", server_name
                )
            except Exception as e:  # Catch other unexpected errors
                _LOGGER.error(
                    "Unexpected error fetching initial static info for server '%s': %s",
                    server_name,
                    e,
                    exc_info=True,
                )

        # Add server sensors if coordinator has data
        if server_coordinator.last_update_success and server_coordinator.data:
            for description in SERVER_SENSOR_DESCRIPTIONS:
                entities_to_add.append(
                    MinecraftServerSensor(
                        coordinator=server_coordinator,
                        description=description,
                        server_name=server_name,
                        manager_identifier=manager_identifier,  # For via_device
                        # Pass the potentially updated static info for DeviceInfo
                        installed_version_static=version_static,
                        world_name_static=world_name_static,
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

    _attr_has_entity_name = (
        True  # Sensor name will be "Device Name Sensor Description Name"
    )

    def __init__(
        self,
        coordinator: MinecraftBedrockCoordinator,
        description: SensorEntityDescription,
        server_name: str,
        manager_identifier: Tuple[str, str],  # (DOMAIN, manager_host_port_id)
        installed_version_static: Optional[str],
        world_name_static: Optional[str],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._server_name = server_name
        self._manager_host_port_id = manager_identifier[1]  # e.g., "host:port"

        self._world_name_static = world_name_static
        self._installed_version_static = installed_version_static  # Used for sw_version

        self._attr_unique_id = f"{DOMAIN}_{self._manager_host_port_id}_{self._server_name}_{description.key}".lower().replace(
            ":", "_"
        )

        server_device_id_value = f"{self._manager_host_port_id}_{self._server_name}"

        config_data = coordinator.config_entry.data
        host_val = config_data[CONF_HOST]
        try:
            # Ensure port is a clean integer for the URL
            port_val = int(float(config_data[CONF_PORT]))
        except (ValueError, TypeError) as e:
            _LOGGER.error(
                "Invalid port value '%s' for sensor on server '%s', device configuration_url. Defaulting to 0. Error: %s",
                config_data.get(CONF_PORT),
                self._server_name,
                e,
            )
            port_val = (
                0  # Fallback, though URL might still be invalid if host is also bad
            )

        protocol = "https" if config_data.get(CONF_USE_SSL, False) else "http"
        safe_config_url = f"{protocol}://{host_val}:{port_val}"

        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, server_device_id_value)},
            name=f"{self._server_name} ({host_val})",  # Updated name for clarity
            manufacturer="Bedrock Server Manager",  # Consistent manufacturer
            model="Minecraft Bedrock Server",  # Consistent model
            sw_version=self._installed_version_static or "Unknown",
            via_device=manager_identifier,
            configuration_url=safe_config_url,  # Use the safely constructed URL
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
        if not self.available or not isinstance(
            self.coordinator.data, dict
        ):  # Should be caught by super().available check too
            return None

        data = self.coordinator.data  # Data from MinecraftBedrockCoordinator
        key = self.entity_description.key
        process_info = data.get(
            "process_info"
        )  # This is a dict if server is running, else None

        if key == "status":
            return "Running" if isinstance(process_info, dict) else "Stopped"

        if isinstance(process_info, dict):  # These sensors depend on process_info
            if key == ATTR_CPU_PERCENT:
                return process_info.get(ATTR_CPU_PERCENT)
            if key == ATTR_MEMORY_MB:
                return process_info.get(ATTR_MEMORY_MB)
            # Other process_info related sensors can be added here

        if key == KEY_SERVER_PERMISSIONS_COUNT:
            return len(data.get("server_permissions", []))
        if key == KEY_WORLD_BACKUPS_COUNT:
            return len(data.get("world_backups", []))
        if key == KEY_CONFIG_BACKUPS_COUNT:
            return len(data.get("config_backups", []))
        if key == KEY_ALLOWLIST_COUNT:
            return len(data.get("allowlist", []))

        if key == KEY_LEVEL_NAME:
            # Prioritize dynamic level-name from properties, fallback to static
            server_properties = data.get("properties", {})
            dynamic_level_name = server_properties.get("level-name")
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

        if key == "status":  # Attributes for the main 'Status' sensor
            if self._world_name_static:
                attrs[ATTR_WORLD_NAME] = self._world_name_static  # Static name
            if self._installed_version_static:
                attrs[ATTR_INSTALLED_VERSION] = (
                    self._installed_version_static
                )  # Static version

            # Dynamic properties if available from coordinator
            server_properties_dyn = data.get("properties", {})
            if server_properties_dyn.get("level-name"):
                attrs[f"current_{KEY_LEVEL_NAME}"] = server_properties_dyn["level-name"]

            if isinstance(process_info, dict):
                if process_info.get(ATTR_PID) is not None:
                    attrs[ATTR_PID] = process_info[ATTR_PID]
                if process_info.get(ATTR_UPTIME) is not None:
                    attrs[ATTR_UPTIME] = process_info[ATTR_UPTIME]

        elif key in [
            ATTR_CPU_PERCENT,
            ATTR_MEMORY_MB,
        ]:  # Attributes for CPU/Memory sensors
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
            attrs[ATTR_SERVER_PROPERTIES] = data.get("properties", {})
            if self._installed_version_static:
                attrs[ATTR_INSTALLED_VERSION] = self._installed_version_static

        return attrs if attrs else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Dynamically update device SW version if coordinator provides it and it changed
        if (
            self.coordinator.last_update_success
            and isinstance(self.coordinator.data, dict)
            and self._attr_device_info
        ):

            dynamic_version_from_coord = self.coordinator.data.get(
                "current_installed_version"
            )  # Example key

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
                # Ensure self._attr_device_info['identifiers'] is correctly formatted for async_get_device
                device_entry = device_registry.async_get_device(
                    identifiers=self._attr_device_info["identifiers"]
                )

                if device_entry:
                    device_registry.async_update_device(
                        device_entry.id, sw_version=dynamic_version_from_coord
                    )
                    # Update local cache to prevent repeated updates if HA takes time to reflect
                    self._attr_device_info["sw_version"] = dynamic_version_from_coord
                    self._installed_version_static = (
                        dynamic_version_from_coord  # Keep this in sync
                    )

        super()._handle_coordinator_update()


class ManagerInfoSensor(CoordinatorEntity[ManagerDataCoordinator], SensorEntity):
    """Representation of a BSM Manager sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ManagerDataCoordinator,
        description: SensorEntityDescription,
        manager_identifier: Tuple[str, str],  # (DOMAIN, manager_host_port_id)
    ):
        """Initialize the manager sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._manager_host_port_id = manager_identifier[1]  # e.g., "host:port"

        self._attr_unique_id = (
            f"{DOMAIN}_{self._manager_host_port_id}_{description.key}".lower().replace(
                ":", "_"
            )
        )
        # All manager sensors are attached to the main manager device
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
    def native_value(self) -> Optional[int]:  # Most manager sensors here are counts
        """Return the state of the sensor."""
        if not self.available or not isinstance(self.coordinator.data, dict):
            return None

        data = self.coordinator.data  # Data from ManagerDataCoordinator
        key = self.entity_description.key

        if key == KEY_GLOBAL_PLAYERS_COUNT:
            return len(data.get("global_players", []))
        elif key == KEY_AVAILABLE_WORLDS_COUNT:
            return len(data.get("available_worlds", []))
        elif key == KEY_AVAILABLE_ADDONS_COUNT:
            return len(data.get("available_addons", []))

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

        # Add manager OS and App Version to all manager sensors for convenience
        manager_info_payload = data.get(
            "info", {}
        )  # 'info' contains {'os_type': ..., 'app_version': ...}
        if isinstance(manager_info_payload, dict):
            attrs["manager_os_type"] = manager_info_payload.get("os_type", "Unknown")
            attrs["manager_app_version"] = manager_info_payload.get(
                "app_version", "Unknown"
            )

        return attrs if attrs else None
