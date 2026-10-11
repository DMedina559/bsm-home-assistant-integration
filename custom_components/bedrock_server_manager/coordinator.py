"""Fetch typed SDK contracts and expose JSON-compatible Home Assistant state."""

import asyncio
import logging
from collections.abc import Awaitable, Mapping
from datetime import timedelta
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
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=name,
            update_interval=timedelta(seconds=scan_interval),
        )

    def invalidate(self, stamp: dict[str, Any]) -> bool:
        """Discard in-flight HTTP data when an accepted mutation event arrives."""
        return self.state.invalidate(stamp)

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
            raise UpdateFailed("Timed out communicating with BSM") from error
        # Authentication failures on any endpoint must trigger reauthentication.
        for result in results:
            if isinstance(result, AuthError):
                raise ConfigEntryAuthFailed(str(result)) from result
        data = {**self.defaults, **(self.data or {})}
        if generation != self.state.generation:
            return data
        successes, failures = self._merge_results(
            data, calls, results, fields, critical, push_generation
        )
        if not successes:
            if failures:
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
                if key == critical:
                    raise UpdateFailed(str(result)) from result
                self.unavailable_resources.add(key)
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
        if not self.state.accept(key, payload):
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
        self.unavailable_resources.discard(key)
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
        self.async_set_updated_data(data)

    async def _async_update_data(self) -> dict:
        servers, content, name = self.api.servers, self.api.content, self.server_name
        calls = {
            "process_info": servers.async_get_server_process_info(name),
            "server_settings": servers.async_get_server_settings(name),
            "allowlist": servers.async_get_server_allowlist(name),
            "properties": servers.async_get_server_properties(name),
            "server_permissions": servers.async_get_server_permissions_data(name),
            "server_addons": content.async_get_server_addons(name),
            "summary": servers.async_get_server_summary(name),
            "server_bans": servers.async_get_server_bans(name),
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
            "info": {},
            "global_players": [],
            "available_worlds": [],
            "available_addons": [],
            "plugins_status": {},
        }

    async def _async_update_data(self) -> dict:
        return await self._fetch(
            {
                "info": self.api.application.async_get_info(),
                "global_players": self.api.players.async_get_players(),
                "available_worlds": self.api.content.async_get_content_worlds(),
                "available_addons": self.api.content.async_get_content_addons(),
                "plugins_status": self.api.plugins.async_get_plugin_statuses(),
            },
            {
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
        self.async_set_updated_data(
            {
                **self.defaults,
                **(self.data or {}),
                "metrics": payload,
                "status": "success",
            }
        )

    async def _async_update_data(self) -> dict:
        try:
            data = await self._fetch(
                {
                    "metrics": self.api.application.async_get_application_metrics(),
                    "health": self.api.application.async_get_application_health(),
                },
                {"metrics": "latest", "health": ""},
            )
        except (UpdateFailed, ConfigEntryAuthFailed):
            self.http_connected = False
            raise
        self.http_connected = True
        return data
