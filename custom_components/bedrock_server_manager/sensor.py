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

# --- IMPORT FROM THE NEW LIBRARY ---
from pybedrock_server_manager import (
    BedrockServerManagerApi,
    APIError,
    AuthError,
    CannotConnectError,
    ServerNotFoundError,
)

# --- END IMPORT FROM NEW LIBRARY ---

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
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_MEMORY_MB,
        name="Memory Usage",
        icon="mdi:memory",
        native_unit_of_measurement="MiB",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATA_SIZE,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
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
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=KEY_CONFIG_BACKUPS_COUNT,
        name="Config Backups",
        icon="mdi:file-cog",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
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
                "Attempting initial fetch of static info for server '%s' during sensor setup.",
                server_name,
            )
            try:
                results = await asyncio.gather(
                    api_client.async_get_server_world_name(server_name),
                    api_client.async_get_server_version(server_name),
                    return_exceptions=True,
                )
                world_name_res, version_res = results

                if isinstance(world_name_res, Exception):
                    _LOGGER.warning(
                        "Failed to fetch world name for '%s': %s",
                        server_name,
                        world_name_res,
                    )
                    # Keep existing world_name if any, otherwise it remains None
                else:
                    world_name = world_name_res

                if isinstance(version_res, Exception):
                    _LOGGER.warning(
                        "Failed to fetch version for '%s': %s", server_name, version_res
                    )
                    # Keep existing installed_version if any
                else:
                    installed_version = version_res

                server_specific_data_dict[ATTR_WORLD_NAME] = world_name
                server_specific_data_dict[ATTR_INSTALLED_VERSION] = installed_version
            except (
                Exception
            ) as e:  # Catch any other unexpected error during gather or processing
                _LOGGER.exception(
                    "Unexpected error fetching static info for server %s during sensor setup: %s",
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
        self._manager_host_port_id = manager_identifier[
            1
        ]  # Used for unique ID prefixing
        self._world_name_static = world_name_static
        self._installed_version_static = installed_version_static
        # Ensure unique ID is distinct across different managers if server names could collide
        self._attr_unique_id = f"{DOMAIN}_{self._manager_host_port_id}_{self._server_name}_{description.key}"

        # Define a unique identifier part for this server's device, including the manager context
        server_device_identifier_value = (
            f"{self._manager_host_port_id}_{self._server_name}"
        )
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, server_device_identifier_value)},
            name=f"BSM Server: {self._server_name} ({self._manager_host_port_id.split(':')[0]})",  # Add manager host for clarity
            manufacturer="Bedrock Server Manager",
            model="Minecraft Bedrock Server",
            sw_version=self._installed_version_static or "Unknown",
            via_device=manager_identifier,
            configuration_url=f"http://{coordinator.config_entry.data[CONF_HOST]}:{int(coordinator.config_entry.data[CONF_PORT])}",
        )

    @property
    def available(self) -> bool:
        # Entity is available if the coordinator successfully updated and has data.
        return self.coordinator.last_update_success and bool(self.coordinator.data)

    @property
    def native_value(self) -> Any:
        if not self.available:
            return None  # Rely on self.available

        coordinator_data = self.coordinator.data
        # Ensure coordinator_data is a dict, which it should be if available is True and update was successful
        if not isinstance(coordinator_data, dict):
            _LOGGER.warning(
                "Coordinator data is not a dictionary for %s, though sensor is available. Data: %s",
                self.unique_id,
                coordinator_data,
            )
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

        # Using direct keys from MinecraftBedrockCoordinator's data structure
        if sensor_key == KEY_SERVER_PERMISSIONS_COUNT:
            return len(coordinator_data.get("server_permissions", []))
        if sensor_key == KEY_WORLD_BACKUPS_COUNT:
            return len(coordinator_data.get("world_backups", []))
        if sensor_key == KEY_CONFIG_BACKUPS_COUNT:
            return len(coordinator_data.get("config_backups", []))
        if sensor_key == KEY_ALLOWLIST_COUNT:
            return len(coordinator_data.get("allowlist", []))

        if sensor_key == KEY_LEVEL_NAME:
            server_props = coordinator_data.get("properties", {})
            return server_props.get("level-name", self._world_name_static or "Unknown")

        _LOGGER.debug(
            "Sensor value not handled for key %s in %s", sensor_key, self.unique_id
        )
        return None

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        if not self.available or not isinstance(self.coordinator.data, dict):
            return None

        coordinator_data = self.coordinator.data
        attrs: Dict[str, Any] = {}
        sensor_key = self.entity_description.key

        if sensor_key == "status":
            if self._world_name_static:
                attrs[ATTR_WORLD_NAME] = self._world_name_static
            if self._installed_version_static:
                attrs[ATTR_INSTALLED_VERSION] = self._installed_version_static
            # Dynamic version from coordinator if available and different from static
            dynamic_version = coordinator_data.get(
                "server_version"
            )  # Assuming coordinator might provide this
            if dynamic_version and dynamic_version != self._installed_version_static:
                attrs["current_server_version"] = dynamic_version
            # Add PID and Uptime to status sensor's attributes if server is running
            process_info_for_status = coordinator_data.get("process_info")
            if isinstance(process_info_for_status, dict):
                if process_info_for_status.get(ATTR_PID) is not None:
                    attrs[ATTR_PID] = process_info_for_status.get(ATTR_PID)
                if process_info_for_status.get(ATTR_UPTIME) is not None:
                    attrs[ATTR_UPTIME] = process_info_for_status.get(ATTR_UPTIME)

        elif sensor_key == ATTR_CPU_PERCENT:  # Attributes specific to CPU sensor
            process_info_for_cpu = coordinator_data.get("process_info")
            if isinstance(process_info_for_cpu, dict):
                if process_info_for_cpu.get(ATTR_PID) is not None:
                    attrs[ATTR_PID] = process_info_for_cpu.get(ATTR_PID)
                if process_info_for_cpu.get(ATTR_UPTIME) is not None:
                    attrs[ATTR_UPTIME] = process_info_for_cpu.get(ATTR_UPTIME)

        # Use direct keys from MinecraftBedrockCoordinator for lists
        elif sensor_key == KEY_SERVER_PERMISSIONS_COUNT:
            attrs[ATTR_SERVER_PERMISSIONS_LIST] = coordinator_data.get(
                "server_permissions", []
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
        """Handle updated data from the coordinator and update sw_version if changed."""
        if (
            self.coordinator.data
            and isinstance(self.coordinator.data, dict)
            and self._attr_device_info
        ):
            # Assuming your MinecraftBedrockCoordinator might fetch dynamic version info
            # and store it under a key like "server_version" in its data.
            # This is an example; adapt the key if your coordinator uses a different one.
            current_dynamic_version = self.coordinator.data.get(
                "server_version"
            )  # Or whatever key holds dynamic version

            # Get current sw_version from DeviceInfo (it's mutable if gotten from registry)
            # For simplicity, we compare against the last known static/updated version.
            # A more robust way might involve fetching device from registry if needed.
            # For now, let's assume self._installed_version_static is updated if a static change happens
            # or we update the DeviceInfo directly.

            if (
                current_dynamic_version
                and current_dynamic_version != self._attr_device_info.get("sw_version")
            ):
                _LOGGER.debug(
                    "Server '%s' dynamic version '%s' differs from device SW version '%s'. Updating device info.",
                    self._server_name,
                    current_dynamic_version,
                    self._attr_device_info.get("sw_version"),
                )
                # Update the device in the registry
                device_registry = dr.async_get(self.hass)
                device_identifiers = self._attr_device_info[
                    "identifiers"
                ]  # Get identifiers

                device_entry = device_registry.async_get_device(
                    identifiers=device_identifiers
                )
                if device_entry:
                    device_registry.async_update_device(
                        device_entry.id, sw_version=current_dynamic_version
                    )
                    # Also update our local cache of the static version if this dynamic one is more current
                    self._installed_version_static = current_dynamic_version
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
    def native_value(self) -> Optional[int]:
        if not self.available or not isinstance(self.coordinator.data, dict):
            return None

        coordinator_data = self.coordinator.data
        sensor_key = self.entity_description.key

        # Use direct keys from ManagerDataCoordinator's data structure
        if sensor_key == KEY_GLOBAL_PLAYERS:
            return len(coordinator_data.get("global_players", []))
        elif sensor_key == KEY_AVAILABLE_WORLDS_COUNT:
            return len(coordinator_data.get("available_worlds", []))
        elif sensor_key == KEY_AVAILABLE_ADDONS_COUNT:
            return len(coordinator_data.get("available_addons", []))

        _LOGGER.warning("Unhandled manager sensor key for value: %s", sensor_key)
        return None

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        if not self.available or not isinstance(self.coordinator.data, dict):
            return None

        coordinator_data = self.coordinator.data
        sensor_key = self.entity_description.key
        attrs: Dict[str, Any] = {}

        # Use direct keys from ManagerDataCoordinator for lists
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
