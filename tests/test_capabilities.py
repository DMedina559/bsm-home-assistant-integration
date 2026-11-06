"""Effective token grants and per-server restrictions drive honest capability states."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from bsm_api_client import AuthError
from homeassistant.exceptions import ConfigEntryAuthFailed

from custom_components.bedrock_server_manager.auth import BsmApiClient
from custom_components.bedrock_server_manager.capabilities import AccessCapabilities
from custom_components.bedrock_server_manager.coordinator import BsmCoordinator


def operation(*permissions, server=False, checks=None, tokens="supported"):
    return {
        "x-bsm-access": {
            "classification": "permission",
            "required_permissions": list(permissions),
            "resource_scope": "server" if server else "global",
            "additional_checks": checks or [],
            "integration_tokens": tokens,
        }
    }


def access():
    result = AccessCapabilities(integration_token=True)
    result.permissions = {"servers:read", "servers:control", "plugins:read"}
    result.server_permission_names = {"servers:read", "servers:control"}
    result.server_permissions = {
        "alpha": {"servers:read", "servers:control"},
        "beta": {"servers:read"},
    }
    result.operations = {
        "start_server": operation("servers:control", server=True),
        "get_server_process_info": operation("servers:read", server=True),
        "list_plugins": operation("plugins:read"),
        "set_properties": operation("properties:manage", server=True),
        "sensitive": operation(
            "plugins:read", checks=["recent-interactive-verification"]
        ),
        "interactive_only": operation("plugins:read", tokens="unsupported"),
    }
    return result


def test_scope_and_server_grants_are_intersected():
    grants = access()
    assert grants.operation("start_server", "alpha")["state"] == "allowed"
    assert grants.operation("start_server", "beta") == {
        **grants.operation("start_server", "alpha"),
        "state": "denied",
        "missing_permissions": ["servers:control"],
    }
    assert grants.operation("start_server", "removed")["state"] == "denied"
    assert grants.operation("set_properties", "alpha")["missing_permissions"] == [
        "properties:manage"
    ]
    assert grants.operation("start_server")["state"] == "conditional"


def test_unknown_conditional_and_unsupported_are_not_full_access():
    grants = access()
    assert grants.operation("sensitive")["state"] == "conditional"
    assert grants.operation("interactive_only")["state"] == "denied"
    assert grants.operation("new_feature")["state"] == "unsupported"
    grants.permissions = None
    assert grants.operation("start_server", "alpha")["state"] == "unknown"
    grants.operations = None
    assert grants.operation("start_server", "alpha")["state"] == "unknown"


def test_global_permissions_are_not_required_in_per_server_grants():
    grants = access()
    grants.operations["plugin_server"] = operation(
        "plugins:read", "servers:read", server=True
    )
    assert grants.operation("plugin_server", "beta")["state"] == "allowed"
    grants.server_permissions = None
    assert grants.operation("plugin_server", "beta")["state"] == "unknown"


@pytest.mark.asyncio
async def test_live_discovery_uses_effective_account_grants_and_updates_after_revocation():
    grants = access()
    schema = {
        "paths": {
            f"/{key}": {"get": {"operationId": key, **value}}
            for key, value in {
                **grants.operations,
                "get_account": {},
                "get_access_policy": {},
                "list_access_servers": {},
            }.items()
        }
    }
    api = SimpleNamespace(
        discovery=SimpleNamespace(
            schema=schema,
            call=AsyncMock(
                side_effect=[
                    {
                        "role": "admin",
                        "permissions": ["servers:read"],
                        "policy_revision": "new",
                    },
                    {"server_permissions": ["servers:read", "servers:control"]},
                    [{"name": "alpha", "permissions": ["servers:read"]}],
                ]
            ),
        )
    )
    await grants.refresh(api)
    assert grants.operation("start_server", "alpha")["state"] == "denied"
    assert grants.revision == "new"
    assert all(
        call.kwargs["authenticated"] for call in api.discovery.call.await_args_list
    )
    api.discovery.call.side_effect = AuthError("Scope denied", 403)
    await grants.refresh(api)
    assert grants.permissions is None
    assert grants.operation("start_server", "alpha")["state"] == "unknown"


@pytest.mark.asyncio
async def test_expired_credential_during_capability_discovery_is_not_a_scope_denial():
    grants = access()
    api = SimpleNamespace(
        discovery=SimpleNamespace(
            schema={"paths": {"/account": {"get": {"operationId": "get_account"}}}},
            call=AsyncMock(side_effect=AuthError("Expired", 401)),
        )
    )
    with pytest.raises(AuthError):
        await grants.refresh(api)


@pytest.mark.asyncio
async def test_known_denied_resource_is_not_polled(hass):
    grants = access()
    grants.permissions = set()
    api = SimpleNamespace(ha_access=grants)
    coordinator = BsmCoordinator(hass, api, "test", 30)
    coordinator.server_name = "alpha"
    request = AsyncMock(return_value={"process_info": {}})
    result = await coordinator._fetch(
        {"process_info": request()}, {"process_info": "process_info"}
    )
    request.assert_not_awaited()
    assert "process_info" in coordinator.forbidden_resources
    assert result == {}


@pytest.mark.asyncio
async def test_http_403_mfa_policy_starts_reauth(hass):
    coordinator = BsmCoordinator(hass, SimpleNamespace(), "test", 30)

    async def challenged():
        raise AuthError("MFA", 403, response_headers={"X-BSM-MFA": "required"})

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._fetch({"info": challenged()}, {})


@pytest.mark.asyncio
async def test_sdk_preflight_blocks_denied_native_calls_without_transport_io():
    client = BsmApiClient("http://manager", jwt_token="bsm_it_test")
    client.ha_access = access()
    try:
        with pytest.raises(AuthError) as error:
            await client.servers.async_start_server("beta")
        assert error.value.status_code == 403
    finally:
        await client.close()


def test_capability_summary_contains_no_credentials():
    result = access().snapshot("beta", detailed=True)
    assert result["actions"]["start_server"]["state"] == "denied"
    assert result["actions"]["start_server"]["missing_permissions"] == [
        "servers:control"
    ]
    assert result["server_permissions"] == ["servers:read"]
    assert "token" not in result
