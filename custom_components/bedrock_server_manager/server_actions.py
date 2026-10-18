"Typed SDK server actions for HA services."

import asyncio
import logging
from typing import Any, Dict, List

from bsm_api_client import BedrockServerManagerApi
from bsm_api_client.models import (
    AllowlistAddPayload,
    AllowlistRemovePayload,
    BanAddRequest,
    BanRemoveRequest,
    CommandPayload,
    PermissionsSetPayload,
    PlayerPermissionPayload,
    PropertiesPayload,
    ServerSettingItemPayload,
)

from .action_common import _base_api_call_handler

_LOGGER = logging.getLogger(__name__)


async def _async_handle_send_command(
    api: BedrockServerManagerApi, server: str, command: str
):
    payload = CommandPayload(command=command)
    return await _base_api_call_handler(
        api.servers.async_send_server_command(server, payload), "Send command", server
    )


async def _async_handle_restore_latest_all(api: BedrockServerManagerApi, server: str):
    return await _base_api_call_handler(
        api.content.async_restore_server_latest_all(server),
        "Restore latest all",
        server,
    )


async def _async_handle_add_to_allowlist(
    api: BedrockServerManagerApi, server: str, players: List[str], ignore_limit: bool
):
    payload = AllowlistAddPayload(players=players, ignoresPlayerLimit=ignore_limit)
    return await _base_api_call_handler(
        api.servers.async_add_server_allowlist(server, payload),
        "Add to allowlist",
        server,
    )


async def _async_handle_remove_from_allowlist(
    api: BedrockServerManagerApi, server: str, players: List[str]
):
    payload = AllowlistRemovePayload(players=players)
    return await _base_api_call_handler(
        api.servers.async_remove_server_allowlist_players(server, payload),
        "Remove from allowlist",
        server,
    )


async def _async_handle_add_server_ban(
    api: BedrockServerManagerApi,
    server: str,
    player_name: str,
    xuid: str,
    reason: str | None,
):
    payload = BanAddRequest(player_name=player_name, xuid=xuid, reason=reason)
    return await _base_api_call_handler(
        api.servers.async_add_server_ban(server, payload), "Add server ban", server
    )


async def _async_handle_remove_server_ban(
    api: BedrockServerManagerApi, server: str, xuid: str
):
    payload = BanRemoveRequest(xuid=xuid)
    return await _base_api_call_handler(
        api.servers.async_remove_server_ban(server, payload),
        "Remove server ban",
        server,
    )


async def _async_handle_set_permissions(
    api: BedrockServerManagerApi, server: str, permissions_list: List[Dict[str, str]]
):
    permissions = [PlayerPermissionPayload.model_validate(p) for p in permissions_list]
    payload = PermissionsSetPayload(permissions=permissions)
    return await _base_api_call_handler(
        api.servers.async_set_server_permissions(server, payload),
        "Set permissions",
        server,
    )


async def _async_handle_update_properties(
    api: BedrockServerManagerApi, server: str, properties_dict: Dict[str, Any]
):
    payload = PropertiesPayload(
        properties={
            key: str(value).lower() if isinstance(value, bool) else str(value)
            for key, value in properties_dict.items()
        }
    )
    return await _base_api_call_handler(
        api.servers.async_update_server_properties(server, payload),
        "Update properties",
        server,
    )


async def _async_handle_configure_os_service(
    api: BedrockServerManagerApi,
    server: str,
    payload_dict: Dict[str, bool],
    manager_id: str,
):
    tasks = []
    for k, v in payload_dict.items():
        setting_key = f"settings.{k}"
        payload = ServerSettingItemPayload(key=setting_key, value=v)
        tasks.append(
            _base_api_call_handler(
                api.servers.async_set_server_setting(server, payload),
                f"Configure OS service ({k})",
                f"{server} on manager '{manager_id}'",
            )
        )
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            raise result
    return results[-1] if results else None
