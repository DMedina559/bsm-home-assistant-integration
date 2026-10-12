"""Reconnect, subscribe to selected servers, and dispatch current BSM envelopes."""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from bsm_api_client import BedrockServerManagerApi, WebSocketClient
from bsm_api_client.models import MetricsSample, ServerProcessInfoResponse, TaskSnapshot
from homeassistant.core import HomeAssistant
from pydantic import ValidationError

from .const import DOMAIN
from .state import ResourceState

_LOGGER = logging.getLogger(__name__)

SERVER_EVENTS = frozenset(
    {
        "after_server_start",
        "after_server_stop",
        "after_command_send",
        "after_server_status_change",
        "after_server_players_change",
        "after_set_server_setting",
        "after_properties_change",
        "after_permission_change",
        "after_allowlist_change",
        "after_add_server_ban",
        "after_remove_server_ban",
        "after_server_install",
        "after_server_update",
        "after_delete_server_data",
        "after_backup",
        "after_restore",
        "after_prune_backups",
        "after_world_export",
        "after_world_import",
        "after_world_reset",
        "after_addon_import",
        "after_addon_enable",
        "after_addon_disable",
        "after_addon_subpack_update",
        "after_addon_uninstall",
        "after_addon_reorder",
    }
)
MANAGER_EVENTS = frozenset(
    {
        "after_players_add",
        "after_player_db_scan",
        "after_set_plugin_status",
        "after_plugin_settings_update",
        "after_setting_update",
        "after_prune_download_cache",
        "after_server_install",
        "after_delete_server_data",
        "after_world_export",
    }
)
TERMINAL_TASK_STATUSES = frozenset({"completed", "failed", "cancelled"})


