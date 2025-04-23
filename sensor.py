"""Sensor platform for Minecraft Bedrock Server Manager."""

import logging
from typing import Optional, Dict, Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
# Import constants from HA if standard, otherwise from local const.py
# CONF_HOST and CONF_PORT are standard
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
# Import CoordinatorEntity separately and the specific coordinator class
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .coordinator import MinecraftBedrockCoordinator # <-- Import specific coordinator

# Import constants and API definitions from this integration
from .const import (
    DOMAIN,
    CONF_SERVER_NAME, # Local constant
    ATTR_CPU_PERCENT,
    ATTR_MEMORY_MB,
    ATTR_PID,
    ATTR_UPTIME,
    ATTR_WORLD_NAME,
    ATTR_INSTALLED_VERSION,
)
from .api import MinecraftBedrockApi, ServerNotRunningError, ServerNotFoundError

_LOGGER = logging.getLogger(__name__)

# Sensor Descriptions - RESTORED DEFINITION
SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="status", # Internal key, derived from process_info presence/state
        name="Status", # Base name, will be prefixed
        icon="mdi:minecraft",
    ),
    SensorEntityDescription(
        key=ATTR_CPU_PERCENT,
        name="CPU Usage", # Base name
        icon="mdi:cpu-64-bit",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key=ATTR_MEMORY_MB,
        name="Memory Usage", # Base name
        icon="mdi:memory",
        native_unit_of_measurement="MiB", # Megabytes (MiB is more accurate technically)
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE, # Using DATA_SIZE which expects MiB
        suggested_unit_of_measurement="MiB", # Explicitly suggest MiB
    ),
    # Add player count sensor here later if data becomes available
    # SensorEntityDescription(
    #     key="player_count",
    #     name="Players Online",
    #     icon="mdi:account-multiple",
    #     state_class=SensorStateClass.MEASUREMENT,
    # ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities based on a config entry."""
    # Retrieve shared data stored in __init__.py
    entry_data = hass.data[DOMAIN][entry.entry_id]
    # Correctly type hint coordinator as the specific class
    coordinator: MinecraftBedrockCoordinator = entry_data["coordinator"]
    server_name: str = entry_data["server_name"]
    # API client is accessed via coordinator.api
    api_client: MinecraftBedrockApi = coordinator.api

    # Fetch static info once using the coordinator's API client
    try:
        world_name = await coordinator.api.async_get_world_name(server_name)
        installed_version = await coordinator.api.async_get_version(server_name)
    except Exception as e:
        # Log error and set defaults if static info fetch fails
        _LOGGER.error("Failed to fetch initial static info for server %s: %s", server_name, e)
        world_name = None
        installed_version = None

    # Store fetched static info back into hass.data for access later (e.g., by attributes)
    entry_data["world_name"] = world_name
    entry_data["installed_version"] = installed_version

    sensors_to_add = []
    # Iterate over the *actual* tuple now
    for description in SENSOR_DESCRIPTIONS:
        sensors_to_add.append(
            # Pass the fetched version to the constructor
            MinecraftServerSensor(
                coordinator,
                description,
                entry,
                installed_version # Pass the variable fetched above
            )
        )

    async_add_entities(sensors_to_add, True) # Pass True for update_before_add


