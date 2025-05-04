"""Config flow for Minecraft Bedrock Server Manager integration."""

import logging
from typing import Any, Dict, Optional, List

import voluptuous as vol
import aiohttp

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    DEFAULT_PORT,
    CONF_SERVER_NAMES,
)
from .api import (
    MinecraftBedrockApi,
    APIError,
    AuthError,
    CannotConnectError,
    ServerNotFoundError,
)
from .options_flow import MinecraftBdsManagerOptionsFlowHandler

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): selector.NumberSelector(
            selector.NumberSelectorConfig(min=1, max=65535, mode=selector.NumberSelectorMode.BOX)
        ),
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)

# Custom Exceptions
class CannotConnect(exceptions.HomeAssistantError):
    def __init__(self, error_key="cannot_connect", error_details=None):
        super().__init__(f"Cannot connect: {error_key} {error_details or ''}")
        self.error_key = error_key
        self.error_details = error_details

class InvalidAuth(exceptions.HomeAssistantError):
    error_key = "invalid_auth"


async def validate_input(hass: HomeAssistant, data: dict) -> Dict[str, Any]:
    """Validate input and fetch servers."""
    session = async_get_clientsession(hass)
    api_client = MinecraftBedrockApi(
        host=data[CONF_HOST], port=int(data[CONF_PORT]),
        username=data[CONF_USERNAME], password=data[CONF_PASSWORD], session=session
    )
    try:
        authenticated = await api_client.authenticate()
        if not authenticated: raise AuthError("Authentication failed silently.")
        discovered_servers = await api_client.async_get_server_list()
        return {"discovered_servers": discovered_servers}
    except CannotConnectError as err: raise CannotConnect() from err
    except AuthError as err: raise InvalidAuth() from err
    except APIError as err: raise CannotConnect("api_error", error_details=str(err)) from err
    # --- Catch broad Exception but raise a standard HA error ---
    except Exception as err:
        _LOGGER.exception("Unexpected error during validation: %s", err)
        # Don't raise ConfigFlowError, just indicate unknown issue
        raise exceptions.HomeAssistantError("unknown_validation_error") from err


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Minecraft Bedrock Server Manager."""
    VERSION = 1

    def __init__(self):
        self._connection_data: Dict[str, Any] = {}
        self._discovered_servers: List[str] = []

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        errors: Dict[str, str] = {}
        if user_input is not None:
            unique_manager_id = f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            await self.async_set_unique_id(unique_manager_id)
            self._abort_if_unique_id_configured()
            try:
                validation_result = await validate_input(self.hass, user_input)
                self._discovered_servers = validation_result["discovered_servers"]
                self._connection_data = user_input
                _LOGGER.debug("Validation successful, proceeding to server selection.")
                return await self.async_step_select_servers()

            # --- Corrected Exception Handling ---
            except CannotConnect as err:
                errors["base"] = err.error_key
                _LOGGER.warning("Config flow connection error: %s", err.error_key)
                if err.error_details: _LOGGER.warning("Connection error details: %s", err.error_details)
            except InvalidAuth as err:
                errors["base"] = err.error_key # Use the key defined in the exception
                _LOGGER.warning("Config flow invalid auth")
            except exceptions.HomeAssistantError as err: # Catch base HA error from validate_input's final catch
                errors["base"] = str(err) if str(err) else "unknown_error" # Use error string if available
                _LOGGER.warning("Config flow validation error: %s", err)
            except Exception as err: # Catch truly unexpected errors in THIS step's logic
                errors["base"] = "unknown_error"
                _LOGGER.exception("Unexpected error in user step: %s", err)
            # --- End Corrected Exception Handling ---

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_DATA_SCHEMA, user_input),
            errors=errors
        )

    async def async_step_select_servers(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        errors: Dict[str, str] = {}
        if user_input is not None:
            selected_servers = user_input.get(CONF_SERVER_NAMES, [])
            _LOGGER.info("Creating config entry for manager %s, initially selected servers: %s", f"{self._connection_data[CONF_HOST]}:{self._connection_data[CONF_PORT]}", selected_servers)
            return self.async_create_entry(title=f"BSM @ {self._connection_data[CONF_HOST]}", data=self._connection_data.copy(), options={CONF_SERVER_NAMES: selected_servers})

        if not self._discovered_servers: description_placeholders = {"message": "No servers were found on this manager. You can still add the manager itself and select servers later via configuration."}
        else: description_placeholders = {"message": "Select the initial Minecraft server instances you want to monitor."}

        select_schema = vol.Schema({
            vol.Optional(CONF_SERVER_NAMES, default=[]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=self._discovered_servers,
                    multiple=True,
                    sort=True # Sort servers alphabetically
                 )
            ),
        })
        return self.async_show_form(step_id="select_servers", data_schema=select_schema, errors=errors, description_placeholders=description_placeholders)

    # Options Flow Link
    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> MinecraftBdsManagerOptionsFlowHandler:
        return MinecraftBdsManagerOptionsFlowHandler(config_entry)