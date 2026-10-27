"""Expose existing backend maintenance and diagnostic contracts as HA actions."""

import asyncio
from dataclasses import dataclass
from functools import partial
from pathlib import Path
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
    body: bool = False
    timeout: int | None = None


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
    "get_diagnostic_activity": OperationalAction(
        "get_diagnostic_activity",
        {
            **limit(200, 100),
            **optional_strings(
                "name",
                "owner",
                "correlation_id",
                "status",
                "phase",
                "sequence_id",
                "operation_id",
                "operation_name",
                "server_name",
                "source",
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


# The discovered backend schema validates component choices and schedule options.
# Do not duplicate its enums here or pin these actions to generated SDK models.
SNAPSHOT_PATH: dict[Any, Any] = {vol.Required("backup_id"): cv.string}
RECOVERY_KEY: dict[Any, Any] = {vol.Optional("recovery_key"): cv.string}
SELECTION: dict[Any, Any] = {vol.Required("components"): [cv.string], **RECOVERY_KEY}
ACTIONS.update(
    {
        "import_server_snapshot": OperationalAction(
            "import_server_snapshot",
            {
                vol.Required("file_path"): cv.string,
                **RECOVERY_KEY,
            },
            server=True,
            mutation=True,
            timeout=1800,
        ),
        "download_server_snapshot": OperationalAction(
            "download_server_snapshot",
            {
                **SNAPSHOT_PATH,
                vol.Required("file_path"): cv.string,
            },
            ("backup_id",),
            server=True,
            timeout=1800,
        ),
        "list_server_snapshots": OperationalAction(
            "list_server_snapshots", {}, server=True
        ),
        "create_server_snapshot": OperationalAction(
            "create_server_snapshot",
            {
                vol.Optional("mode"): vol.In(["world", "selected", "full"]),
                vol.Optional("components"): [cv.string],
                vol.Optional("encrypted"): cv.boolean,
            },
            server=True,
            mutation=True,
            body=True,
        ),
        "inspect_server_snapshot": OperationalAction(
            "inspect_server_snapshot",
            {
                **SNAPSHOT_PATH,
                **RECOVERY_KEY,
            },
            ("backup_id",),
            server=True,
            body=True,
        ),
        "plan_snapshot_restore": OperationalAction(
            "plan_snapshot_restore",
            {
                **SNAPSHOT_PATH,
                **SELECTION,
            },
            ("backup_id",),
            server=True,
            body=True,
        ),
        "restore_server_snapshot": OperationalAction(
            "restore_server_snapshot",
            {
                **SNAPSHOT_PATH,
                **SELECTION,
                vol.Required("token"): cv.string,
                vol.Optional("restart"): cv.boolean,
                vol.Optional("stop_running"): cv.boolean,
            },
            ("backup_id",),
            server=True,
            mutation=True,
            body=True,
        ),
        "dry_run_server_restore": OperationalAction(
            "dry_run_server_restore",
            {
                **SNAPSHOT_PATH,
                **SELECTION,
            },
            ("backup_id",),
            server=True,
            mutation=True,
            body=True,
        ),
        "manage_server_snapshot": OperationalAction(
            "manage_server_snapshot",
            {
                **SNAPSHOT_PATH,
                **RECOVERY_KEY,
                vol.Required("action"): vol.In(
                    ["verify", "pin", "unpin", "copy", "test_key", "annotate", "drill"]
                ),
                **optional_strings("destination", "label", "notes"),
            },
            ("backup_id",),
            server=True,
            mutation=True,
            body=True,
        ),
        "get_backup_health": OperationalAction("get_backup_health", {}, server=True),
        "get_restore_recovery": OperationalAction(
            "get_restore_recovery", {}, server=True
        ),
        "recover_server_backup": OperationalAction(
            "recover_server_backup", {}, server=True, mutation=True, body=True
        ),
        "download_backup_recovery_report": OperationalAction(
            "download_backup_recovery_report", {}, server=True
        ),
        "prepare_backup_copy": OperationalAction(
            "prepare_backup_copy",
            {
                **SNAPSHOT_PATH,
                **RECOVERY_KEY,
                vol.Required("target_server"): cv.string,
                vol.Optional("target_version"): cv.string,
                vol.Required("server_port"): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                vol.Required("server_portv6"): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
            },
            ("backup_id",),
            server=True,
            mutation=True,
            body=True,
        ),
        "cleanup_backup_destination": OperationalAction(
            "cleanup_backup_destination",
            {
                vol.Required("destination"): cv.string,
                vol.Optional("token"): cv.string,
            },
            ("destination",),
            server=True,
            mutation=True,
            body=True,
        ),
        "list_backup_keys": OperationalAction("list_backup_keys", {}),
        "rotate_backup_key": OperationalAction(
            "rotate_backup_key",
            {
                vol.Required("confirm"): vol.In([True]),
            },
            mutation=True,
            body=True,
        ),
        "list_schedules": OperationalAction(
            "list_schedules", optional_strings("server_name")
        ),
        "save_schedule": OperationalAction(
            "save_schedule",
            {
                vol.Required("schedule_id"): cv.string,
                vol.Required("configuration"): dict,
            },
            ("schedule_id",),
            mutation=True,
            body=True,
        ),
        "delete_schedule": OperationalAction(
            "delete_schedule",
            {
                vol.Required("schedule_id"): cv.string,
            },
            ("schedule_id",),
            mutation=True,
        ),
    }
)


async def _transfer_archive(api, spec, fields, path, server, hass):
    """Restrict archive transfers to Home Assistant allowed paths."""
    local_path = str(Path(fields["file_path"]).expanduser().resolve())
    if hass is None or not hass.config.is_allowed_path(local_path):
        raise ServiceValidationError(
            "File must be inside a Home Assistant allowed path"
        )
    if spec.operation == "download_server_snapshot":
        destination = await api.backups.async_download_to(
            server, path["backup_id"], local_path
        )
        return {"status": "success", "file_path": str(destination)}
    stream = await hass.async_add_executor_job(open, local_path, "rb")
    try:
        return await api.backups.async_import(
            server, stream, Path(local_path).name, fields.get("recovery_key")
        )
    finally:
        await hass.async_add_executor_job(stream.close)


def _request_kwargs(spec, fields, path):
    """Keep HA-only confirmation and targeting fields out of API requests."""
    kwargs: dict[str, Any] = {"path_params": path}
    if spec.operation == "save_schedule":
        kwargs["json_data"] = fields["configuration"]
    elif spec.operation == "rotate_backup_key":
        if fields.pop("confirm", False) is not True:
            raise ServiceValidationError(
                "Explicit key rotation confirmation is required"
            )
        kwargs["json_data"] = {}
    elif spec.body or spec.operation == "compare_diagnostic_snapshots":
        kwargs["json_data"] = fields
    elif spec.operation == "shutdown_web_runtime":
        if fields.get("confirm") is not True:
            raise ServiceValidationError("Explicit shutdown confirmation is required")
        kwargs["json_data"] = {}
    elif spec.operation not in {"list_audit_logs", "delete_schedule"}:
        kwargs["query"] = fields
    return kwargs


async def _execute(
    api: Any,
    spec: OperationalAction,
    values: dict,
    server: str | None,
    hass: HomeAssistant | None = None,
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
    if spec.operation in {"import_server_snapshot", "download_server_snapshot"}:
        return await _transfer_archive(api, spec, fields, path, server, hass)
    kwargs = _request_kwargs(spec, fields, path)
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
            async with asyncio.timeout(spec.timeout or (180 if spec.mutation else 30)):
                response = await _execute(
                    data["api"], spec, dict(call.data), server, hass
                )
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
