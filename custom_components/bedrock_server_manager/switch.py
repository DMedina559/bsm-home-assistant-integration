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
)  # callback not used here, but often in entities
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .coordinator import MinecraftBedrockCoordinator
from .const import (
    DOMAIN,
    CONF_USE_SSL,
    ATTR_INSTALLED_VERSION,
)  # Assuming these are in const

from pybedrock_server_manager import (
    BedrockServerManagerApi,  # For type hinting self.coordinator.api
    APIError,
    AuthError,
    CannotConnectError,
    ServerNotFoundError,
    ServerNotRunningError,
    # InvalidInputError, APIServerSideError etc. are caught by APIError
)

_LOGGER = logging.getLogger(__name__)

# Single description for the server control switch
SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="server_control",  # This key is primarily for internal use if you had multiple switch types
    name="Server Power",  # This will be the entity's friendly name suffix
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
        manager_identifier = cast(Tuple[str, str], entry_data["manager_identifier"])
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

    switches_to_add: List[MinecraftServerSwitch] = []
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
                    manager_identifier=manager_identifier,
                    installed_version_static=installed_version_static,
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
        description: SwitchEntityDescription,
        server_name: str,
        manager_identifier: Tuple[str, str],  # (DOMAIN, manager_host_port_id)
        installed_version_static: Optional[str],
    ) -> None:
        """Initialize the server switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._server_name = server_name
        self._manager_host_port_id = manager_identifier[1]
        self._attr_installed_version_static = installed_version_static

        self._attr_unique_id = f"{DOMAIN}_{self._manager_host_port_id}_{self._server_name}_{description.key}".lower().replace(
            ":", "_"
        )

        _LOGGER.debug(
            "Initializing ServerSwitch for '%s' (Manager: %s), Unique ID: %s",
            self._server_name,  # Using self._server_name as description.name might be just "Server Power"
            self._manager_host_port_id,
            self._attr_unique_id,
        )

        server_device_identifier_value = (
            f"{self._manager_host_port_id}_{self._server_name}"
        )

        config_data = coordinator.config_entry.data
        host_val = config_data[CONF_HOST]
        try:
            # Ensure port is a clean integer for the URL
            port_val = int(float(config_data[CONF_PORT]))
        except (ValueError, TypeError) as e:
            _LOGGER.error(
                "Invalid port value '%s' for switch on server '%s', device configuration_url. Defaulting to 0. Error: %s",
                config_data.get(CONF_PORT),
                self._server_name,
                e,
            )
            port_val = 0  # Fallback

        protocol = "https" if config_data.get(CONF_USE_SSL, False) else "http"
        safe_config_url = f"{protocol}://{host_val}:{port_val}"
        # --- End of corrected configuration_url construction ---

        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, server_device_identifier_value)},
            name=f"Server: {self._server_name} ({host_val})",  # Use host_val
            manufacturer="Bedrock Server Manager Integration",
            model="Managed Minecraft Server",
            sw_version=self._attr_installed_version_static or "Unknown",
            via_device=manager_identifier,
            configuration_url=safe_config_url,  # Use the safely constructed URL
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
