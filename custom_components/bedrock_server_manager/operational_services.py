"""Expose existing backend maintenance and diagnostic contracts as HA actions."""

import asyncio
from dataclasses import dataclass
from functools import partial
from typing import Any

import probatio as vol
from bsm_api_client import APIError
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .reconcile import refresh_after_action
from .responses import action_error, action_response, target_result
from .service_schemas import TARGETING_SCHEMA_FIELDS
from .targets import resolve_manager_targets, resolve_server_targets


@dataclass(frozen=True)
class OperationalAction:
    """Describe routing independently of the discovered SDK request schema."""

    operation: str
    fields: dict[Any, Any]
    path: tuple[str, ...] = ()
    server: bool = False
    mutation: bool = False


def limit(maximum: int, default: int = 50) -> dict:
    """Limit on-demand collections before contract validation."""
    return {
        vol.Optional("limit", default=default): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=maximum)
        )
    }


def optional_strings(*names: str) -> dict:
    """Declare optional filters without forwarding HA targeting fields."""
    return {vol.Optional(name): cv.string for name in names}


ACTIONS = {
    "get_application_diagnostics": OperationalAction("get_application_diagnostics", {}),
    "get_subsystem_diagnostics": OperationalAction(
        "get_subsystem_diagnostics",
        {vol.Required("subsystem"): cv.string},
        ("subsystem",),
    ),
    "get_diagnostic_history": OperationalAction(
        "get_diagnostic_history",
        {
            **limit(200),
            **optional_strings(
                "subsystem",
                "instance_id",
                "correlation_id",
                "cursor",
                "owner",
                "code",
                "outcome",
                "operation_id",
            ),
        },
    ),
    "get_diagnostic_runs": OperationalAction("get_diagnostic_runs", limit(50, 20)),
    "get_diagnostic_trace": OperationalAction(
        "get_diagnostic_trace",
        {
            vol.Required("correlation_id"): cv.string,
            **limit(200),
            **optional_strings("cursor"),
        },
        ("correlation_id",),
    ),
    "get_diagnostic_report": OperationalAction("get_diagnostic_report", {}),
    "compare_diagnostic_snapshots": OperationalAction(
        "compare_diagnostic_snapshots",
        {vol.Required("before"): dict, vol.Required("after"): dict},
    ),
    "list_application_events": OperationalAction("list_application_events", {}),
    "get_event_activity": OperationalAction(
        "get_event_activity",
        {**limit(200), **optional_strings("name", "owner", "correlation_id", "status")},
    ),
    "get_web_runtime": OperationalAction("get_web_runtime", {}),
    "shutdown_web_runtime": OperationalAction(
        "shutdown_web_runtime", {vol.Required("confirm"): vol.In([True])}, mutation=True
    ),
    "get_log_history": OperationalAction(
        "get_log_history",
        {
            vol.Optional("before"): vol.All(vol.Coerce(int), vol.Range(min=0)),
            vol.Optional("file_id"): cv.string,
        },
        server=True,
    ),
    "get_application_log_history": OperationalAction(
        "get_log_history",
        {
            vol.Optional("before"): vol.All(vol.Coerce(int), vol.Range(min=0)),
            vol.Optional("file_id"): cv.string,
        },
    ),
    "list_audit_logs": OperationalAction(
        "list_audit_logs", {**limit(200), **optional_strings("action")}
    ),
    "get_raw_properties": OperationalAction("get_raw_properties", {}, server=True),
    "validate_server": OperationalAction("validate_server", {}, server=True),
    "prune_backups": OperationalAction("prune_backups", {}, server=True, mutation=True),
    "reload_plugin": OperationalAction(
        "reload_plugin",
        {vol.Required("plugin_name"): cv.string},
        ("plugin_name",),
        mutation=True,
    ),
}


async def _execute(
    api: Any, spec: OperationalAction, values: dict, server: str | None
) -> Any:
    """Validate requests through the live SDK contract, including plugin contracts."""
    operations = await api.discovery.discover()
    if spec.operation not in operations:
        raise ServiceValidationError("This backend does not support this action")
    fields = {
        str(key.schema): values[str(key.schema)]
        for key in spec.fields
        if str(key.schema) in values
    }
    path = {name: fields.pop(name) for name in spec.path}
    if spec.server and spec.operation != "get_log_history":
        path["server_name"] = server
    if spec.operation == "get_log_history":
        # Log topics are derived from the authorized target, never supplied by callers.
        fields["topic"] = f"server_log:{server}" if server else "app_log"
    kwargs: dict[str, Any] = {"path_params": path}
    if spec.operation == "compare_diagnostic_snapshots":
        kwargs["json_data"] = fields
    elif spec.operation == "shutdown_web_runtime":
        if fields.get("confirm") is not True:
            raise ServiceValidationError("Explicit shutdown confirmation is required")
        kwargs["json_data"] = {}
    elif spec.operation != "list_audit_logs":
        kwargs["query"] = fields
    response = await api.discovery.call(spec.operation, authenticated=True, **kwargs)
    if spec.operation == "list_audit_logs":
        # The current backend has no pagination/filter parameters. Filter on demand.
        rows = response if isinstance(response, list) else []
        action = fields.get("action")
        rows = [row for row in rows if not action or row.get("action") == action]
        return {
            "records": rows[: fields["limit"]],
            "total_matches": len(rows),
            "truncated": len(rows) > fields["limit"],
        }
    return response


async def operational_action(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return independent target failures and acknowledged mutations without replay."""
    spec = ACTIONS[call.service]
    targets = (
        await resolve_server_targets(call, hass)
        if spec.server
        else [(entry, None) for entry in await resolve_manager_targets(call, hass)]
    )
    results = []
    for entry, server in sorted(targets):
        data = hass.data[DOMAIN][entry]
        try:
            async with asyncio.timeout(180 if spec.mutation else 30):
                response = await _execute(data["api"], spec, dict(call.data), server)
            outcome = target_result(
                data["manager_identifier"][1], response, server_name=server
            )
        except (APIError, ValueError, OSError, HomeAssistantError) as error:
            outcome = target_result(
                data["manager_identifier"][1],
                server_name=server,
                status="failed",
                error=action_error(error),
            )
            if isinstance(error, ServiceValidationError) and "does not support" in str(
                error
            ):
                outcome["error"]["code"] = "unsupported_operation"
        results.append(outcome)
        if (
            outcome["status"] != "failed"
            and spec.mutation
            and call.service != "shutdown_web_runtime"
        ):
            coordinator = (
                data.get("servers", {}).get(server, {}).get("coordinator")
                if server
                else data.get("manager_coordinator")
            )
            refresh_after_action(coordinator)
    if not call.return_response and any(item["status"] == "failed" for item in results):
        raise HomeAssistantError(
            "BSM action failed for one or more targets. Check current state before retrying: "
            + "; ".join(
                item["error"]["message"] for item in results if item.get("error")
            )
        )
    return action_response(results)


def register_operational_services(hass: HomeAssistant) -> None:
    """Register native targets, bounded fields and optional action responses."""
    for name, spec in ACTIONS.items():
        hass.services.async_register(
            DOMAIN,
            name,
            partial(operational_action, hass),
            schema=vol.Schema({**TARGETING_SCHEMA_FIELDS, **spec.fields}),
            supports_response=SupportsResponse.OPTIONAL,
        )


def unregister_operational_services(hass: HomeAssistant) -> None:
    """Remove operational actions after the final manager unloads."""
    for name in ACTIONS:
        hass.services.async_remove(DOMAIN, name)
