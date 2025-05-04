"""Options flow for Minecraft Bedrock Server Manager integration."""

import logging
from typing import Any, Dict, Optional, List

import voluptuous as vol

from homeassistant import config_entries, exceptions
# Import CONF constants from HA
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import callback # Ensure callback is imported
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

# Import local constants
from .const import (
    DOMAIN,
    CONF_SERVER_NAMES, # Import the constant for the server list
    DEFAULT_SCAN_INTERVAL_SECONDS,
)
# Import API definitions and exceptions
from .api import (
    MinecraftBedrockApi,
    APIError,
    AuthError,
    CannotConnectError,
    # ServerNotFoundError, # Not directly needed in options flow itself typically
)

_LOGGER = logging.getLogger(__name__)

# --- Schemas ---
# Schema for credential update step
STEP_CREDENTIALS_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): str, # Pre-filled from current data
    vol.Required(CONF_PASSWORD): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    ),
})

# Schema for polling interval step (copied from previous version)
STEP_POLLING_SCHEMA = vol.Schema({
    vol.Optional(CONF_SCAN_INTERVAL): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=5,
            max=3600,
            step=1,
            mode=selector.NumberSelectorMode.BOX,
            unit_of_measurement="seconds",
        )
    ),
})


class MinecraftBdsManagerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for Minecraft Bedrock Server Manager."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        # Store discovered servers list if fetched during flow
        self._discovered_servers: Optional[List[str]] = None

    async def _get_api_client(self, data_override: Optional[Dict[str, Any]] = None) -> MinecraftBedrockApi:
        """Get an API client instance using stored or overridden data."""
        # Use override data if provided (for testing new credentials)
        # Otherwise use data stored in the config entry
        data_source = data_override if data_override else self.config_entry.data

        host = data_source[CONF_HOST]
        port = int(data_source[CONF_PORT]) # Ensure int
        username = data_source[CONF_USERNAME]
        password = data_source[CONF_PASSWORD]
        session = async_get_clientsession(self.hass)

        return MinecraftBedrockApi(host, port, username, password, session)

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Manage the options flow entry point -> Show menu."""
        # Show menu doesn't typically use user_input
        return self.async_show_menu(
            step_id="init", # Important: Needs a step_id for the menu itself
            menu_options=["update_credentials", "select_servers", "update_interval"],
            # Add description_placeholders if needed
        )

    async def async_step_update_credentials(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Handle the step for updating API credentials."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Create temporary data dict with NEW credentials for validation
            validation_data = self.config_entry.data.copy()
            validation_data.update(user_input) # Overwrite user/pass with new values

            try:
                # Get API client with the NEW credentials
                api_client = await self._get_api_client(data_override=validation_data)
                # Attempt authentication with new credentials
                await api_client.authenticate()

                # If auth succeeds, update the stored config entry data
                _LOGGER.info("Credentials validation successful for %s. Updating entry.", self.config_entry.entry_id)
                # Update only the changed data fields
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **self.config_entry.data, # Keep existing data (host, port)
                        CONF_USERNAME: user_input[CONF_USERNAME], # Update user
                        CONF_PASSWORD: user_input[CONF_PASSWORD], # Update password
                    }
                )
                # Abort the flow, indicating success. The update listener in __init__ should trigger reload.
                return self.async_abort(reason="credentials_updated")

            except (AuthError, InvalidAuth): # Catch specific auth errors
                _LOGGER.warning("Failed to authenticate with new credentials for %s.", self.config_entry.entry_id)
                errors["base"] = "invalid_auth" # Use translation key
            except (APIError, CannotConnectError) as err: # Catch other API/connection issues
                _LOGGER.error("API/Connection error validating new credentials: %s", err)
                errors["base"] = "cannot_connect" # Or a more generic API error key
            except Exception as err: # Catch unexpected errors
                _LOGGER.exception("Unexpected error validating new credentials: %s", err)
                errors["base"] = "unknown_error"

        # Show form for the first time or if errors occurred
        # Pre-fill username, leave password blank
        current_data = self.config_entry.data
        schema = self.add_suggested_values_to_schema(
            STEP_CREDENTIALS_SCHEMA,
            suggested_values={CONF_USERNAME: current_data.get(CONF_USERNAME)}, # Only suggest username
        )

        return self.async_show_form(
            step_id="update_credentials",
            data_schema=schema,
            errors=errors,
            description_placeholders={"host": current_data.get(CONF_HOST)}, # Example placeholder
        )


    async def async_step_select_servers(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Handle the step for selecting which servers to monitor."""
        errors: Dict[str, str] = {}

        # Fetch the latest list of available servers first (if not already fetched)
        if self._discovered_servers is None:
            try:
                api_client = await self._get_api_client() # Use current credentials
                await api_client.authenticate() # Ensure token is valid
                self._discovered_servers = await api_client.async_get_server_list()
            except (APIError, CannotConnectError, AuthError) as err:
                 _LOGGER.error("Failed to fetch server list for options flow: %s", err)
                 # Abort this step if we cannot get the list
                 # TODO: Add specific translation key for this abort reason
                 return self.async_abort(reason="fetch_servers_failed")
            except Exception as err:
                _LOGGER.exception("Unexpected error fetching server list for options flow: %s", err)
                return self.async_abort(reason="unknown_error")


        if user_input is not None:
            # User submitted the form, update the options
            selected_servers = user_input.get(CONF_SERVER_NAMES, [])
            _LOGGER.debug(
                "Updating server selection for entry %s to: %s",
                self.config_entry.entry_id, selected_servers
            )
            # Create entry updates options. Title="" ensures it updates current entry.
            # Pass current options merged with new selection
            new_options = {**self.config_entry.options, CONF_SERVER_NAMES: selected_servers}
            return self.async_create_entry(title="", data=new_options)


        # Show the form
        # Get the currently selected servers from options
        current_selection = self.config_entry.options.get(CONF_SERVER_NAMES, [])

        # Define the multi-select schema
        select_schema = vol.Schema({
            vol.Optional(CONF_SERVER_NAMES, default=current_selection): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=self._discovered_servers or [], # Use fetched list or empty if fetch failed
                    multiple=True,
                    mode=selector.SelectSelectorMode.LISTBOX,
                    sort=True, # Sort the list for better UI
                )
            ),
        })

        return self.async_show_form(
            step_id="select_servers",
            data_schema=select_schema,
            errors=errors, # Errors typically not set here unless future validation added
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
                     self.config_entry.entry_id, scan_interval
                 )
                 # Merge with existing options and save
                 new_options = {**self.config_entry.options, CONF_SCAN_INTERVAL: scan_interval}
                 return self.async_create_entry(title="", data=new_options)


        # Show the form
        # Get current value to pre-fill
        current_scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS
        )
        # Use schema defined earlier, setting default
        schema = self.add_suggested_values_to_schema(
            STEP_POLLING_SCHEMA,
            suggested_values={CONF_SCAN_INTERVAL: current_scan_interval}
        )

        return self.async_show_form(
            step_id="update_interval",
            data_schema=schema,
            errors=errors,
        )
