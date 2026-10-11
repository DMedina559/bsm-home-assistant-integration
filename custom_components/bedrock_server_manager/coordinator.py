"""Fetch typed SDK contracts and expose JSON-compatible Home Assistant state."""

import asyncio
import logging
from collections.abc import Awaitable, Mapping
from datetime import timedelta
from time import time
from typing import Any

from bsm_api_client import AuthError, BedrockServerManagerApi
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pydantic import BaseModel

from .const import DOMAIN
from .state import ResourceState

_LOGGER = logging.getLogger(__name__)
MIN_API_TIMEOUT = 180


def json_data(value: Any) -> Any:
    """Serialize nested contracts at the HA entity and frontend boundary."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: json_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_data(item) for item in value]
    return value


class BsmCoordinator(DataUpdateCoordinator):
    """Preserve good data on partial failures and guard concurrent live updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: BedrockServerManagerApi,
        name: str,
        scan_interval: int,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        self.manager_device_id = (
            hass.data.get(DOMAIN, {})
            .get(config_entry.entry_id, {})
            .get("manager_device_id")
            if config_entry
            else None
        )
        self.api = api
        self.state = ResourceState()
        self.defaults: dict[str, Any] = {}
        self._push_generation: dict[str, int] = {}
        self.unavailable_resources: set[str] = set()
        self.unsupported_resources: set[str] = set()
        self.forbidden_resources: set[str] = set()
        self.resource_updated_at: dict[str, float] = {}
        self._requested_resources: set[str] | None = None
        self._full_refresh_pending = False
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=name,
            update_interval=timedelta(seconds=scan_interval),
        )

    def invalidate(
        self, stamp: dict[str, Any], resources: set[str] | None = None
    ) -> bool:
        """Discard in-flight HTTP data when an accepted mutation event arrives."""
        accepted = self.state.invalidate(stamp)
        if accepted:
            if resources is None:
                self._requested_resources = None
                self._full_refresh_pending = True
            elif self.data is not None and not self._full_refresh_pending:
                self._requested_resources = (
                    self._requested_resources or set()
                ) | resources
        return accepted

    def _publish_push(self, data: dict[str, Any]) -> None:
        """Publish live data without postponing HTTP polls or cancelling retries."""
        self.data = data
        self.last_update_success = True
        self.async_update_listeners()

    def supports(self, operation_id: str) -> bool:
        """Use discovered capabilities when available, otherwise shipped support."""
        if getattr(self.api, "schema", None) is None:
            return True
        capabilities = getattr(self.api, "capabilities", None)
        return capabilities is None or capabilities.has(operation_id)

    def resource_metadata(self, resource: str | None) -> dict[str, Any]:
        """Describe unsupported, unavailable and retained data independently."""
        updated = self.resource_updated_at.get(resource or "")
        state = (
            "forbidden"
            if resource in self.forbidden_resources
            else (
                "unsupported"
                if resource in self.unsupported_resources
                else (
                    "stale"
                    if updated
                    and (
                        resource in self.unavailable_resources
                        or not self.last_update_success
                    )
                    else (
                        "unavailable"
                        if resource in self.unavailable_resources
                        or not self.last_update_success
                        else "current" if updated else "unknown"
                    )
                )
            )
        )
        return {"bsm_resource_state": state, "bsm_updated_at": updated}

    async def _fetch(
        self,
        calls: Mapping[str, Awaitable[Any]],
        fields: dict[str, str],
        critical: str | None = None,
    ) -> dict:
        generation = self.state.generation
        push_generation = self._push_generation.copy()
        try:
            async with asyncio.timeout(MIN_API_TIMEOUT):
                results = await asyncio.gather(*calls.values(), return_exceptions=True)
        except TimeoutError as error:
            self.unavailable_resources.update(calls)
            raise UpdateFailed("Timed out communicating with BSM") from error
        # Expired credentials trigger reauthentication; forbidden resources do not.
        for result in results:
            if isinstance(result, AuthError) and result.status_code != 403:
                raise ConfigEntryAuthFailed(str(result)) from result
        data = {**self.defaults, **(self.data or {})}
        if generation != self.state.generation:
            return data
        successes, failures = self._merge_results(
            data, calls, results, fields, critical, push_generation
        )
        if not successes:
            if failures and not set(failures) <= self.forbidden_resources:
                raise UpdateFailed("No BSM data available: " + ", ".join(failures))
            return data
        data.update(status="success", message="Data updated")
        if failures:
            _LOGGER.debug(
                "Keeping previous %s data after partial fetch failure: %s",
                self.name,
                ", ".join(failures),
            )
        return data

    def _merge_results(
        self,
        data: dict,
        calls: Mapping[str, Awaitable[Any]],
        results: list[Any],
        fields: dict[str, str],
        critical: str | None,
        push_generation: dict[str, int],
    ) -> tuple[int, list[str]]:
        """Merge successful resources while keeping partial failures isolated."""
        successes = 0
        failures = []
        for key, result in zip(calls, results):
            if isinstance(result, Exception):
                if isinstance(result, AuthError) and result.status_code == 403:
                    self.forbidden_resources.add(key)
                    self.unavailable_resources.add(key)
                    failures.append(key)
                    continue
                self.unavailable_resources.add(key)
                if key == critical:
                    raise UpdateFailed(str(result)) from result
                failures.append(key)
                continue
            if push_generation.get(key, 0) != self._push_generation.get(key, 0):
                continue
            if self._apply_result(data, key, result, fields):
                successes += 1
        return successes, failures

    def _apply_result(
        self, data: dict, key: str, result: Any, fields: dict[str, str]
    ) -> bool:
        """Merge an accepted typed response into its independent resource."""
        payload = json_data(result)
        stamp = payload
        if key == "metrics" and isinstance(payload.get("latest"), dict):
            latest = payload["latest"]
            if latest.get("epoch") is not None or latest.get("revision") is not None:
                stamp = latest
        if not self.state.accept(key, stamp):
            return False
        if key == "summary":
            data.update(
                server_status=payload["status"],
                online_players=payload.get("players") or [],
                player_count=payload.get("player_count") or 0,
                version=payload["version"],
            )
        else:
            value = payload.get(fields[key]) if fields[key] else payload
            data[key] = value if value is not None else self.defaults.get(key)
        self.forbidden_resources.discard(key)
        self.unavailable_resources.discard(key)
        self.resource_updated_at[key] = time()
        return True


