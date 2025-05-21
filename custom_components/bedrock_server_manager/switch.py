# custom_components/bedrock_server_manager/switch.py
"""Switch platform for Bedrock Server Manager."""

import logging
from typing import Any, Optional, Dict, Tuple, cast, List

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import (
    HomeAssistant,
    callback,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .coordinator import MinecraftBedrockCoordinator, ManagerDataCoordinator
from .const import (
    DOMAIN,
    CONF_USE_SSL,
    ATTR_INSTALLED_VERSION,
)
from .utils import sanitize_host_port_string
from pybedrock_server_manager import (
    BedrockServerManagerApi,
    APIError,
    AuthError,
    CannotConnectError,
    ServerNotFoundError,
    ServerNotRunningError,
)

_LOGGER = logging.getLogger(__name__)

# Single description for the server control switch
SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="server_control",  # This key is primarily for internal use if you had multiple switch types
    name="Server",  # This will be the entity's friendly name suffix
    icon="mdi:minecraft",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bedrock Server Manager switch entities based on a config entry."""
    _LOGGER.debug("Setting up switch platform for BSM entry: %s", entry.entry_id)
    try:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        servers_config_data: Dict[str, Dict[str, Any]] = entry_data.get("servers", {})
        original_manager_identifier_tuple = cast(
            Tuple[str, str], entry_data["manager_identifier"]
        )
        manager_coordinator = cast(
            Optional[ManagerDataCoordinator], entry_data.get("manager_coordinator")
        )
    except KeyError as e:
        _LOGGER.error(
            "Switch setup failed for entry %s: Missing expected data (Key: %s). "
            "This might happen if __init__.py did not complete successfully.",
            entry.entry_id,
            e,
        )
        return

    if not servers_config_data:
        _LOGGER.info(
            "No servers configured for BSM '%s'; no switch entities will be created.",
            entry.title,
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
    manager_identifier_for_switches = (
        original_manager_identifier_tuple[0],
        sanitized_manager_id_str,
    )

    switches_to_add: List[MinecraftServerSwitch] = []

    # Get BSM OS Type to pass to server switches
    bsm_os_type_for_servers: str = "Unknown"  # Default value
    if (
        manager_coordinator
        and manager_coordinator.last_update_success
        and manager_coordinator.data
    ):
        manager_info = manager_coordinator.data.get("info", {})
        if isinstance(manager_info, dict):
            bsm_os_type_for_servers = manager_info.get("os_type", "Unknown")
        _LOGGER.debug(
            "BSM OS type determined as: %s for entry %s (switch setup)",
            bsm_os_type_for_servers,
            entry.title,
        )
    else:
        _LOGGER.warning(
            "ManagerDataCoordinator for BSM '%s' not available, has no data, or last update failed; "
            "BSM OS type for server switch devices will default to '%s'.",
            entry.title,
            bsm_os_type_for_servers,
        )

    for server_name, server_data_dict in servers_config_data.items():
        coordinator = cast(
            Optional[MinecraftBedrockCoordinator], server_data_dict.get("coordinator")
        )
        if not coordinator:
            _LOGGER.warning(
                "Coordinator missing for server '%s' under BSM '%s'. Skipping its switch.",
                server_name,
                entry.title,
            )
            continue

        # Get static version info, potentially fetched during __init__ or sensor setup
        # This is for the initial DeviceInfo. It can be updated by _handle_coordinator_update.
        installed_version_static = server_data_dict.get(
            ATTR_INSTALLED_VERSION
        )  # From __init__/sensor setup

        # Add switch only if coordinator has data or has successfully run once
        if (
            coordinator.last_update_success and coordinator.data is not None
        ):  # Check data is not None
            switches_to_add.append(
                MinecraftServerSwitch(
                    coordinator=coordinator,
                    description=SWITCH_DESCRIPTION,
                    server_name=server_name,
                    manager_identifier=manager_identifier_for_switches,
                    installed_version_static=installed_version_static,
                    bsm_os_type=bsm_os_type_for_servers,
                )
            )
        else:
            _LOGGER.warning(
                "Coordinator for server '%s' (BSM '%s') has no data or last update failed; "
                "skipping its switch entity. It might be created on next successful update.",
                server_name,
                entry.title,
            )

    if switches_to_add:
        _LOGGER.info(
            "Adding %d BSM switch entities for BSM '%s'.",
            len(switches_to_add),
            entry.title,
        )
        async_add_entities(switches_to_add)
    else:
        _LOGGER.info("No switch entities were added for BSM '%s'.", entry.title)


class MinecraftServerSwitch(
    CoordinatorEntity[MinecraftBedrockCoordinator], SwitchEntity
):
    """Represents a switch to control a Minecraft Bedrock server."""

    _attr_has_entity_name = True  # Name will be "Device Name Switch Name" (e.g. "Server MyServer Server Power")

    def __init__(
        self,
        coordinator: MinecraftBedrockCoordinator,
        description: SwitchEntityDescription,  # Make sure this is SwitchEntityDescription
        server_name: str,  # The configured name of the server (e.g., "s1", "my_world")
        manager_identifier: Tuple[str, str],  # (DOMAIN, manager_host_port_id string)
        installed_version_static: Optional[
            str
        ],  # Can be None, used as fallback for sw_version
        bsm_os_type: Optional[str],
    ) -> None:
        """Initialize the server switch."""
        super().__init__(coordinator)  # Initialize CoordinatorEntity
        self.entity_description = description
        self._server_name = server_name
        self._manager_host_port_id = manager_identifier[1]
        self._attr_installed_version_static = installed_version_static
        self._bsm_os_type = bsm_os_type

        # Construct unique_id for the switch entity itself
        self._attr_unique_id = (
            f"{DOMAIN}_{self._manager_host_port_id}_{self._server_name}_{description.key}".lower()
            .replace(":", "_")
            .replace(".", "_")
        )  # Make it a safe string for an entity ID

        _LOGGER.debug(
            "Init ServerSwitch '%s' for server '%s' (Manager ID: %s), UniqueID: %s",
            description.key,  # Log the key for dev clarity, UI name will be entity_description.name
            self._server_name,
            self._manager_host_port_id,
            self._attr_unique_id,
        )

        # --- Construct configuration_url for the DeviceInfo ---
        # This URL should point to the BSM manager's UI.
        config_entry_data = (
            coordinator.config_entry.data
        )  # Main config data for the BSM manager
        bsm_host = config_entry_data[CONF_HOST]
        bsm_use_ssl = config_entry_data.get(CONF_USE_SSL, False)

        port_from_config = config_entry_data.get(CONF_PORT)  # Safely get, could be None
        bsm_effective_port: Optional[int] = None
        display_port_str_for_url = ""  # For constructing the URL part like ":8080"

        if port_from_config is not None:
            port_input_str = str(port_from_config).strip()
            if port_input_str:  # Only process if not empty
                try:
                    # Robust parsing: try float then int, to handle "123.0"
                    port_float = float(port_input_str)
                    if port_float == int(port_float):  # Check if it's a whole number
                        port_val_int = int(port_float)
                        if 1 <= port_val_int <= 65535:  # Validate range
                            bsm_effective_port = port_val_int
                        else:
                            _LOGGER.warning(
                                "Switch DeviceInfo for server '%s': Invalid BSM manager port range '%s' from config.",
                                self._server_name,
                                port_input_str,
                            )
                    else:
                        _LOGGER.warning(
                            "Switch DeviceInfo for server '%s': BSM manager port '%s' from config is not a whole number.",
                            self._server_name,
                            port_input_str,
                        )
                except ValueError:
                    _LOGGER.warning(
                        "Switch DeviceInfo for server '%s': BSM manager port '%s' from config is not a valid number.",
                        self._server_name,
                        port_input_str,
                    )

        if bsm_effective_port is not None:
            display_port_str_for_url = f":{bsm_effective_port}"

        protocol = "https" if bsm_use_ssl else "http"

        safe_config_url: str
        if ":" in bsm_host and bsm_effective_port is None:
            safe_config_url = f"{protocol}://{bsm_host}"
        else:
            safe_config_url = f"{protocol}://{bsm_host}{display_port_str_for_url}"
        # --- End of configuration_url construction ---

        # Construct the model string
        base_model_name = "Minecraft Bedrock Server"
        model_name_with_os = base_model_name
        uninformative_os_types = ["Unknown", None, ""]
        if self._bsm_os_type and self._bsm_os_type not in uninformative_os_types:
            model_name_with_os = f"{base_model_name} ({self._bsm_os_type})"
        else:
            _LOGGER.debug(
                "BSM OS type for server switch device '%s' is '%s' (or uninformative), using base model name: '%s'.",
                self._server_name,
                self._bsm_os_type,
                base_model_name,
            )

        # Define the device for this specific Minecraft server.
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, f"{self._manager_host_port_id}_{self._server_name}")},
            name=f"{self._server_name} ({bsm_host}{display_port_str_for_url})",  # Use the configured server name
            manufacturer="Bedrock Server Manager",
            model=model_name_with_os,
            # Try to get dynamic version from coordinator, then static, then Unknown
            sw_version=(
                self.coordinator.data.get("version") if self.coordinator.data else None
            )
            or installed_version_static
            or "Unknown",
            via_device=manager_identifier,
            configuration_url=safe_config_url,
        )

    @property
    def available(self) -> bool:
        """Return True if coordinator is available and has data."""
        # last_update_success is checked by super().available
        return super().available and self.coordinator.data is not None

    @property
    def is_on(self) -> bool:
        """Return true if the server is considered running."""
        # Ensure coordinator data is valid before accessing
        if not self.available:  # Relies on the refined available property
            _LOGGER.debug(
                "Switch %s unavailable, reporting is_on as False.", self.unique_id
            )
            return False  # Or self._attr_is_on to retain last known state if preferred

        # process_info is a dict if server is running, None if stopped/not found by API
        process_info = self.coordinator.data.get("process_info")
        # Server is 'on' if process_info is a dictionary (implying process details were found)
        current_state_is_on = isinstance(process_info, dict)

        return current_state_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the server on."""
        api: BedrockServerManagerApi = (
            self.coordinator.api
        )  # Get API client from coordinator
        _LOGGER.info(
            "Turning ON server '%s' via BSM '%s'.",
            self._server_name,
            self._manager_host_port_id,
        )
        try:
            await api.async_start_server(self._server_name)
            # After a successful action, request a refresh of the coordinator
            await self.coordinator.async_request_refresh()
        except AuthError as err:
            _LOGGER.error(
                "Auth error starting server '%s': %s",
                self._server_name,
                err.api_message or err,
            )
            raise HomeAssistantError(
                f"Authentication failed for server {self._server_name}: {err.api_message or str(err)}"
            ) from err
        except CannotConnectError as err:
            _LOGGER.error(
                "Connection error starting server '%s': %s",
                self._server_name,
                err.args[0] if err.args else err,
            )
            raise HomeAssistantError(
                f"Could not connect to BSM to start server {self._server_name}: {err.args[0] if err.args else str(err)}"
            ) from err
        except (
            ServerNotFoundError
        ) as err:  # Should ideally not happen if device exists, but API might change
            _LOGGER.error(
                "Server Not Found error starting server '%s': %s",
                self._server_name,
                err.api_message or err,
            )
            raise HomeAssistantError(
                f"Server {self._server_name} not found by BSM API: {err.api_message or str(err)}"
            ) from err
        except (
            APIError
        ) as err:  # Catch other API errors (e.g., server already running, other 500s)
            _LOGGER.error(
                "API error starting server '%s': %s",
                self._server_name,
                err.api_message or err,
            )
            raise HomeAssistantError(
                f"Failed to start server {self._server_name}: {err.api_message or str(err)}"
            ) from err
        except Exception as err:  # Catch-all for truly unexpected issues
            _LOGGER.exception(
                "Unexpected error turning ON server '%s'", self._server_name
            )
            raise HomeAssistantError(
                f"Unexpected error starting server {self._server_name}: {type(err).__name__}"
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the server off."""
        api: BedrockServerManagerApi = self.coordinator.api
        _LOGGER.info(
            "Turning OFF server '%s' via BSM '%s'.",
            self._server_name,
            self._manager_host_port_id,
        )
        try:
            await api.async_stop_server(self._server_name)
            await self.coordinator.async_request_refresh()
        except (
            ServerNotRunningError
        ) as err:  # API/Client specifically indicates server wasn't running
            _LOGGER.warning(
                "Attempted to stop server '%s', but BSM reported it was not running: %s",
                self._server_name,
                err.api_message or err,
            )
            await self.coordinator.async_request_refresh()  # Refresh state even if "error" was benign
            # Do not re-raise HomeAssistantError, this is an idempotent success.
        except (
            APIError
        ) as err:  # Check for other API errors that might imply it was already stopped
            # Use err.api_message from the client exception for more direct error string
            err_msg_lower = (err.api_message or str(err)).lower()
            if "not running" in err_msg_lower or "already stopped" in err_msg_lower:
                _LOGGER.warning(
                    "Attempted to stop server '%s'; API indicated it was not running: %s",
                    self._server_name,
                    err_msg_lower,
                )
                await self.coordinator.async_request_refresh()
                return  # Idempotent success
            _LOGGER.error(
                "API error stopping server '%s': %s",
                self._server_name,
                err.api_message or err,
            )
            raise HomeAssistantError(
                f"Failed to stop server {self._server_name}: {err.api_message or str(err)}"
            ) from err
        except (
            AuthError
        ) as err:  # Order matters, catch more specific before general APIError
            _LOGGER.error(
                "Auth error stopping server '%s': %s",
                self._server_name,
                err.api_message or err,
            )
            raise HomeAssistantError(
                f"Authentication failed for server {self._server_name}: {err.api_message or str(err)}"
            ) from err
        except CannotConnectError as err:
            _LOGGER.error(
                "Connection error stopping server '%s': %s",
                self._server_name,
                err.args[0] if err.args else err,
            )
            raise HomeAssistantError(
                f"Could not connect to BSM to stop server {self._server_name}: {err.args[0] if err.args else str(err)}"
            ) from err
        except ServerNotFoundError as err:  # Should ideally not happen if device exists
            _LOGGER.error(
                "Server Not Found error stopping server '%s': %s",
                self._server_name,
                err.api_message or err,
            )
            # Refresh, as server might have been deleted from BSM but HA entity still exists.
            await self.coordinator.async_request_refresh()

        except Exception as err:  # Catch-all
            _LOGGER.exception(
                "Unexpected error turning OFF server '%s'", self._server_name
            )
            raise HomeAssistantError(
                f"Unexpected error stopping server {self._server_name}: {type(err).__name__}"
            ) from err

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator and update device sw_version if applicable."""
        if (
            self.coordinator.last_update_success
            and isinstance(self.coordinator.data, dict)
            and self._attr_device_info
        ):  # Ensure device_info was set

            # Dynamic SW Version update logic
            dynamic_version_from_coord = self.coordinator.data.get(
                "current_installed_version"
            )  # Must match key in coordinator data

            current_device_sw_version = self._attr_device_info.get("sw_version")

            if (
                dynamic_version_from_coord
                and dynamic_version_from_coord != "Unknown"
                and dynamic_version_from_coord != current_device_sw_version
            ):

                _LOGGER.debug(
                    "Switch for server '%s': version '%s' from coordinator differs from device SW version '%s'. Updating device.",
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
                    self._attr_device_info["sw_version"] = (
                        dynamic_version_from_coord  # Update local cache
                    )
                    self._attr_installed_version_static = (
                        dynamic_version_from_coord  # Update static cache
                    )

        super()._handle_coordinator_update()  # This calls self.async_write_ha_state()
