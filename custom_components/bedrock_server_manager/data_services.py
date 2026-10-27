"""Response-capable typed plugin settings and task actions for HA automations."""

from functools import partial

import probatio as vol
from bsm_api_client import APIError
from bsm_api_client.models import PluginSettingsPayload
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .configuration_services import (
    register_configuration_services,
    unregister_configuration_services,
)
from .const import DOMAIN
from .coordinator import json_data
from .operational_services import (
    register_operational_services,
    unregister_operational_services,
)
from .reconcile import refresh_after_action
from .responses import action_error, action_response, target_result
from .service_schemas import TARGETING_SCHEMA_FIELDS
from .targets import resolve_manager_targets

GET_SETTINGS_SCHEMA = vol.Schema(
    {
        vol.Required("plugin_name"): cv.string,
        vol.Optional("scope", default="plugin"): vol.In(["plugin", "global", "server"]),
        vol.Optional("server_name"): cv.string,
        **TARGETING_SCHEMA_FIELDS,
    }
)
UPDATE_SETTINGS_SCHEMA = GET_SETTINGS_SCHEMA.extend({vol.Required("settings"): dict})


async def _read_settings(api, plugin_name, options):
    """Use discovery for scoped fields absent from the installed SDK models."""
    if options["scope"] == "plugin":
        return await api.plugins.async_get_plugin_settings(plugin_name)
    return await api.discovery.call(
        "get_plugin_settings",
        authenticated=True,
        path_params={"plugin_name": plugin_name},
        query=options,
    )


async def _write_settings(api, plugin_name, options, settings):
    """Forward scope explicitly rather than dropping fields in old SDK models."""
    if options["scope"] == "plugin":
        return await api.plugins.async_update_plugin_settings(
            plugin_name, PluginSettingsPayload(settings=settings)
        )
    return await api.discovery.call(
        "update_plugin_settings",
        authenticated=True,
        path_params={"plugin_name": plugin_name},
        json_data={**options, "settings": settings},
    )


def _raise_failed_settings(errors, results, return_response):
    """Preserve per-target outcomes for response calls and raise total failures otherwise."""
    if errors and len(errors) == len(results) and not return_response:
        if isinstance(errors[0], HomeAssistantError):
            raise errors[0]
        raise HomeAssistantError("; ".join(str(error) for error in errors)) from errors[
            0
        ]


