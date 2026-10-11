"""Exercise current SDK contracts at the HA action boundary."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from bsm_api_client.models import ServerSettingItemPayload, ServerSettingsResponse
from homeassistant.core import ServiceCall
from homeassistant.exceptions import ServiceValidationError

from custom_components.bedrock_server_manager.configuration_services import (
    SCHEMAS,
    configuration_action,
)
from custom_components.bedrock_server_manager.const import DOMAIN


@pytest.mark.asyncio
async def test_server_setting_retains_json_types_and_refreshes_target(hass, api):
    coordinator = SimpleNamespace(invalidate=Mock(), async_request_refresh=AsyncMock())
    api.servers.async_set_server_setting = AsyncMock(
        return_value=ServerSettingsResponse(
            status="success", settings={"settings": {"autostart": True}}
        )
    )
    hass.data[DOMAIN] = {
        "entry": {
            "api": api,
            "manager_identifier": (DOMAIN, "http://host"),
            "servers": {"selected": {"coordinator": coordinator}},
        }
    }
    call = ServiceCall(
        hass, DOMAIN, "set_server_setting", {"key": "settings.autostart", "value": True}
    )
    with patch(
        "custom_components.bedrock_server_manager.configuration_services.resolve_server_targets",
        AsyncMock(return_value=[("entry", "selected")]),
    ):
        response = await configuration_action(hass, call)
    name, payload = api.servers.async_set_server_setting.call_args.args
    assert name == "selected"
    assert isinstance(payload, ServerSettingItemPayload)
    assert payload.value is True
    assert response["results"][0]["result"]["settings"]["settings"]["autostart"] is True
    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_dynamic_calls_use_sdk_validation_and_authenticated_transport(hass, api):
    api.discovery = SimpleNamespace(
        operations={"plugin_operation": SimpleNamespace(method="POST")},
        discover=AsyncMock(return_value={}),
        call=AsyncMock(return_value={"outcome": "done"}),
    )
    hass.data[DOMAIN] = {
        "entry": {"api": api, "manager_identifier": (DOMAIN, "http://host")}
    }
    call = ServiceCall(
        hass,
        DOMAIN,
        "call_operation",
        {
            "operation_id": "plugin_operation",
            "path_params": {"server_name": "selected"},
            "json_data": {"enabled": False},
        },
    )
    with patch(
        "custom_components.bedrock_server_manager.configuration_services.resolve_manager_targets",
        AsyncMock(return_value=["entry"]),
    ):
        result = await configuration_action(hass, call)
    api.discovery.call.assert_awaited_once_with(
        "plugin_operation",
        authenticated=True,
        path_params={"server_name": "selected"},
        json_data={"enabled": False},
    )
    assert result["results"][0]["result"] == {"outcome": "done"}


@pytest.mark.asyncio
async def test_upload_rejects_paths_outside_ha_allowlist(hass, api):
    hass.data[DOMAIN] = {
        "entry": {"api": api, "manager_identifier": (DOMAIN, "http://host")}
    }
    api.content.async_upload_content = AsyncMock()
    call = ServiceCall(
        hass, DOMAIN, "upload_content", {"file_path": "/outside/world.mcworld"}
    )
    with patch(
        "custom_components.bedrock_server_manager.configuration_services.resolve_manager_targets",
        AsyncMock(return_value=["entry"]),
    ):
        with pytest.raises(ServiceValidationError):
            await configuration_action(hass, call)
    api.content.async_upload_content.assert_not_awaited()


def test_all_added_services_are_documented():
    from pathlib import Path

    import yaml

    definitions = yaml.safe_load(
        Path("custom_components/bedrock_server_manager/services.yaml").read_text()
    )
    assert set(SCHEMAS) <= definitions.keys()


def test_used_operations_exist_in_released_sdk_contract():
    from bsm_api_client.openapi import generated_schema, index_operations

    operations = index_operations(generated_schema())
    assert {
        "get_settings",
        "set_setting",
        "get_server_settings",
        "set_server_setting",
        "get_application_health",
        "get_application_metrics",
        "get_server_bans",
        "list_tasks",
        "get_task_status",
        "export_world",
    } <= operations.keys()


def test_all_bundled_cards_are_registered_for_ha_dashboards():
    from pathlib import Path

    from custom_components.bedrock_server_manager.const import JS_MODULES

    bundles = {
        path.name
        for path in Path("custom_components/bedrock_server_manager/frontend").glob(
            "bsm-*-card.js"
        )
    }
    assert bundles == {module["filename"] for module in JS_MODULES}
