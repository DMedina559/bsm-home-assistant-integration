"Typed SDK manager actions for HA services."

import json
import logging
from typing import Any, Dict, List, Optional

from bsm_api_client import BedrockServerManagerApi
from bsm_api_client.models import (
    AddPlayersPayload,
    PluginStatusSetPayload,
    SettingItemResponse,
    TriggerEventPayload,
)

from .action_common import _base_api_call_handler

_LOGGER = logging.getLogger(__name__)


async def _async_handle_add_global_players(
    api: BedrockServerManagerApi, players_data: List[str], manager_id: str
):
    payload = AddPlayersPayload(players=players_data)
    return await _base_api_call_handler(
        api.players.async_add_players(payload), "Add global players", manager_id
    )


async def _async_handle_scan_players(api: BedrockServerManagerApi, manager_id: str):
    return await _base_api_call_handler(
        api.players.async_scan_players(), "Scan players", manager_id
    )


async def _async_handle_set_plugin_enabled(
    api: BedrockServerManagerApi, plugin_name: str, enabled: bool, manager_id: str
):
    payload = PluginStatusSetPayload(enabled=enabled)
    return await _base_api_call_handler(
        api.plugins.async_set_plugin_status(plugin_name, payload),
        f"Set plugin '{plugin_name}' to {enabled}",
        manager_id,
    )


async def _async_handle_trigger_plugin_event(
    api: BedrockServerManagerApi,
    event_name: str,
    payload_dict: Optional[Dict[str, Any]],
    manager_id: str,
):
    payload = TriggerEventPayload(event_name=event_name, payload=payload_dict)
    return await _base_api_call_handler(
        api.plugins.async_trigger_plugin_event(payload),
        f"Trigger plugin event '{event_name}'",
        manager_id,
    )


async def _async_handle_set_global_setting(
    api: BedrockServerManagerApi, key: str, value: Any, manager_id: str
):
    parsed_value = value
    if isinstance(value, str):
        stripped_value = value.strip()
        if (
            stripped_value.startswith("{")
            and stripped_value.endswith("}")
            or (stripped_value.startswith("[") and stripped_value.endswith("]"))
        ):
            try:
                parsed_value = json.loads(stripped_value)
            except json.JSONDecodeError:
                _LOGGER.warning(
                    "Value for setting '%s' looked like JSON but failed to parse. Sending as string.",
                    key,
                )
    payload = SettingItemResponse(key=key, value=parsed_value)
    return await _base_api_call_handler(
        api.application.async_set_setting(payload),
        f"Set global setting '{key}'",
        manager_id,
    )


async def _async_handle_reload_global_settings(
    api: BedrockServerManagerApi, manager_id: str
):
    return await _base_api_call_handler(
        api.application.async_reload_settings(), "Reload global settings", manager_id
    )
