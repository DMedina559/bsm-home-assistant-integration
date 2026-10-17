"""Cover permissions, entry ownership and bounded live state found in the audit."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from bsm_api_client import AuthError
from homeassistant.core import Context, ServiceCall
from homeassistant.exceptions import HomeAssistantError, Unauthorized

from custom_components.bedrock_server_manager.const import DOMAIN
from custom_components.bedrock_server_manager.coordinator import (
    MinecraftBedrockCoordinator,
)
from custom_components.bedrock_server_manager.diagnostics import _redact_diagnostics
from custom_components.bedrock_server_manager.runtime import EntryRuntime
from custom_components.bedrock_server_manager.services import _execute_targeted_service
from custom_components.bedrock_server_manager.state import ResourceState
from custom_components.bedrock_server_manager.targets import (
    resolve_manager_targets,
    resolve_server_targets,
)
from tests.test_coordinator import server_api


@pytest.mark.asyncio
async def test_unload_cancels_action_before_transport_is_closed():
    runtime = EntryRuntime()
    entered = asyncio.Event()

    async def request():
        entered.set()
        await asyncio.Event().wait()

    transport = runtime.transport(
        SimpleNamespace(servers=SimpleNamespace(request=request))
    )
    task = asyncio.create_task(transport.servers.request())
    await entered.wait()
    await runtime.shutdown()
    assert task.cancelled()
    assert not runtime.tasks
    with pytest.raises(HomeAssistantError, match="unloading"):
        await transport.servers.request()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "target",
    [{"entity_id": "sensor.private"}, {"device_id": "private"}, {"area_id": "private"}],
)
async def test_server_actions_reject_restricted_ha_targets(hass, target):
    user = SimpleNamespace(
        is_admin=False,
        permissions=SimpleNamespace(check_entity=Mock(return_value=False)),
    )
    hass.data[DOMAIN] = {
        "entry": {"manager_identifier": (DOMAIN, "http://host"), "servers": {"a": {}}}
    }
    device = SimpleNamespace(
        id="private",
        area_id="private",
        identifiers={(DOMAIN, "http://host_a")},
        config_entries={"entry"},
    )
    devices = SimpleNamespace(
        async_get=Mock(return_value=device), devices={"private": device}
    )
    anchor = SimpleNamespace(
        platform=DOMAIN, unique_id="host_a_status", entity_id="sensor.private"
    )
    call = ServiceCall(
        hass, DOMAIN, "send_command", target, context=Context(user_id="restricted")
    )
    with patch.object(
        hass,
        "auth",
        SimpleNamespace(async_get_user=AsyncMock(return_value=user)),
        create=True,
    ), patch(
        "custom_components.bedrock_server_manager.targets.dr.async_get",
        return_value=devices,
    ), patch(
        "custom_components.bedrock_server_manager.targets.er.async_get",
        return_value=Mock(),
    ), patch(
        "custom_components.bedrock_server_manager.targets.er.async_entries_for_device",
        return_value=[anchor],
    ):
        with pytest.raises(Unauthorized):
            await resolve_server_targets(call, hass)


@pytest.mark.asyncio
async def test_dynamic_manager_calls_require_ha_admin(hass):
    user = SimpleNamespace(is_admin=False)
    call = ServiceCall(
        hass, DOMAIN, "call_operation", {}, context=Context(user_id="restricted")
    )
    with patch.object(
        hass,
        "auth",
        SimpleNamespace(async_get_user=AsyncMock(return_value=user)),
        create=True,
    ):
        with pytest.raises(Unauthorized):
            await resolve_manager_targets(call, hass)


def test_diagnostics_redact_current_nested_and_flattened_jwt_settings():
    entry = SimpleNamespace(data={"base_url": "http://private", "password": "password"})
    redacted = _redact_diagnostics(
        {
            "settings": {
                "web": {"jwt_secret_key": "nested-secret"},
                "web.jwt_secret_key": "flat-secret",
            }
        },
        entry,
    )
    assert "nested-secret" not in str(redacted)
    assert "flat-secret" not in str(redacted)


def test_revision_history_is_bounded_and_recent_tasks_reject_old_updates():
    state = ResourceState()
    for index in range(700):
        assert state.accept(f"task:{index}", {"epoch": "a", "revision": 3})
    assert len(state.revisions) == 500
    assert not state.accept("task:699", {"epoch": "a", "revision": 2})


@pytest.mark.asyncio
async def test_forbidden_resource_does_not_start_reauthentication(hass, api):
    server_api(api)
    api.servers.async_get_server_allowlist.side_effect = AuthError(
        "Forbidden", status_code=403
    )
    coordinator = MinecraftBedrockCoordinator(hass, api, "test", 30)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert (
        coordinator.resource_metadata("allowlist")["bsm_resource_state"] == "forbidden"
    )


@pytest.mark.asyncio
async def test_process_push_recovers_resource_availability(hass, api):
    server_api(api)
    coordinator = MinecraftBedrockCoordinator(hass, api, "test", 30)
    await coordinator.async_refresh()
    coordinator.unavailable_resources.add("process_info")
    coordinator.update_process_info(
        {"epoch": "one", "revision": 2, "process_info": {"pid": 123}}
    )
    assert "process_info" not in coordinator.unavailable_resources


@pytest.mark.asyncio
async def test_partial_success_preserves_accepted_task_and_failed_target(hass, api):
    hass.data[DOMAIN] = {
        "entry": {
            "api": api,
            "manager_identifier": (DOMAIN, "http://host"),
            "servers": {"a": {}, "b": {}},
        }
    }

    async def action(api, name):
        if name == "b":
            raise HomeAssistantError("Denied")
        return {"task_id": "accepted"}

    call = ServiceCall(hass, DOMAIN, "start_server", {})
    with patch(
        "custom_components.bedrock_server_manager.services.resolve_server_targets",
        AsyncMock(return_value=[("entry", "a"), ("entry", "b")]),
    ):
        response = await _execute_targeted_service(call, hass, action)
    assert response["results"][0]["result"]["task_id"] == "accepted"
    assert response["results"][1]["error"]["message"] == "Denied"


@pytest.mark.asyncio
async def test_action_response_survives_entry_removal_after_api_acceptance(hass, api):
    data = {
        "api": api,
        "manager_identifier": (DOMAIN, "http://host"),
        "servers": {"a": {}},
    }
    hass.data[DOMAIN] = {"entry": data}

    async def action(api, name):
        hass.data[DOMAIN].pop("entry")
        return {"task_id": "accepted"}

    call = ServiceCall(hass, DOMAIN, "start_server", {})
    with patch(
        "custom_components.bedrock_server_manager.services.resolve_server_targets",
        AsyncMock(return_value=[("entry", "a")]),
    ):
        response = await _execute_targeted_service(call, hass, action)
    assert response["results"][0]["manager_url"] == "http://host"
    assert response["results"][0]["result"]["task_id"] == "accepted"


@pytest.mark.asyncio
async def test_runtime_diagnostics_are_bounded_and_tolerate_non_admin_accounts():
    from bsm_api_client.models import EventDiagnostics, RuntimeStatus

    from custom_components.bedrock_server_manager.diagnostics import (
        _async_runtime_diagnostics,
    )

    api = SimpleNamespace(
        discovery=SimpleNamespace(
            call=AsyncMock(
                return_value={
                    "report_id": "report",
                    "snapshot": {"summary": {"ready": True}},
                }
            )
        ),
        application=SimpleNamespace(
            async_get_web_runtime=AsyncMock(
                return_value=RuntimeStatus(
                    instance_id="instance",
                    pid=123,
                    phase="ready",
                    shutdown_requested=False,
                )
            )
        ),
        events=SimpleNamespace(
            async_get_event_activity=AsyncMock(
                return_value=EventDiagnostics(
                    accepting=True,
                    emitted=0,
                    suppressed=0,
                    failed_listeners=0,
                    subscriptions=0,
                    active=[],
                    recent=[],
                )
            )
        ),
    )
    result = await _async_runtime_diagnostics(api)
    assert result["web"]["phase"] == "ready"
    assert result["backend"]["snapshot"]["summary"]["ready"] is True
    api.discovery.call.assert_awaited_once_with("get_diagnostic_report")
    api.events.async_get_event_activity.assert_awaited_once_with(limit=10)
    api.application.async_get_web_runtime.side_effect = AuthError(
        "Administrator required", status_code=403
    )
    api.discovery.call.side_effect = AuthError(
        "Administrator required", status_code=403
    )
    result = await _async_runtime_diagnostics(api)
    assert result["backend"] == {"available": False, "error_type": "AuthError"}
    assert result["web"] == {"available": False, "error_type": "AuthError"}
    assert result["events"]["recent"] == []
