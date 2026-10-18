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
                "ready": False,
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
    health = ApplicationHealthSensor(coordinator, identifier, "health")
    assert health.available and health.is_on
    assert health.extra_state_attributes["ready"] is False
    assert health.extra_state_attributes["failed_checks"] == ["database"]
    assert (
        health.extra_state_attributes["checks"]["database"]["message"]
        == "Database unavailable"
    )
    coordinator.set_websocket_connected(True)
    coordinator.http_connected = False
    assert ApplicationHealthSensor(coordinator, identifier, "websocket").is_on
    assert not ApplicationHealthSensor(coordinator, identifier, "connection").is_on
    coordinator.unavailable_resources.add("health")
    assert not health.available


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
            checked_at=1,
            checks={},
            health="healthy",
            lifecycle="ready",
            ready=True,
            pid=123,
            version="4.0.0",
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


@pytest.mark.asyncio
async def test_native_setting_number_reads_confirmed_values_and_uses_typed_payload(
    hass, api
):

    from custom_components.bedrock_server_manager.coordinator import (
        ManagerDataCoordinator,
    )
    from custom_components.bedrock_server_manager.number import SettingNumber

    coordinator = ManagerDataCoordinator(hass, api, 600)
    coordinator.async_set_updated_data(
        {"application_settings": {"monitoring": {"app_metrics_interval_sec": 3}}}
    )
    entity = SettingNumber(
        coordinator,
        ("bedrock_server_manager", "http://host"),
        "monitoring.app_metrics_interval_sec",
    )
    assert entity.native_value == 3
    assert entity.available
    api.application.async_set_setting = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    await entity.async_set_native_value(5)
    assert api.application.async_set_setting.call_args.args[0].value == 5
    assert entity.native_value == 3  # Confirmation comes from the coordinator.
    coordinator.async_request_refresh.assert_awaited_once()
    coordinator.unavailable_resources.add("application_settings")
    assert not entity.available


@pytest.mark.asyncio
async def test_native_update_channel_retains_exact_versions(hass, api):
    from custom_components.bedrock_server_manager.select import UpdateChannelSelect

    coordinator = MinecraftBedrockCoordinator(hass, api, "selected", 30)
    coordinator.async_set_updated_data(
        {"server_settings": {"settings": {"target_version": "1.21.99"}}}
    )
    entity = UpdateChannelSelect(coordinator, ("bedrock_server_manager", "http://host"))
    assert entity.current_option == "1.21.99"
    assert entity.options == ["LATEST", "PREVIEW", "1.21.99"]
    api.servers.async_set_server_setting = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    await entity.async_select_option("PREVIEW")
    assert api.servers.async_set_server_setting.call_args.args[1].value == "PREVIEW"
    assert entity.current_option == "1.21.99"
    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_server_identity_survives_unavailable_data(hass, api):
    from homeassistant.components.sensor import SensorEntityDescription

    from custom_components.bedrock_server_manager.sensor import MinecraftServerSensor

    coordinator = MinecraftBedrockCoordinator(hass, api, "selected", 30)
    entity = MinecraftServerSensor(
        coordinator,
        SensorEntityDescription(key="status", name="Status"),
        "selected",
        ("bedrock_server_manager", "http://host"),
        None,
        None,
        None,
    )
    assert entity.native_value is None
    assert entity.extra_state_attributes["bsm_server_name"] == "selected"
    assert entity.extra_state_attributes["bsm_manager_url"] == "http://host"


@pytest.mark.asyncio
async def test_consolidated_health_removes_old_registry_entities(hass, api):
    from types import SimpleNamespace
    from unittest.mock import Mock

    from homeassistant.helpers import area_registry as ar
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    from custom_components.bedrock_server_manager.binary_sensor import async_setup_entry
    from custom_components.bedrock_server_manager.const import DOMAIN

    coordinator = ApplicationMonitorCoordinator(hass, api)
    identifier = (DOMAIN, "http://host")
    hass.data[DOMAIN] = {
        "entry": {"monitor_coordinator": coordinator, "manager_identifier": identifier}
    }
    await ar.async_load(hass, load_empty=True)
    dr.async_setup(hass)
    await dr.async_load(hass, load_empty=True)
    await er.async_load(hass, load_empty=True)
    registry = er.async_get(hass)
    old_ids = []
    for domain, keys in (
        ("binary_sensor", ("lifecycle", "database", "state", "metrics")),
        ("sensor", ("application_lifecycle", "health_checked_at")),
    ):
        for key in keys:
            old_ids.append(
                registry.async_get_or_create(
                    domain,
                    DOMAIN,
                    f"{DOMAIN}_{identifier[1]}_{key}".lower().replace(":", "_"),
                ).entity_id
            )
    add = Mock()
    await async_setup_entry(hass, SimpleNamespace(entry_id="entry"), add)
    assert {entity.key for entity in add.call_args.args[0]} == {
        "connection",
        "websocket",
        "health",
        "ready",
    }
    assert all(registry.async_get(entity_id) is None for entity_id in old_ids)
    enabled = {
        description.key
        for description in METRIC_DESCRIPTIONS
        if description.entity_registry_enabled_default
    }
    assert enabled == {
        "app_cpu_percent",
        "app_ram_mb",
        "background_task_count",
        "uptime_seconds",
        "sys_cpu_percent",
        "sys_ram_percent",
    }


@pytest.mark.asyncio
async def test_status_attributes_preserve_nested_settings_and_protect_identity(
    hass, api
):
    import json

    from homeassistant.components.sensor import SensorEntityDescription

    from custom_components.bedrock_server_manager.sensor import MinecraftServerSensor

    coordinator = MinecraftBedrockCoordinator(hass, api, "survival", 30)
    settings = {
        "server_info": {"name": "survival"},
        "settings": {"autostart": False, "nested": {"retry": 0}},
        "custom": {"bsm_role": "attacker", "nested": [1, None]},
        "bsm_role": "attacker",
        "bsm_manager_url": "attacker",
    }
    coordinator.async_set_updated_data(
        {"server_status": "STOPPED", "server_settings": settings}
    )
    sensor = MinecraftServerSensor(
        coordinator,
        SensorEntityDescription(key="status"),
        "survival",
        ("bedrock_server_manager", "http://host"),
        None,
        None,
        "Linux",
    )
    attrs = sensor.extra_state_attributes
    assert attrs["bsm_role"] == "server"
    assert attrs["bsm_manager_url"] == "http://host"
    assert attrs["server_settings"] == settings
    assert "settings_autostart" not in attrs
    assert attrs["server_settings"]["settings"]["autostart"] is False
    assert attrs["server_settings"]["settings"]["nested"]["retry"] == 0
    json.dumps(attrs, allow_nan=False)
    attrs["server_settings"]["settings"]["autostart"] = True
    assert settings["settings"]["autostart"] is False
    assert "server_settings" in sensor._unrecorded_attributes
    assert "bsm_role" not in sensor._unrecorded_attributes
    coordinator.last_update_success = False
    assert sensor.extra_state_attributes["bsm_role"] == "server"


@pytest.mark.asyncio
async def test_health_without_evidence_is_unknown_not_healthy(hass, api):
    coordinator = ApplicationMonitorCoordinator(hass, api, 30)
    coordinator.async_set_updated_data(
        {"health": {"ready": None, "checks": {"database": {}}}}
    )
    entity = ApplicationHealthSensor(
        coordinator, ("bedrock_server_manager", "http://host"), "health"
    )
    assert not entity.available
    assert entity.is_on is None
    assert entity.extra_state_attributes["failed_checks"] == []
