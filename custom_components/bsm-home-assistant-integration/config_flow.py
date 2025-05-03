"""Config flow for Minecraft Bedrock Server Manager integration."""

import logging
from typing import Any, Dict, Optional, List

import voluptuous as vol
import aiohttp

from homeassistant import config_entries, exceptions
# Import CONF constants from HA
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
# Import callback decorator
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

# Import local constants
from .const import (
    DOMAIN,
    # CONF_SERVER_NAME is no longer primary data, use a new const for the list
    DEFAULT_PORT,
)
# Define a new constant for the list of servers in options
CONF_SERVER_NAMES = "servers" # Use plural

# Import API definitions
from .api import (
    MinecraftBedrockApi,
    APIError,
    AuthError,
    CannotConnectError,
    ServerNotFoundError, # Keep for API definition
)
# Import the Options Flow Handler - needed for linking
from .options_flow import MinecraftBdsManagerOptionsFlowHandler

_LOGGER = logging.getLogger(__name__)

# --- Schema for initial user step (connection details ONLY) ---
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

# --- Custom Exceptions ---
# Define custom exceptions subclassing HomeAssistantError for flow control
class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
    def __init__(self, error_key="cannot_connect", error_details=None):
        super().__init__(f"Cannot connect: {error_key} {error_details or ''}")
        self.error_key = error_key
        self.error_details = error_details

class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate invalid auth."""
    error_key = "invalid_auth"


# --- Validation Function ---
async def validate_input(hass: HomeAssistant, data: dict) -> Dict[str, Any]:
    """Validate the user input allows us to connect, authenticate and get server list.

    Data has the keys from STEP_USER_DATA_SCHEMA.
    Raises CannotConnect, InvalidAuth on failure.
    Returns dict with list of discovered server names on success.
    """
    session = async_get_clientsession(hass)
    api_client = MinecraftBedrockApi(
        host=data[CONF_HOST],
        port=int(data[CONF_PORT]), # Explicitly cast port to int
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        session=session,
    )

    try:
        authenticated = await api_client.authenticate()
        if not authenticated: raise AuthError("Authentication failed silently.")
        discovered_servers = await api_client.async_get_server_list()
        return {"discovered_servers": discovered_servers}

    except CannotConnectError as err:
        _LOGGER.error("Connection error during validation: %s", err)
        raise CannotConnect() from err
    except AuthError as err:
        _LOGGER.error("Authentication error during validation: %s", err)
        raise InvalidAuth() from err
    except APIError as err:
        _LOGGER.error("API error during validation (fetching server list): %s", err)
        raise CannotConnect("api_error", error_details=str(err)) from err
    except Exception as err:
        _LOGGER.exception("Unexpected error during validation: %s", err)
        raise exceptions.ConfigFlowError("unknown_validation_error") from err


# --- Main Config Flow Class ---
class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Minecraft Bedrock Server Manager."""

    VERSION = 1
    # CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLLING # Deprecated

    def __init__(self):
        """Initialize the config flow."""
        self._connection_data: Dict[str, Any] = {}
        self._discovered_servers: List[str] = []

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Handle the initial step (gathering connection info)."""
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

            except CannotConnect as err:
                errors["base"] = err.error_key
                if err.error_details: _LOGGER.warning("Connection error details: %s", err.error_details)
            except InvalidAuth: errors["base"] = "invalid_auth"
            except exceptions.ConfigFlowError as err: errors["base"] = str(err) if str(err) else "unknown_error"
            except Exception: errors["base"] = "unknown_error"

        # Show form for the first time or if errors occurred
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_DATA_SCHEMA, user_input),
            errors=errors
        )

    async def async_step_select_servers(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Handle the server multi-selection step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            selected_servers = user_input.get(CONF_SERVER_NAMES, [])

            _LOGGER.info(
                "Creating config entry for manager %s, initially selected servers: %s",
                f"{self._connection_data[CONF_HOST]}:{self._connection_data[CONF_PORT]}",
                selected_servers
            )

            # Create the config entry
            return self.async_create_entry(
                title=f"BSM @ {self._connection_data[CONF_HOST]}",
                data=self._connection_data.copy(),
                options={CONF_SERVER_NAMES: selected_servers}
            )

        # Show the selection form
        if not self._discovered_servers:
             description_placeholders = {"message": "No servers were found on this manager. You can still add the manager itself and select servers later via configuration."}
        else:
             description_placeholders = {"message": "Select the initial Minecraft server instances you want to monitor."}


        select_schema = vol.Schema({
            vol.Optional(CONF_SERVER_NAMES, default=[]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=self._discovered_servers,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LISTBOX,
                 )
            ),
        })

        return self.async_show_form(
            step_id="select_servers",
            data_schema=select_schema,
            errors=errors,
            description_placeholders=description_placeholders
        )

    # --- Options Flow Link ---
    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MinecraftBdsManagerOptionsFlowHandler:
        """Get the options flow for this handler."""
        return MinecraftBdsManagerOptionsFlowHandler(config_entry)
