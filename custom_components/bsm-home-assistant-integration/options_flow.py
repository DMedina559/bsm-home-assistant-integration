"""Options flow for Minecraft Bedrock Server Manager integration."""

import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    CONF_SERVER_NAME,
)

_LOGGER = logging.getLogger(__name__)


class MinecraftBdsManagerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for Minecraft Bedrock Server Manager."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.FlowResult:
        """Manage the options. This is the initial (and likely only) step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Retrieve the scan_interval value provided by the user
            scan_interval = user_input.get(CONF_SCAN_INTERVAL)

            # Perform validation (Voluptuous schema handles basic type check)
            if scan_interval is not None and scan_interval < 5:
                 # Example: Ensure minimum interval is respected
                 errors[CONF_SCAN_INTERVAL] = "invalid_scan_interval"
                 # Ensure the translation key exists in translations/en.json under options->error

            if not errors:
                # Input is valid, create/update the options entry
                _LOGGER.debug(
                    "Updating options for entry %s (%s) with: %s",
                    self.config_entry.entry_id,
                    self.config_entry.data.get(CONF_SERVER_NAME, "Unknown Server"),
                    user_input
                )
                # Create the options entry (title="" means modify existing)
                # 'data=user_input' contains the dictionary of options to save
                return self.async_create_entry(title="", data=user_input)

        # If it's the first time showing the form, or if there were errors:
        # Get the current value for scan_interval to pre-fill the form
        # Use .options accessor on config_entry
        current_scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS
        )

        # Define the schema for the options form shown to the user
        options_schema = vol.Schema({
            # Use Optional to allow users to keep the default if they don't interact
            # Use the current value (or default) as the suggested value
            vol.Optional(CONF_SCAN_INTERVAL, default=current_scan_interval): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=5, # Set a reasonable minimum poll interval (e.g., 5 seconds)
                    max=3600, # Set a reasonable maximum (e.g., 1 hour)
                    step=1,
                    mode=selector.NumberSelectorMode.BOX, # Or slider
                    unit_of_measurement="seconds",
                )
            ),
        })

        # Show the form to the user
        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )