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
        data={"plugins_status": {"backup": {"has_settings": True}}},
        invalidate=Mock(),
        async_request_refresh=AsyncMock(),
    )
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
            {"key": "monitor.app_interval_seconds", "value": 3}
        )["value"]
        == 3
    )


@pytest.mark.asyncio
async def test_global_settings_action_receives_manager_context_and_refreshes(hass, api):
    from custom_components.bedrock_server_manager.services import (
        _async_handle_set_global_setting,
        _execute_manager_targeted_service,
    )

    coordinator = SimpleNamespace(invalidate=Mock(), async_request_refresh=AsyncMock())
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
            "monitor.app_interval_seconds",
            3,
        )
    assert api.application.async_set_setting.call_args.args[0].value == 3
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
