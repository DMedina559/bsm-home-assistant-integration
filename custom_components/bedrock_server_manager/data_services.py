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
from .operational_services import (
    register_operational_services,
    unregister_operational_services,
)
from .reconcile import refresh_after_action
from .responses import action_error, action_response, target_result
from .service_schemas import TARGETING_SCHEMA_FIELDS
from .targets import resolve_manager_targets

GET_SETTINGS_SCHEMA = vol.Schema(
    {vol.Required("plugin_name"): cv.string, **TARGETING_SCHEMA_FIELDS}
)
UPDATE_SETTINGS_SCHEMA = GET_SETTINGS_SCHEMA.extend({vol.Required("settings"): dict})


async def settings_action(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Read schemas or validate updates through the plugin's declared API contract."""
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
            if not plugin or not plugin.get("has_settings"):
                raise ServiceValidationError(
                    f"Plugin '{plugin_name}' does not declare settings"
                )
            if call.service == "update_plugin_settings":
                write_response = await data["api"].plugins.async_update_plugin_settings(
                    plugin_name, PluginSettingsPayload(settings=call.data["settings"])
                )
                applied = True
                refresh_after_action(data["manager_coordinator"])
            response = await data["api"].plugins.async_get_plugin_settings(plugin_name)
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
                    "error": action_error(error),
                }
            )
            continue
        results.append(target_result(data["manager_identifier"][1], response))
        result.append(
            {
                "manager_url": data["manager_identifier"][1],
                "plugin_name": plugin_name,
                **response.model_dump(mode="json"),
            }
        )
    if errors and len(errors) == len(result) and not call.return_response:
        if isinstance(errors[0], HomeAssistantError):
            raise errors[0]
        raise HomeAssistantError("; ".join(str(error) for error in errors)) from errors[
            0
        ]
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