# Use specific coordinator type hint
class MinecraftServerSensor(CoordinatorEntity[MinecraftBedrockCoordinator], SensorEntity):
    """Base class for a Minecraft Server Manager sensor."""

    _attr_has_entity_name = True # Use Description.name as the base name

    def __init__(
        self,
        # Use specific coordinator type hint
        coordinator: MinecraftBedrockCoordinator,
        description: SensorEntityDescription,
        entry: ConfigEntry,
        # Add parameter to accept installed_version
        installed_version: Optional[str],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator) # Pass the specific coordinator instance
        self.entity_description = description
        self._entry = entry
        self._server_name = entry.data[CONF_SERVER_NAME]

        # Unique ID: domain_servername_sensorkey
        self._attr_unique_id = f"{DOMAIN}_{self._server_name}_{description.key}"

        # Set initial device info using the passed-in version
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._server_name, entry.entry_id)}, # Unique identifier for the device
            name=f"Minecraft Server ({self._server_name})",
            manufacturer="Minecraft Bedrock Manager", # Or your specific manager name
            model=f"Managed Server ({self._server_name})",
            # Use the passed-in variable, fallback to "Unknown"
            sw_version=installed_version or "Unknown",
            # Use the imported CONF_HOST and CONF_PORT constants here
            configuration_url=f"http://{entry.data[CONF_HOST]}:{int(entry.data[CONF_PORT])}",
        )

    @property
    def available(self) -> bool:
        """Return True if coordinator has data and the specific sensor's value is valid."""
        if not super().available:
            return False
        if isinstance(self.coordinator.data, dict) and self.coordinator.data.get("status") == "error":
             error_type_name = self.coordinator.data.get("error_type")
             if error_type_name in [ServerNotRunningError.__name__, ServerNotFoundError.__name__]:
                  if self.entity_description.key == "status": return True
                  else: return False
             else: return False
        if self.entity_description.key in [ATTR_CPU_PERCENT, ATTR_MEMORY_MB]:
             process_info = self.coordinator.data.get("process_info")
             return process_info is not None and isinstance(process_info, dict)
        if self.entity_description.key == "status": return True
        return True

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if not self.coordinator.data or (isinstance(self.coordinator.data, dict) and self.coordinator.data.get("status") == "error"):
             if self.entity_description.key == "status":
                  if isinstance(self.coordinator.data, dict):
                      error_type_name = self.coordinator.data.get("error_type")
                      if error_type_name == ServerNotRunningError.__name__: return "Stopped"
                      if error_type_name == ServerNotFoundError.__name__: return "Not Found"
                  return "Unknown"
             return None
        process_info = self.coordinator.data.get("process_info")
        sensor_key = self.entity_description.key
        if sensor_key == "status":
            return "Running" if isinstance(process_info, dict) else "Stopped"
        if not isinstance(process_info, dict): return None
        if sensor_key == ATTR_CPU_PERCENT: return process_info.get(ATTR_CPU_PERCENT)
        if sensor_key == ATTR_MEMORY_MB: return process_info.get(ATTR_MEMORY_MB)
        _LOGGER.warning("Sensor state requested for unhandled key: %s", sensor_key)
        return None

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return entity specific state attributes."""
        attrs = {}
        try:
            # Access hass.data using self.hass (available in entities)
            entry_data = self.hass.data[DOMAIN][self._entry.entry_id]
            world_name = entry_data.get("world_name")
            installed_version = entry_data.get("installed_version")
            if world_name: attrs[ATTR_WORLD_NAME] = world_name
            if installed_version: attrs[ATTR_INSTALLED_VERSION] = installed_version
        except KeyError:
            # This shouldn't happen if setup succeeded, but handle defensively
            _LOGGER.warning("Could not find entry data for %s in hass.data when getting attributes", self._entry.entry_id)

        # Add dynamic attributes only if coordinator data is valid and server is running
        if self.coordinator.data and isinstance(self.coordinator.data, dict) and self.coordinator.data.get("status") != "error":
             process_info = self.coordinator.data.get("process_info")
             # Add dynamic attributes only if process_info exists (server is running)
             if isinstance(process_info, dict):
                  pid = process_info.get("pid")
                  uptime = process_info.get("uptime") # Already a string
                  if pid is not None: attrs[ATTR_PID] = pid
                  if uptime is not None: attrs[ATTR_UPTIME] = uptime

             # Add player list here later if available from coordinator.data
             # Example:
             # player_list = self.coordinator.data.get("player_list")
             # if player_list is not None:
             #     attrs[ATTR_PLAYERS_ONLINE] = player_list

        # Return attributes dictionary, or None if empty
        return attrs if attrs else None