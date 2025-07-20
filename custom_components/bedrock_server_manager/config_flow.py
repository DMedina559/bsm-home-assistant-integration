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
from homeassistant.components.diagnostics.util import async_redact_data

# --- IMPORT FROM CONSTANTS ---
from .const import (
    DOMAIN,
    CONF_SERVER_NAMES,
    CONF_USE_SSL,
    CONF_VERIFY_SSL,
)

from bsm_api_client import (
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
        vol.Optional(CONF_PORT): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1,
                max=65535,
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Optional(CONF_USE_SSL, default=False): bool,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
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


# --- Helper to clean just the port string component ---
def _clean_port_string_component(port_input: Any) -> str:
    """
    Takes various port inputs (None, int, float, str) and returns a clean
    integer string if it represents a whole number port, or an empty string.
    Logs warnings for unexpected formats but tries to return a usable string.
    """
    if port_input is None:
        return ""  # Return empty string for None input

    port_str = str(port_input).strip()
    if not port_str:
        return ""  # Return empty string for empty or whitespace-only input

    try:
        port_float = float(port_str)
        # Check if it's effectively an integer (e.g., 123.0 or 123)
        if port_float == int(port_float):
            port_int = int(port_float)
            return str(port_int)  # Return clean integer string like "11325"
        else:
            # Port has non-zero decimals (e.g., "80.5")
            _LOGGER.warning(
                "Port string component '%s' is a non-whole float. This is unusual for a port number "
                "and might lead to unexpected behavior if used in identifiers/titles without further processing.",
                port_str,
            )
            return port_str  # Return original stripped string (e.g., "80.5")
    except ValueError:
        # Port string is not a valid number (e.g., "abc")
        _LOGGER.warning(
            "Port string component '%s' is not a valid number. This might be an issue if a port was expected.",
            port_str,
        )
        return port_str  # Return original stripped string (e.g., "abc")


# --- Validation Function ---
async def validate_input(hass: HomeAssistant, data: dict) -> Dict[str, Any]:
    """Validate the user input allows us to connect and authenticate."""
    port_input = data.get(CONF_PORT)
    port_to_api: Optional[int] = None  # This must be an int or None for the API client
    host_for_log = data[CONF_HOST]

    if port_input is not None:
        port_input_str = str(port_input).strip()
        if port_input_str:  # Only process if not empty after stripping
            try:
                port_float = float(port_input_str)
                if port_float == int(port_float):  # Check if it's a whole number
                    port_val = int(port_float)
                    if not (1 <= port_val <= 65535):
                        _LOGGER.warning(
                            "Invalid port number '%s' entered in config flow for %s. Must be 1-65535.",
                            port_val,
                            host_for_log,
                        )
                        raise CannotConnect(
                            "invalid_port_range",
                            error_details=f"Port '{port_val}' out of range (1-65535).",
                        )
                    port_to_api = port_val  # Assign valid integer port
                else:  # Is a float, but not a whole number (e.g. 123.5)
                    _LOGGER.warning(
                        "Port value '%s' from config flow for %s is a non-integer number.",
                        port_input_str,
                        host_for_log,
                    )
                    raise CannotConnect(
                        "invalid_port_format",
                        error_details=f"Port '{port_input_str}' must be a whole number.",
                    )
            except ValueError:  # float() conversion failed (e.g. "abc")
                _LOGGER.warning(
                    "Port value '%s' from config flow for %s is not a valid number.",
                    port_input_str,
                    host_for_log,
                )
                raise CannotConnect(
                    "invalid_port_format",
                    error_details=f"Port '{port_input_str}' is not a valid number.",
                )

    user_requests_verify_ssl = data.get(CONF_VERIFY_SSL, True)
    user_requests_use_ssl = data.get(CONF_USE_SSL, False)

    # Use HA's shared session, respecting user's verify_ssl choice for this validation session
    validation_session = async_get_clientsession(
        hass, verify_ssl=user_requests_verify_ssl
    )
    api_client = None
    try:
        api_client = BedrockServerManagerApi(
            host=data[CONF_HOST],
            port=port_to_api,  # Pass the processed integer port or None
            username=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
            use_ssl=user_requests_use_ssl,
            verify_ssl=user_requests_verify_ssl,  # Let API client know user's preference
        )
        _LOGGER.debug(
            "Validating input: Attempting authentication to BSM at %s (Port: %s, SSL: %s, Verify SSL: %s)",
            host_for_log,
            port_to_api if port_to_api is not None else "derived/omitted",
            user_requests_use_ssl,
            user_requests_verify_ssl,
        )

        await api_client.authenticate()
        _LOGGER.debug("Authentication successful for %s.", host_for_log)

        _LOGGER.debug("Fetching server names list from %s...", host_for_log)
        discovered_server_names: List[str] = await api_client.async_get_server_names()
        _LOGGER.debug(
            "Successfully fetched server names from %s: %s",
            host_for_log,
            discovered_server_names,
        )

        return {"discovered_servers": discovered_server_names}

    except CannotConnectError as err:
        details = getattr(err, "error_details", None) or (
            err.args[0] if err.args else str(err)
        )
        key = getattr(err, "error_key", "cannot_connect")
        _LOGGER.warning(
            "Config flow validation: Cannot connect to BSM at %s. Error: %s. Details: %s",
            host_for_log,
            key,
            details,
        )
        raise CannotConnect(error_key=key, error_details=details) from err
    except AuthError as err:
        details = err.api_message or (err.args[0] if err.args else str(err))
        _LOGGER.warning(
            "Config flow validation: Invalid credentials for BSM user '%s' at %s. Details: %s",
            data[CONF_USERNAME],
            host_for_log,
            details,
        )
        raise InvalidAuth(error_details=details) from err
    except APIError as err:
        details = err.api_message or (err.args[0] if err.args else str(err))
        _LOGGER.warning(
            "Config flow validation: API error with BSM at %s. Details: %s",
            host_for_log,
            details,
        )
        raise CannotConnect("api_error", error_details=details) from err
    except Exception as err:
        if isinstance(err, (CannotConnect, InvalidAuth)):
            raise err
        _LOGGER.exception(
            "Unexpected error during config flow validation for %s", host_for_log
        )
        raise exceptions.HomeAssistantError("unknown_validation_error") from err
    finally:
        # The HA-managed session (validation_session) does not need to be closed here by us.
        # If BedrockServerManagerApi had a specific close/cleanup that wasn't session-related, it would go here.
        # If api_client has a .close() that is safe to call (e.g. idempotent or handles shared session), it's okay.
        if api_client and hasattr(api_client, "close"):
            # Assuming api_client.close() is safe for shared sessions or no-op if not needed.
            await api_client.close()  # bsm_api_client ClientBase.close() is safe
            _LOGGER.debug(
                "Temporary API client for validation (using HA session) was closed (if applicable)."
            )


# --- Config Flow Class ---
class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bedrock Server Manager."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._connection_data: Dict[str, Any] = {}
        self._discovered_servers: List[str] = []

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
            host_val = user_input[CONF_HOST]
            # port_val_input will be a float/int from NumberSelector, or None
            port_val_input = user_input.get(CONF_PORT)

            # Get a clean string for the port component (e.g., "11325" or "")
            cleaned_port_str_for_id = _clean_port_string_component(port_val_input)
            _LOGGER.info(
                "[CONFIG_FLOW_USER_DEBUG] For unique_id. Input port from form: '%s' (type: %s), Cleaned port string: '%s'",
                port_val_input,
                type(port_val_input).__name__,
                cleaned_port_str_for_id,
            )

            # Construct unique_id using the cleaned port string
            if cleaned_port_str_for_id:
                unique_manager_id = f"{host_val}:{cleaned_port_str_for_id}"
            else:
                unique_manager_id = host_val
            _LOGGER.info(
                "[CONFIG_FLOW_USER_DEBUG] Final unique_manager_id for async_set_unique_id: '%s'",
                unique_manager_id,
            )

            await self.async_set_unique_id(unique_manager_id)
            self._abort_if_unique_id_configured(updates=user_input)

            try:
                # validate_input ensures port_to_api is an int or None for the API call.
                # The user_input still contains the original port value (e.g. float) from the form.
                validation_result = await validate_input(self.hass, user_input)
                self._discovered_servers = validation_result["discovered_servers"]
                # Store the original user_input to be saved in config_entry.data
                self._connection_data = user_input.copy()

                _LOGGER.debug(
                    "Validation successful for BSM instance '%s', proceeding to server selection. Discovered servers: %s",
                    unique_manager_id,
                    self._discovered_servers,
                )
                return await self.async_step_select_servers()

            except CannotConnect as err:
                errors["base"] = err.error_key
                description_placeholders = {"error_details": err.error_details or ""}
                _LOGGER.warning(
                    "Config flow connection error for '%s': %s. Details: %s",
                    unique_manager_id,
                    err.error_key,
                    err.error_details,
                )
            except InvalidAuth as err:
                errors["base"] = err.error_key
                description_placeholders = {"error_details": err.error_details or ""}
                _LOGGER.warning(
                    "Config flow invalid auth error for '%s'. Details: %s",
                    unique_manager_id,
                    err.error_details,
                )
            except exceptions.HomeAssistantError as err_ha:
                # Catch any other HomeAssistantError that might not have been specifically handled
                errors["base"] = str(err_ha) if str(err_ha) else "unknown_config_error"
                _LOGGER.warning(
                    "Config flow HomeAssistantError for '%s': %s",
                    unique_manager_id,
                    err_ha,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
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
        )  # Not typically used in this step unless validation added

        if user_input is not None:
            selected_servers = user_input.get(CONF_SERVER_NAMES, [])

            # Construct title using cleaned port string from stored connection_data
            host_title_part = self._connection_data[CONF_HOST]
            # port_title_input is the original value from the form (e.g. float, int, or None)
            port_title_input = self._connection_data.get(CONF_PORT)

            cleaned_port_str_for_title = _clean_port_string_component(port_title_input)
            _LOGGER.info(
                "[CONFIG_FLOW_SERVERS_DEBUG] For title. Input port from connection_data: '%s' (type: %s), Cleaned port string: '%s'",
                port_title_input,
                type(port_title_input).__name__,
                cleaned_port_str_for_title,
            )

            if cleaned_port_str_for_title:
                title = f"BSM @ {host_title_part}:{cleaned_port_str_for_title}"
            else:
                title = f"BSM @ {host_title_part}"
            _LOGGER.info(
                "[CONFIG_FLOW_SERVERS_DEBUG] Final title for async_create_entry: '%s'",
                title,
            )

            _LOGGER.info(
                "Creating config entry with title '%s'. Host: %s, Explicit Port (from form): %s, Selected servers: %s. Full connection data (redacted): %s",
                title,
                self._connection_data[CONF_HOST],
                port_title_input if port_title_input is not None else "derived/omitted",
                selected_servers,
                async_redact_data(self._connection_data, [CONF_PASSWORD]),
            )

            # self._connection_data contains the original user input (host, port as float/int/None, user, pass, ssl flags)
            # This is what gets stored in config_entry.data
            return self.async_create_entry(
                title=title,  # Use the cleaned title
                data=self._connection_data.copy(),
                options={CONF_SERVER_NAMES: selected_servers},
            )

        # --- Display form for server selection ---
        description_placeholders: Dict[str, str] = {}
        connection_host = self._connection_data.get(CONF_HOST, "Unknown Host")
        connection_port_input = self._connection_data.get(CONF_PORT)  # Original input

        # For display messages, use the cleaned port string
        cleaned_display_port_str = _clean_port_string_component(connection_port_input)
        manager_display_name_for_message = f"{connection_host}{f':{cleaned_display_port_str}' if cleaned_display_port_str else ''}"

        if not self._discovered_servers:
            _LOGGER.warning(
                "Showing server selection step, but no servers were discovered for manager at %s.",
                manager_display_name_for_message,
            )
            description_placeholders["message"] = (
                f"No Minecraft servers were found on the Bedrock Server Manager instance at '{manager_display_name_for_message}'. "
                "You can still add the manager now and select servers later by reconfiguring the integration options, "
                "or verify server configurations on your BSM host."
            )
        else:
            description_placeholders["message"] = (
                f"Select the initial Minecraft servers you want to monitor and control from the BSM instance at '{manager_display_name_for_message}'. "
                "You can change this selection later."
            )

        server_options = sorted(self._discovered_servers)
        select_schema = vol.Schema(
            {
                vol.Optional(CONF_SERVER_NAMES, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=server_options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="select_servers",
            data_schema=select_schema,
            errors=errors,  # Usually empty for this step
            description_placeholders=description_placeholders,
        )
