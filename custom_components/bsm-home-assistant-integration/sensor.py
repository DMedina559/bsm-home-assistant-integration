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
from homeassistant.const import CONF_HOST, CONF_PORT # Needed for manager URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
# Import the specific Coordinator class
from .coordinator import MinecraftBedrockCoordinator

# Import constants and API definitions
from .const import (
    DOMAIN,
    CONF_SERVER_NAME, # Still used for identifying server within entry data
    ATTR_CPU_PERCENT,
    ATTR_MEMORY_MB,
    ATTR_PID,
    ATTR_UPTIME,
    ATTR_WORLD_NAME,
    ATTR_INSTALLED_VERSION,
)
from .api import MinecraftBedrockApi, ServerNotRunningError, ServerNotFoundError

_LOGGER = logging.getLogger(__name__)

# Sensor Descriptions (remain the same)
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
)


# --- Refactored async_setup_entry ---
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for all selected servers for this config entry."""
    # Retrieve the central data stored by __init__.py
    try:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        servers_data: dict = entry_data["servers"] # Dict keyed by server_name
        manager_device_id: str = entry_data["manager_device_id"]
        api_client: MinecraftBedrockApi = entry_data["api"] # Shared API client
    except KeyError as e:
        _LOGGER.error("Missing expected data for entry %s: %s. Cannot set up sensors.", entry.entry_id, e)
        return

    if not servers_data:
        _LOGGER.info("No servers configured for this manager entry (%s). Skipping sensor setup.", entry.entry_id)
        return

    _LOGGER.debug("Setting up sensors for servers: %s", list(servers_data.keys()))

    sensors_to_add = []
    # --- Loop through each server managed by this entry ---
    for server_name, server_data in servers_data.items():
        try:
            coordinator: MinecraftBedrockCoordinator = server_data["coordinator"]
        except KeyError:
            _LOGGER.error("Coordinator missing for server '%s' in entry %s. Skipping sensors for this server.", server_name, entry.entry_id)
            continue # Skip this server if coordinator setup failed

        # --- Fetch static info for *this* server (if not already stored) ---
        # Check if info was already fetched and stored (e.g., by __init__ or previous platform setup)
        if "world_name" not in server_data or "installed_version" not in server_data:
             _LOGGER.debug("Fetching static info for server '%s'", server_name)
             try:
                 world_name = await api_client.async_get_world_name(server_name)
                 installed_version = await api_client.async_get_version(server_name)
                 # Store it back in the server_data dict for other platforms/attributes
                 server_data["world_name"] = world_name
                 server_data["installed_version"] = installed_version
             except Exception as e:
                 _LOGGER.warning("Failed to fetch static info for server %s: %s. Using defaults.", server_name, e)
                 server_data["world_name"] = None
                 server_data["installed_version"] = None

        # --- Create sensor entities for *this* server ---
        for description in SENSOR_DESCRIPTIONS:
            sensors_to_add.append(
                MinecraftServerSensor(
                    coordinator=coordinator, # Pass the correct coordinator for this server
                    description=description,
                    entry=entry,
                    server_name=server_name, # Pass the server name explicitly
                    manager_device_id=manager_device_id, # Pass manager device ID for linking
                    # Pass fetched static data for initial DeviceInfo setup
                    installed_version=server_data.get("installed_version"),
                    world_name=server_data.get("world_name")
                )
            )

    if sensors_to_add:
        _LOGGER.info("Adding %d sensor entities for manager entry %s", len(sensors_to_add), entry.entry_id)
        async_add_entities(sensors_to_add, False) # Don't need update_before_add as coordinator handles initial refresh


# Use specific coordinator type hint
class MinecraftServerSensor(CoordinatorEntity[MinecraftBedrockCoordinator], SensorEntity):
    """Base class for a Minecraft Server Manager sensor for a specific server."""

    _attr_has_entity_name = True # Use Description.name as the base name

    def __init__(
        self,
        coordinator: MinecraftBedrockCoordinator,
        description: SensorEntityDescription,
        entry: ConfigEntry,
        server_name: str, # Explicitly receive server_name
        manager_device_id: str, # Receive manager device ID
        installed_version: Optional[str], # Receive static info
        world_name: Optional[str], # Receive static info
    ) -> None:
        """Initialize the sensor."""
        # Pass the specific coordinator instance for this server
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._server_name = server_name # Store the server name for this entity
        self._manager_device_id = manager_device_id
        # Store static info if needed later (e.g., for attributes)
        self._world_name = world_name
        self._installed_version = installed_version

        # Unique ID: domain_servername_sensorkey
        self._attr_unique_id = f"{DOMAIN}_{self._server_name}_{description.key}"

        # --- Refactored Device Info ---
        # This device represents the *specific Minecraft Server instance*
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._server_name)}, # Unique identifier for THIS server instance
            name=f"Minecraft Server ({self._server_name})", # Name for this server device
            manufacturer="Minecraft Bedrock Manager", # Can be the same
            model=f"Managed Server", # Model indicating it's managed
            sw_version=self._installed_version or "Unknown", # Use stored static info
            # Link this server device TO the manager device
            via_device=(DOMAIN, self._manager_device_id),
            # Configuration URL could still point to the main manager UI
            configuration_url=f"http://{entry.data[CONF_HOST]}:{int(entry.data[CONF_PORT])}",
        )
        # --- End Refactored Device Info ---

    # Properties available, native_value remain largely the same,
    # relying on self.coordinator (which is now specific to this server)
    @property
    def available(self) -> bool:
        """Return True if coordinator has data and the specific sensor's value is valid."""
        # Availability logic using self.coordinator remains the same as before
        if not super().available: return False
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
        # Logic using self.coordinator.data remains the same as before
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
        # Use static info stored on self during init
        if self._world_name: attrs[ATTR_WORLD_NAME] = self._world_name
        if self._installed_version: attrs[ATTR_INSTALLED_VERSION] = self._installed_version

        # Add dynamic attributes from the coordinator's data
        if self.coordinator.data and isinstance(self.coordinator.data, dict) and self.coordinator.data.get("status") != "error":
             process_info = self.coordinator.data.get("process_info")
             if isinstance(process_info, dict):
                  pid = process_info.get("pid")
                  uptime = process_info.get("uptime")
                  if pid is not None: attrs[ATTR_PID] = pid
                  if uptime is not None: attrs[ATTR_UPTIME] = uptime
             # Add player list here later if available from coordinator.data
             # player_list = self.coordinator.data.get("player_list")
             # if player_list is not None: attrs[ATTR_PLAYERS_ONLINE] = player_list

        return attrs if attrs else None
