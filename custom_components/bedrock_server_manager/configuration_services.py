"""Settings, runtime API discovery and content actions through the released SDK."""

from functools import partial
from typing import Any

import probatio as vol
from bsm_api_client import APIError
from bsm_api_client.models import ServerSettingItemPayload
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import json_data
from .reconcile import SERVER_RESOURCES, refresh_after_action
from .service_schemas import TARGETING_SCHEMA_FIELDS
from .targets import resolve_manager_targets, resolve_server_targets

SCHEMAS: dict[str, dict[Any, Any]] = {
    "get_application_settings": {},
    "get_server_settings": {},
    "set_server_setting": {
        vol.Required("key"): cv.string,
        vol.Required("value"): object,
    },
    "discover_operations": {vol.Optional("refresh", default=False): cv.boolean},
    "call_operation": {
        vol.Required("operation_id"): cv.string,
        vol.Optional("path_params", default={}): dict,
        vol.Optional("query", default={}): dict,
        vol.Optional("json_data"): object,
    },
    "upload_content": {vol.Required("file_path"): cv.string},
    "export_world": {},
}
SERVER_ACTIONS = {"get_server_settings", "set_server_setting", "export_world"}


async def configuration_action(  # noqa: C901
    hass: HomeAssistant, call: ServiceCall
) -> dict:
    """Validate targets and return JSON-safe settings, contracts or action outcomes."""
    targets: list[tuple[str, str | None]]
    if call.service in SERVER_ACTIONS:
        targets = [
            (entry, name) for entry, name in await resolve_server_targets(call, hass)
        ]
    else:
        targets = [(entry, None) for entry in await resolve_manager_targets(call, hass)]
    results = []
    errors = []
    for entry_id, server in sorted(targets):
        data = hass.data[DOMAIN][entry_id]
        api = data["api"]
        try:
            response = await _execute(hass, api, call, server)
        except (APIError, ValueError, OSError, HomeAssistantError) as error:
            errors.append(error)
            results.append(
                {
                    "manager_url": data["manager_identifier"][1],
                    "server_name": server,
                    "status": "failed",
                    "error": {"message": str(error)},
                }
            )
            continue
        results.append(
            {
                "manager_url": data["manager_identifier"][1],
                "server_name": server,
                "result": json_data(response),
            }
        )
        mutation = call.service != "call_operation" or api.discovery.operations[
            call.data["operation_id"]
        ].method.upper() not in {"GET", "HEAD", "OPTIONS"}
        if mutation and call.service in {
            "set_server_setting",
            "upload_content",
            "export_world",
            "call_operation",
        }:
            coordinators = [data.get("manager_coordinator")]
            if server:
                coordinators.append(
                    data.get("servers", {}).get(server, {}).get("coordinator")
                )
            else:
                coordinators.extend(
                    item["coordinator"] for item in data.get("servers", {}).values()
                )
            for coordinator in coordinators:
                if coordinator is not None:
                    refresh_after_action(
                        coordinator,
                        SERVER_RESOURCES.get(call.service) if server else None,
                    )
    if errors and len(errors) == len(results):
        if isinstance(errors[0], HomeAssistantError):
            raise errors[0]
        raise HomeAssistantError("; ".join(str(error) for error in errors)) from errors[
            0
        ]
    return {"results": results}


async def _execute(
    hass: HomeAssistant, api: Any, call: ServiceCall, server: str | None
) -> Any:
    """Keep dynamic calls authenticated and leave validation to the SDK contract."""
    values = call.data
    if call.service == "get_application_settings":
        return await api.application.async_get_all_settings()
    if call.service == "get_server_settings":
        return await api.servers.async_get_server_settings(server)
    if call.service == "set_server_setting":
        return await api.servers.async_set_server_setting(
            server, ServerSettingItemPayload(key=values["key"], value=values["value"])
        )
    if call.service == "export_world":
        return await api.content.async_export_server_world(server)
    if call.service == "upload_content":
        path = values["file_path"]
        if not hass.config.is_allowed_path(path):
            raise ServiceValidationError(
                "File must be inside a Home Assistant allowed path"
            )
        return await api.content.async_upload_content(path)
    operations = await api.discovery.discover(force=values.get("refresh", False))
    if call.service == "discover_operations":
        return {
            "operations": [operation.to_dict() for operation in operations.values()]
        }
    kwargs = {
        key: values[key]
        for key in ("path_params", "query", "json_data")
        if key in values
    }
    response = await api.discovery.call(
        values["operation_id"], authenticated=True, **kwargs
    )
    if isinstance(response, bytes):
        raise ServiceValidationError(
            "Binary responses cannot be returned by HA actions"
        )
    return response


def register_configuration_services(hass: HomeAssistant) -> None:
    """Register response-capable actions with native HA targets."""
    for name, fields in SCHEMAS.items():
        hass.services.async_register(
            DOMAIN,
            name,
            partial(configuration_action, hass),
            schema=vol.Schema({**fields, **TARGETING_SCHEMA_FIELDS}),
            supports_response=SupportsResponse.OPTIONAL,
        )


def unregister_configuration_services(hass: HomeAssistant) -> None:
    """Remove actions when the final manager unloads."""
    for name in SCHEMAS:
        hass.services.async_remove(DOMAIN, name)
