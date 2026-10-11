"""Live envelope routing, task outcomes, connection lifecycle and subscriptions."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import callback

from custom_components.bedrock_server_manager.websocket import BsmWebSocketManager


def manager(hass, api):
    return BsmWebSocketManager(
        hass, api, Mock(), Mock(), ["selected"], "http://bsm", Mock(), Mock()
    )


@pytest.mark.asyncio
async def test_selected_process_and_application_metrics(hass, api):
    ws = manager(hass, api)
    payload = {"status": "success", "epoch": "a", "revision": 1, "process_info": None}
    ws._handle_message(
        {
            "type": "resource_update",
            "topic": "resource-monitor:selected",
            "data": payload,
        }
    )
    ws.update_server_process_info_callback.assert_called_once()
    ws._handle_message(
        {"type": "resource_update", "topic": "resource-monitor:other", "data": payload}
    )
    assert ws.update_server_process_info_callback.call_count == 1
    sample = {
        "timestamp": 1,
        "asyncio_task_count": 4,
        "background_task_count": 1,
        "loop_lag_ms": 2,
        "epoch": "a",
        "revision": 1,
    }
    ws._handle_message(
        {"type": "resource_update", "topic": "application-metrics", "data": sample}
    )
    assert (
        ws.update_application_metrics_callback.call_args.args[0]["asyncio_task_count"]
        == 4
    )
    ws.coordinator_refresh_callback.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event",
    [
        "after_set_server_setting",
        "after_server_players_change",
        "after_plugin_settings_update",
        "after_remove_server_ban",
    ],
)
async def test_mutation_stamp_comes_from_envelope(hass, api, event):
    ws = manager(hass, api)
    ws._handle_message(
        {
            "type": "event",
            "topic": f"event:{event}",
            "epoch": "a",
            "revision": 12,
            "data": {"server_name": "selected", "result": {"status": "success"}},
        }
    )
    topic, payload = ws.coordinator_refresh_callback.call_args.args
    assert topic == f"event:{event}"
    assert payload["epoch"] == "a" and payload["revision"] == 12
    ws.update_server_process_info_callback.assert_not_called()


@pytest.mark.asyncio
async def test_before_failed_and_ack_messages_do_not_refresh(hass, api):
    ws = manager(hass, api)
    for message in (
        {"type": "event", "topic": "event:before_server_start", "data": {}},
        {
            "type": "event",
            "topic": "event:after_server_start",
            "data": {"result": {"status": "error"}},
        },
        {"type": "ack", "topic": "event:after_server_start", "data": {}},
    ):
        ws._handle_message(message)
    ws.coordinator_refresh_callback.assert_not_called()


@pytest.mark.asyncio
async def test_tasks_expose_results_and_only_terminal_updates_refresh(hass, api):
    ws = manager(hass, api)
    events = []

    @callback
    def capture_task(event):
        events.append(event.data)

    hass.bus.async_listen("bedrock_server_manager_task_update", capture_task)
    for revision, status in (
        (1, "queued"),
        (2, "running"),
        (3, "completed"),
        (3, "completed"),
        (2, "running"),
    ):
        ws._handle_message(
            {
                "type": "task_update",
                "topic": "task:abc",
                "data": {
                    "id": "abc",
                    "status": status,
                    "message": "Done",
                    "epoch": "a",
                    "revision": revision,
                    "result": {"server_name": "selected", "outcome": "installed"},
                },
            }
        )
    await hass.async_block_till_done()
    assert [event["status"] for event in events] == ["queued", "running", "completed"]
    assert events[-1]["result"]["outcome"] == "installed"
    assert events[-1]["status"] == "completed"
    ws.coordinator_refresh_callback.assert_called_once()


@pytest.mark.asyncio
async def test_worker_subscribes_selected_topics_and_stops_cleanly(hass, api):
    ws = manager(hass, api)
    subscribed = asyncio.Event()
    client = Mock()
    client.subscribe = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    async def listen():
        subscribed.set()
        await asyncio.Event().wait()
        yield {}

    client.listen = listen
    api.websocket_connect.return_value = client
    await ws.async_start()
    await ws.async_start()
    await asyncio.wait_for(subscribed.wait(), 1)
    topics = [call.args[0] for call in client.subscribe.call_args_list]
    assert "resource-monitor:selected" in topics
    assert "application-metrics" in topics
    assert "*" not in topics
    api.websocket_connect.assert_awaited_once()
    await ws.async_stop()
    client.__aexit__.assert_awaited_once()
    assert not ws._is_connected
    assert ws._worker is None


@pytest.mark.asyncio
async def test_deleted_server_is_unsubscribed_and_removed_from_reconnect(hass, api):
    ws = manager(hass, api)
    ws.ws_client = Mock(unsubscribe=AsyncMock())
    ws._is_connected = True
    await ws.async_remove_server("selected")
    ws.ws_client.unsubscribe.assert_awaited_once_with("resource-monitor:selected")
    assert not ws.server_names
