"""Entry failure/unload closes owned SDK transports and preserves shared cards."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed

from custom_components.bedrock_server_manager import (
    async_setup_entry,
    async_unload_entry,
)
from custom_components.bedrock_server_manager.config_flow import ConfigFlow
from custom_components.bedrock_server_manager.const import DOMAIN


@pytest.mark.asyncio
async def test_failed_setup_preserves_auth_error_and_closes_client(hass, api):
    entry = SimpleNamespace(entry_id="entry", data={"base_url": "http://host"})
    registrar = SimpleNamespace(async_unregister=AsyncMock())
    hass.data[f"{DOMAIN}_frontend"] = registrar
    hass.data[DOMAIN] = {
        "entry": {"api": api, "frontend_registrar": registrar},
        "_frontend_registrar": registrar,
    }
    with patch(
        "custom_components.bedrock_server_manager._async_setup_entry",
        AsyncMock(side_effect=ConfigEntryAuthFailed("expired")),
    ):
        with pytest.raises(ConfigEntryAuthFailed):
            await async_setup_entry(hass, entry)
    api.close.assert_awaited_once()
    registrar.async_unregister.assert_awaited_once()
    assert DOMAIN not in hass.data


@pytest.mark.asyncio
async def test_unload_stops_socket_before_client_and_keeps_other_manager_resources(
    hass, api
):
    entry = SimpleNamespace(entry_id="entry", data={"base_url": "http://host"})
    order = []

    async def stop():
        order.append("websocket")

    async def close():
        order.append("http")

    api.close.side_effect = close
    registrar = SimpleNamespace(async_unregister=AsyncMock())
    hass.data[DOMAIN] = {
        "entry": {
            "api": api,
            "ws_manager": SimpleNamespace(async_stop=stop),
            "frontend_registrar": registrar,
        },
        "other": {},
        "_frontend_registrar": registrar,
    }
    hass.config_entries = SimpleNamespace(
        async_unload_platforms=AsyncMock(return_value=True)
    )
    assert await async_unload_entry(hass, entry)
    assert order == ["websocket", "http"]
    registrar.async_unregister.assert_not_called()
    assert "other" in hass.data[DOMAIN]


def test_options_flow_uses_framework_config_entry():
    flow = ConfigFlow.async_get_options_flow(Mock())
    assert flow._api_client_instance is None


def test_diagnostics_redact_nested_credentials_and_registry_urls():
    from custom_components.bedrock_server_manager.diagnostics import _redact_diagnostics

    entry = SimpleNamespace(
        data={
            "base_url": "http://private-host",
            "username": "secret-user",
            "password": "secret-password",
        }
    )
    result = _redact_diagnostics(
        {
            "token": "private-token",
            "registry": {
                "http://private-host_server": ["secret-password", "secret-user"]
            },
            "players": {"xuid": "private-player"},
        },
        entry,
    )
    rendered = str(result)
    for secret in (
        "private-host",
        "secret-password",
        "secret-user",
        "private-token",
        "private-player",
    ):
        assert secret not in rendered
