"""Own entry actions and transports without duplicating coordinator state."""

import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Any

from homeassistant.exceptions import HomeAssistantError


@dataclass
class EntryRuntime:
    """Cancel entry-owned work before closing the SDK during unload."""

    closing: bool = False
    tasks: set[asyncio.Task[Any]] = field(default_factory=set)

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