class MinecraftBedrockCoordinator(BsmCoordinator):
    """Coordinate server configuration, access control, backups and process metrics."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: BedrockServerManagerApi,
        server_name: str,
        scan_interval: int,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        super().__init__(
            hass,
            api_client,
            f"{DOMAIN} Server ({server_name})",
            scan_interval,
            config_entry,
        )
        self.server_name = server_name
        self.defaults = {
            "process_info": None,
            "server_settings": {},
            "allowlist": [],
            "properties": {},
            "server_permissions": [],
            "server_addons": {},
            "world_backups": [],
            "allowlist_backups": [],
            "permissions_backups": [],
            "properties_backups": [],
            "online_players": [],
            "server_bans": [],
            "server_status": "UNKNOWN",
            "player_count": 0,
        }

    def update_process_info(self, payload: dict[str, Any]) -> None:
        """Apply a revisioned process snapshot without inventing process values."""
        if not self.state.accept("process_info", payload):
            return
        self.unavailable_resources.discard("process_info")
        self.forbidden_resources.discard("process_info")
        self.resource_updated_at["process_info"] = time()
        # Prevent an HTTP poll started before this push from overwriting it.
        for key in ("process_info", "summary"):
            self._push_generation[key] = self._push_generation.get(key, 0) + 1
        data = {
            **self.defaults,
            **(self.data or {}),
            "process_info": payload.get("process_info"),
            "status": "success",
        }
        process = data["process_info"]
        if process and process.get("pid"):
            data["server_status"] = "RUNNING"
        elif data["server_status"] == "RUNNING":
            data["server_status"] = "STOPPED"
        self._publish_push(data)

    async def _async_update_data(self) -> dict:
        servers, content, name = self.api.servers, self.api.content, self.server_name
        methods = {
            "process_info": servers.async_get_server_process_info,
            "server_settings": servers.async_get_server_settings,
            "allowlist": servers.async_get_server_allowlist,
            "properties": servers.async_get_server_properties,
            "server_permissions": servers.async_get_server_permissions_data,
            "server_addons": content.async_get_server_addons,
            "summary": servers.async_get_server_summary,
            **(
                {"server_bans": servers.async_get_server_bans}
                if self.supports("get_server_bans")
                else {}
            ),
        }
        if not self.supports("get_server_bans"):
            self.unsupported_resources.add("server_bans")
        else:
            self.unsupported_resources.discard("server_bans")
        requested = self._requested_resources
        self._requested_resources = None
        self._full_refresh_pending = False
        calls = {
            key: method(name)
            for key, method in methods.items()
            if requested is None
            or key in requested
            or key in self.unavailable_resources
        }
        fields = {
            "process_info": "process_info",
            "server_settings": "settings",
            "allowlist": "players",
            "properties": "properties",
            "server_permissions": "permissions",
            "server_addons": "addons",
            "server_bans": "bans",
        }
        for kind in ("world", "allowlist", "permissions", "properties"):
            key = f"{kind}_backups"
            if (
                requested is None
                or key in requested
                or key in self.unavailable_resources
            ):
                calls[key] = content.async_list_server_backups(name, kind)
            fields[key] = "backups"
        return await self._fetch(calls, fields, critical="process_info")


class ManagerDataCoordinator(BsmCoordinator):
    """Coordinate manager information, player lists, content and plugin statuses."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: BedrockServerManagerApi,
        scan_interval: int,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        super().__init__(
            hass, api_client, f"{DOMAIN} Manager", scan_interval, config_entry
        )
        self.defaults = {
            "application_settings": {},
            "info": {},
            "global_players": [],
            "available_worlds": [],
            "available_addons": [],
            "plugins_status": {},
        }

    async def _async_update_data(self) -> dict:
        discovery = getattr(self.api, "discovery", None)
        if discovery is not None and not getattr(self, "_discovered", False):
            try:
                await discovery.discover()
                self._discovered = True
            except AuthError as error:
                if error.status_code != 403:
                    raise ConfigEntryAuthFailed(str(error)) from error
            except Exception:
                _LOGGER.debug(
                    "Runtime API discovery unavailable; using shipped contracts"
                )
        if not self.supports("get_settings"):
            self.unsupported_resources.add("application_settings")
        else:
            self.unsupported_resources.discard("application_settings")
        return await self._fetch(
            {
                **(
                    {
                        "application_settings": self.api.application.async_get_all_settings()
                    }
                    if hasattr(self.api.application, "async_get_all_settings")
                    and self.supports("get_settings")
                    else {}
                ),
                "info": self.api.application.async_get_info(),
                "global_players": self.api.players.async_get_players(),
                "available_worlds": self.api.content.async_get_content_worlds(),
                "available_addons": self.api.content.async_get_content_addons(),
                "plugins_status": self.api.plugins.async_get_plugin_statuses(),
            },
            {
                "application_settings": "settings",
                "info": "info",
                "global_players": "players",
                "available_worlds": "files",
                "available_addons": "files",
                "plugins_status": "plugins",
            },
        )


