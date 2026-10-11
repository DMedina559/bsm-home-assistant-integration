"""Real HA entry setup, registry/platform registration, actions and unload."""

import json
from pathlib import Path
from types import MappingProxyType
from unittest.mock import AsyncMock, Mock, patch

import pytest
from bsm_api_client.models import (
    AppInfoResponse,
    ContentListResponse,
    GetApplicationHealthResponse,
    GetApplicationMetricsResponse,
    ListAvailableAddonsResponse,
    PlayerListResponse,
    PluginStatusesResponse,
    TaskAcceptedResponse,
)
from homeassistant import loader
from homeassistant.config_entries import ConfigEntries, ConfigEntry, ConfigEntryState
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from test_coordinator import server_api
from test_entities import sample

from custom_components.bedrock_server_manager.const import DOMAIN


@pytest.mark.asyncio
async def test_real_entry_registers_entities_actions_live_updates_and_unloads(
    hass, api
):
    """Mock network I/O, using HA itself for registries, entities and service calls."""
    component = Path(__file__).resolve().parents[1] / "custom_components" / DOMAIN
    manifest = json.loads((component / "manifest.json").read_text())
    # Dashboard dependencies are outside this platform test; transport contracts are local.
    loader.async_setup(hass)
    integration = loader.Integration(
        hass,
        f"custom_components.{DOMAIN}",
        component,
        {**manifest, "dependencies": [], "requirements": []},
        top_level_files={p.name for p in component.iterdir()},
    )
    hass.data[loader.DATA_INTEGRATIONS] = {DOMAIN: integration}
    hass.config_entries = ConfigEntries(hass, {})
    await ar.async_load(hass, load_empty=True)
    dr.async_setup(hass)
    await dr.async_load(hass, load_empty=True)
    await er.async_load(hass, load_empty=True)
    entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Test BSM",
        data={"base_url": "http://host", "username": "test", "password": "secret"},
        options={"servers": ["test"]},
        source="user",
        unique_id="host",
        discovery_keys=MappingProxyType({}),
        subentries_data=[],
    )
    server_api(api)
    api.application.async_get_info = AsyncMock(
        return_value=AppInfoResponse(
            status="success", info={"app_version": "4", "os_type": "linux"}
        )
    )
    api.application.async_get_application_health = AsyncMock(
        return_value=GetApplicationHealthResponse(
            checked_at=1700000000, checks={}, health="healthy", lifecycle="ready"
        )
    )
    api.application.async_get_application_metrics = AsyncMock(
        return_value=GetApplicationMetricsResponse(
            latest={**sample(), "app_cpu_percent": 1},
            history=[],
            history_limit=180,
            interval_seconds=3,
        )
    )
    api.players.async_get_players = AsyncMock(
        return_value=PlayerListResponse(status="success", players=[])
    )
    api.content.async_get_content_worlds = AsyncMock(
        return_value=ContentListResponse(status="success", files=[])
    )
    api.content.async_get_content_addons = AsyncMock(
        return_value=ListAvailableAddonsResponse(status="success", files=[])
    )
    api.plugins.async_get_plugin_statuses = AsyncMock(
        return_value=PluginStatusesResponse(status="success", plugins={})
    )
    api.servers.async_update_server = AsyncMock(
        return_value=TaskAcceptedResponse(task_id="update-task", message="Queued")
    )
    api.servers.async_restart_server = AsyncMock()
    api.content.async_trigger_server_backup = AsyncMock(
        return_value=TaskAcceptedResponse(task_id="backup-task", message="Queued")
    )
    with patch(
        f"custom_components.{DOMAIN}.BedrockServerManagerApi", return_value=api
    ), patch(
        f"custom_components.{DOMAIN}.async_get_clientsession", return_value=Mock()
    ), patch(
        f"custom_components.{DOMAIN}.BsmFrontendRegistration.async_register",
        AsyncMock(),
    ), patch(
        f"custom_components.{DOMAIN}.BsmFrontendRegistration.async_unregister",
        AsyncMock(),
    ), patch(
        f"custom_components.{DOMAIN}.BsmWebSocketManager.async_start", AsyncMock()
    ):
        await hass.config_entries.async_add(entry)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        registry = er.async_get(hass)
        owned = [
            entity
            for entity in registry.entities.values()
            if entity.config_entry_id == entry.entry_id
        ]
        assert {entity.domain for entity in owned} == {
            "sensor",
            "binary_sensor",
            "switch",
            "text",
            "button",
        }
        status = next(
            entity
            for entity in owned
            if entity.domain == "sensor" and entity.unique_id.endswith("_status")
        )
        assert hass.states.get(status.entity_id).attributes["bsm_key"] == "status"
        result = await hass.services.async_call(
            DOMAIN,
            "trigger_backup",
            {"entity_id": status.entity_id, "backup_type": "all"},
            blocking=True,
            return_response=True,
        )
        assert result["results"][0]["result"]["task_id"] == "backup-task"
        updated = await hass.services.async_call(
            DOMAIN,
            "update_server",
            {"entity_id": status.entity_id},
            blocking=True,
            return_response=True,
        )
        assert updated["results"][0]["result"]["task_id"] == "update-task"
        api.servers.async_update_server.assert_awaited_once_with("test")
        coordinator = hass.data[DOMAIN][entry.entry_id]["monitor_coordinator"]
        coordinator.update_metrics(
            {
                "timestamp": 1700000001,
                "app_cpu_percent": 5,
                "app_ram_mb": 110,
                "epoch": "a",
                "revision": 2,
            }
        )
        await hass.async_block_till_done()
        cpu = next(
            entity for entity in owned if entity.unique_id.endswith("_app_cpu_percent")
        )
        assert hass.states.get(cpu.entity_id).state == "5"
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get(cpu.entity_id).state == "5"
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert not hass.services.has_service(DOMAIN, "trigger_backup")
        assert not hass.services.has_service(DOMAIN, "update_server")
        assert not hass.services.has_service(DOMAIN, "reload_plugins")
        assert DOMAIN not in hass.data
        api.close.assert_awaited_once()
