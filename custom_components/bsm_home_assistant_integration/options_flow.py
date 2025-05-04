"""Options flow for Bedrock Server Manager integration."""

import logging
from typing import Any, Dict, Optional, List

import voluptuous as vol

from homeassistant import config_entries, exceptions

# Import CONF constants from HA
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import callback  # Ensure callback is imported
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

# Import local constants
from .const import (
    DOMAIN,
    CONF_SERVER_NAMES,  # Import the constant for the server list
    DEFAULT_SCAN_INTERVAL_SECONDS,
)

# Import API definitions and exceptions
from .api import (
    BedrockServerManagerApi,  # <-- Make sure this matches api.py class name EXACTLY
    APIError,
    AuthError,  # <-- Make sure this is imported
    CannotConnectError,  # <-- Make sure this is imported
)

_LOGGER = logging.getLogger(__name__)

# --- Schemas ---
# Schema for credential update step
STEP_CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)

# Schema for polling interval step
STEP_POLLING_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SCAN_INTERVAL): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=5,
                max=3600,
                step=1,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="seconds",
            )
        ),
    }
)


class BSMOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for Bedrock Server Manager."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        # Base class handles self.config_entry storage
        self._discovered_servers: Optional[List[str]] = None

    async def _get_api_client(
        self, data_override: Optional[Dict[str, Any]] = None
    ) -> BedrockServerManagerApi: 
        """Get an API client instance using stored or overridden data."""
        data_source = data_override if data_override else self.config_entry.data
        host = data_source[CONF_HOST]
        port = int(data_source[CONF_PORT])
        username = data_source[CONF_USERNAME]
        password = data_source[CONF_PASSWORD]
        session = async_get_clientsession(self.hass)
        return BedrockServerManagerApi(host, port, username, password, session)

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Manage the options flow entry point -> Show menu."""
        manager_host = self.config_entry.data.get(CONF_HOST, "Unknown Host")
        return self.async_show_menu(
            step_id="init",
            menu_options=["update_credentials", "select_servers", "update_interval"],
            description_placeholders={"host": manager_host},
        )

    async def async_step_update_credentials(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Handle the step for updating API credentials."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            validation_data = self.config_entry.data.copy()
            validation_data.update(user_input)
            try:
                api_client = await self._get_api_client(data_override=validation_data)
                await api_client.authenticate()
                _LOGGER.info(
                    "Credentials validation successful for %s. Updating entry.",
                    self.config_entry.entry_id,
                )
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data={**self.config_entry.data, **user_input}
                )
                return self.async_abort(reason="credentials_updated")
            except AuthError:
                _LOGGER.warning(
                    "Failed to authenticate with new credentials for %s.",
                    self.config_entry.entry_id,
                )
                errors["base"] = "invalid_auth"
            except CannotConnectError as err:
                _LOGGER.error("Connection error validating new credentials: %s", err)
                errors["base"] = "cannot_connect"
            except APIError as err:
                _LOGGER.error("API error validating new credentials: %s", err)
                errors["base"] = "api_error"
            except Exception as err:
                _LOGGER.exception(
                    "Unexpected error validating new credentials: %s", err
                )
                errors["base"] = "unknown_error"

        current_data = self.config_entry.data
        schema = self.add_suggested_values_to_schema(
            STEP_CREDENTIALS_SCHEMA,
            suggested_values={CONF_USERNAME: current_data.get(CONF_USERNAME)},
        )
        return self.async_show_form(
            step_id="update_credentials",
            data_schema=schema,
            errors=errors,
            description_placeholders={"host": current_data.get(CONF_HOST)},
        )

    async def async_step_select_servers(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Handle the step for selecting which servers to monitor."""
        errors: Dict[str, str] = {}
        if self._discovered_servers is None:
            try:
                api_client = await self._get_api_client()
                await api_client.authenticate()
                self._discovered_servers = await api_client.async_get_server_list()
            except (APIError, CannotConnectError, AuthError) as err:
                _LOGGER.error("Failed to fetch server list for options flow: %s", err)
                errors["base"] = "fetch_servers_failed"
                self._discovered_servers = []
            except Exception as err:
                _LOGGER.exception(
                    "Unexpected error fetching server list for options flow: %s", err
                )
                errors["base"] = "unknown_error"
                self._discovered_servers = []

        if user_input is not None and not errors:
            selected_servers = user_input.get(CONF_SERVER_NAMES, [])
            _LOGGER.debug(
                "Updating server selection for entry %s to: %s",
                self.config_entry.entry_id,
                selected_servers,
            )
            new_options = {
                **self.config_entry.options,
                CONF_SERVER_NAMES: selected_servers,
            }
            return self.async_create_entry(title="", data=new_options)

        current_selection = self.config_entry.options.get(CONF_SERVER_NAMES, [])
        select_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SERVER_NAMES, default=current_selection
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self._discovered_servers or [],
                        multiple=True,
                        sort=True,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="select_servers", data_schema=select_schema, errors=errors
        )

    async def async_step_update_interval(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Handle the step for updating the polling interval."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            scan_interval = user_input.get(CONF_SCAN_INTERVAL)
            if scan_interval is not None and scan_interval < 5:
                errors[CONF_SCAN_INTERVAL] = "invalid_scan_interval"
            if not errors:
                _LOGGER.debug(
                    "Updating scan interval for entry %s to: %s seconds",
                    self.config_entry.entry_id,
                    scan_interval,
                )
                new_options = {
                    **self.config_entry.options,
                    CONF_SCAN_INTERVAL: scan_interval,
                }
                # --- CORRECTED: Use async_create_entry to save options ---
                return self.async_create_entry(title="", data=new_options)
                # --- END CORRECTION ---

        current_scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS
        )
        schema = self.add_suggested_values_to_schema(
            STEP_POLLING_SCHEMA,
            suggested_values={CONF_SCAN_INTERVAL: current_scan_interval},
        )
        return self.async_show_form(
            step_id="update_interval", data_schema=schema, errors=errors
        )
