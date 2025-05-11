"""Sensor platform for Bedrock Server Manager."""

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
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

# Import the specific Coordinator class
from .coordinator import MinecraftBedrockCoordinator, ManagerDataCoordinator

# Import constants and API definitions
from .const import (
    DOMAIN,
    CONF_SERVER_NAME,  # Still used conceptually for server identity
    ATTR_CPU_PERCENT,
    ATTR_MEMORY_MB,
    ATTR_PID,
    ATTR_UPTIME,
    ATTR_WORLD_NAME,
    ATTR_INSTALLED_VERSION,
    ATTR_ALLOWLISTED_PLAYERS,
    ATTR_SERVER_PROPERTIES,
    KEY_GLOBAL_PLAYERS,
    ATTR_GLOBAL_PLAYERS_LIST,
)
from .api import (
    BedrockServerManagerApi,
    ServerNotRunningError,
    ServerNotFoundError,
)

_LOGGER = logging.getLogger(__name__)

# Server-Specific Sensor Descriptions
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
)

# Manager-Global Players Sensor Description
MANAGER_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=KEY_GLOBAL_PLAYERS,
        name="Global Players",
        icon="mdi:account-group",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for manager and all selected servers."""
    try:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        servers_data: dict = entry_data.get("servers", {})
        manager_identifier: tuple = entry_data["manager_identifier"]
        # Get the specific manager coordinator instance
        manager_coordinator: ManagerDataCoordinator = entry_data["manager_coordinator"]
        api_client: BedrockServerManagerApi = entry_data["api"]
    except KeyError as e:
        _LOGGER.error(
            "Missing expected data for entry %s: %s. Cannot set up sensors.",
            entry.entry_id,
            e,
        )
        return

    entities_to_add = []

    # --- Add Global Players Sensor for the Manager Device, using ManagerDataCoordinator ---
    for description in MANAGER_SENSOR_DESCRIPTIONS:
        entities_to_add.append(
            GlobalPlayersSensor(
                coordinator=manager_coordinator,  # Pass the manager's coordinator
                description=description,
                manager_identifier=manager_identifier,
                entry_id=entry.entry_id,  # For unique ID construction
            )
        )

    # --- Server-Specific Sensors (Loop) ---
    if servers_data:  # Check if there are any server coordinators
        _LOGGER.debug("Setting up server sensors for: %s", list(servers_data.keys()))
        for server_name, server_specific_data in servers_data.items():
            server_coordinator = server_specific_data.get("coordinator")
            if not server_coordinator:
                _LOGGER.warning(
                    "Coordinator missing for server '%s'. Skipping sensors.",
                    server_name,
                )
                continue

            # Fetch/retrieve static info for this server if needed by constructor
            # It's better if static info is also part of coordinator data or fetched once reliably
            world_name = server_specific_data.get("world_name")
            installed_version = server_specific_data.get("installed_version")

            if (
                world_name is None or installed_version is None
            ):  # Check for None explicitly
                _LOGGER.debug(
                    "Static info missing for server '%s', attempting fetch.",
                    server_name,
                )
                try:
                    world_name = await api_client.async_get_world_name(server_name)
                    installed_version = await api_client.async_get_version(server_name)
                    # Store it back in the server_specific_data for other platforms
                    server_specific_data["world_name"] = world_name
                    server_specific_data["installed_version"] = installed_version
                except Exception as e:
                    _LOGGER.warning(
                        "Failed to fetch static info for server %s: %s.", server_name, e
                    )
                    # Ensure they are set to something, even if None, for the constructor
                    if world_name is None:
                        world_name = None
                    if installed_version is None:
                        installed_version = None

            for description in SERVER_SENSOR_DESCRIPTIONS:
                entities_to_add.append(
                    MinecraftServerSensor(  # Correct class name for server sensors
                        coordinator=server_coordinator,  # Pass server's coordinator
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
            "Adding %d sensor entities for manager entry %s",
            len(entities_to_add),
            entry.entry_id,
        )
        async_add_entities(entities_to_add)


# Use specific coordinator type hint
class MinecraftServerSensor(
    CoordinatorEntity[MinecraftBedrockCoordinator], SensorEntity
):
    """Base class for a Minecraft Server Manager sensor for a specific server."""

    _attr_has_entity_name = (
        True  # Use Description.name as the base name ("Status", "CPU Usage", etc.)
    )

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
            name=self._server_name,
            manufacturer="Bedrock Server Manager",
            model="Minecraft Bedrock Server",
            sw_version=self._installed_version or "Unknown",
            via_device=manager_identifier,
            configuration_url=f"http://{entry.data[CONF_HOST]}:{int(entry.data[CONF_PORT])}",
        )

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if (
            isinstance(self.coordinator.data, dict)
            and self.coordinator.data.get("status") == "error"
        ):
            error_type_name = self.coordinator.data.get("error_type")
            return (
                error_type_name
                in [ServerNotRunningError.__name__, ServerNotFoundError.__name__]
                and self.entity_description.key == "status"
            )
        if self.entity_description.key in [ATTR_CPU_PERCENT, ATTR_MEMORY_MB]:
            process_info = self.coordinator.data.get("process_info")
            return isinstance(process_info, dict)
        if self.entity_description.key == "status":
            return True
        return True

    @property
    def native_value(self) -> Any:
        if not self.coordinator.data or (
            isinstance(self.coordinator.data, dict)
            and self.coordinator.data.get("status") == "error"
        ):
            if self.entity_description.key == "status":
                if isinstance(self.coordinator.data, dict):
                    error_type_name = self.coordinator.data.get("error_type")
                    return (
                        "Stopped"
                        if error_type_name == ServerNotRunningError.__name__
                        else (
                            "Not Found"
                            if error_type_name == ServerNotFoundError.__name__
                            else "Unknown"
                        )
                    )
                return "Unknown"
            return None
        process_info = self.coordinator.data.get("process_info")
        sensor_key = self.entity_description.key
        if sensor_key == "status":
            return "Running" if isinstance(process_info, dict) else "Stopped"
        if not isinstance(process_info, dict) and sensor_key in [
            ATTR_CPU_PERCENT,
            ATTR_MEMORY_MB,
        ]:
            return None
        if sensor_key == ATTR_CPU_PERCENT:
            return process_info.get(ATTR_CPU_PERCENT)
        if sensor_key == ATTR_MEMORY_MB:
            return process_info.get(ATTR_MEMORY_MB)
        _LOGGER.warning("Sensor state for unhandled key: %s", sensor_key)
        return None

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        attrs = {}
        sensor_key = self.entity_description.key
        if sensor_key == "status":
            if self._world_name:
                attrs[ATTR_WORLD_NAME] = self._world_name
            if self._installed_version:
                attrs[ATTR_INSTALLED_VERSION] = self._installed_version
            if self.coordinator.data and isinstance(self.coordinator.data, dict):
                allowlist = self.coordinator.data.get("allowlist")
                attrs[ATTR_ALLOWLISTED_PLAYERS] = (
                    [
                        p.get("name")
                        for p in allowlist
                        if isinstance(p, dict) and p.get("name")
                    ]
                    if isinstance(allowlist, list)
                    else []
                )
                server_props = self.coordinator.data.get("properties")
                attrs[ATTR_SERVER_PROPERTIES] = (
                    server_props if isinstance(server_props, dict) else {}
                )
                process_info = self.coordinator.data.get("process_info")
                if isinstance(process_info, dict):
                    pid = process_info.get("pid")
                    uptime = process_info.get("uptime")
                    attrs[ATTR_PID] = pid
                    attrs[ATTR_UPTIME] = uptime
                else:
                    attrs[ATTR_PID] = None
                    attrs[ATTR_UPTIME] = None
        elif sensor_key == ATTR_CPU_PERCENT:
            if self.coordinator.data and isinstance(self.coordinator.data, dict):
                process_info = self.coordinator.data.get("process_info")
                pid = process_info.get("pid")
                uptime = process_info.get("uptime")
                attrs[ATTR_PID] = pid
                attrs[ATTR_UPTIME] = uptime
        return attrs if attrs else None


# --- New Global Players Sensor Class ---
class GlobalPlayersSensor(CoordinatorEntity[ManagerDataCoordinator], SensorEntity):
    """Representation of a sensor for the global player list count."""

    _attr_has_entity_name = True  # Use description.name as base

    def __init__(
        self,
        coordinator: ManagerDataCoordinator,  # Use the Manager's coordinator
        description: SensorEntityDescription,
        manager_identifier: tuple,  # To link to manager device
        entry_id: str,  # For unique ID construction if needed
    ):
        """Initialize the global players sensor."""
        super().__init__(coordinator)  # Pass the manager's coordinator
        self.entity_description = description
        self._manager_identifier = manager_identifier

        # Unique ID based on manager + sensor key
        manager_id_str = manager_identifier[1]  # Get the "host:port" part
        self._attr_unique_id = f"{DOMAIN}_{manager_id_str}_{description.key}"

        # Link to the Manager device
        self._attr_device_info = DeviceInfo(
            identifiers={self._manager_identifier},  # Identifies the Manager device
        )

    # No async_added_to_hass or signal handler needed; coordinator handles updates.

    @property
    def native_value(self) -> int:
        """Return the state of the sensor (count of global players)."""
        if self.coordinator.last_update_success and self.coordinator.data:
            players_list = self.coordinator.data.get("global_players", [])
            return len(players_list if isinstance(players_list, list) else [])
        return 0  # Or STATE_UNAVAILABLE if preferred when coordinator fails

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return entity specific state attributes (the list of players)."""
        if self.coordinator.last_update_success and self.coordinator.data:
            players_list = self.coordinator.data.get("global_players", [])
            # Return the raw list of player objects from the API
            return {
                ATTR_GLOBAL_PLAYERS_LIST: (
                    players_list if isinstance(players_list, list) else []
                )
            }
        return {ATTR_GLOBAL_PLAYERS_LIST: []}  # Return empty list on error/no data

    @property
    def available(self) -> bool:
        """Sensor availability is based on coordinator's last success."""
        return self.coordinator.last_update_success
