# custom_components/bedrock_server_manager/options_flow.py
"""Options flow for Bedrock Server Manager integration."""

import logging
from typing import Any, Dict, Optional, List

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector
from homeassistant.helpers import device_registry as dr

# --- IMPORT FROM LOCAL CONSTANTS ---
from .const import (
    DOMAIN,
    CONF_SERVER_NAMES,
    CONF_MANAGER_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEFAULT_MANAGER_SCAN_INTERVAL_SECONDS,
)


from pybedrock_server_manager import (
    BedrockServerManagerApi,
    APIError,
    AuthError,
    CannotConnectError,
)



_LOGGER = logging.getLogger(__name__)

# --- Schemas (Unchanged) ---
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
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._discovered_servers: Optional[List[str]] = None

    async def _get_api_client(
        self, data_override: Optional[Dict[str, Any]] = None
    ) -> BedrockServerManagerApi:
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
        manager_host = self.config_entry.data.get(CONF_HOST, "Unknown Host")
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "update_credentials",
                "select_servers",
                "update_server_interval",
                "update_manager_interval",
            ],
            description_placeholders={"host": manager_host},
        )

    async def async_step_update_credentials(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        errors: Dict[str, str] = {}
        if user_input is not None:
            validation_data = self.config_entry.data.copy()
            validation_data.update(user_input)
            try:
                api_client = await self._get_api_client(data_override=validation_data)
                await api_client.authenticate()  # Method name OK
                _LOGGER.info(
                    "New credentials validated successfully for %s.",
                    self.config_entry.title,
                )
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data={**self.config_entry.data, **user_input}
                )
                return self.async_abort(reason="credentials_updated")
            except AuthError:
                _LOGGER.warning(
                    "Failed to authenticate with new credentials for %s.",
                    self.config_entry.title,
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
        errors: Dict[str, str] = {}
        current_options = self.config_entry.options
        old_selected_servers = set(current_options.get(CONF_SERVER_NAMES, []))

        if self._discovered_servers is None:
            try:
                api_client = await self._get_api_client()
                await api_client.authenticate()  # Method name OK
                # --- UPDATED METHOD CALL ---
                self._discovered_servers = await api_client.async_get_servers()
                # --- END UPDATED METHOD CALL ---
                _LOGGER.debug(
                    "Fetched server list for options flow: %s", self._discovered_servers
                )
            except AuthError as err:
                _LOGGER.error(
                    "Authentication error fetching server list for options flow: %s",
                    err,
                )
                errors["base"] = "invalid_auth"
                self._discovered_servers = []
            except CannotConnectError as err:
                _LOGGER.error(
                    "Connection error fetching server list for options flow: %s", err
                )
                errors["base"] = "cannot_connect"
                self._discovered_servers = []
            except APIError as err:
                _LOGGER.error(
                    "API error fetching server list for options flow: %s", err
                )
                errors["base"] = "fetch_servers_failed"
                self._discovered_servers = []
            except Exception as err:
                _LOGGER.exception(
                    "Unexpected error fetching server list for options flow: %s", err
                )
                errors["base"] = "unknown_error"
                self._discovered_servers = []

        if user_input is not None and not errors:
            newly_selected_servers_list = user_input.get(CONF_SERVER_NAMES, [])
            newly_selected_servers_set = set(newly_selected_servers_list)
            _LOGGER.debug(
                "Updating server selection. Old: %s, New: %s",
                old_selected_servers,
                newly_selected_servers_set,
            )

            servers_to_disassociate = old_selected_servers - newly_selected_servers_set
            if servers_to_disassociate:
                device_registry = dr.async_get(self.hass)
                for server_name_to_remove in servers_to_disassociate:
                    device_identifier = (DOMAIN, server_name_to_remove)
                    device_entry = device_registry.async_get_device(
                        identifiers={device_identifier}
                    )
                    if device_entry:
                        _LOGGER.info(
                            "Disassociating device for deselected server '%s' (ID: %s) from entry %s",
                            server_name_to_remove,
                            device_entry.id,
                            self.config_entry.entry_id,
                        )
                        device_registry.async_update_device(
                            device_entry.id,
                            remove_config_entry_id=self.config_entry.entry_id,
                        )
                    else:
                        _LOGGER.warning(
                            "Could not find device for deselected server '%s' to disassociate.",
                            server_name_to_remove,
                        )

            new_options_data = {
                **current_options,
                CONF_SERVER_NAMES: newly_selected_servers_list,
            }
            return self.async_create_entry(title="", data=new_options_data)

        available_servers = (
            self._discovered_servers if self._discovered_servers is not None else []
        )
        current_selection_list = list(old_selected_servers)
        select_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SERVER_NAMES, default=current_selection_list
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=available_servers,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                        sort=True,
                    )
                ),
            }
        )
        placeholders = {}
        if "base" in errors and errors["base"] == "fetch_servers_failed":
            placeholders["fetch_error"] = (
                "Could not fetch server list. Check manager status/logs."
            )
        elif "base" in errors and errors["base"] in ["cannot_connect", "invalid_auth"]:
            placeholders["fetch_error"] = (
                "Could not connect or authenticate to fetch server list."
            )
        return self.async_show_form(
            step_id="select_servers",
            data_schema=select_schema,
            errors=errors,
            description_placeholders=placeholders if placeholders else None,
        )

    async def async_step_update_server_interval(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        errors: Dict[str, str] = {}
        if user_input is not None:
            scan_interval = user_input.get(CONF_SCAN_INTERVAL)
            if scan_interval is not None and scan_interval < 5:
                errors[CONF_SCAN_INTERVAL] = "invalid_scan_interval"
            if not errors:
                new_options_data = {
                    **self.config_entry.options,
                    CONF_SCAN_INTERVAL: scan_interval,
                }
                return self.async_create_entry(title="", data=new_options_data)
        current_scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS
        )
        schema = self.add_suggested_values_to_schema(
            STEP_SERVER_POLLING_SCHEMA,
            suggested_values={CONF_SCAN_INTERVAL: current_scan_interval},
        )
        return self.async_show_form(
            step_id="update_server_interval", data_schema=schema, errors=errors
        )

    async def async_step_update_manager_interval(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        errors: Dict[str, str] = {}
        if user_input is not None:
            manager_scan_interval = user_input.get(CONF_MANAGER_SCAN_INTERVAL)
            if manager_scan_interval is not None and manager_scan_interval < 60:
                errors[CONF_MANAGER_SCAN_INTERVAL] = "invalid_manager_scan_interval"
            if not errors:
                new_options_data = {
                    **self.config_entry.options,
                    CONF_MANAGER_SCAN_INTERVAL: manager_scan_interval,
                }
                return self.async_create_entry(title="", data=new_options_data)
        current_manager_scan_interval = self.config_entry.options.get(
            CONF_MANAGER_SCAN_INTERVAL, DEFAULT_MANAGER_SCAN_INTERVAL_SECONDS
        )
        schema = self.add_suggested_values_to_schema(
            STEP_MANAGER_POLLING_SCHEMA,
            suggested_values={
                CONF_MANAGER_SCAN_INTERVAL: current_manager_scan_interval
            },
        )
        return self.async_show_form(
            step_id="update_manager_interval", data_schema=schema, errors=errors
        )
