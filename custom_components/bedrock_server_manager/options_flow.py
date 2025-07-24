# custom_components/bedrock_server_manager/options_flow.py
"""Options flow for Bedrock Server Manager integration."""

import logging
from typing import Any, Dict, Optional, List, cast

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    # CONF_SCAN_INTERVAL, # This is used as a key, defined below
)
from homeassistant.core import callback  # Required for async_get_options_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector
from homeassistant.helpers import device_registry as dr

# --- IMPORT FROM LOCAL CONSTANTS ---
from .const import (
    DOMAIN,
    CONF_SERVER_NAMES,
    CONF_MANAGER_SCAN_INTERVAL,
    CONF_SERVER_SCAN_INTERVAL,
    CONF_VERIFY_SSL,  # Make sure this is in your const.py
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEFAULT_MANAGER_SCAN_INTERVAL_SECONDS,
    CONF_BASE_URL,
)

from bsm_api_client import (
    BedrockServerManagerApi,
    APIError,
    AuthError,
    CannotConnectError,
)

_LOGGER = logging.getLogger(__name__)

# --- Schemas ---
STEP_CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)
STEP_SERVER_POLLING_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SERVER_SCAN_INTERVAL): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=10,
                max=3600,
                step=1,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="seconds",
            )
        ),
    }
)
STEP_MANAGER_POLLING_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_MANAGER_SCAN_INTERVAL): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=60,
                max=86400,
                step=10,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="seconds",
            )
        ),
    }
)


class BSMOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Bedrock Server Manager options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize BSM options flow."""
        self.config_entry = config_entry
        self._discovered_servers: Optional[List[str]] = None
        self._api_client_instance: Optional[BedrockServerManagerApi] = None

    async def _get_api_client(
        self, data_override: Optional[Dict[str, Any]] = None
    ) -> BedrockServerManagerApi:
        """Get an API client instance, potentially with overridden data for validation."""
        if self._api_client_instance and not data_override:
            # Consider if re-using is safe or always create new with overrides
            pass

        current_data = self.config_entry.data
        effective_data = {**current_data, **(data_override or {})}

        url = effective_data[CONF_BASE_URL]
        username = effective_data[CONF_USERNAME]  # Assumed to always exist
        password = effective_data[CONF_PASSWORD]  # Assumed to always exist
        verify_ssl = effective_data.get(CONF_VERIFY_SSL, True)  # Use verify_ssl

        # Always create a new session for short-lived validation/option tasks
        session = async_get_clientsession(self.hass, verify_ssl=verify_ssl)

        api_client = BedrockServerManagerApi(
            base_url=url,
            username=username,
            password=password,
            session=session,
            verify_ssl=verify_ssl,  # Pass to API client if it supports/needs it
        )
        if not data_override:  # Store if it's using the main config for multiple steps
            self._api_client_instance = api_client
        return api_client

    async def _close_api_client_if_created(self):
        """Close the API client if it was created by this flow instance."""
        if self._api_client_instance:
            await self._api_client_instance.close()
            self._api_client_instance = None

    def _get_manager_display_name(self) -> str:
        """Helper to get a display string for the manager (host or host:port)."""
        return self.config_entry.data.get(CONF_BASE_URL, "Unknown BSM URL")

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Manage the options menu."""
        manager_display_name = self._get_manager_display_name()
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "update_credentials",
                "select_servers",
                "update_server_interval",
                "update_manager_interval",
            ],
            description_placeholders={"base_url": manager_display_name},
        )

    async def async_step_update_credentials(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Handle updating credentials."""
        errors: Dict[str, str] = {}
        description_placeholders: Optional[Dict[str, str]] = None
        manager_display_name = self._get_manager_display_name()

        if user_input is not None:
            # Create a temporary data dict for validation, including existing host/port/ssl/verify_ssl
            validation_data = {
                CONF_BASE_URL: self.config_entry.data[CONF_BASE_URL],
                CONF_VERIFY_SSL: self.config_entry.data.get(
                    CONF_VERIFY_SSL, True
                ),  # Add verify_ssl
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            temp_api_client = None
            try:
                temp_api_client = await self._get_api_client(
                    data_override=validation_data
                )
                await temp_api_client.authenticate()
                _LOGGER.info(
                    "New credentials validated successfully for BSM: %s",
                    self.config_entry.title,
                )
                # Persist the new credentials along with existing non-credential data
                new_data = {**self.config_entry.data, **user_input}
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                return self.async_abort(reason="credentials_updated")
            except AuthError as err:
                _LOGGER.warning(
                    "Failed to authenticate with new credentials for BSM %s: %s",
                    self.config_entry.title,
                    err.api_message or err,
                )
                errors["base"] = "invalid_auth"
                description_placeholders = {
                    "error_details": err.api_message or str(err)
                }
            except CannotConnectError as err:
                _LOGGER.error(
                    "Connection error validating new credentials for BSM %s: %s",
                    self.config_entry.title,
                    err.args[0] if err.args else err,
                )
                errors["base"] = "cannot_connect"
                description_placeholders = {
                    "error_details": err.args[0] if err.args else str(err)
                }
            except APIError as err:
                _LOGGER.error(
                    "API error validating new credentials for BSM %s: %s",
                    self.config_entry.title,
                    err.api_message or err,
                )
                errors["base"] = "api_error"
                description_placeholders = {
                    "error_details": err.api_message or str(err)
                }
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception(
                    "Unexpected error validating new credentials for BSM %s",
                    self.config_entry.title,
                )
                errors["base"] = "unknown_error"
                description_placeholders = {"error_details": str(err)}
            finally:
                if temp_api_client:
                    await temp_api_client.close()

        current_data = self.config_entry.data
        schema_with_suggestions = self.add_suggested_values_to_schema(
            STEP_CREDENTIALS_SCHEMA,
            suggested_values={
                CONF_USERNAME: current_data.get(CONF_USERNAME, ""),
            },
        )
        return self.async_show_form(
            step_id="update_credentials",
            data_schema=schema_with_suggestions,
            errors=errors,
            description_placeholders=description_placeholders
            or {"base_url": manager_display_name},
        )

    async def async_step_select_servers(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Handle server selection."""
        errors: Dict[str, str] = {}
        description_placeholders: Optional[Dict[str, str]] = None
        manager_display_name = self._get_manager_display_name()

        # Fetch server list if not already fetched in this flow instance
        if self._discovered_servers is None:
            api_client_for_list = None
            try:
                # _get_api_client now handles optional port correctly
                api_client_for_list = await self._get_api_client()

                self._discovered_servers = (
                    await api_client_for_list.async_get_server_names()
                )  # Returns List[str]
                _LOGGER.debug(
                    "Fetched server names for options flow of BSM %s: %s",
                    self.config_entry.title,
                    self._discovered_servers,
                )
                if not isinstance(self._discovered_servers, list):
                    _LOGGER.warning(
                        "Discovered servers from API is not a list: %s. Resetting to empty.",
                        type(self._discovered_servers),
                    )
                    self._discovered_servers = []
                else:  # Ensure all items are strings for the selector
                    self._discovered_servers = sorted(
                        [str(s) for s in self._discovered_servers if isinstance(s, str)]
                    )

            except AuthError as err:
                _LOGGER.error(
                    "Auth error fetching server list for BSM %s options: %s",
                    self.config_entry.title,
                    err.api_message or err,
                )
                errors["base"] = "invalid_auth"
                description_placeholders = {
                    "fetch_error": f"Authentication failed: {err.api_message or str(err)}"
                }
                self._discovered_servers = []
            except CannotConnectError as err:
                _LOGGER.error(
                    "Connection error fetching server list for BSM %s options: %s",
                    self.config_entry.title,
                    err.args[0] if err.args else err,
                )
                errors["base"] = "cannot_connect"
                description_placeholders = {
                    "fetch_error": f"Connection failed: {err.args[0] if err.args else str(err)}"
                }
                self._discovered_servers = []
            except APIError as err:
                _LOGGER.error(
                    "API error fetching server list for BSM %s options: %s",
                    self.config_entry.title,
                    err.api_message or err,
                )
                errors["base"] = (
                    "fetch_servers_failed"  # Custom error key for strings.json
                )
                description_placeholders = {
                    "fetch_error": f"API error: {err.api_message or str(err)}"
                }
                self._discovered_servers = []
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception(
                    "Unexpected error fetching server list for BSM %s options",
                    self.config_entry.title,
                )
                errors["base"] = "unknown_error"
                description_placeholders = {
                    "fetch_error": f"An unexpected error occurred: {str(err)}"
                }
                self._discovered_servers = []
            finally:
                if api_client_for_list:  # Close client if created just for this step
                    await api_client_for_list.close()

        if (
            user_input is not None and not errors
        ):  # Process selection if form submitted and no fetch errors
            newly_selected_servers = user_input.get(CONF_SERVER_NAMES, [])
            if not isinstance(
                newly_selected_servers, list
            ):  # Should be a list from selector
                newly_selected_servers = []

            current_options = self.config_entry.options
            old_selected_servers_raw = current_options.get(CONF_SERVER_NAMES, [])
            old_selected_servers = set(
                str(s) for s in old_selected_servers_raw if isinstance(s, str)
            )

            newly_selected_servers_set = set(
                str(s) for s in newly_selected_servers if isinstance(s, str)
            )

            _LOGGER.debug(
                "Updating server selection for BSM %s. Old: %s, New: %s",
                self.config_entry.title,
                old_selected_servers,
                newly_selected_servers_set,
            )

            # Device disassociation logic
            servers_to_disassociate = old_selected_servers - newly_selected_servers_set
            if servers_to_disassociate:
                dev_reg = dr.async_get(self.hass)
                manager_url = self.config_entry.data[CONF_BASE_URL]

                for server_name_to_remove in servers_to_disassociate:
                    server_device_identifier_value = (
                        f"{server_name_to_remove}_{manager_url}"
                    )
                    device_id_tuple = (DOMAIN, server_device_identifier_value)

                    device_entry = dev_reg.async_get_device(
                        identifiers={device_id_tuple}
                    )
                    if (
                        device_entry
                        and self.config_entry.entry_id in device_entry.config_entries
                    ):
                        _LOGGER.info(
                            "Disassociating device for deselected server '%s' (Device HA ID: %s) from config entry %s",
                            server_name_to_remove,
                            device_entry.id,
                            self.config_entry.entry_id,
                        )
                        dev_reg.async_update_device(
                            device_entry.id,
                            remove_config_entry_id=self.config_entry.entry_id,
                        )
                    elif device_entry:
                        _LOGGER.debug(
                            "Device for server '%s' found but not linked to this config entry.",
                            server_name_to_remove,
                        )
                    else:
                        _LOGGER.warning(
                            "Could not find device for deselected server '%s' (Identifier: %s) to disassociate.",
                            server_name_to_remove,
                            device_id_tuple,
                        )

            # Create new options entry
            new_options = {
                **current_options,
                CONF_SERVER_NAMES: list(newly_selected_servers_set),
            }  # Store as list
            return self.async_create_entry(
                title="", data=new_options
            )  # title="" means use existing, data= updates options

        # Prepare form for display
        options_for_selector = (
            self._discovered_servers if self._discovered_servers else []
        )

        current_selection_from_options = self.config_entry.options.get(
            CONF_SERVER_NAMES, []
        )
        valid_current_selection = [
            s for s in current_selection_from_options if s in options_for_selector
        ]

        select_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SERVER_NAMES, default=valid_current_selection
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options_for_selector,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }
        )

        if not description_placeholders:  # If not set by error handling above
            description_placeholders = {}
            if not options_for_selector and not errors:
                description_placeholders["fetch_error"] = (
                    f"No Minecraft servers were found on this BSM manager ({manager_display_name}). "
                    "Verify configurations on your BSM host or add servers there first."
                )
        description_placeholders["base_url"] = manager_display_name

        return self.async_show_form(
            step_id="select_servers",
            data_schema=select_schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_update_server_interval(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Handle server polling interval update."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            scan_interval_val = user_input.get(CONF_SERVER_SCAN_INTERVAL)
            interval: Optional[int] = None  # Define interval before try block

            if scan_interval_val is not None:
                try:
                    interval = int(scan_interval_val)
                    if not (10 <= interval <= 3600):
                        errors[CONF_SERVER_SCAN_INTERVAL] = (
                            "invalid_server_scan_interval_range"
                        )
                except ValueError:
                    errors[CONF_SERVER_SCAN_INTERVAL] = (
                        "invalid_server_scan_interval_type"
                    )
            else:
                errors[CONF_SERVER_SCAN_INTERVAL] = "value_required"

            if not errors and interval is not None:  # Check interval is assigned
                new_options = {
                    **self.config_entry.options,
                    CONF_SERVER_SCAN_INTERVAL: interval,
                }
                _LOGGER.info(
                    "Updating server scan interval to %s seconds for BSM %s",
                    interval,
                    self.config_entry.title,
                )
                return self.async_create_entry(title="", data=new_options)

        current_interval = self.config_entry.options.get(
            CONF_SERVER_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS
        )
        schema_with_suggestions = self.add_suggested_values_to_schema(
            STEP_SERVER_POLLING_SCHEMA,
            suggested_values={CONF_SERVER_SCAN_INTERVAL: current_interval},
        )
        return self.async_show_form(
            step_id="update_server_interval",
            data_schema=schema_with_suggestions,
            errors=errors,
        )

    async def async_step_update_manager_interval(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Handle manager polling interval update."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            manager_interval_val = user_input.get(CONF_MANAGER_SCAN_INTERVAL)
            interval: Optional[int] = None  # Define interval before try block

            if manager_interval_val is not None:
                try:
                    interval = int(manager_interval_val)
                    if not (60 <= interval <= 86400):
                        errors[CONF_MANAGER_SCAN_INTERVAL] = (
                            "invalid_manager_scan_interval_range"
                        )
                except ValueError:
                    errors[CONF_MANAGER_SCAN_INTERVAL] = (
                        "invalid_manager_scan_interval_type"
                    )
            else:
                errors[CONF_MANAGER_SCAN_INTERVAL] = "value_required"

            if not errors and interval is not None:  # Check interval is assigned
                new_options = {
                    **self.config_entry.options,
                    CONF_MANAGER_SCAN_INTERVAL: interval,
                }
                _LOGGER.info(
                    "Updating manager scan interval to %s seconds for BSM %s",
                    interval,
                    self.config_entry.title,
                )
                return self.async_create_entry(title="", data=new_options)

        current_interval = self.config_entry.options.get(
            CONF_MANAGER_SCAN_INTERVAL, DEFAULT_MANAGER_SCAN_INTERVAL_SECONDS
        )
        schema_with_suggestions = self.add_suggested_values_to_schema(
            STEP_MANAGER_POLLING_SCHEMA,
            suggested_values={CONF_MANAGER_SCAN_INTERVAL: current_interval},
        )
        return self.async_show_form(
            step_id="update_manager_interval",
            data_schema=schema_with_suggestions,
            errors=errors,
        )

    async def async_will_remove_config_entry(self) -> None:
        """Handle removal of config entry."""
        _LOGGER.debug(
            "Options flow: Config entry %s is being removed.",
            self.config_entry.entry_id,
        )
        await self._close_api_client_if_created()
