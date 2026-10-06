import asyncio
import logging
from typing import Callable, Any, Optional


from homeassistant.core import HomeAssistant
from bsm_api_client import BedrockServerManagerApi, WebSocketClient

_LOGGER = logging.getLogger(__name__)


class BsmWebSocketManager:
    """Manages the WebSocket connection for the BSM integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: BedrockServerManagerApi,
        coordinator_refresh_callback: Callable,
        update_server_process_info_callback: Callable,
        update_server_event_callback: Callable,
    ):
        """Initialize the WebSocket manager."""
        self.hass = hass
        self.api_client = api_client
        self.ws_client: Optional[WebSocketClient] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._is_connected = False
        self._should_reconnect = True
        self.coordinator_refresh_callback = coordinator_refresh_callback
        self.update_server_process_info_callback = update_server_process_info_callback
        self.update_server_event_callback = update_server_event_callback
        self._reconnect_attempts = 0
        self._connect_lock = asyncio.Lock()

    async def async_start(self):
        """Start the WebSocket connection and listen for messages."""
        self._should_reconnect = True
        self._reconnect_attempts = 0
        await self._connect()

    async def async_stop(self):
        """Stop the WebSocket connection and cleanup."""
        self._should_reconnect = False
        tasks = [task for task in (self._listen_task, self._reconnect_task) if task]
        self._listen_task = self._reconnect_task = None
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        async with self._connect_lock:
            await self._disconnect()
        self._is_connected = False

    async def _disconnect(self):
        if self.ws_client:
            try:
                await self.ws_client.disconnect()
            except Exception as e:
                _LOGGER.debug(f"Error disconnecting websocket: {e}")
            self.ws_client = None
        self._is_connected = False

    async def _connect(self):
        """Serialize connection attempts with shutdown."""
        async with self._connect_lock:
            await self._connect_once()

    async def _connect_once(self):
        """Establish the WebSocket connection."""
        if not self._should_reconnect:
            return

        try:
            if self.ws_client:
                await self.ws_client.disconnect()
                self.ws_client = None
            self.ws_client = await self.api_client.websocket_connect()
            await self.ws_client.connect()
            if not self._should_reconnect:
                await self._disconnect()
                return
            await self.ws_client.subscribe("*")
            if not self._should_reconnect:
                await self._disconnect()
                return
            self._is_connected = True
            self._reconnect_attempts = 0
            _LOGGER.info("Connected to BSM WebSocket")

            # Start listening
            if self._listen_task:
                old_task = self._listen_task
                self._listen_task = None
                old_task.cancel()
                await asyncio.gather(old_task, return_exceptions=True)
            self._listen_task = self.hass.async_create_background_task(
                self._listen(), "BSM WebSocket listener"
            )

        except Exception as e:
            _LOGGER.error(f"Failed to connect to BSM WebSocket: {e}")
            self._is_connected = False
            self._schedule_reconnect()

    async def _listen(self):
        """Listen for WebSocket messages."""
        try:
            async for msg in self.ws_client.listen():
                if not self._should_reconnect:
                    break
                await self._handle_message(msg)
        except Exception as e:
            if self._should_reconnect:
                _LOGGER.error(f"WebSocket connection lost: {e}")
        finally:
            self._is_connected = False
            if self._should_reconnect and self._listen_task is asyncio.current_task():
                self._schedule_reconnect()

    def _schedule_reconnect(self):
        """Schedule a reconnection attempt with exponential backoff."""
        if not self._should_reconnect:
            return
        if (self._reconnect_task and not self._reconnect_task.done()
                and self._reconnect_task is not asyncio.current_task()):
            return

        self._reconnect_attempts += 1
        delay = min(2 ** min(self._reconnect_attempts, 6), 60)
        _LOGGER.info(f"Scheduling WebSocket reconnect in {delay} seconds")
        self._reconnect_task = self.hass.async_create_background_task(
            self._reconnect_delay(delay), "BSM WebSocket reconnect"
        )

    async def _reconnect_delay(self, delay: int):
        await asyncio.sleep(delay)
        # The current retry may schedule its successor if this attempt fails.
        if self._should_reconnect:
            await self._connect()

    async def _handle_message(self, msg: dict[str, Any]):
        """Handle incoming WebSocket messages."""
        try:
            if not isinstance(msg, dict):
                return
            topic = msg.get("topic", "")
            msg_type = msg.get("type", "")
            data = msg.get("data", {})
            if not isinstance(topic, str) or not isinstance(data, dict):
                return

            _LOGGER.debug(f"Received WS msg. Topic: {topic}, Type: {msg_type}")

            if topic.startswith("resource-monitor:") and msg_type == "resource_update":
                server_name = topic.split(":", 1)[1]
                if "process_info" in data:
                    self.update_server_process_info_callback(
                        server_name, data["process_info"]
                    )

            elif topic.startswith("event:"):
                # Handle specific events that change server state directly in memory
                if msg_type == "event" and topic in [
                    "event:after_server_stop",
                    "event:after_server_start",
                    "event:after_properties_change",
                    "event:after_permission_change",
                    "event:after_allowlist_change",
                ]:
                    if "server_name" in data:
                        server_name = data["server_name"]
                        self.update_server_event_callback(server_name, topic, data)

                # Always trigger a refresh for events as a fallback
                self.coordinator_refresh_callback(topic, data)

            elif topic.startswith("task:") and msg_type == "task_update":
                # For tasks, we might also want to trigger a refresh just in case
                self.coordinator_refresh_callback(topic, data)

        except Exception as e:
            _LOGGER.error(f"Error handling WebSocket message: {e}", exc_info=True)
