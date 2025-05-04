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
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
# Import the specific Coordinator class
from .coordinator import MinecraftBedrockCoordinator

# Import constants and API definitions
from .const import (
    DOMAIN,
    CONF_SERVER_NAME, # Still used conceptually for server identity
    ATTR_CPU_PERCENT,
    ATTR_MEMORY_MB,
    ATTR_PID,
    ATTR_UPTIME,
    ATTR_WORLD_NAME,
    ATTR_INSTALLED_VERSION,
)
from .api import MinecraftBedrockApi, ServerNotRunningError, ServerNotFoundError # Keep API import if needed

_LOGGER = logging.getLogger(__name__)

# Sensor Descriptions for Server entities (remains the same)
SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="status", name="Status", icon="mdi:minecraft",
    ),
    SensorEntityDescription(
        key=ATTR_CPU_PERCENT, name="CPU Usage", icon="mdi:cpu-64-bit",
        native_unit_of_measurement="%", state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key=ATTR_MEMORY_MB, name="Memory Usage", icon="mdi:memory",
        native_unit_of_measurement="MiB", state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1, device_class=SensorDeviceClass.DATA_SIZE,
        suggested_unit_of_measurement="MiB",
    ),
    # Add player count sensor description here later if implemented
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for all selected servers for this config entry."""
    # Retrieve the central data stored by __init__.py
    try:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        servers_data: dict = entry_data["servers"] # Dict keyed by server_name containing coordinator etc.
        manager_identifier: tuple = entry_data["manager_identifier"] # Get manager identifier tuple
        api_client: MinecraftBedrockApi = entry_data["api"] # Shared API client
    except KeyError as e:
        _LOGGER.error("Missing expected data for entry %s: %s. Cannot set up sensors.", entry.entry_id, e)
        return

    if not servers_data:
        _LOGGER.debug("No servers configured or successfully initialized for manager entry %s. Skipping sensor setup.", entry.entry_id)
        return

    _LOGGER.debug("Setting up sensors for servers: %s", list(servers_data.keys()))

    sensors_to_add = []
    # --- Loop through each server managed by this entry ---
    for server_name, server_data in servers_data.items():
        # Check if coordinator exists for this server (it might have failed in __init__)
        coordinator = server_data.get("coordinator")
        if not coordinator:
            _LOGGER.warning("Coordinator object missing for server '%s' in entry %s. Skipping sensors.", server_name, entry.entry_id)
            continue

        # --- Fetch or retrieve static info for *this* server ---
        # We store it back into server_data within hass.data for reuse
        if "world_name" not in server_data or "installed_version" not in server_data:
             _LOGGER.debug("Fetching static info for server '%s' via sensor setup", server_name)
             try:
                 world_name = await api_client.async_get_world_name(server_name)
                 installed_version = await api_client.async_get_version(server_name)
                 server_data["world_name"] = world_name # Store back
                 server_data["installed_version"] = installed_version # Store back
             except Exception as e:
                 _LOGGER.warning("Failed to fetch static info for server %s during sensor setup: %s. Using defaults.", server_name, e)
                 server_data["world_name"] = None
                 server_data["installed_version"] = None

        # --- Create sensor entities for *this* server ---
        for description in SENSOR_DESCRIPTIONS:
            sensors_to_add.append(
                MinecraftServerSensor(
                    coordinator=coordinator, # Pass the correct coordinator
                    description=description,
                    entry=entry,
                    server_name=server_name, # Pass the server name explicitly
                    manager_identifier=manager_identifier, # Pass manager identifier tuple for linking
                    # Pass fetched static data for initial DeviceInfo setup and attributes
                    installed_version=server_data.get("installed_version"),
                    world_name=server_data.get("world_name")
                )
            )

    if sensors_to_add:
        _LOGGER.info("Adding %d sensor entities for manager entry %s", len(sensors_to_add), entry.entry_id)
        # Don't use update_before_add=True; coordinator handles initial refresh.
        async_add_entities(sensors_to_add)


# Use specific coordinator type hint
class MinecraftServerSensor(CoordinatorEntity[MinecraftBedrockCoordinator], SensorEntity):
    """Base class for a Minecraft Server Manager sensor for a specific server."""

    _attr_has_entity_name = True # Use Description.name as the base name ("Status", "CPU Usage", etc.)

    def __init__(
        self,
        coordinator: MinecraftBedrockCoordinator,
        description: SensorEntityDescription,
        entry: ConfigEntry,
        server_name: str, # Explicitly receive server_name
        manager_identifier: tuple, # Receive manager identifier tuple
        installed_version: Optional[str], # Receive static info
        world_name: Optional[str], # Receive static info
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator) # Pass the specific coordinator for this server
        self.entity_description = description
        self._entry = entry
        self._server_name = server_name # Store the server name for this entity
        # Store static info on self for easy access in properties
        self._world_name = world_name
        self._installed_version = installed_version

        # Unique ID: domain_servername_sensorkey
        self._attr_unique_id = f"{DOMAIN}_{self._server_name}_{description.key}"

        # --- Device Info for the Server Device ---
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._server_name)}, # Unique identifier for THIS server instance
            name=f"Minecraft Server ({self._server_name})", # Name for this server device
            manufacturer="Minecraft Bedrock Manager", # Can be the same
            model=f"Managed Server", # Model indicating it's managed
            sw_version=self._installed_version or "Unknown", # Use stored static info
            # Link this server device TO the manager device using the manager's identifier tuple
            via_device=manager_identifier,
            configuration_url=f"http://{entry.data[CONF_HOST]}:{int(entry.data[CONF_PORT])}", # Use int() cast
        )

    # --- Properties (available, native_value, extra_state_attributes) ---
    # These rely on self.coordinator (which is specific to this server)
    # and self._world_name / self._installed_version (stored during init)
    # Their internal logic remains the same as the last fully working version.

    @property
    def available(self) -> bool:
        """Return True if coordinator has data and the specific sensor's value is valid."""
        if not super().available: return False # Check coordinator's base availability
        # Check for specific error states reported by coordinator
        if isinstance(self.coordinator.data, dict) and self.coordinator.data.get("status") == "error":
             error_type_name = self.coordinator.data.get("error_type")
             # Status sensor can report Stopped/Not Found even if there was an error of that type
             if error_type_name in [ServerNotRunningError.__name__, ServerNotFoundError.__name__]:
                  return self.entity_description.key == "status"
             else: # Other errors (connection, auth, API) make all sensors unavailable
                 return False
        # Check if process_info exists for process-dependent sensors
        if self.entity_description.key in [ATTR_CPU_PERCENT, ATTR_MEMORY_MB]:
             process_info = self.coordinator.data.get("process_info")
             return isinstance(process_info, dict)
        # Status sensor is available if we passed error checks
        if self.entity_description.key == "status": return True
        # Default to available if coordinator seems okay
        return True

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        # Handle coordinator error or no data states
        if not self.coordinator.data or (isinstance(self.coordinator.data, dict) and self.coordinator.data.get("status") == "error"):
             if self.entity_description.key == "status":
                  if isinstance(self.coordinator.data, dict):
                      error_type_name = self.coordinator.data.get("error_type")
                      if error_type_name == ServerNotRunningError.__name__: return "Stopped"
                      if error_type_name == ServerNotFoundError.__name__: return "Not Found"
                  return "Unknown" # General error or no data
             return None # Other sensors are None/Unknown

        # Extract data if available
        process_info = self.coordinator.data.get("process_info")
        sensor_key = self.entity_description.key

        if sensor_key == "status":
            return "Running" if isinstance(process_info, dict) else "Stopped"

        # Return None if process info needed but missing (server stopped)
        if not isinstance(process_info, dict):
             if sensor_key in [ATTR_CPU_PERCENT, ATTR_MEMORY_MB]: return None
             # Handle other sensors that might depend on process_info

        # Extract specific values if process_info exists
        if sensor_key == ATTR_CPU_PERCENT: return process_info.get(ATTR_CPU_PERCENT)
        if sensor_key == ATTR_MEMORY_MB: return process_info.get(ATTR_MEMORY_MB)

        _LOGGER.warning("Sensor state requested for unhandled key: %s", sensor_key)
        return None

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return entity specific state attributes."""
        attrs = {}
        # Use static info stored on self
        if self._world_name: attrs[ATTR_WORLD_NAME] = self._world_name
        if self._installed_version: attrs[ATTR_INSTALLED_VERSION] = self._installed_version

        # Add dynamic attributes from coordinator if available and server running
        if self.coordinator.data and isinstance(self.coordinator.data, dict) and self.coordinator.data.get("status") != "error":
             process_info = self.coordinator.data.get("process_info")
             if isinstance(process_info, dict):
                  pid = process_info.get("pid")
                  uptime = process_info.get("uptime")
                  if pid is not None: attrs[ATTR_PID] = pid
                  if uptime is not None: attrs[ATTR_UPTIME] = uptime
             # Add player list here later if/when available

        return attrs if attrs else None