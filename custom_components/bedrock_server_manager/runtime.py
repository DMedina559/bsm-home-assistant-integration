"""Own entry actions and transports without duplicating coordinator state."""

import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.exceptions import HomeAssistantError


@dataclass
class EntryRuntime:
    """Cancel entry-owned work before closing the SDK during unload."""

    closing: bool = False
    tasks: set[asyncio.Task[Any]] = field(default_factory=set)

    refresh_tasks: dict[int, asyncio.Task[Any]] = field(default_factory=dict)
    pending_refreshes: set[int] = field(default_factory=set)

    def schedule_refresh(self, coordinator: Any) -> None:
        """Coalesce refresh bursts, retaining invalidations received during a fetch."""
        if self.closing:
            return
        key = id(coordinator)
        self.pending_refreshes.add(key)
        if key in self.refresh_tasks:
            return

        async def refresh() -> None:
            try:
                while key in self.pending_refreshes and not self.closing:
                    self.pending_refreshes.discard(key)
                    await coordinator.async_request_refresh()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logging.getLogger(__name__).warning(
                    "BSM refresh failed (%s)", type(error).__name__
                )
            finally:
                self.refresh_tasks.pop(key, None)
                self.pending_refreshes.discard(key)

        task = coordinator.hass.async_create_task(refresh(), eager_start=False)
        self.refresh_tasks[key] = task
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def own_task(self) -> None:
        """Retain the whole HA action, including response assembly and refreshes."""
        if self.closing:
            raise HomeAssistantError("This BSM manager is unloading")
        task = asyncio.current_task()
        if task is not None and task not in self.tasks:
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)

    async def shutdown(self) -> None:
        """Stop pending actions; do not cancel the caller performing cleanup."""
        self.closing = True
        tasks = self.tasks - {asyncio.current_task()}
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()
        self.refresh_tasks.clear()
        self.pending_refreshes.clear()

    def transport(self, api: Any) -> Any:
        """Guard native entity calls and preserve the released SDK interface."""
        return OwnedTransport(api, self)


class OwnedTransport:
    """Forward SDK calls while registering their enclosing HA action task."""

    def __init__(self, source: Any, runtime: EntryRuntime) -> None:
        self.source = source
        self.runtime = runtime

    def __getattr__(self, name: str) -> Any:
        value = getattr(self.source, name)
        if name == "close":
            return value
        if name in {
            "servers",
            "content",
            "application",
            "players",
            "plugins",
            "tasks",
            "discovery",
            "account",
            "users",
        }:
            return OwnedTransport(value, self.runtime)
        if inspect.iscoroutinefunction(value):

            async def owned(*args: Any, **kwargs: Any) -> Any:
                self.runtime.own_task()
                return await value(*args, **kwargs)

            return owned
        return value
