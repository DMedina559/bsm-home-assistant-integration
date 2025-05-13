# custom_components/bedrock_server_manager/config_flow.py
"""Config flow for Bedrock Server Manager integration."""

import logging
from typing import Any, Dict, Optional, List

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

# --- IMPORT FROM CONSTANTS ---
from .const import (
    DOMAIN,
    DEFAULT_PORT,
    CONF_SERVER_NAMES,
)

# --- IMPORT FROM THE NEW LIBRARY ---
from pybedrock_server_manager import (
    BedrockServerManagerApi,
    APIError,
    AuthError,
    CannotConnectError,
)

# --- END IMPORT FROM NEW LIBRARY ---

# Import the Options Flow Handler
from .options_flow import (
    BSMOptionsFlowHandler,
)  # Assuming this will also be updated if it uses API

_LOGGER = logging.getLogger(__name__)

# --- Schema Definition (Unchanged) ---
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=65535, mode=selector.NumberSelectorMode.BOX
            )
        ),
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)


# --- Custom Internal Config Flow Exceptions (Unchanged) ---
class CannotConnect(exceptions.HomeAssistantError):
    def __init__(self, error_key="cannot_connect", error_details=None):
        super().__init__(f"Cannot connect: {error_key} {error_details or ''}")
        self.error_key = error_key
        self.error_details = error_details


class InvalidAuth(exceptions.HomeAssistantError):
    error_key = "invalid_auth"


# --- Validation Function (Updated API call) ---
async def validate_input(hass: HomeAssistant, data: dict) -> Dict[str, Any]:
    session = async_get_clientsession(hass)
    api_client = BedrockServerManagerApi(
        host=data[CONF_HOST],
        port=int(data[CONF_PORT]),
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        session=session,
    )

    try:
        _LOGGER.debug("Validating connection: Attempting authentication...")
        authenticated = await api_client.authenticate()  # This method name is fine
        if not authenticated:
            _LOGGER.warning("API client authenticate() returned False unexpectedly.")
            raise AuthError("Authentication failed silently.")

        _LOGGER.debug("Authentication successful. Fetching server list...")
        # --- UPDATED METHOD CALL ---
        discovered_servers = await api_client.async_get_servers()
        # --- END UPDATED METHOD CALL ---
        _LOGGER.debug("Successfully fetched server list: %s", discovered_servers)
        return {"discovered_servers": discovered_servers}

    except CannotConnectError as err:
        _LOGGER.warning(
            "Validation error: Cannot connect to manager at %s:%s - %s",
            data[CONF_HOST],
            data[CONF_PORT],
            err,
        )
        raise CannotConnect() from err
    except AuthError as err:
        _LOGGER.warning(
            "Validation error: Invalid credentials for %s - %s",
            data[CONF_USERNAME],
            err,
        )
        raise InvalidAuth() from err
    except APIError as err:
        _LOGGER.warning("Validation error: API communication error - %s", err)
        raise CannotConnect("api_error", error_details=str(err)) from err
    except Exception as err:
        _LOGGER.exception("Unexpected error during config flow validation: %s", err)
        raise exceptions.HomeAssistantError("unknown_validation_error") from err


# --- Config Flow Class (Unchanged logic, uses updated validate_input) ---
class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        self._connection_data: Dict[str, Any] = {}
        self._discovered_servers: List[str] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return BSMOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        errors: Dict[str, str] = {}
        if user_input is not None:
            unique_manager_id = f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            await self.async_set_unique_id(unique_manager_id)
            self._abort_if_unique_id_configured()

            try:
                validation_result = await validate_input(
                    self.hass, user_input
                )  # Calls updated function
                self._discovered_servers = validation_result["discovered_servers"]
                self._connection_data = user_input
                _LOGGER.debug("Validation successful, proceeding to server selection.")
                return await self.async_step_select_servers()
            except CannotConnect as err:
                errors["base"] = err.error_key
                _LOGGER.warning("Config flow connection error: %s", err.error_key)
                if err.error_details:
                    _LOGGER.warning("Connection error details: %s", err.error_details)
            except InvalidAuth as err:
                errors["base"] = err.error_key
                _LOGGER.warning("Config flow invalid auth error.")
            except exceptions.HomeAssistantError as err:
                errors["base"] = str(err) if str(err) else "unknown_error"
                _LOGGER.warning("Config flow validation error: %s", err)
            except Exception as err:
                errors["base"] = "unknown_error"
                _LOGGER.exception("Unexpected error in user step: %s", err)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_select_servers(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        errors: Dict[str, str] = {}
        if user_input is not None:
            selected_servers = user_input.get(CONF_SERVER_NAMES, [])
            _LOGGER.info(
                "Creating config entry for manager %s:%s, initially selected servers: %s",
                self._connection_data[CONF_HOST],
                self._connection_data[CONF_PORT],
                selected_servers,
            )
            return self.async_create_entry(
                title=f"BSM @ {self._connection_data[CONF_HOST]}",
                data=self._connection_data.copy(),
                options={CONF_SERVER_NAMES: selected_servers},
            )

        description_placeholders = {}
        if not self._discovered_servers:
            _LOGGER.warning(
                "Showing server selection step, but no servers were discovered."
            )
            description_placeholders["message"] = (
                "No servers were found on this manager. You can add the manager now and select servers later via 'CONFIGURE'."
            )
        else:
            description_placeholders["message"] = (
                "Select the initial Minecraft servers you want to monitor."
            )

        select_schema = vol.Schema(
            {
                vol.Optional(CONF_SERVER_NAMES, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self._discovered_servers,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                        sort=True,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="select_servers",
            data_schema=select_schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )
