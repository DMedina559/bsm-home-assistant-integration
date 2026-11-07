"""Password/MFA and bearer credentials survive setup, restart and replacement safely."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import pytest
from bsm_api_client import AuthError
from bsm_api_client.models import TokenResponse

from custom_components.bedrock_server_manager.auth import (
    CredentialError,
    auth_error_key,
    create_api_client,
    credential_data,
    credential_updates,
    needs_reauthentication,
    validate_credentials,
)
from custom_components.bedrock_server_manager.config_flow import ConfigFlow
from custom_components.bedrock_server_manager.options_flow import BSMOptionsFlowHandler

BASE = {"base_url": "http://manager", "verify_ssl": False}
PASSWORD = {**BASE, "username": "admin", "password": "secret", "auth_type": "password"}
TOKEN = {**BASE, "auth_type": "token", "token": "bsm_it_example"}


@pytest.fixture
def client():
    return SimpleNamespace(
        authenticate=AsyncMock(return_value=TokenResponse(access_token="session")),
        servers=SimpleNamespace(
            async_get_server_names=AsyncMock(return_value=["alpha"])
        ),
        close=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_token_login_never_posts_password_and_closes_transport(hass, client):
    with patch(
        "custom_components.bedrock_server_manager.auth.create_api_client",
        return_value=client,
    ) as factory:
        result = await validate_credentials(
            hass, {**TOKEN, "username": "old", "password": "old"}
        )
    assert result["data"] == TOKEN
    assert result["discovered_servers"] == ["alpha"]
    assert factory.call_args.args[1] == TOKEN
    client.authenticate.assert_not_awaited()
    client.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("remember", [True, False])
async def test_mfa_saves_session_and_only_explicitly_remembered_device(
    hass, client, remember
):
    client.authenticate.return_value = TokenResponse(
        access_token="session", trusted_device_token="trusted"
    )
    with patch(
        "custom_components.bedrock_server_manager.auth.create_api_client",
        return_value=client,
    ):
        result = await validate_credentials(
            hass, PASSWORD, otp="123456", remember_device=remember
        )
    assert result["data"]["jwt_token"] == "session"
    assert ("trusted_device_token" in result["data"]) is remember
    assert "otp" not in result["data"]
    assert "remember_device" not in result["data"]
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_auth_failure_closes_client_without_storing_pending_secrets(hass, client):
    client.authenticate.side_effect = AuthError(
        "MFA required", 403, response_headers={"X-BSM-MFA": "required"}
    )
    with patch(
        "custom_components.bedrock_server_manager.auth.create_api_client",
        return_value=client,
    ):
        with pytest.raises(AuthError):
            await validate_credentials(hass, PASSWORD)
    client.close.assert_awaited_once()
    client.servers.async_get_server_names.assert_not_awaited()


@pytest.mark.parametrize(
    "data,key",
    [
        ({**BASE, "auth_type": "token"}, "token_required"),
        ({**BASE, "username": "admin"}, "credentials_required"),
        ({**BASE, "auth_type": "other"}, "invalid_auth_type"),
    ],
)
def test_incomplete_credentials_rejected(data, key):
    with pytest.raises(CredentialError, match=key):
        credential_data(data)


def test_switching_login_method_clears_previous_secrets():
    old = {**PASSWORD, "jwt_token": "old-session", "trusted_device_token": "old-device"}
    updated = {**old, **credential_updates(credential_data(TOKEN))}
    assert updated["token"] == TOKEN["token"]
    assert all(
        updated[key] is None
        for key in ["password", "username", "jwt_token", "trusted_device_token"]
    )


@pytest.mark.parametrize(
    "headers,key,reauth",
    [
        ({}, "insufficient_permissions", False),
        ({"X-BSM-MFA": "required"}, "mfa_required", True),
        ({"X-BSM-MFA": "passkey"}, "passkey_required", True),
        ({"X-BSM-MFA-Enrollment": "required"}, "enrollment_required", True),
        ({"X-BSM-Session-Invalid": "1"}, "invalid_auth", True),
        ({"X-BSM-Recent-Auth": "required"}, "recent_auth_required", True),
    ],
)
def test_forbidden_scope_is_distinct_from_account_challenge(headers, key, reauth):
    error = AuthError("Denied", 403, response_headers=headers)
    assert auth_error_key(error) == key
    assert needs_reauthentication(error) is reauth


def test_runtime_client_preserves_saved_session_device_and_legacy_password(hass):
    with patch(
        "custom_components.bedrock_server_manager.auth.BsmApiClient"
    ) as factory, patch(
        "custom_components.bedrock_server_manager.auth.async_get_clientsession",
        return_value=Mock(),
    ):
        create_api_client(
            hass,
            {**PASSWORD, "jwt_token": "session", "trusted_device_token": "trusted"},
        )
        kwargs = factory.call_args.kwargs
        assert kwargs["jwt_token"] == "session"
        assert kwargs["trusted_device_token"] == "trusted"
        assert kwargs["password"] == "secret"
        assert kwargs["verify_ssl"] is False
        create_api_client(hass, {**TOKEN, "password": "stale"})
        assert factory.call_args.kwargs["username"] is None
        assert factory.call_args.kwargs["password"] is None
        assert factory.call_args.kwargs["trusted_device_token"] is None


@pytest.mark.asyncio
async def test_setup_challenges_only_after_backend_requests_mfa(hass):
    flow = ConfigFlow()
    flow.hass = hass
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = Mock()
    challenge = AuthError("MFA", 403, response_headers={"X-BSM-MFA": "required"})
    validated = {
        "data": {**PASSWORD, "jwt_token": "session"},
        "discovered_servers": ["alpha"],
    }
    with patch(
        "custom_components.bedrock_server_manager.config_flow.validate_credentials",
        AsyncMock(side_effect=[challenge, validated]),
    ) as validate:
        result = await flow.async_step_user(PASSWORD)
        assert result["step_id"] == "mfa"
        result = await flow.async_step_mfa({"otp": "123456", "remember_device": True})
    assert result["step_id"] == "select_servers"
    assert validate.await_args.kwargs["otp"] == "123456"
    result = await flow.async_step_select_servers({"servers": ["alpha"]})
    assert result["data"]["jwt_token"] == "session"
    assert "otp" not in result["data"]
    assert not flow._pending_data


@pytest.mark.asyncio
async def test_reauth_preserves_entry_and_clears_stale_password(hass):
    flow = ConfigFlow()
    flow.hass = hass
    entry = SimpleNamespace(data=PASSWORD)
    with patch.object(flow, "_get_reauth_entry", return_value=entry), patch.object(
        flow, "async_update_reload_and_abort", return_value={"type": "abort"}
    ) as update, patch(
        "custom_components.bedrock_server_manager.config_flow.validate_credentials",
        AsyncMock(return_value={"data": TOKEN, "discovered_servers": ["alpha"]}),
    ):
        await flow.async_step_reauth_confirm(
            {"auth_type": "token", "token": TOKEN["token"]}
        )
    assert update.call_args.args[0] is entry
    assert update.call_args.kwargs["data_updates"]["password"] is None
    assert update.call_args.kwargs["data_updates"]["token"] == TOKEN["token"]


@pytest.mark.asyncio
async def test_options_credentials_reload_existing_entry(hass):
    flow = BSMOptionsFlowHandler()
    flow.hass = hass
    entry = SimpleNamespace(data=PASSWORD, entry_id="entry", title="BSM")
    hass.config_entries = SimpleNamespace(
        async_update_entry=Mock(), async_reload=AsyncMock()
    )
    with patch.object(
        type(flow), "config_entry", PropertyMock(return_value=entry)
    ), patch(
        "custom_components.bedrock_server_manager.options_flow.validate_credentials",
        AsyncMock(return_value={"data": TOKEN, "discovered_servers": []}),
    ):
        result = await flow.async_step_update_credentials(
            {"auth_type": "token", "token": TOKEN["token"]}
        )
    assert result["reason"] == "credentials_updated"
    assert (
        hass.config_entries.async_update_entry.call_args.kwargs["data"]["password"]
        is None
    )
    hass.config_entries.async_reload.assert_awaited_once_with("entry")