class ApplicationMonitorCoordinator(BsmCoordinator):
    """Live application/host observations with a bounded HTTP fallback poll."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: BedrockServerManagerApi,
        scan_interval: int = 30,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        super().__init__(
            hass,
            api_client,
            f"{DOMAIN} Application Monitor",
            scan_interval,
            config_entry,
        )
        self.defaults = {"metrics": {}, "health": {}}
        self.websocket_connected = False
        self.http_connected = False

    def set_websocket_connected(self, connected: bool) -> None:
        """Notify connection entities without changing HTTP availability."""
        self.websocket_connected = connected
        self.async_update_listeners()

    def update_metrics(self, payload: dict[str, Any]) -> None:
        """Store the latest live sample; history belongs in HA's recorder."""
        if not self.state.accept("metrics", payload):
            return
        self._push_generation["metrics"] = self._push_generation.get("metrics", 0) + 1
        self.unavailable_resources.discard("metrics")
        self.resource_updated_at["metrics"] = time()
        self._publish_push(
            {
                **self.defaults,
                **(self.data or {}),
                "metrics": payload,
                "status": "success",
            }
        )

    async def _async_update_data(self) -> dict:
        for resource, operation in (
            ("metrics", "get_application_metrics"),
            ("health", "get_application_health"),
        ):
            if self.supports(operation):
                self.unsupported_resources.discard(resource)
            else:
                self.unsupported_resources.add(resource)
        if len(self.unsupported_resources) == 2:
            self.http_connected = False
            return {**self.defaults, **(self.data or {})}
        try:
            data = await self._fetch(
                {
                    **(
                        {
                            "metrics": self.api.application.async_get_application_metrics()
                        }
                        if self.supports("get_application_metrics")
                        else {}
                    ),
                    **(
                        {"health": self.api.application.async_get_application_health()}
                        if self.supports("get_application_health")
                        else {}
                    ),
                },
                {"metrics": "latest", "health": ""},
            )
        except (UpdateFailed, ConfigEntryAuthFailed):
            self.http_connected = False
            raise
        self.http_connected = True
        return data
