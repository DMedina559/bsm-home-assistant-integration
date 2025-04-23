"""Config flow for Minecraft Bedrock Server Manager integration."""

import logging
from typing import Any, Dict, Optional, List

import voluptuous as vol
import aiohttp

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector
from homeassistant.core import callback

from .options_flow import MinecraftBdsManagerOptionsFlowHandler
from .const import (
    DOMAIN,
    CONF_SERVER_NAME,
    DEFAULT_PORT,
)
from .api import (
    MinecraftBedrockApi,
    APIError,
    AuthError,
    CannotConnectError,
    ServerNotFoundError,
)

_LOGGER = logging.getLogger(__name__)

# Schema for user step (collecting connection details)
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

# Define a custom exception subclass for Config Flow specific errors
class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
    def __init__(self, error_key="cannot_connect", error_details=None):
        super().__init__(f"Cannot connect: {error_key} {error_details or ''}")
        self.error_key = error_key
        self.error_details = error_details

class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate invalid auth."""
    error_key = "invalid_auth"


async def validate_input(hass: HomeAssistant, data: dict) -> Dict[str, Any]:
    """Validate the user input allows us to connect and authenticate.

    Data has the keys from STEP_USER_DATA_SCHEMA.
    Raises CannotConnect, InvalidAuth on failure.
    """
    session = async_get_clientsession(hass)
    api_client = MinecraftBedrockApi(
        host=data[CONF_HOST],
        port=int(data[CONF_PORT]),
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        session=session,
    )

    try:
        # Attempt authentication first
        authenticated = await api_client.authenticate()
        if not authenticated:
            # Should not happen if authenticate() doesn't raise, but double-check
            raise AuthError("Authentication failed silently.") # Will be caught below

        # If authenticated, try fetching the server list
        discovered_servers = await api_client.async_get_server_list()

        # Return data needed for the next step or for creating the entry
        return {
            "api_client": api_client, # Pass the authenticated client for potential reuse (though maybe not needed)
            "discovered_servers": discovered_servers
         }

    except CannotConnectError as err:
        _LOGGER.error("Connection error during validation: %s", err)
        raise CannotConnect() from err # Reraise specific exception
    except AuthError as err:
        _LOGGER.error("Authentication error during validation: %s", err)
        raise InvalidAuth() from err # Reraise specific exception
    except APIError as err:
        # Catch other API errors during server list fetch
        _LOGGER.error("API error during validation (fetching server list): %s", err)
        # Use CannotConnect but provide details for the message
        raise CannotConnect("api_error", error_details=str(err)) from err
    except Exception as err:
        # Handle unexpected errors during validation
        _LOGGER.exception("Unexpected error during validation: %s", err)
        # Map to a generic ConfigFlowError or raise a custom one if needed
        raise exceptions.ConfigFlowError("unknown_validation_error") from err


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Minecraft Bedrock Server Manager."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        # Store data gathered across steps
        self._user_input: Dict[str, Any] = {}
        self._discovered_servers: List[str] = []

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult: # Use FlowResult type hint
        """Handle the initial step (gathering connection info)."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            try:
                # Validate connection and auth, get server list
                validation_result = await validate_input(self.hass, user_input)
                self._discovered_servers = validation_result["discovered_servers"]
                # Store the validated user input (host, port, user, pass)
                self._user_input = user_input

                if not self._discovered_servers:
                    # Connected fine, but no servers found on the manager
                    errors["base"] = "no_servers_found"
                    # Fall through to re-show form with error - *** NO! Need explicit return ***
                else:
                    # Validation successful and servers found, proceed to server selection
                    _LOGGER.debug("Validation successful, proceeding to server selection.")
                    # Pass discovered servers to the next step via instance variable
                    return await self.async_step_select_server()

            except CannotConnect as err:
                _LOGGER.warning("Config flow connection error: %s", err.error_key)
                errors["base"] = err.error_key
                # If error_details exist, append them for more specific feedback if desired
                if err.error_details:
                     # NOTE: Translations might not support dynamic parts well in 'base' errors.
                     # Consider logging details instead or using specific error keys.
                     _LOGGER.warning("Connection error details: %s", err.error_details)
            except InvalidAuth:
                _LOGGER.warning("Config flow invalid auth")
                errors["base"] = "invalid_auth"
            except exceptions.ConfigFlowError as err: # Catch errors raised from validate_input
                 _LOGGER.warning("Config flow validation error: %s", err)
                 # Use the message key if available, otherwise a generic one
                 errors["base"] = str(err) if str(err) else "unknown_error"
            except Exception as err: # Catch unexpected errors during flow logic
                _LOGGER.exception("Unexpected error in user step: %s", err)
                errors["base"] = "unknown_error"

            if errors:
                return self.async_show_form(
                    step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
                )

        # Show the form for the first time or if validation failed above
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_select_server(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Handle the server selection step."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            selected_server = user_input[CONF_SERVER_NAME]
            try:
                # Validate the selected server exists using the specific API endpoint
                await self._validate_server_selection(selected_server)

                # Set unique ID based on host/port/server_name to prevent duplicates
                # Use a stable identifier if possible. Host+Port+ServerName is usually good.
                unique_id = f"{self._user_input[CONF_HOST]}:{self._user_input[CONF_PORT]}-{selected_server}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                # Combine original user input with selected server name
                final_data = self._user_input.copy()
                final_data[CONF_SERVER_NAME] = selected_server

                _LOGGER.info("Creating config entry for server: %s", selected_server)
                # Data to store in the config entry
                return self.async_create_entry(
                    title=f"Minecraft Server ({selected_server})", data=final_data
                )

            except ServerNotFoundError:
                 _LOGGER.warning("Selected server '%s' not found via validation API.", selected_server)
                 errors["base"] = "server_validation_failed"
            except APIError as err:
                _LOGGER.error("API error during server selection validation: %s", err)
                errors["base"] = "api_error" # Generic API error
                # Consider logging str(err) for details
            except Exception as err:  # Catch unexpected errors
                _LOGGER.exception("Unexpected error during server selection: %s", err)
                errors["base"] = "unknown_error"
            if errors:
                 # Need to reconstruct the schema with the available servers
                 select_schema = vol.Schema({
                     vol.Required(CONF_SERVER_NAME): selector.SelectSelector(
                         selector.SelectSelectorConfig(
                             options=self._discovered_servers,
                             mode=selector.SelectSelectorMode.DROPDOWN,
                         )
                     ),
                 })
                 return self.async_show_form(
                     step_id="select_server", data_schema=select_schema, errors=errors
                 )


        # Show the selection form (first time or if error occurred above)
        if not self._discovered_servers:
             # Should not happen if we got here from step_user, but handle defensively
             _LOGGER.error("Reached select_server step but no discovered servers list.")
             return self.async_abort(reason="no_servers_found") # Abort if list is missing

        # Define the schema for the dropdown dynamically
        select_schema = vol.Schema({
            vol.Required(CONF_SERVER_NAME): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=self._discovered_servers,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                 )
            ),
        })

        return self.async_show_form(
            step_id="select_server", data_schema=select_schema, errors=errors
        )


    async def _validate_server_selection(self, server_name: str) -> None:
        """Validate the selected server exists using the API."""
        # Recreate client briefly for this validation
        session = async_get_clientsession(self.hass)
        api_client = MinecraftBedrockApi(
            host=self._user_input[CONF_HOST],
            port=int(self._user_input[CONF_PORT]),
            username=self._user_input[CONF_USERNAME],
            password=self._user_input[CONF_PASSWORD],
            session=session,
        )
        try:
            # Authentication might be needed even for validate endpoint based on docs
            await api_client.authenticate() # Ensure token is fresh
            await api_client.async_validate_server_exists(server_name)
        except AuthError as err:
             # Should not happen if initial validation passed, but handle just in case
             _LOGGER.error("Auth error during server selection validation: %s", err)
             raise APIError(f"Authentication failed validating server {server_name}") from err
        # Let ServerNotFoundError and other APIErrors propagate up
        except Exception as err:
             _LOGGER.exception("Unexpected error validating server selection: %s", err)
             raise APIError(f"Unexpected error validating server {server_name}") from err

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MinecraftBdsManagerOptionsFlowHandler: # Return type is your options handler class
        """Get the options flow for this handler."""
        return MinecraftBdsManagerOptionsFlowHandler(config_entry)