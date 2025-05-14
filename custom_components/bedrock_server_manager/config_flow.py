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
    CONF_USE_SSL,
)

from pybedrock_server_manager import (
    BedrockServerManagerApi,
    APIError,
    AuthError,
    CannotConnectError,
)

# Import the Options Flow Handler
from .options_flow import BSMOptionsFlowHandler

_LOGGER = logging.getLogger(__name__)

# --- Schema Definition ---
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
        vol.Optional(CONF_USE_SSL, default=False): bool,
    }
)


# --- Custom Internal Config Flow Exceptions ---
class CannotConnect(exceptions.HomeAssistantError):
    """Custom error for connection issues."""

    def __init__(self, error_key="cannot_connect", error_details: Optional[str] = None):
        super().__init__(f"Cannot connect: {error_key} {error_details or ''}")
        self.error_key = error_key
        self.error_details = error_details


class InvalidAuth(exceptions.HomeAssistantError):
    """Custom error for authentication failures."""

    def __init__(self, error_key="invalid_auth", error_details: Optional[str] = None):
        super().__init__(f"Invalid authentication: {error_key} {error_details or ''}")
        self.error_key = error_key
        self.error_details = error_details


# --- Validation Function ---
async def validate_input(hass: HomeAssistant, data: dict) -> Dict[str, Any]:
    """Validate the user input allows us to connect and authenticate."""
    session = async_get_clientsession(hass)
    api_client = BedrockServerManagerApi(
        host=data[CONF_HOST],
        port=int(data[CONF_PORT]),
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        session=session,
        use_ssl=data.get(CONF_USE_SSL, False),
    )

    try:
        _LOGGER.debug(
            "Validating input: Attempting authentication to BSM at %s:%s (SSL: %s)",
            data[CONF_HOST],
            data[CONF_PORT],
            data.get(CONF_USE_SSL, False),
        )
        # api_client.authenticate() will raise AuthError on failure
        await api_client.authenticate()
        _LOGGER.debug("Authentication successful.")

        _LOGGER.debug("Fetching server names list...")
        # Use async_get_server_names() to get a list of strings for the selector
        discovered_server_names: List[str] = await api_client.async_get_server_names()
        _LOGGER.debug("Successfully fetched server names: %s", discovered_server_names)

        await api_client.close()  # Close the session created by this BedrockServerManagerApi instance

        return {"discovered_servers": discovered_server_names}

    except CannotConnectError as err:
        _LOGGER.warning(
            "Validation error: Cannot connect to BSM at %s:%s - %s",
            data[CONF_HOST],
            data[CONF_PORT],
            err.args[0] if err.args else err,
        )
        # Pass the specific message from the client library's exception
        raise CannotConnect(
            error_details=err.args[0] if err.args else str(err)
        ) from err
    except AuthError as err:
        _LOGGER.warning(
            "Validation error: Invalid credentials for BSM user '%s' - %s",
            data[CONF_USERNAME],
            err.api_message or err,
        )
        raise InvalidAuth(error_details=err.api_message or str(err)) from err
    except (
        APIError
    ) as err:  # Catch other API errors (e.g., 500 from server during get_server_names)
        _LOGGER.warning(
            "Validation error: API communication error with BSM - %s",
            err.api_message or err,
        )
        # Re-map to CannotConnect for user feedback, or a new "api_error" key
        raise CannotConnect(
            "api_error", error_details=err.api_message or str(err)
        ) from err
    except Exception as err:  # Catch-all for truly unexpected issues
        _LOGGER.exception("Unexpected error during config flow validation")
        # Raise a generic HA error or a specific one for unknown validation issues
        raise exceptions.HomeAssistantError("unknown_validation_error") from err
    finally:
        # Ensure client session is closed if validate_input created it and didn't return early
        if "api_client" in locals() and hasattr(api_client, "close"):
            # Check if already closed, might be closed if validate_input completes successfully.
            if (
                api_client._session and not api_client._session.closed
            ):  # Accessing protected _session, better if client has is_closed property
                await api_client.close()


