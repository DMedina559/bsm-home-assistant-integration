"""Fixtures using Home Assistant itself and the current SDK services."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import frame


@pytest_asyncio.fixture
async def hass(tmp_path):
    instance = HomeAssistant(str(tmp_path))
    frame.async_setup(instance)
    instance.config_entries = ConfigEntries(instance, {})
    await instance.config_entries.async_initialize()
    yield instance
    await instance.async_stop(force=True)


@pytest.fixture
def api():
    return SimpleNamespace(
        servers=SimpleNamespace(),
        content=SimpleNamespace(),
        application=SimpleNamespace(),
        players=SimpleNamespace(),
        plugins=SimpleNamespace(),
        tasks=SimpleNamespace(async_get_task_status=AsyncMock()),
        websocket_connect=AsyncMock(),
        close=AsyncMock(),
    )