class BsmWebSocketManager:
    """Own one connection worker; restore subscriptions and reconcile on reconnect."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: BedrockServerManagerApi,
        coordinator_refresh_callback: Callable,
        update_server_process_info_callback: Callable,
        server_names: list[str],
        manager_url: str,
        update_application_metrics_callback: Callable,
        connection_callback: Callable,
    ) -> None:
        self.hass = hass
        self.api_client = api_client
        self.coordinator_refresh_callback = coordinator_refresh_callback
        self.update_server_process_info_callback = update_server_process_info_callback
        self.manager_url = manager_url
        self.update_application_metrics_callback = update_application_metrics_callback
        self.connection_callback = connection_callback
        self.server_names = frozenset(server_names)
        self.ws_client: WebSocketClient | None = None
        self._worker: asyncio.Task | None = None
        self._is_connected = False
        self._task_state = ResourceState()
        self._terminal_tasks: dict[str, str] = {}

    async def async_start(self) -> None:
        """Start the owned worker without blocking entry setup on connectivity."""
        if self._worker is None or self._worker.done():
            self._worker = self.hass.async_create_background_task(
                self._run(), "BSM WebSocket"
            )

    async def async_stop(self) -> None:
        """Cancel and await the worker before the SDK transports are closed."""
        if self._worker is not None:
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)
            self._worker = None
        self._is_connected = False

    async def async_remove_server(self, server_name: str) -> None:
        """Stop sampling a deleted server, including after future reconnects."""
        self.server_names = self.server_names - {server_name}
        if self.ws_client and self._is_connected:
            try:
                await self.ws_client.unsubscribe(f"resource-monitor:{server_name}")
            except Exception:
                _LOGGER.debug(
                    "Could not unsubscribe removed server; selection retained for reconnect",
                    exc_info=True,
                )

    async def _run(self) -> None:
        delay = 2
        while True:
            try:
                self.ws_client = await self.api_client.websocket_connect()
                async with self.ws_client:
                    # The wildcard receives future core/plugin events and owner task updates.
                    # Explicit resource topics still enable selected-server producers.
                    topics = ["*", "application-metrics"] + [
                        f"resource-monitor:{name}" for name in self.server_names
                    ]
                    for topic in topics:
                        await self.ws_client.subscribe(topic)
                    self._is_connected = True
                    self.connection_callback(True)
                    delay = 2
                    _LOGGER.info("Connected to BSM WebSocket")
                    self.coordinator_refresh_callback("reconnect", {})
                    async for message in self.ws_client.listen():
                        try:
                            self._handle_message(message)
                        except (KeyError, TypeError, ValueError):
                            _LOGGER.debug(
                                "Ignoring malformed BSM WebSocket message",
                                exc_info=True,
                            )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                _LOGGER.debug(
                    "BSM WebSocket unavailable; retrying in %ss: %s", delay, error
                )
            finally:
                self._is_connected = False
                self.connection_callback(False)
                self.ws_client = None
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)

    def _handle_message(self, message: dict[str, Any]) -> None:
        """Skip incompatible snapshots without interrupting the receive loop."""
        try:
            self._dispatch_message(message)
        except ValidationError:
            _LOGGER.debug(
                "Skipping invalid BSM WebSocket payload (type=%s)", message.get("type")
            )

    def _dispatch_message(self, message: dict[str, Any]) -> None:
        """Route process snapshots, mutation invalidations, and task outcomes."""
        topic, kind, data = (
            message.get("topic"),
            message.get("type"),
            message.get("data"),
        )
        if not isinstance(topic, str) or not isinstance(data, dict):
            return
        if kind == "resource_update" and topic == "application-metrics":
            self.update_application_metrics_callback(
                MetricsSample.model_validate(data).model_dump(mode="json")
            )
        elif kind == "resource_update" and topic.startswith("resource-monitor:"):
            name = topic.split(":", 1)[1]
            if name in self.server_names and "process_info" in data:
                self.update_server_process_info_callback(
                    name,
                    ServerProcessInfoResponse.model_validate(data).model_dump(
                        mode="json"
                    ),
                )
        elif kind == "event" and topic.startswith("event:"):
            event = topic.split(":", 1)[1]
            self.hass.bus.async_fire(
                f"{DOMAIN}_event",
                {**message, "manager_url": self.manager_url, "event": event},
            )
            # Before events describe intent, not committed state.
            if not event.startswith("after_"):
                return
            result = data.get("result")
            if isinstance(result, dict) and result.get("status") not in {
                "success",
                "skipped",
            }:
                return
            # Mutation revisions are on the event envelope, not inside its data.
            payload = {
                **data,
                "epoch": message.get("epoch"),
                "revision": message.get("revision"),
            }
            self.coordinator_refresh_callback(topic, payload)
        elif kind == "task_update" and topic.startswith("task:"):
            self._handle_task(topic, data)
        elif kind in {"ws_event", "broadcast"}:
            self.hass.bus.async_fire(
                f"{DOMAIN}_event", {**message, "manager_url": self.manager_url}
            )

    def _handle_task(self, topic: str, data: dict[str, Any]) -> None:
        """Expose task snapshots, refreshing only once per terminal outcome."""
        data = TaskSnapshot.model_validate(data).model_dump(mode="json")
        task_id = data.get("id")
        if not isinstance(task_id, str) or topic != f"task:{task_id}":
            return
        if not self._task_state.accept(task_id, data):
            return
        status = data.get("status")
        if status not in {"queued", "running", "cancelling"} | TERMINAL_TASK_STATUSES:
            return
        if status in TERMINAL_TASK_STATUSES:
            key = f"{data.get('epoch')}:{task_id}"
            if self._terminal_tasks.get(key) == status:
                return
            self._terminal_tasks[key] = status
            # Bound deduplication storage during long HA runtimes.
            if len(self._terminal_tasks) > 256:
                self._terminal_tasks.pop(next(iter(self._terminal_tasks)))
            self.coordinator_refresh_callback(topic, data)
        self.hass.bus.async_fire(
            f"{DOMAIN}_task_update", {"manager_url": self.manager_url, **data}
        )