async def settings_action(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Read schemas or validate updates through the plugin's declared API contract."""
    scope = call.data.get("scope", "plugin")
    server_name = call.data.get("server_name")
    if (scope == "server") != bool(server_name):
        raise ServiceValidationError(
            "Server scope requires server_name; other scopes must omit it"
        )
    targets = await resolve_manager_targets(call, hass)
    result = []
    results = []
    errors = []
    for entry_id in sorted(targets):
        data = hass.data[DOMAIN][entry_id]
        plugin_name = call.data["plugin_name"]
        plugin = (data["manager_coordinator"].data.get("plugins_status") or {}).get(
            plugin_name
        )
        applied = False
        write_response = None
        try:
            if not plugin or not plugin.get(
                {
                    "plugin": "has_settings",
                    "global": "has_global_settings",
                    "server": "has_server_settings",
                }[scope]
            ):
                raise ServiceValidationError(
                    f"Plugin '{plugin_name}' does not declare settings"
                )
            api = data["api"]
            options = {
                "scope": scope,
                **({"server_name": server_name} if server_name else {}),
            }
            if call.service == "update_plugin_settings":
                write_response = await _write_settings(
                    api, plugin_name, options, call.data["settings"]
                )
                applied = True
                refresh_after_action(data["manager_coordinator"])
                if server_name:
                    refresh_after_action(
                        data.get("servers", {}).get(server_name, {}).get("coordinator")
                    )
            response = await _read_settings(api, plugin_name, options)
        except (APIError, ValueError, HomeAssistantError) as error:
            failure = action_error(error)
            if applied:
                outcome = target_result(
                    data["manager_identifier"][1],
                    write_response,
                    warnings=[
                        {
                            "code": "refresh_failed",
                            "message": "Settings were saved; refreshing them failed. Refresh before retrying.",
                            "error": failure,
                        }
                    ],
                )
                results.append(outcome)
                result.append(
                    {
                        "manager_url": data["manager_identifier"][1],
                        "plugin_name": plugin_name,
                        "scope": scope,
                        "server_name": server_name,
                        "applied": True,
                        "warnings": outcome["warnings"],
                    }
                )
                continue
            errors.append(error)
            results.append(
                target_result(
                    data["manager_identifier"][1], status="failed", error=failure
                )
            )
            result.append(
                {
                    "manager_url": data["manager_identifier"][1],
                    "plugin_name": plugin_name,
                    "scope": scope,
                    "server_name": server_name,
                    "error": action_error(error),
                }
            )
            continue
        results.append(target_result(data["manager_identifier"][1], response))
        result.append(
            {
                "manager_url": data["manager_identifier"][1],
                "plugin_name": plugin_name,
                "scope": scope,
                "server_name": server_name,
                **json_data(response),
            }
        )
    _raise_failed_settings(errors, result, call.return_response)
    return action_response(results, managers=result)


def register_data_services(hass: HomeAssistant) -> None:
    """Register read/update actions that expose the backend validation schema."""
    register_configuration_services(hass)
    register_operational_services(hass)
    for name, schema in (
        ("get_plugin_settings", GET_SETTINGS_SCHEMA),
        ("update_plugin_settings", UPDATE_SETTINGS_SCHEMA),
    ):
        hass.services.async_register(
            DOMAIN,
            name,
            partial(settings_action, hass),
            schema=schema,
            supports_response=SupportsResponse.OPTIONAL,
        )
    for name, schema in (
        ("list_tasks", vol.Schema(TARGETING_SCHEMA_FIELDS)),
        (
            "get_task",
            vol.Schema({vol.Required("task_id"): cv.string, **TARGETING_SCHEMA_FIELDS}),
        ),
    ):
        hass.services.async_register(
            DOMAIN,
            name,
            partial(task_action, hass),
            schema=schema,
            supports_response=SupportsResponse.OPTIONAL,
        )


def unregister_data_services(hass: HomeAssistant) -> None:
    """Remove response-capable actions when the final manager unloads."""
    unregister_configuration_services(hass)
    unregister_operational_services(hass)
    for name in (
        "get_plugin_settings",
        "update_plugin_settings",
        "list_tasks",
        "get_task",
    ):
        hass.services.async_remove(DOMAIN, name)


async def task_action(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return current typed task outcomes visible to each targeted manager account."""
    targets = await resolve_manager_targets(call, hass)
    managers = []
    results = []
    errors = []
    for entry_id in sorted(targets):
        data = hass.data[DOMAIN][entry_id]
        try:
            if call.service == "get_task":
                response = await data["api"].tasks.async_get_task_status(
                    call.data["task_id"]
                )
                outcome = {"task": response.model_dump(mode="json")}
            else:
                tasks = await data["api"].tasks.async_list_tasks()
                outcome = {"tasks": [task.model_dump(mode="json") for task in tasks]}
        except APIError as error:
            errors.append(error)
            results.append(
                target_result(
                    data["manager_identifier"][1],
                    status="failed",
                    error=action_error(error),
                )
            )
            managers.append(
                {
                    "manager_url": data["manager_identifier"][1],
                    "error": action_error(error),
                }
            )
            continue
        results.append(target_result(data["manager_identifier"][1], outcome))
        managers.append({"manager_url": data["manager_identifier"][1], **outcome})
    if errors and len(errors) == len(managers) and not call.return_response:
        raise HomeAssistantError("; ".join(str(error) for error in errors)) from errors[
            0
        ]
    return action_response(results, managers=managers)
