"""Entry refresh bursts, in-flight invalidations, and unload ownership."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.bedrock_server_manager.runtime import EntryRuntime


@pytest.mark.asyncio
async def test_refresh_bursts_keep_an_inflight_followup_and_cancel_on_unload(hass):
    runtime = EntryRuntime()
    started = asyncio.Event()
    release = asyncio.Event()

    async def refresh():
        started.set()
        await release.wait()

    coordinator = SimpleNamespace(
        hass=hass, async_request_refresh=AsyncMock(side_effect=refresh)
    )
    for _ in range(10):
        runtime.schedule_refresh(coordinator)
    await started.wait()
    for _ in range(10):
        runtime.schedule_refresh(coordinator)
    release.set()
    await asyncio.gather(*runtime.tasks)
    assert coordinator.async_request_refresh.await_count == 2
    release.clear()
    started.clear()
    runtime.schedule_refresh(coordinator)
    await started.wait()
    await runtime.shutdown()
    assert not runtime.tasks
    assert not runtime.refresh_tasks
    runtime.schedule_refresh(coordinator)
    assert not runtime.tasks
