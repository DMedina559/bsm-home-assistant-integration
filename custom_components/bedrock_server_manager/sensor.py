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
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, UpdateFailed
from homeassistant.helpers import device_registry as dr


# --- IMPORT FROM LOCAL MODULES ---
from .coordinator import MinecraftBedrockCoordinator, ManagerDataCoordinator
from .utils import sanitize_host_port_string
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
    SensorEntityDescription(
        key=KEY_MANAGER_APP_VERSION,
        name="Manager App Version",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities based on a config entry."""
    _LOGGER.debug("Setting up sensor platform for BSM entry: %s", entry.entry_id)
    try:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        api_client = cast(BedrockServerManagerApi, entry_data["api"])
        original_manager_identifier_tuple = cast(
            Tuple[str, str], entry_data["manager_identifier"]
        )
        manager_coordinator = cast(
            ManagerDataCoordinator, entry_data["manager_coordinator"]
        )
        servers_config_data: Dict[str, Dict[str, Any]] = entry_data.get("servers", {})
    except KeyError as e:
        _LOGGER.error(
            "Sensor setup failed for entry %s: Missing expected data (Key: %s). ",
            entry.entry_id,
            e,
        )
        return

    # Sanitize the host-port string part of the manager_identifier
    original_manager_id_str = original_manager_identifier_tuple[1]
    sanitized_manager_id_str = sanitize_host_port_string(original_manager_id_str)

    if sanitized_manager_id_str != original_manager_id_str:
        _LOGGER.info(
            "Sanitized manager identifier string from '%s' to '%s' for entry %s",
            original_manager_id_str,
            sanitized_manager_id_str,
            entry.entry_id,
        )
    # Create a new, sanitized manager_identifier tuple to be used by sensors
    # The first part of the tuple is typically the DOMAIN.
    manager_identifier_for_sensors = (
        original_manager_identifier_tuple[0],
        sanitized_manager_id_str,
    )

    entities_to_add: List[SensorEntity] = []

    if manager_coordinator.last_update_success and manager_coordinator.data:
        for description in MANAGER_SENSOR_DESCRIPTIONS:
            entities_to_add.append(
                ManagerInfoSensor(
                    coordinator=manager_coordinator,
                    description=description,
                    manager_identifier=manager_identifier_for_sensors,
                )
            )
    else:
        _LOGGER.warning(
            "ManagerDataCoordinator for BSM '%s' has no data or last update failed; "
            "skipping manager-level sensors.",
            entry.title,
        )

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
                    "Error fetching initial static info for server '%s': %s",
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
                        manager_identifier=manager_identifier_for_sensors,
                        installed_version_static=version_static,
                        world_name_static=world_name_static,
                    )
                )
        else:
            _LOGGER.warning(
                "MinecraftBedrockCoordinator for server '%s' (BSM '%s') has no data or "
                "last update failed AT SENSOR SETUP; skipping its sensors. Check coordinator logs.",
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

        config_entry_data = coordinator.config_entry.data
        bsm_host = config_entry_data[CONF_HOST]
        bsm_use_ssl = config_entry_data.get(CONF_USE_SSL, False)
        port_from_config = config_entry_data.get(CONF_PORT)
        bsm_effective_port: Optional[int] = None
        display_port_str_for_url = ""

        if port_from_config is not None:
            port_input_str = str(port_from_config).strip()
            if port_input_str:
                try:
                    port_val_int = int(float(port_input_str))
                    if 1 <= port_val_int <= 65535:
                        bsm_effective_port = port_val_int
                    else:
                        _LOGGER.warning("Invalid BSM port range '%s'", port_input_str)
                except ValueError:
                    _LOGGER.warning(
                        "BSM port '%s' is not a valid number.", port_input_str
                    )

        if bsm_effective_port is not None:
            display_port_str_for_url = f":{bsm_effective_port}"
        protocol = "https" if bsm_use_ssl else "http"
        safe_config_url = (
            f"{protocol}://{bsm_host}{display_port_str_for_url}"
            if not (":" in bsm_host and bsm_effective_port is None)
            else f"{protocol}://{bsm_host}"
        )

        dynamic_sw_version = None
        if self.coordinator.data:
            dynamic_sw_version = self.coordinator.data.get("version")

        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, f"{self._manager_host_port_id}_{self._server_name}")},
            name=f"Minecraft Server: {self._server_name}",
            manufacturer="Bedrock Server Manager",
            model=f"Managed Server ({self._server_name})",
            sw_version=dynamic_sw_version
            or self._installed_version_static
            or "Unknown",
            via_device=manager_identifier,
            configuration_url=safe_config_url,
        )

    @property
    def available(self) -> bool:
        is_avail = (
            super().available
            and self.coordinator.last_update_success
            and bool(self.coordinator.data)
        )
        return is_avail

    @property
    def native_value(self) -> Any:
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
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        if not self.available or not isinstance(self.coordinator.data, dict):
            return None
        data = self.coordinator.data
        attrs: Dict[str, Any] = {}
        key = self.entity_description.key
        process_info = data.get("process_info")

        if key == "status":
            if self._installed_version_static:  # This should now be safe
                attrs[ATTR_INSTALLED_VERSION] = self._installed_version_static
        elif key in [ATTR_CPU_PERCENT, ATTR_MEMORY_MB]:
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
            attrs[ATTR_ALLOWLISTED_PLAYERS] = [
                p.get("name") for p in data.get("allowlist", []) if isinstance(p, dict)
            ]
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
        return (
            super().available
            and self.coordinator.last_update_success
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
        _LOGGER.warning(
            "Unhandled manager sensor key '%s' for native_value in %s",
            key,
            self.unique_id,
        )
        return None

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        if not self.available or not isinstance(self.coordinator.data, dict):
            return None
        data = self.coordinator.data
        key = self.entity_description.key
        attrs: Dict[str, Any] = {}
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
        return attrs if attrs else None
