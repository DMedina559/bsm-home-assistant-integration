"""Current backup, scheduler and scoped settings contracts reach the backend intact."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import ServiceCall
from homeassistant.exceptions import ServiceValidationError

from custom_components.bedrock_server_manager.const import DOMAIN
from custom_components.bedrock_server_manager.data_services import settings_action
from custom_components.bedrock_server_manager.operational_services import (
    ACTIONS,
    _execute,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,values,server,expected",
    [
        (
            "create_server_snapshot",
            {"mode": "selected", "components": ["world"]},
            "alpha",
            {
                "path_params": {"server_name": "alpha"},
                "json_data": {"mode": "selected", "components": ["world"]},
            },
        ),
        (
            "plan_snapshot_restore",
            {"backup_id": "archive", "components": ["bsm_settings"]},
            "alpha",
            {
                "path_params": {"server_name": "alpha", "backup_id": "archive"},
                "json_data": {"components": ["bsm_settings"]},
            },
        ),
        (
            "restore_server_snapshot",
            {"backup_id": "archive", "components": ["world"], "token": "reviewed"},
            "alpha",
            {
                "path_params": {"server_name": "alpha", "backup_id": "archive"},
                "json_data": {"components": ["world"], "token": "reviewed"},
            },
        ),
        (
            "save_schedule",
            {
                "schedule_id": "nightly",
                "configuration": {"task": "verify", "timezone": "America/Los_Angeles"},
            },
            None,
            {
                "path_params": {"schedule_id": "nightly"},
                "json_data": {"task": "verify", "timezone": "America/Los_Angeles"},
            },
        ),
        (
            "delete_schedule",
            {"schedule_id": "nightly"},
            None,
            {"path_params": {"schedule_id": "nightly"}},
        ),
        (
            "list_schedules",
            {"server_name": "alpha"},
            None,
            {"path_params": {}, "query": {"server_name": "alpha"}},
        ),
        (
            "manage_server_snapshot",
            {"backup_id": "archive", "action": "verify"},
            "alpha",
            {
                "path_params": {"server_name": "alpha", "backup_id": "archive"},
                "json_data": {"action": "verify"},
            },
        ),
    ],
)
async def test_current_actions_route_only_contract_fields(
    name, values, server, expected
):
    api = SimpleNamespace(
        discovery=SimpleNamespace(
            discover=AsyncMock(return_value={name: object()}),
            call=AsyncMock(return_value={}),
        )
    )
    await _execute(
        api, ACTIONS[name], {**values, "entity_id": "sensor.private"}, server
    )
    api.discovery.call.assert_awaited_once_with(name, authenticated=True, **expected)


@pytest.mark.asyncio
@pytest.mark.parametrize("scope,server", [("global", None), ("server", "alpha")])
async def test_scoped_settings_save_and_followup_keep_scope(hass, scope, server):
    coordinator = SimpleNamespace(
        data={
            "plugins_status": {
                "profile": {"has_global_settings": True, "has_server_settings": True}
            }
        },
        invalidate=Mock(),
        schedule_refresh=Mock(),
        api=SimpleNamespace(),
    )
    api = SimpleNamespace(
        discovery=SimpleNamespace(
            call=AsyncMock(
                side_effect=[
                    {"status": "success"},
                    {
                        "settings": {"enabled": True},
                        "settings_schema": {"type": "object"},
                    },
                ]
            )
        )
    )
    hass.data[DOMAIN] = {
        "entry": {
            "api": api,
            "manager_coordinator": coordinator,
            "manager_identifier": (DOMAIN, "http://host"),
        }
    }
    options = {"scope": scope, **({"server_name": server} if server else {})}
    call = ServiceCall(
        hass,
        DOMAIN,
        "update_plugin_settings",
        {"plugin_name": "profile", "settings": {"enabled": True}, **options},
    )
    with patch(
        "custom_components.bedrock_server_manager.data_services.resolve_manager_targets",
        AsyncMock(return_value={"entry"}),
    ):
        response = await settings_action(hass, call)
    calls = api.discovery.call.await_args_list
    assert calls[0].kwargs["json_data"] == {"settings": {"enabled": True}, **options}
    assert calls[1].kwargs["query"] == options
    assert response["managers"][0]["scope"] == scope


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "options", [{"scope": "server"}, {"scope": "global", "server_name": "alpha"}]
)
async def test_invalid_scope_target_pair_fails_before_target_resolution(hass, options):
    call = ServiceCall(
        hass, DOMAIN, "get_plugin_settings", {"plugin_name": "profile", **options}
    )
    with pytest.raises(ServiceValidationError):
        await settings_action(hass, call)


@pytest.mark.asyncio
async def test_backup_transfer_rejects_disallowed_path_before_io(hass):
    api = SimpleNamespace(
        discovery=SimpleNamespace(
            discover=AsyncMock(return_value={"download_server_snapshot": object()})
        ),
        backups=SimpleNamespace(async_download_to=AsyncMock()),
    )
    with patch.object(hass.config, "is_allowed_path", return_value=False):
        with pytest.raises(ServiceValidationError):
            await _execute(
                api,
                ACTIONS["download_server_snapshot"],
                {"backup_id": "archive", "file_path": "/private/archive.bsmbackup"},
                "alpha",
                hass,
            )
    api.backups.async_download_to.assert_not_called()


@pytest.mark.asyncio
async def test_archive_import_closes_stream_after_backend_failure(hass, tmp_path):
    archive = tmp_path / "archive.bsmbackup"
    archive.write_bytes(b"archive")
    streams = []

    async def fail_import(server, stream, filename, key):
        assert stream.read() == b"archive"
        assert filename == "archive.bsmbackup"
        assert key == "recovery"
        streams.append(stream)
        raise ValueError("Invalid archive")

    api = SimpleNamespace(
        discovery=SimpleNamespace(
            discover=AsyncMock(return_value={"import_server_snapshot": object()})
        ),
        backups=SimpleNamespace(async_import=fail_import),
    )
    with patch.object(hass.config, "is_allowed_path", return_value=True):
        with pytest.raises(ValueError, match="Invalid archive"):
            await _execute(
                api,
                ACTIONS["import_server_snapshot"],
                {"file_path": str(archive), "recovery_key": "recovery"},
                "alpha",
                hass,
            )
    assert streams[0].closed


@pytest.mark.asyncio
async def test_archive_download_returns_path_without_buffering_content(hass, tmp_path):
    destination = tmp_path / "new.bsmbackup"
    api = SimpleNamespace(
        discovery=SimpleNamespace(
            discover=AsyncMock(return_value={"download_server_snapshot": object()})
        ),
        backups=SimpleNamespace(async_download_to=AsyncMock(return_value=destination)),
    )
    with patch.object(hass.config, "is_allowed_path", return_value=True):
        result = await _execute(
            api,
            ACTIONS["download_server_snapshot"],
            {"backup_id": "archive", "file_path": str(destination)},
            "alpha",
            hass,
        )
    api.backups.async_download_to.assert_awaited_once_with(
        "alpha", "archive", str(destination)
    )
    assert result == {"status": "success", "file_path": str(destination)}


def test_service_targets_follow_home_assistant_entity_filter_contract():
    """Hassfest prohibits device filters inside a service target declaration."""
    from pathlib import Path

    from homeassistant.helpers.selector import TargetSelector
    from homeassistant.util.yaml import load_yaml_dict

    services = load_yaml_dict(
        str(
            Path(__file__).parents[1]
            / "custom_components/bedrock_server_manager/services.yaml"
        )
    )
    for name, service in services.items():
        target = service.get("target")
        if target is None:
            continue
        assert "device" not in target, name
        TargetSelector.CONFIG_SCHEMA(target)


@pytest.mark.asyncio
async def test_schedule_controls_forward_revision_and_explicit_action():
    api = SimpleNamespace(
        discovery=SimpleNamespace(
            discover=AsyncMock(return_value={"control_schedule": object()}),
            call=AsyncMock(return_value={"status": "success"}),
        )
    )
    await _execute(
        api,
        ACTIONS["control_schedule"],
        {"schedule_id": "nightly", "action": "pause", "revision": "current"},
        None,
    )
    api.discovery.call.assert_awaited_once_with(
        "control_schedule",
        authenticated=True,
        path_params={"schedule_id": "nightly"},
        json_data={"action": "pause", "revision": "current"},
    )
