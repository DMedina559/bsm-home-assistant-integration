"""Typed action payloads, task completion and multi-server HA targeting."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from bsm_api_client.models import (
    GetPluginSettingsResponse,
    TaskAcceptedResponse,
    TaskSnapshot,
)
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.bedrock_server_manager.const import DOMAIN
from custom_components.bedrock_server_manager.coordinator import BsmCoordinator
from custom_components.bedrock_server_manager.data_services import settings_action
from custom_components.bedrock_server_manager.services import (
    _async_handle_restore_latest_all,
    _async_handle_update_properties,
    _await_task_completion,
)
from custom_components.bedrock_server_manager.targets import (
    resolve_manager_targets,
    resolve_server_targets,
)


@pytest.mark.asyncio
async def test_restore_latest_all_uses_dedicated_operation(api):
    api.content.async_restore_server_latest_all = AsyncMock(
        return_value=TaskAcceptedResponse(message="Queued", task_id="abc")
    )
    result = await _async_handle_restore_latest_all(api, "server")
    assert result.task_id == "abc"
    api.content.async_restore_server_latest_all.assert_awaited_once_with("server")


@pytest.mark.asyncio
async def test_properties_payload_matches_string_contract(api):
    api.servers.async_update_server_properties = AsyncMock()
    await _async_handle_update_properties(
        api, "server", {"allow-cheats": False, "max-players": 10}
    )
    payload = api.servers.async_update_server_properties.call_args.args[1]
    assert payload.properties == {"allow-cheats": "false", "max-players": "10"}


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["completed", "failed", "cancelled"])
async def test_destructive_actions_wait_for_actual_task_outcome(api, status):
    accepted = TaskAcceptedResponse(message="Queued", task_id="abc")
    snapshot = TaskSnapshot(id="abc", status=status, message="Outcome")
    api.tasks.async_get_task_status.return_value = snapshot
    if status == "completed":
        assert await _await_task_completion(api, accepted) == snapshot
    else:
        with pytest.raises(HomeAssistantError, match="Outcome"):
            await _await_task_completion(api, accepted)


@pytest.mark.asyncio
async def test_multiple_servers_from_same_manager_are_not_discarded(hass):
    hass.data[DOMAIN] = {
        "entry": {
            "manager_identifier": (DOMAIN, "http://host"),
            "servers": {"a": {}, "b": {}},
        }
    }
    devices = {
        name: SimpleNamespace(
            id=name,
            identifiers={(DOMAIN, "http://host_" + name)},
            config_entries={"entry"},
        )
        for name in ("a", "b")
    }
    registry = Mock()
    registry.async_get.side_effect = devices.get
    call = ServiceCall(hass, DOMAIN, "send_command", {"device_id": ["a", "b"]})
    with patch(
        "custom_components.bedrock_server_manager.targets.dr.async_get",
        return_value=registry,
    ), patch(
        "custom_components.bedrock_server_manager.targets.er.async_get",
        return_value=Mock(),
    ):
        assert await resolve_server_targets(call, hass) == [
            ("entry", "a"),
            ("entry", "b"),
        ]


@pytest.mark.asyncio
async def test_manager_action_can_target_a_sensor_entity(hass):
    hass.data[DOMAIN] = {"entry": {}}
    entity = SimpleNamespace(platform=DOMAIN, domain="sensor", config_entry_id="entry")
    registry = Mock()
    registry.async_get.return_value = entity
    call = ServiceCall(
        hass, DOMAIN, "scan_players", {"entity_id": "sensor.bsm_players"}
    )
    with patch(
        "custom_components.bedrock_server_manager.targets.er.async_get",
        return_value=registry,
    ), patch(
        "custom_components.bedrock_server_manager.targets.dr.async_get",
        return_value=Mock(),
    ):
        assert await resolve_manager_targets(call, hass) == ["entry"]


@pytest.mark.asyncio
async def test_plugin_settings_use_typed_payloads_and_return_schema(hass, api):
    coordinator = SimpleNamespace(
        hass=hass,
        api=api,
        data={"plugins_status": {"backup": {"has_settings": True}}},
        invalidate=Mock(),
        async_request_refresh=AsyncMock(),
    )
    coordinator.schedule_refresh = lambda: BsmCoordinator.schedule_refresh(coordinator)
    hass.data[DOMAIN] = {
        "entry": {
            "api": api,
            "manager_coordinator": coordinator,
            "manager_identifier": (DOMAIN, "http://host"),
        }
    }
    api.plugins.async_update_plugin_settings = AsyncMock()
    api.plugins.async_get_plugin_settings = AsyncMock(
        return_value=GetPluginSettingsResponse(
            settings={"servers": ["a"]}, settings_schema={"type": "object"}
        )
    )
    call = ServiceCall(
        hass,
        DOMAIN,
        "update_plugin_settings",
        {"plugin_name": "backup", "settings": {"servers": ["a"]}},
    )
    with patch(
        "custom_components.bedrock_server_manager.data_services.resolve_manager_targets",
        AsyncMock(return_value={"entry"}),
    ):
        result = await settings_action(hass, call)
        assert result["managers"][0]["settings_schema"] == {"type": "object"}
        assert api.plugins.async_update_plugin_settings.call_args.args[1].settings == {
            "servers": ["a"]
        }
        coordinator.data["plugins_status"]["backup"]["has_settings"] = False
        with pytest.raises(ServiceValidationError):
            await settings_action(hass, call)


@pytest.mark.asyncio
async def test_service_registry_exposes_missing_actions_and_validates_typed_values(
    hass,
):
    from custom_components.bedrock_server_manager import services
    from custom_components.bedrock_server_manager.service_schemas import (
        SET_GLOBAL_SETTING_SERVICE_SCHEMA,
    )

    await services.async_register_services(hass)
    for name in (
        "scan_players",
        "reset_world",
        "get_plugin_settings",
        "update_plugin_settings",
        "trigger_backup",
    ):
        assert hass.services.has_service(DOMAIN, name)
    assert (
        SET_GLOBAL_SETTING_SERVICE_SCHEMA(
            {"key": "monitoring.app_metrics_interval_sec", "value": 3}
        )["value"]
        == 3
    )


@pytest.mark.asyncio
async def test_global_settings_action_receives_manager_context_and_refreshes(hass, api):
    from custom_components.bedrock_server_manager.services import (
        _async_handle_set_global_setting,
        _execute_manager_targeted_service,
    )

    coordinator = SimpleNamespace(
        hass=hass, api=api, invalidate=Mock(), async_request_refresh=AsyncMock()
    )
    coordinator.schedule_refresh = lambda: BsmCoordinator.schedule_refresh(coordinator)
    hass.data[DOMAIN] = {
        "entry": {
            "api": api,
            "manager_identifier": (DOMAIN, "http://host"),
            "manager_coordinator": coordinator,
        }
    }
    api.application.async_set_setting = AsyncMock()
    call = ServiceCall(hass, DOMAIN, "set_global_setting", {})
    with patch(
        "custom_components.bedrock_server_manager.services.resolve_manager_targets",
        AsyncMock(return_value=["entry"]),
    ):
        await _execute_manager_targeted_service(
            call,
            hass,
            _async_handle_set_global_setting,
            "monitoring.app_metrics_interval_sec",
            3,
        )
    assert api.application.async_set_setting.call_args.args[0].value == 3
    await hass.async_block_till_done()
    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_actions_are_reported_to_ha(hass, api):
    from custom_components.bedrock_server_manager.services import (
        _execute_manager_targeted_service,
    )

    hass.data[DOMAIN] = {
        "entry": {"api": api, "manager_identifier": (DOMAIN, "http://host")}
    }
    call = ServiceCall(hass, DOMAIN, "action", {})

    async def failed(api):
        raise HomeAssistantError("Unavailable")

    with patch(
        "custom_components.bedrock_server_manager.services.resolve_manager_targets",
        AsyncMock(return_value=["entry"]),
    ):
        with pytest.raises(HomeAssistantError, match="Unavailable"):
            await _execute_manager_targeted_service(call, hass, failed)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["partial", "skipped"])
async def test_completed_destructive_task_does_not_confirm_incomplete_work(api, status):
    from custom_components.bedrock_server_manager.action_common import (
        OperationOutcomeError,
    )

    accepted = TaskAcceptedResponse(message="Queued", task_id="abc")
    api.tasks.async_get_task_status.return_value = TaskSnapshot(
        id="abc",
        status="completed",
        message="Task finished",
        result={
            "status": status,
            "message": "Cleanup incomplete",
            "server_name": "test",
        },
    )
    with pytest.raises(OperationOutcomeError, match=f"Operation {status}") as error:
        await _await_task_completion(api, accepted)
    assert error.value.result["result"]["status"] == status


@pytest.mark.asyncio
async def test_partial_scan_preserves_results_and_requires_refresh(api):
    from bsm_api_client.models import AddPlayersResponse

    from custom_components.bedrock_server_manager.action_common import (
        OperationOutcomeError,
    )
    from custom_components.bedrock_server_manager.manager_actions import (
        _async_handle_scan_players,
    )
    from custom_components.bedrock_server_manager.services import (
        _applied_work,
        _outcome,
    )

    api.players.async_scan_players = AsyncMock(
        return_value=AddPlayersResponse(
            status="partial",
            message="One log unavailable",
            details={
                "total_entries_in_logs": 1,
                "unique_players_submitted_for_saving": 1,
                "actually_saved_or_updated_in_db": 1,
                "scan_errors": [
                    {
                        "server": "test",
                        "error": {
                            "code": "file_error",
                            "message": "Log unavailable",
                            "details": {},
                        },
                    }
                ],
            },
        )
    )
    with pytest.raises(OperationOutcomeError) as error:
        await _async_handle_scan_players(api, "http://host")
    assert _applied_work(error.value)
    assert (
        _outcome(error.value)["result"]["details"]["scan_errors"][0]["error"]["code"]
        == "file_error"
    )


@pytest.mark.asyncio
async def test_committed_api_error_preserves_details_and_refreshes():
    from bsm_api_client import APIServerSideError

    from custom_components.bedrock_server_manager.action_common import (
        _base_api_call_handler,
    )
    from custom_components.bedrock_server_manager.services import (
        _applied_work,
        _outcome,
    )

    async def call():
        raise APIServerSideError(
            "Operation incomplete",
            status_code=500,
            response_data={
                "error": {
                    "code": "operation_incomplete",
                    "message": "Operation incomplete",
                    "details": {
                        "result": {
                            "committed": True,
                            "resource": "account",
                            "action": "update_account",
                        }
                    },
                }
            },
        )

    with pytest.raises(HomeAssistantError, match="change was saved") as error:
        await _base_api_call_handler(call(), "Update account")
    assert _applied_work(error.value)
    outcome = _outcome(error.value)
    assert outcome["error"]["code"] == "operation_incomplete"
    assert outcome["result"]["committed"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action,path,body,response",
    [
        (
            "command",
            "/api/server/test/send_command",
            {"command": "say hello"},
            {"status": "success", "message": "Sent", "server_name": "test"},
        ),
        (
            "properties",
            "/api/server/test/properties/set",
            {"properties": {"server-name": "Example"}},
            {"status": "success", "message": "Saved", "server_name": "test"},
        ),
        (
            "add",
            "/api/server/test/allowlist/add",
            {"players": ["Alex"], "ignoresPlayerLimit": False},
            {"status": "success", "message": "Added", "added_count": 1},
        ),
        (
            "remove",
            "/api/server/test/allowlist/remove",
            {"players": ["Alex"]},
            {
                "status": "success",
                "message": "Removed",
                "details": {"removed": ["Alex"], "not_found": []},
            },
        ),
    ],
)
async def test_server_actions_preserve_generated_http_contract(
    action, path, body, response
):
    import json

    import httpx
    from bsm_api_client import BedrockServerManagerApi

    from custom_components.bedrock_server_manager.coordinator import json_data
    from custom_components.bedrock_server_manager.server_actions import (
        _async_handle_add_to_allowlist,
        _async_handle_remove_from_allowlist,
        _async_handle_send_command,
    )

    async def respond(request):
        assert request.url.path == path
        assert json.loads(request.content) == body
        return httpx.Response(200, json=response)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as transport:
        async with BedrockServerManagerApi(
            "http://host", jwt_token="token", http_client=transport
        ) as client:
            if action == "command":
                result = await _async_handle_send_command(client, "test", "say hello")
            elif action == "properties":
                result = await _async_handle_update_properties(
                    client, "test", {"server-name": "Example"}
                )
            elif action == "add":
                result = await _async_handle_add_to_allowlist(
                    client, "test", ["Alex"], False
                )
            else:
                result = await _async_handle_remove_from_allowlist(
                    client, "test", ["Alex"]
                )
    assert json_data(result) == response


@pytest.mark.asyncio
@pytest.mark.parametrize("return_response", [False, True])
async def test_partial_actions_refresh_and_return_details_only_when_requested(
    hass, return_response
):
    from custom_components.bedrock_server_manager.action_common import (
        OperationOutcomeError,
    )
    from custom_components.bedrock_server_manager.services import (
        _execute_manager_targeted_service,
    )

    coordinator = Mock()
    hass.data[DOMAIN] = {
        "entry": {
            "api": Mock(),
            "manager_identifier": (DOMAIN, "http://host"),
            "manager_coordinator": coordinator,
        }
    }
    call = ServiceCall(
        hass, DOMAIN, "scan_players", {}, return_response=return_response
    )
    handler = AsyncMock(
        side_effect=OperationOutcomeError(
            "Operation partially completed",
            {
                "status": "partial",
                "message": "One log unavailable",
                "details": {"saved": 1},
            },
        )
    )
    with patch(
        "custom_components.bedrock_server_manager.services.resolve_manager_targets",
        AsyncMock(return_value=["entry"]),
    ), patch(
        "custom_components.bedrock_server_manager.services.refresh_after_action"
    ) as refresh:
        if return_response:
            response = await _execute_manager_targeted_service(call, hass, handler)
            assert response["results"][0]["result"]["details"]["saved"] == 1
            assert (
                response["results"][0]["error"]["message"]
                == "Operation partially completed"
            )
        else:
            with pytest.raises(HomeAssistantError, match="partially completed"):
                await _execute_manager_targeted_service(call, hass, handler)
        refresh.assert_any_call(coordinator)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["partial", "skipped"])
async def test_incomplete_delete_keeps_home_assistant_device(hass, api, status):
    from custom_components.bedrock_server_manager.services import (
        _async_handle_delete_server,
    )

    api.servers.async_delete_server = AsyncMock(
        return_value=TaskAcceptedResponse(task_id="abc", message="Queued")
    )
    api.tasks.async_get_task_status.return_value = TaskSnapshot(
        id="abc",
        status="completed",
        message="Task finished",
        result={"status": status, "message": "Deletion not complete"},
    )
    with patch(
        "custom_components.bedrock_server_manager.services.dr.async_get"
    ) as registry:
        with pytest.raises(HomeAssistantError, match=f"Operation {status}"):
            await _async_handle_delete_server(hass, api, "test", "http://host")
        registry.assert_not_called()
