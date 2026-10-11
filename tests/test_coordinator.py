"""Current contract serialization and HTTP/WebSocket ordering regressions."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from bsm_api_client import AuthError, CannotConnectError
from bsm_api_client.models import (
    AddonListResponse,
    AppInfoResponse,
    BackupFilesResponse,
    ContentListResponse,
    GetAllowlistResponse,
    GetPermissionsResponse,
    GetPropertiesResponse,
    GetServerBansResponse,
    ListAvailableAddonsResponse,
    PlayerListResponse,
    PluginStatusesResponse,
    ServerProcessInfoResponse,
    ServerSettingsResponse,
    ServerSummary,
)
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.bedrock_server_manager.coordinator import (
    ManagerDataCoordinator,
    MinecraftBedrockCoordinator,
)


def server_api(api):
    responses = {
        "async_get_server_process_info": ServerProcessInfoResponse(
            status="success", process_info=None, epoch="one", revision=1
        ),
        "async_get_server_settings": ServerSettingsResponse(
            status="success", settings={"settings": {"target_version": "LATEST"}}
        ),
        "async_get_server_allowlist": GetAllowlistResponse(
            status="success", players=[{"name": "Alex", "ignoresPlayerLimit": False}]
        ),
        "async_get_server_properties": GetPropertiesResponse(
            properties={"server-name": "Example"}, raw_content="server-name=Example"
        ),
        "async_get_server_permissions_data": GetPermissionsResponse(
            permissions=[{"name": "Alex", "xuid": "123", "permission_level": "member"}]
        ),
        "async_get_server_bans": GetServerBansResponse(
            bans=[{"player_name": "Blocked", "xuid": "321"}]
        ),
        "async_get_server_summary": ServerSummary(
            name="test", status="INSTALLED", version="1.21", epoch="one", revision=1
        ),
    }
    for method, response in responses.items():
        setattr(api.servers, method, AsyncMock(return_value=response))
    api.content.async_get_server_addons = AsyncMock(
        return_value=AddonListResponse(
            status="success", addons={"behavior_packs": [], "resource_packs": []}
        )
    )
    api.content.async_list_server_backups = AsyncMock(
        return_value=BackupFilesResponse(backups=["backup.zip"])
    )
    return api


@pytest.mark.asyncio
async def test_server_contracts_are_json_compatible(hass, api):
    coordinator = MinecraftBedrockCoordinator(hass, server_api(api), "test", 30)
    data = await coordinator._async_update_data()
    assert data["allowlist"][0]["name"] == "Alex"
    assert data["server_permissions"][0]["permission_level"] == "member"
    assert data["server_bans"][0]["player_name"] == "Blocked"
    assert data["world_backups"] == ["backup.zip"]
    assert data["server_addons"] == {"behavior_packs": [], "resource_packs": []}
    assert data["server_status"] == "INSTALLED"
    assert data["process_info"] is None


@pytest.mark.asyncio
async def test_manager_handles_available_addons_contract(hass, api):
    api.application.async_get_info = AsyncMock(
        return_value=AppInfoResponse(status="success", info={"app_version": "4"})
    )
    api.players.async_get_players = AsyncMock(
        return_value=PlayerListResponse(status="success", players=[])
    )
    api.content.async_get_content_worlds = AsyncMock(
        return_value=ContentListResponse(status="success", files=["world.mcworld"])
    )
    api.content.async_get_content_addons = AsyncMock(
        return_value=ListAvailableAddonsResponse(files=["pack.mcaddon"])
    )
    api.plugins.async_get_plugin_statuses = AsyncMock(
        return_value=PluginStatusesResponse(status="success", plugins={})
    )
    coordinator = ManagerDataCoordinator(hass, api, 600)
    data = await coordinator._async_update_data()
    assert data["available_addons"] == ["pack.mcaddon"]
    assert data["available_worlds"] == ["world.mcworld"]


@pytest.mark.asyncio
async def test_partial_failure_preserves_last_good_data(hass, api):
    coordinator = MinecraftBedrockCoordinator(hass, server_api(api), "test", 30)
    coordinator.async_set_updated_data(await coordinator._async_update_data())
    api.servers.async_get_server_allowlist.side_effect = CannotConnectError("offline")
    assert (await coordinator._async_update_data())["allowlist"] == coordinator.data[
        "allowlist"
    ]


@pytest.mark.asyncio
async def test_noncritical_auth_failure_triggers_reauthentication(hass, api):
    coordinator = MinecraftBedrockCoordinator(hass, server_api(api), "test", 30)
    api.servers.async_get_server_allowlist.side_effect = AuthError("expired")
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_process_failure_makes_server_unavailable(hass, api):
    coordinator = MinecraftBedrockCoordinator(hass, server_api(api), "test", 30)
    api.servers.async_get_server_process_info.side_effect = CannotConnectError(
        "offline"
    )
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_push_during_http_poll_preserves_live_process_and_configuration(
    hass, api
):
    coordinator = MinecraftBedrockCoordinator(hass, server_api(api), "test", 30)
    coordinator.async_set_updated_data(await coordinator._async_update_data())
    ready, release = asyncio.Event(), asyncio.Event()
    original = api.servers.async_get_server_process_info.return_value

    async def delayed(*args):
        ready.set()
        await release.wait()
        return original

    api.servers.async_get_server_process_info.side_effect = delayed
    task = asyncio.create_task(coordinator._async_update_data())
    await ready.wait()
    coordinator.update_process_info(
        {
            "epoch": "one",
            "revision": 2,
            "process_info": {"pid": 123, "cpu_percent": 1, "memory_mb": 80},
        }
    )
    release.set()
    data = await task
    assert data["process_info"]["pid"] == 123
    assert data["server_status"] == "RUNNING"
    assert data["properties"] == {"server-name": "Example"}
    coordinator.update_process_info(
        {"epoch": "one", "revision": 1, "process_info": None}
    )
    assert coordinator.data["process_info"]["pid"] == 123


@pytest.mark.asyncio
async def test_mutation_invalidates_http_request_already_in_flight(hass, api):
    coordinator = MinecraftBedrockCoordinator(hass, server_api(api), "test", 30)
    coordinator.async_set_updated_data(await coordinator._async_update_data())
    ready, release = asyncio.Event(), asyncio.Event()

    async def delayed(*args):
        ready.set()
        await release.wait()
        return GetPropertiesResponse(properties={"server-name": "old"}, raw_content="")

    api.servers.async_get_server_properties.side_effect = delayed
    task = asyncio.create_task(coordinator._async_update_data())
    await ready.wait()
    assert coordinator.invalidate({"epoch": "one", "revision": 2})
    release.set()
    assert (await task)["properties"] == {"server-name": "Example"}


@pytest.mark.asyncio
async def test_scoped_events_fetch_only_affected_resources_and_full_refresh_wins(
    hass, api
):
    server_api(api)
    coordinator = MinecraftBedrockCoordinator(hass, api, "test", 30)
    await coordinator.async_refresh()
    api.servers.async_get_server_process_info.reset_mock()
    api.servers.async_get_server_properties.reset_mock()
    coordinator.invalidate({}, {"properties"})
    await coordinator.async_refresh()
    api.servers.async_get_server_properties.assert_awaited_once()
    api.servers.async_get_server_process_info.assert_not_awaited()
    coordinator.invalidate({})
    coordinator.invalidate({}, {"properties"})
    await coordinator.async_refresh()
    api.servers.async_get_server_process_info.assert_awaited_once()


@pytest.mark.asyncio
async def test_optional_bans_skip_absent_runtime_capability(hass, api):

    from bsm_api_client.openapi import ApiCapabilities

    server_api(api)
    api.schema = {"openapi": "3.1.0"}
    api.capabilities = ApiCapabilities({})
    coordinator = MinecraftBedrockCoordinator(hass, api, "test", 30)
    await coordinator.async_refresh()
    api.servers.async_get_server_bans.assert_not_awaited()
    assert coordinator.data["server_bans"] == []


@pytest.mark.asyncio
async def test_resource_freshness_distinguishes_current_stale_and_unsupported(
    hass, api
):
    coordinator = MinecraftBedrockCoordinator(hass, server_api(api), "test", 30)
    await coordinator.async_refresh()
    assert (
        coordinator.resource_metadata("properties")["bsm_resource_state"] == "current"
    )
    previous = coordinator.resource_updated_at["properties"]
    api.servers.async_get_server_properties.side_effect = CannotConnectError("offline")
    coordinator.invalidate({}, {"properties"})
    await coordinator.async_refresh()
    metadata = coordinator.resource_metadata("properties")
    assert metadata == {"bsm_resource_state": "stale", "bsm_updated_at": previous}
    coordinator.unsupported_resources.add("server_bans")
    assert (
        coordinator.resource_metadata("server_bans")["bsm_resource_state"]
        == "unsupported"
    )
