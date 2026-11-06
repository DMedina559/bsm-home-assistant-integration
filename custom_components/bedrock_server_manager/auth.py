"""Shared credentials and authentication for setup, options and runtime clients."""

from typing import Any

import probatio as vol
from bsm_api_client import AuthError, BedrockServerManagerApi
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .capabilities import AccessCapabilities
from .const import CONF_BASE_URL, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL

CONF_AUTH_TYPE = "auth_type"
CONF_TOKEN = "token"
CONF_JWT_TOKEN = "jwt_token"
CONF_TRUSTED_DEVICE_TOKEN = "trusted_device_token"
AUTH_PASSWORD = "password"
AUTH_TOKEN = "token"
CREDENTIAL_KEYS = {
    CONF_AUTH_TYPE,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_JWT_TOKEN,
    CONF_TRUSTED_DEVICE_TOKEN,
    "remember_me",
}
PASSWORD_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)
CREDENTIAL_FIELDS = {
    vol.Required(CONF_AUTH_TYPE, default=AUTH_PASSWORD): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[AUTH_PASSWORD, AUTH_TOKEN], translation_key="auth_type"
        )
    ),
    vol.Optional(CONF_USERNAME): str,
    vol.Optional(CONF_PASSWORD): PASSWORD_SELECTOR,
    vol.Optional(CONF_TOKEN): PASSWORD_SELECTOR,
    vol.Optional("remember_me", default=True): bool,
}
CREDENTIALS_SCHEMA = vol.Schema(CREDENTIAL_FIELDS)
MFA_SCHEMA = vol.Schema(
    {
        vol.Required("otp"): PASSWORD_SELECTOR,
        vol.Optional("remember_device", default=True): bool,
    }
)


class CredentialError(ValueError):
    """An incomplete credential form; the message is a translation key."""


def credential_data(data: dict[str, Any]) -> dict[str, Any]:
    """Select one login type and discard credentials from the previous type."""
    method = data.get(CONF_AUTH_TYPE, AUTH_PASSWORD)
    result = {
        CONF_BASE_URL: data[CONF_BASE_URL],
        CONF_VERIFY_SSL: data.get(CONF_VERIFY_SSL, True),
        CONF_AUTH_TYPE: method,
    }
    if method == AUTH_TOKEN:
        token = str(data.get(CONF_TOKEN) or "").strip()
        if not token:
            raise CredentialError("token_required")
        result[CONF_TOKEN] = token
    elif method == AUTH_PASSWORD:
        username = str(data.get(CONF_USERNAME) or "").strip()
        password = data.get(CONF_PASSWORD)
        if not username or not password:
            raise CredentialError("credentials_required")
        result.update(
            username=username,
            password=password,
            remember_me=data.get("remember_me", True),
        )
    else:
        raise CredentialError("invalid_auth_type")
    return result


def credential_updates(data: dict[str, Any]) -> dict[str, Any]:
    """Clear superseded secrets when HA merges replacement entry credentials."""
    return {**dict.fromkeys(CREDENTIAL_KEYS), **data}


class BsmApiClient(BedrockServerManagerApi):
    """Check known HTTP grants at the SDK operation boundary."""

    ha_access: AccessCapabilities

    async def async_call_generated(self, operation_id: str, **kwargs: Any) -> Any:
        access = getattr(self, "ha_access", None)
        server = (kwargs.get("parameters") or {}).get("server_name")
        if (
            access is not None
            and access.operation(operation_id, server)["state"] == "denied"
        ):
            raise AuthError(
                "The BSM credential does not grant this action", status_code=403
            )
        return await super().async_call_generated(operation_id, **kwargs)


def create_api_client(
    hass: HomeAssistant, data: dict[str, Any], **kwargs: Any
) -> BsmApiClient:
    """Use the same login and TLS policy for REST and WebSocket transports."""
    verify_ssl = data.get(CONF_VERIFY_SSL, True)
    token_login = data.get(CONF_AUTH_TYPE) == AUTH_TOKEN
    client = BsmApiClient(
        base_url=data[CONF_BASE_URL],
        username=None if token_login else data.get(CONF_USERNAME),
        password=None if token_login else data.get(CONF_PASSWORD),
        jwt_token=data.get(CONF_TOKEN) if token_login else data.get(CONF_JWT_TOKEN),
        trusted_device_token=(
            None if token_login else data.get(CONF_TRUSTED_DEVICE_TOKEN)
        ),
        remember_me=data.get("remember_me", False),
        verify_ssl=verify_ssl,
        session=async_get_clientsession(hass, verify_ssl=verify_ssl),
        client_name="BSM Home Assistant",
        **kwargs,
    )
    client.ha_access = AccessCapabilities(
        integration_token=bool(
            token_login and str(data.get(CONF_TOKEN, "")).startswith("bsm_it_")
        )
    )
    return client


def auth_error_key(error: AuthError) -> str:
    """Keep MFA challenges and account policies distinct from bad credentials."""
    if error.passkey_required:
        return "passkey_required"
    if error.enrollment_required:
        return "enrollment_required"
    if error.mfa_required:
        return "mfa_required"
    if error.recent_auth_required:
        return "recent_auth_required"
    if error.status_code == 403 and not error.session_invalid:
        return "insufficient_permissions"
    return "invalid_auth"


def needs_reauthentication(error: AuthError) -> bool:
    """A policy challenge can be HTTP 403; a denied resource is not a login failure."""
    return error.status_code != 403 or any(
        (
            error.session_invalid,
            error.mfa_required,
            error.passkey_required,
            error.enrollment_required,
            error.recent_auth_required,
        )
    )


async def validate_credentials(
    hass: HomeAssistant,
    data: dict[str, Any],
    *,
    otp: str = "",
    remember_device: bool = False
) -> dict[str, Any]:
    """Check credentials and discover servers, keeping one-use proofs out of storage."""
    credentials = credential_data(data)
    client = create_api_client(
        hass, credentials, otp=otp, remember_device=remember_device
    )
    try:
        if credentials[CONF_AUTH_TYPE] == AUTH_PASSWORD:
            response = await client.authenticate()
            credentials[CONF_JWT_TOKEN] = response.access_token
            if remember_device and response.trusted_device_token:
                credentials[CONF_TRUSTED_DEVICE_TOKEN] = response.trusted_device_token
        servers = await client.servers.async_get_server_names()
        return {"data": credentials, "discovered_servers": servers}
    finally:
        await client.close()
