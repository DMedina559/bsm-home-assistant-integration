"""Native metric units, health availability and authoritative control values."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from bsm_api_client.models import (
    GetApplicationHealthResponse,
    GetApplicationMetricsResponse,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

from custom_components.bedrock_server_manager.binary_sensor import (
    ApplicationHealthSensor,
)
from custom_components.bedrock_server_manager.coordinator import (
    ApplicationMonitorCoordinator,
    MinecraftBedrockCoordinator,
)
from custom_components.bedrock_server_manager.metrics import (
    METRIC_DESCRIPTIONS,
    ApplicationMetricSensor,
)
from custom_components.bedrock_server_manager.text import TargetVersionText


def sample(revision=1):
    return {
        "timestamp": 1700000000,
        "asyncio_task_count": 6,
        "background_task_count": 2,
        "loop_lag_ms": 1.5,
        "app_ram_mb": 128,
        "sys_cpu_percent": 0,
        "net_rx_kib_s": 64,
        "uptime_seconds": 120,
        "epoch": "a",
        "revision": revision,
    }


@pytest.mark.asyncio
async def test_native_units_statistics_and_unavailable_values(hass, api):
    coordinator = ApplicationMonitorCoordinator(hass, api)
    coordinator.update_metrics(sample())
    entities = {
        d.key: ApplicationMetricSensor(
            coordinator, d, ("bedrock_server_manager", "http://host")
        )
        for d in METRIC_DESCRIPTIONS
    }
    assert entities["app_ram_mb"].native_value == 128
    assert entities["app_ram_mb"].native_unit_of_measurement == "MiB"
    assert entities["app_ram_mb"].state_class == SensorStateClass.MEASUREMENT
    assert entities["net_rx_kib_s"].device_class == SensorDeviceClass.DATA_RATE
    assert entities["sys_cpu_percent"].available  # Zero is a valid sample.
    assert not entities["sys_ram_mb"].available
    assert entities["metrics_sampled_at"].native_value == datetime.fromtimestamp(
        1700000000, timezone.utc
    )
    assert entities["uptime_seconds"].native_unit_of_measurement == "s"
    assert "history" not in coordinator.data["metrics"]


@pytest.mark.asyncio
async def test_health_problems_are_separate_from_connection_and_live_state(hass, api):
    coordinator = ApplicationMonitorCoordinator(hass, api)
    coordinator.async_set_updated_data(
        {
            "health": {
                "health": "degraded",
                "checks": {
                    "database": {"healthy": False, "message": "Database unavailable"},
                    "state": {"healthy": True, "message": "State loaded"},
                },
            }
        }
    )
    identifier = ("bedrock_server_manager", "http://host")
    assert ApplicationHealthSensor(coordinator, identifier, "health").is_on
    database = ApplicationHealthSensor(coordinator, identifier, "database")
    assert database.available and database.is_on
    assert database.extra_state_attributes == {"message": "Database unavailable"}
    assert not ApplicationHealthSensor(coordinator, identifier, "state").is_on
    coordinator.set_websocket_connected(True)
    coordinator.http_connected = False
    assert ApplicationHealthSensor(coordinator, identifier, "websocket").is_on
    assert not ApplicationHealthSensor(coordinator, identifier, "connection").is_on
    coordinator.unavailable_resources.add("health")
    assert not database.available


@pytest.mark.asyncio
async def test_monitor_fetches_health_and_only_latest_metrics(hass, api):
    api.application.async_get_application_metrics = AsyncMock(
        return_value=GetApplicationMetricsResponse(
            latest=sample(),
            history=[sample()],
            history_limit=180,
            interval_seconds=3,
            epoch="a",
            revision=1,
        )
    )
    api.application.async_get_application_health = AsyncMock(
        return_value=GetApplicationHealthResponse(
            checked_at=1, checks={}, health="healthy", lifecycle="ready"
        )
    )
    coordinator = ApplicationMonitorCoordinator(hass, api)
    data = await coordinator._async_update_data()
    assert data["metrics"]["app_ram_mb"] == 128
    assert "history" not in data
    assert data["health"]["lifecycle"] == "ready"
    assert coordinator.http_connected


@pytest.mark.asyncio
async def test_target_version_uses_settings_namespace(hass, api):
    coordinator = MinecraftBedrockCoordinator(hass, api, "server", 30)
    coordinator.async_set_updated_data(
        {"server_settings": {"settings": {"target_version": "LATEST"}}}
    )
    api.servers.async_set_server_setting = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    entity = TargetVersionText(coordinator, ("bedrock_server_manager", "http://host"))
    assert entity.native_value == "LATEST"
    await entity.async_set_value("PREVIEW")
    args = api.servers.async_set_server_setting.call_args.args
    assert args[0] == "server" and args[1].key == "settings.target_version"
    assert args[1].value == "PREVIEW"
    assert (
        entity.native_value == "LATEST"
    )  # The authoritative refresh supplies the new value.


@pytest.mark.parametrize(
    "value,expected",
    [("01:02:03", 3723), ("2 days, 01:00:00", 176400), ("bad", None), (None, None)],
)
def test_server_uptime_is_a_native_duration(value, expected):
    from custom_components.bedrock_server_manager.sensor import uptime_seconds

    assert uptime_seconds(value) == expected
