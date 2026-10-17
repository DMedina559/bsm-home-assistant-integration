"""Bounded attributes retain JSON types, metadata ownership and missing values."""

import json
from datetime import datetime, timezone

from custom_components.bedrock_server_manager.attributes import (
    MAX_ITEMS,
    VOLATILE_ATTRIBUTES,
    bounded_attributes,
    entity_attributes,
)


def test_identity_metadata_cannot_override_contract():
    attrs = entity_attributes(
        "server",
        "status",
        "http://host",
        server_name="test",
        metadata={
            "bsm_role": "manager",
            "bsm_server_name": "other",
            "bsm_resource_state": "stale",
            "bsm_updated_at": None,
        },
    )
    assert attrs["bsm_role"] == "server"
    assert attrs["bsm_server_name"] == "test"
    assert attrs["bsm_resource_state"] == "stale"
    assert attrs["bsm_updated_at"] is None


def test_details_are_bounded_native_json_and_do_not_mutate_sources():
    source = {
        "players": list(range(MAX_ITEMS + 1)),
        "missing": None,
        "zero": 0,
        "false": False,
        "sample": float("nan"),
        "time": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    attrs = bounded_attributes(source)
    assert len(attrs["players"]) == MAX_ITEMS
    assert attrs["bsm_truncated_attributes"] == ["players", "sample"]
    assert attrs["missing"] is None and attrs["sample"] is None
    assert attrs["zero"] == 0 and attrs["false"] is False
    assert attrs["time"] == "2026-01-01T00:00:00+00:00"
    json.dumps(attrs, allow_nan=False)
    attrs["players"].append(999)
    assert len(source["players"]) == MAX_ITEMS + 1
    assert "bsm_truncated_attributes" in VOLATILE_ATTRIBUTES


def test_depth_and_total_work_have_explicit_limits():
    nested = None
    for _ in range(20):
        nested = {"child": nested}
    attrs = bounded_attributes(
        {"nested": nested, "wide": [[0] * 100 for _ in range(100)]}
    )
    assert attrs["bsm_truncated_attributes"] == ["nested", "wide"]
    json.dumps(attrs, allow_nan=False)
