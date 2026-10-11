# custom_components/bedrock_server_manager/config_flow.py
"""Config flow for Bedrock Server Manager integration."""

import logging
from typing import Any, Dict, List, Optional

import probatio as vol
from bsm_api_client import (
    APIError,
    AuthError,
    BedrockServerManagerApi,
    CannotConnectError,
)
from homeassistant import config_entries, exceptions
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

# --- IMPORT FROM CONSTANTS ---
from .const import CONF_BASE_URL, CONF_SERVER_NAMES, CONF_VERIFY_SSL, DOMAIN

# Import the Options Flow Handler
from .options_flow import STEP_CREDENTIALS_SCHEMA, BSMOptionsFlowHandler

_LOGGER = logging.getLogger(__name__)

# --- Schema Definition ---
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BASE_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
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


# --- Validation Function ---
async def validate_input(hass: HomeAssistant, data: dict) -> Dict[str, Any]:
    """Validate the user input allows us to connect and authenticate."""
    url_for_log = data[CONF_BASE_URL]
    user_requests_verify_ssl = data.get(CONF_VERIFY_SSL, True)

    # Use HA's shared session, respecting user's verify_ssl choice for this validation session
    session = async_get_clientsession(hass, verify_ssl=user_requests_verify_ssl)
    api_client = None
    try:
        api_client = BedrockServerManagerApi(
            base_url=data[CONF_BASE_URL],
            session=session,
            username=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
            verify_ssl=user_requests_verify_ssl,
        )
        _LOGGER.debug(
            "Validating input: Attempting authentication to BSM at %s (Verify SSL: %s)",
            url_for_log,
            user_requests_verify_ssl,
        )

        await api_client.authenticate()
        _LOGGER.debug("Authentication successful for %s.", url_for_log)

        _LOGGER.debug("Fetching server names list from %s...", url_for_log)
        discovered_server_names: List[str] = (
            await api_client.servers.async_get_server_names()
        )
        _LOGGER.debug(
            "Successfully fetched server names from %s: %s",
            url_for_log,
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
            url_for_log,
            key,
            details,
        )
        raise CannotConnect(error_key=key, error_details=details) from err
    except AuthError as err:
        details = err.api_message or (err.args[0] if err.args else str(err))
        _LOGGER.warning(
            "Config flow validation: Invalid credentials for BSM user '%s' at %s. Details: %s",
            data[CONF_USERNAME],
            url_for_log,
            details,
        )
        raise InvalidAuth(error_details=details) from err
    except APIError as err:
        details = err.api_message or (err.args[0] if err.args else str(err))
        _LOGGER.warning(
            "Config flow validation: API error with BSM at %s. Details: %s",
            url_for_log,
            details,
        )
        raise CannotConnect("api_error", error_details=details) from err
    except Exception as err:
        if isinstance(err, (CannotConnect, InvalidAuth)):
            raise err
        _LOGGER.exception(
            "Unexpected error during config flow validation for %s", url_for_log
        )
        raise exceptions.HomeAssistantError("unknown_validation_error") from err
    finally:
        # Close the SDK-owned transport; the borrowed HA session remains open.
        if api_client is not None:
            await api_client.close()


# --- Config Flow Class ---
class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow for Bedrock Server Manager."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._connection_data: Dict[str, Any] = {}
        self._discovered_servers: List[str] = []

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> BSMOptionsFlowHandler:
        """Get the options flow for this handler."""
        return BSMOptionsFlowHandler()

    async def async_step_reauth(
        self, entry_data: dict
    ) -> config_entries.ConfigFlowResult:
        """Recover expired credentials for the existing manager entry."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Validate replacement credentials before updating and reloading."""
        entry = self._get_reauth_entry()
        errors = {}
        placeholders = {"error_details": ""}
        if user_input is not None:
            credentials = {
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            try:
                await validate_input(self.hass, {**entry.data, **credentials})
            except (CannotConnect, InvalidAuth) as err:
                errors["base"] = err.error_key
                placeholders["error_details"] = err.error_details or ""
            except exceptions.HomeAssistantError:
                errors["base"] = "unknown_error"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates=credentials
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_CREDENTIALS_SCHEMA,
                {CONF_USERNAME: entry.data.get(CONF_USERNAME, "")},
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}
        description_placeholders: Optional[Dict[str, str]] = None

        if user_input is not None:
            unique_manager_id = user_input[CONF_BASE_URL]
            _LOGGER.info(
                "[CONFIG_FLOW_USER_DEBUG] Final unique_manager_id for async_set_unique_id: '%s'",
                unique_manager_id,
            )

            await self.async_set_unique_id(unique_manager_id)
            self._abort_if_unique_id_configured()

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
    ) -> config_entries.ConfigFlowResult:
        """Handle the server selection step."""
        errors: Dict[str, str] = (
            {}
        )  # Not typically used in this step unless validation added

        if user_input is not None:
            selected_servers = user_input.get(CONF_SERVER_NAMES, [])

            # Construct title using cleaned port string from stored connection_data
            url_title_part = self._connection_data[CONF_BASE_URL]

            title = f"BSM @ {url_title_part}"
            _LOGGER.info(
                "[CONFIG_FLOW_SERVERS_DEBUG] Final title for async_create_entry: '%s'",
                title,
            )

            _LOGGER.info(
                "Creating config entry with title '%s'. URL: %s, Selected servers: %s. Full connection data (redacted): %s",
                title,
                self._connection_data[CONF_BASE_URL],
                selected_servers,
                async_redact_data(
                    self._connection_data, [CONF_PASSWORD, CONF_USERNAME]
                ),
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
        manager_display_name_for_message = self._connection_data.get(
            CONF_BASE_URL, "Unknown BSM"
        )

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
