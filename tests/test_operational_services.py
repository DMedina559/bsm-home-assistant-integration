"""Exercise existing-backend operations, safe outcomes and optional collection."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from bsm_api_client import APIError, CannotConnectError
from bsm_api_client.models import ActionResponse
from homeassistant.core import ServiceCall
from homeassistant.exceptions import ServiceValidationError
from pydantic import BaseModel, ValidationError

from custom_components.bedrock_server_manager.const import DOMAIN
from custom_components.bedrock_server_manager.coordinator import (
    ApplicationMonitorCoordinator,
)
from custom_components.bedrock_server_manager.data_services import settings_action
from custom_components.bedrock_server_manager.operational_services import (
    ACTIONS,
    _execute,
    operational_action,
)
from custom_components.bedrock_server_manager.responses import action_error
from custom_components.bedrock_server_manager.websocket import BsmWebSocketManager


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,values,server,kwargs",
    [
        (
            "get_log_history",
            {"before": 100, "file_id": "file"},
            "alpha",
            {
                "path_params": {},
                "query": {
                    "before": 100,
                    "file_id": "file",
                    "topic": "server_log:alpha",
                },
            },
        ),
        (
            "get_diagnostic_trace",
            {"correlation_id": "trace", "limit": 20},
            None,
            {"path_params": {"correlation_id": "trace"}, "query": {"limit": 20}},
        ),
        (
            "prune_backups",
            {},
            "alpha",
            {"path_params": {"server_name": "alpha"}, "query": {}},
        ),
        (
            "reload_plugin",
            {"plugin_name": "plugin"},
            None,
            {"path_params": {"plugin_name": "plugin"}, "query": {}},
        ),
        (
            "shutdown_web_runtime",
            {"confirm": True},
            None,
            {"path_params": {}, "json_data": {}},
        ),
        (
            "compare_diagnostic_snapshots",
            {"before": {}, "after": {}},
            None,
            {"path_params": {}, "json_data": {"before": {}, "after": {}}},
        ),
    ],
)
async def test_operational_routing_is_authenticated_and_uses_only_contract_fields(
    name, values, server, kwargs
):
    spec = ACTIONS[name]
    api = SimpleNamespace(
        discovery=SimpleNamespace(
            discover=AsyncMock(return_value={spec.operation: object()}),
            call=AsyncMock(return_value={"status": "success"}),
        )
    )
    await _execute(api, spec, {**values, "entity_id": "sensor.private"}, server)
    api.discovery.call.assert_awaited_once_with(
        spec.operation, authenticated=True, **kwargs
    )


@pytest.mark.asyncio
async def test_shutdown_requires_confirmation_before_transport():
    spec = ACTIONS["shutdown_web_runtime"]
    api = SimpleNamespace(
        discovery=SimpleNamespace(
            discover=AsyncMock(return_value={spec.operation: object()}),
            call=AsyncMock(),
        )
    )
    with pytest.raises(ServiceValidationError, match="confirmation"):
        await _execute(api, spec, {"confirm": False}, None)
    api.discovery.call.assert_not_awaited()


@pytest.mark.asyncio
async def test_unsupported_backend_returns_structured_failure_without_calling(
    hass, api
):
    api.discovery = SimpleNamespace(
        discover=AsyncMock(return_value={}), call=AsyncMock()
    )
    hass.data[DOMAIN] = {
        "entry": {"api": api, "manager_identifier": (DOMAIN, "http://host")}
    }
    with patch(
        "custom_components.bedrock_server_manager.operational_services.resolve_manager_targets",
        AsyncMock(return_value=["entry"]),
    ):
        response = await operational_action(
            hass, ServiceCall(hass, DOMAIN, "get_web_runtime", {}, return_response=True)
        )
    assert response["response_schema_version"] == 1
    assert response["results"][0]["error"]["code"] == "unsupported_operation"
    api.discovery.call.assert_not_awaited()


@pytest.mark.asyncio
async def test_log_rotation_preserves_status_for_card_recovery(hass, api):
    api.discovery = SimpleNamespace(
        discover=AsyncMock(return_value={"get_log_history": object()}),
        call=AsyncMock(
            side_effect=APIError(
                "rotated",
                status_code=409,
                response_data={
                    "error": {"code": "log_changed", "message": "Reload the viewer"}
                },
            )
        ),
    )
    hass.data[DOMAIN] = {
        "entry": {"api": api, "manager_identifier": (DOMAIN, "http://host")}
    }
    with patch(
        "custom_components.bedrock_server_manager.operational_services.resolve_server_targets",
        AsyncMock(return_value=[("entry", "alpha")]),
    ):
        response = await operational_action(
            hass, ServiceCall(hass, DOMAIN, "get_log_history", {}, return_response=True)
        )
    error = response["results"][0]["error"]
    assert error["status_code"] == 409
    assert error["code"] == "log_changed"
    assert not error["retryable"]


@pytest.mark.asyncio
async def test_saved_plugin_settings_survive_failed_followup_read(hass, api):
    api.plugins.async_update_plugin_settings = AsyncMock(
        return_value=ActionResponse(status="success", message="Saved")
    )
    api.plugins.async_get_plugin_settings = AsyncMock(
        side_effect=CannotConnectError("offline")
    )
    coordinator = SimpleNamespace(
        data={"plugins_status": {"example": {"has_settings": True}}},
        invalidate=Mock(),
        schedule_refresh=Mock(),
        api=api,
    )
    hass.data[DOMAIN] = {
        "entry": {
            "api": api,
            "manager_identifier": (DOMAIN, "http://host"),
            "manager_coordinator": coordinator,
        }
    }
    with patch(
        "custom_components.bedrock_server_manager.data_services.resolve_manager_targets",
        AsyncMock(return_value=["entry"]),
    ):
        response = await settings_action(
            hass,
            ServiceCall(
                hass,
                DOMAIN,
                "update_plugin_settings",
                {"plugin_name": "example", "settings": {"enabled": True}},
            ),
        )
    result = response["results"][0]
    assert result["status"] == "success"
    assert result["warnings"][0]["code"] == "refresh_failed"
    assert "error" not in result
    assert response["managers"][0]["applied"] is True
    api.plugins.async_update_plugin_settings.assert_awaited_once()


def test_validation_details_never_include_input_or_secrets():
    class Request(BaseModel):
        count: int

    try:
        Request(count="sensitive-input")
    except ValidationError as error:
        result = action_error(error)
    assert "sensitive-input" not in str(result)
    api_error = APIError(
        "bad",
        status_code=422,
        response_data={
            "error": {
                "code": "invalid",
                "details": {
                    "password": "secret",
                    "nested": {"input": "secret", "field": "count"},
                },
            }
        },
    )
    result = action_error(api_error)
    assert result["code"] == "invalid"
    assert result["details"] == {"nested": {"field": "count"}}


@pytest.mark.asyncio
async def test_event_filter_does_not_filter_state_reconciliation(hass, api):
    refresh = Mock()
    ws = BsmWebSocketManager(
        hass,
        api,
        refresh,
        Mock(),
        ["alpha"],
        "http://host",
        Mock(),
        Mock(),
        event_names=["example"],
    )
    events = []
    remove = hass.bus.async_listen(f"{DOMAIN}_event", events.append)
    ws._handle_message(
        {
            "type": "event",
            "topic": "event:after_server_stop",
            "data": {"server_name": "alpha"},
        }
    )
    await hass.async_block_till_done()
    assert not events
    refresh.assert_called_once()
    remove()


@pytest.mark.asyncio
async def test_optional_diagnostics_fetch_only_for_enabled_consumers_and_store_scalars(
    hass, api
):
    api.application.async_get_application_metrics = AsyncMock(
        return_value={"latest": {}}
    )
    api.application.async_get_application_health = AsyncMock(
        return_value={"health": "healthy", "ready": True}
    )
    api.discovery = SimpleNamespace(
        call=AsyncMock(
            return_value={
                "summary": {"status": "ok", "findings": []},
                "sections": [
                    {
                        "status": "ok",
                        "data": {"kind": "events", "activity": {"pending_workers": 2}},
                    },
                    {"status": "ok", "data": {"kind": "transport", "failed_sends": 3}},
                ],
            }
        )
    )
    coordinator = ApplicationMonitorCoordinator(hass, api)
    await coordinator.async_refresh()
    api.discovery.call.assert_not_awaited()
    coordinator.diagnostic_consumers = 1
    await coordinator.async_refresh()
    assert coordinator.data["diagnostics"] == {
        "issue_count": 0,
        "event_pending_workers": 2,
        "delivery_failures": 3,
    }
    api.discovery.call.assert_awaited_once_with(
        "get_application_diagnostics", authenticated=True
    )


def test_dedicated_operations_are_shipped_or_explicit_discovery_extensions():
    from bsm_api_client.openapi import generated_schema, index_operations

    operations = index_operations(generated_schema())
    # Scheduler controls intentionally use live discovery until the SDK release.
    assert {spec.operation for spec in ACTIONS.values()} <= operations.keys() | {
        "control_schedule"
    }


@pytest.mark.asyncio
async def test_malformed_json_setting_is_not_logged(hass, api, caplog):
    from custom_components.bedrock_server_manager.manager_actions import (
        _async_handle_set_global_setting,
    )

    api.application.async_set_setting = AsyncMock(
        return_value=ActionResponse(status="success", message="Saved")
    )
    await _async_handle_set_global_setting(
        api, "custom", '{"credential":"sensitive",}', "host"
    )
    assert "failed to parse" in caplog.text
    assert "sensitive" not in caplog.text


@pytest.mark.asyncio
async def test_manager_read_actions_honor_entity_read_permissions(hass):
    from homeassistant.core import Context
    from homeassistant.exceptions import Unauthorized

    from custom_components.bedrock_server_manager.targets import resolve_manager_targets

    user = SimpleNamespace(
        is_admin=False,
        permissions=SimpleNamespace(check_entity=Mock(return_value=True)),
    )
    anchor = SimpleNamespace(
        platform=DOMAIN,
        config_entry_id="entry",
        device_id="manager",
        unique_id="manager_bsm_version",
        entity_id="sensor.manager",
    )
    registry = SimpleNamespace(async_get=Mock(return_value=anchor))
    hass.data[DOMAIN] = {"entry": {"manager_device_id": "manager"}}
    call = ServiceCall(
        hass,
        DOMAIN,
        "list_tasks",
        {"entity_id": "sensor.manager"},
        context=Context(user_id="reader"),
    )
    hass.auth = SimpleNamespace(async_get_user=AsyncMock(return_value=user))
    with patch(
        "custom_components.bedrock_server_manager.targets.er.async_get",
        return_value=registry,
    ), patch(
        "custom_components.bedrock_server_manager.targets.er.async_entries_for_config_entry",
        return_value=[anchor],
    ), patch(
        "custom_components.bedrock_server_manager.targets.dr.async_get",
        return_value=Mock(),
    ):
        assert await resolve_manager_targets(call, hass) == ["entry"]
        user.permissions.check_entity.return_value = False
        with pytest.raises(Unauthorized):
            await resolve_manager_targets(call, hass)


@pytest.mark.asyncio
async def test_backend_version_change_invalidates_capability_cache(hass, api):
    from custom_components.bedrock_server_manager.coordinator import (
        ManagerDataCoordinator,
    )

    api.discovery = SimpleNamespace(discover=AsyncMock(return_value={}))
    api.application.async_get_info = AsyncMock(
        return_value={"info": {"app_version": "4.0.0b2"}}
    )
    api.players.async_get_players = AsyncMock(return_value={"players": []})
    api.content.async_get_content_worlds = AsyncMock(return_value={"files": []})
    api.content.async_get_content_addons = AsyncMock(return_value={"files": []})
    api.plugins.async_get_plugin_statuses = AsyncMock(return_value={"plugins": {}})
    coordinator = ManagerDataCoordinator(hass, api, 60)
    await coordinator.async_refresh()
    api.application.async_get_info.return_value = {"info": {"app_version": "4.0.0b3"}}
    await coordinator.async_refresh()
    assert coordinator._discovered is False
    await coordinator.async_refresh()
    assert api.discovery.discover.await_count == 2
    api.discovery.discover.assert_awaited_with(force=True)


@pytest.mark.asyncio
async def test_unrelated_resources_do_not_change_settings_revision(hass, api):
    from custom_components.bedrock_server_manager.coordinator import (
        MinecraftBedrockCoordinator,
    )
    from tests.test_coordinator import server_api

    coordinator = MinecraftBedrockCoordinator(hass, server_api(api), "test", 30)
    await coordinator.async_refresh()
    revision = coordinator.resource_revisions["server_settings"]
    coordinator.invalidate({}, {"server_bans"})
    await coordinator.async_refresh()
    assert coordinator.resource_revisions["server_settings"] == revision
    coordinator.invalidate({}, {"server_settings"})
    assert coordinator.resource_revisions["server_settings"] > revision


@pytest.mark.asyncio
async def test_audit_filter_preserves_backend_newest_first_order():
    rows = [
        {"id": 3, "action": "start"},
        {"id": 2, "action": "stop"},
        {"id": 1, "action": "start"},
    ]
    api = SimpleNamespace(
        discovery=SimpleNamespace(
            discover=AsyncMock(return_value={"list_audit_logs": object()}),
            call=AsyncMock(return_value=rows),
        )
    )
    result = await _execute(
        api, ACTIONS["list_audit_logs"], {"action": "start", "limit": 1}, None
    )
    assert result == {"records": [rows[0]], "total_matches": 2, "truncated": True}


@pytest.mark.asyncio
async def test_failed_action_without_response_raises_instead_of_acknowledging(
    hass, api
):
    from homeassistant.exceptions import HomeAssistantError

    api.discovery = SimpleNamespace(
        discover=AsyncMock(return_value={}), call=AsyncMock()
    )
    hass.data[DOMAIN] = {
        "entry": {"api": api, "manager_identifier": (DOMAIN, "http://host")}
    }
    with patch(
        "custom_components.bedrock_server_manager.operational_services.resolve_manager_targets",
        AsyncMock(return_value=["entry"]),
    ):
        with pytest.raises(HomeAssistantError, match="does not support"):
            await operational_action(
                hass, ServiceCall(hass, DOMAIN, "get_web_runtime", {})
            )


@pytest.mark.asyncio
async def test_unavailable_diagnostic_sections_do_not_become_zero(hass, api):
    coordinator = ApplicationMonitorCoordinator(hass, api)
    data = {}
    coordinator._apply_result(
        data,
        "diagnostics",
        {
            "summary": {"status": "unknown"},
            "sections": [
                {
                    "status": "unavailable",
                    "data": {"kind": "events", "activity": {"pending_workers": 0}},
                }
            ],
        },
        {"diagnostics": ""},
    )
    assert data["diagnostics"] == {
        "issue_count": None,
        "event_pending_workers": None,
        "delivery_failures": None,
    }