# --- Config Flow Class ---
class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bedrock Server Manager."""

    VERSION = 1
    # Remove CONNECTION_CLASS if you want Home Assistant to not automatically try to re-auth
    # on startup if it fails. Given your manual re-auth logic in the client,
    # and ConfigEntryNotReady from coordinator, this might be better.
    # CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the config flow."""
        self._connection_data: Dict[str, Any] = {}
        self._discovered_servers: List[str] = []  # Stores server names

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> BSMOptionsFlowHandler:
        """Get the options flow for this handler."""
        return BSMOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}
        description_placeholders: Optional[Dict[str, str]] = None

        if user_input is not None:
            # Create a unique ID for this BSM instance based on host and port
            unique_manager_id = f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            await self.async_set_unique_id(unique_manager_id)
            self._abort_if_unique_id_configured()

            try:
                validation_result = await validate_input(self.hass, user_input)
                self._discovered_servers = validation_result["discovered_servers"]
                self._connection_data = user_input  # Store validated user input

                _LOGGER.debug(
                    "Validation successful for %s, proceeding to server selection. Discovered servers: %s",
                    unique_manager_id,
                    self._discovered_servers,
                )
                return await self.async_step_select_servers()

            except CannotConnect as err:
                errors["base"] = err.error_key
                description_placeholders = {"error_details": err.error_details or ""}
                _LOGGER.warning(
                    "Config flow connection error: %s. Details: %s",
                    err.error_key,
                    err.error_details,
                )
            except InvalidAuth as err:
                errors["base"] = err.error_key
                description_placeholders = {"error_details": err.error_details or ""}
                _LOGGER.warning(
                    "Config flow invalid auth error. Details: %s", err.error_details
                )
            except (
                exceptions.HomeAssistantError
            ) as err_ha:  # Catch other HA specific errors
                errors["base"] = str(err_ha) if str(err_ha) else "unknown_config_error"
                _LOGGER.warning("Config flow HomeAssistantError: %s", err_ha)

        # Show the form again with errors or for the first time
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input  # Pre-fill form on error
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_select_servers(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Handle the server selection step."""
        errors: Dict[str, str] = (
            {}
        )  # Not typically used in this step unless complex validation

        if user_input is not None:
            # User has made their selection
            selected_servers = user_input.get(CONF_SERVER_NAMES, [])
            title = f"BSM @ {self._connection_data[CONF_HOST]}"

            _LOGGER.info(
                "Creating config entry '%s' for manager %s:%s. Selected servers: %s. Full connection data: %s",
                title,
                self._connection_data[CONF_HOST],
                self._connection_data[CONF_PORT],
                selected_servers,
                self._connection_data,  # Log full data being saved (excluding password in production logs ideally)
            )

            # Data stored in config_entry.data (credentials, host, port, ssl)
            # Options stored in config_entry.options (selected servers, scan intervals)
            return self.async_create_entry(
                title=title,
                data=self._connection_data.copy(),  # Store credentials and connection info
                options={
                    CONF_SERVER_NAMES: selected_servers
                },  # Store selectable options
            )

        # Show the server selection form
        description_placeholders: Dict[str, str] = {}
        if not self._discovered_servers:
            _LOGGER.warning(
                "Showing server selection step, but no servers were discovered for manager at %s:%s.",
                self._connection_data.get(CONF_HOST),
                self._connection_data.get(CONF_PORT),
            )
            # Provide a more helpful message if no servers are found
            description_placeholders["message"] = (
                "No Minecraft servers were found on this Bedrock Server Manager instance. "
                "You can still add the manager now and select servers later by reconfiguring the integration options, "
                "or verify server configurations on your BSM host."
            )
        else:
            description_placeholders["message"] = (
                "Select the initial Minecraft servers you want to monitor and control in Home Assistant. "
                "You can change this selection later."
            )

        # Schema for server selection
        server_options = sorted(
            self._discovered_servers
        )  # Ensure options are sorted for UI
        select_schema = vol.Schema(
            {
                vol.Optional(CONF_SERVER_NAMES, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=server_options,  # Use the fetched and sorted server names
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="select_servers",
            data_schema=select_schema,
            errors=errors,  # Typically no errors in this simple selection step
            description_placeholders=description_placeholders,
        )
