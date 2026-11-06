"""Configure a BSM manager with password, MFA or an integration bearer token."""

from typing import Any

import probatio as vol
from bsm_api_client import APIError, AuthError, CannotConnectError
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .auth import (
    CREDENTIAL_FIELDS,
    CREDENTIALS_SCHEMA,
    MFA_SCHEMA,
    CredentialError,
    auth_error_key,
    credential_updates,
    validate_credentials,
)
from .const import (
    CONF_BASE_URL,
    CONF_SERVER_NAMES,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    DOMAIN,
)
from .options_flow import BSMOptionsFlowHandler

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BASE_URL): str,
        **CREDENTIAL_FIELDS,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Keep pending credentials in the flow until authentication succeeds."""

    VERSION = 1

    def __init__(self) -> None:
        self._connection_data: dict[str, Any] = {}
        self._pending_data: dict[str, Any] = {}
        self._discovered_servers: list[str] = []
        self._reauth = False

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> BSMOptionsFlowHandler:
        return BSMOptionsFlowHandler()

    async def async_step_user(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Collect the connection and exactly one credential type."""
        if user_input is not None:
            data = {
                **user_input,
                CONF_BASE_URL: user_input[CONF_BASE_URL].strip().rstrip("/"),
            }
            await self.async_set_unique_id(data[CONF_BASE_URL])
            self._abort_if_unique_id_configured(
                description_placeholders={"base_url": data[CONF_BASE_URL]}
            )
            return await self._async_validate(data, "user", STEP_USER_DATA_SCHEMA)
        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

    async def async_step_reauth(self, entry_data) -> config_entries.ConfigFlowResult:
        """Replace credentials without changing manager or entity identifiers."""
        self._reauth = True
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        self._reauth = True
        entry = self._get_reauth_entry()
        if user_input is not None:
            # Do not carry old token or remembered-device credentials into a new login.
            data = {
                CONF_BASE_URL: entry.data[CONF_BASE_URL],
                CONF_VERIFY_SSL: entry.data.get(CONF_VERIFY_SSL, True),
                **user_input,
            }
            return await self._async_validate(
                data, "reauth_confirm", CREDENTIALS_SCHEMA
            )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                CREDENTIALS_SCHEMA,
                {
                    "auth_type": entry.data.get("auth_type", "password"),
                    CONF_USERNAME: entry.data.get(CONF_USERNAME, ""),
                },
            ),
        )

    async def _async_validate(
        self, data, step_id, schema, **proof
    ) -> config_entries.ConfigFlowResult:
        """Apply the same validation and challenge handling to setup and reauth."""
        try:
            validated = await validate_credentials(self.hass, data, **proof)
        except AuthError as error:
            key = auth_error_key(error)
            if key == "mfa_required" and step_id != "mfa":
                self._pending_data = data
                return await self.async_step_mfa()
        except CredentialError as error:
            key = str(error)
        except CannotConnectError:
            key = "cannot_connect"
        except APIError:
            key = "api_error"
        except ValueError:
            key = "invalid_url"
        else:
            self._pending_data = {}
            if self._reauth:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates=credential_updates(validated["data"]),
                )
            self._connection_data = validated["data"]
            self._discovered_servers = validated["discovered_servers"]
            return await self.async_step_select_servers()
        return self.async_show_form(
            step_id=step_id, data_schema=schema, errors={"base": key}
        )

    async def async_step_mfa(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Request a one-time authenticator or recovery code only after a challenge."""
        if not self._pending_data:
            return self.async_abort(reason="reauth_failed")
        if user_input is not None:
            return await self._async_validate(
                self._pending_data,
                "mfa",
                MFA_SCHEMA,
                otp=user_input["otp"].strip(),
                remember_device=user_input.get("remember_device", True),
            )
        return self.async_show_form(step_id="mfa", data_schema=MFA_SCHEMA)

    async def async_step_select_servers(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=f"BSM @ {self._connection_data[CONF_BASE_URL]}",
                data=self._connection_data,
                options={CONF_SERVER_NAMES: user_input.get(CONF_SERVER_NAMES, [])},
            )
        return self.async_show_form(
            step_id="select_servers",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SERVER_NAMES, default=[]
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=sorted(self._discovered_servers),
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
            description_placeholders={
                "message": "Select servers to monitor. You can change this selection later."
            },
        )
