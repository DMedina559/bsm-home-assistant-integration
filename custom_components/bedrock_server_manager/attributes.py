"""Stable entity identity and bounded JSON data for Home Assistant attributes."""

from collections.abc import Mapping
from datetime import date, datetime
from enum import Enum
from itertools import islice
from math import isfinite
from typing import Any

from pydantic import BaseModel

MAX_ITEMS = 100
MAX_DEPTH = 8
MAX_TEXT = 4096
MAX_NODES = 2048
FRESHNESS_KEYS = {"bsm_resource_state", "bsm_updated_at", "bsm_last_error"}
VOLATILE_ATTRIBUTES = frozenset(
    {
        "bsm_updated_at",
        "bsm_last_error",
        "bsm_truncated_attributes",
        "bsm_settings_revision",
        "server_settings",
        "server_settings_freshness",
        "checks",
        "failed_checks",
        "checked_at",
        "server_properties",
        "server_permissions",
        "server_addons_list",
        "world_backups_list",
        "allowlist_backups_list",
        "properties_backups_list",
        "permissions_backups_list",
        "allowed_players",
        "online_players",
        "server_bans",
        "global_players_list",
        "available_worlds_list",
        "available_addons_list",
        "plugins_data",
        "pid",
        "uptime",
    }
)


def entity_attributes(
    role: str,
    key: str,
    manager_url: str,
    *,
    server_name: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build protected identity and freshness without accepting arbitrary keys."""
    result: dict[str, Any] = {
        "bsm_role": role,
        "bsm_key": key,
        "bsm_manager_url": manager_url,
        "bsm_attribute_schema": 1,
    }
    if server_name is not None:
        result["bsm_server_name"] = server_name
    result.update(
        {
            name: value
            for name, value in (metadata or {}).items()
            if name in FRESHNESS_KEYS
        }
    )
    return result


class _AttributeEncoder:
    """Bound work for one entity snapshot without retaining payload state."""

    def __init__(self) -> None:
        self.truncated: set[str] = set()
        self.nodes = 0

    def scalar(self, value: Any, key: str) -> Any:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, str):
            if len(value) > MAX_TEXT:
                self.truncated.add(key)
            return value[:MAX_TEXT]
        if isinstance(value, float) and not isfinite(value):
            self.truncated.add(key)
            return None
        if value is None or isinstance(value, (bool, int, float)):
            return value
        self.truncated.add(key)
        return None

    def encode(self, value: Any, key: str, depth: int = 0) -> Any:
        self.nodes += 1
        if self.nodes > MAX_NODES or depth > MAX_DEPTH:
            self.truncated.add(key)
            return None
        if isinstance(value, BaseModel):
            value = value.model_dump(mode="json")
        if isinstance(value, Enum):
            value = value.value
        if isinstance(value, (Mapping, list, tuple)):
            if len(value) > MAX_ITEMS:
                self.truncated.add(key)
            if isinstance(value, Mapping):
                return {
                    str(name): self.encode(item, key, depth + 1)
                    for name, item in islice(value.items(), MAX_ITEMS)
                }
            return [self.encode(item, key, depth + 1) for item in value[:MAX_ITEMS]]
        return self.scalar(value, key)


def bounded_attributes(attributes: Mapping[str, Any]) -> dict[str, Any]:
    """Copy native JSON attributes and identify any bounded/invalid detail values."""
    encoder = _AttributeEncoder()
    result = {key: encoder.encode(value, key) for key, value in attributes.items()}
    if encoder.truncated:
        result["bsm_truncated_attributes"] = sorted(encoder.truncated)
    return result
