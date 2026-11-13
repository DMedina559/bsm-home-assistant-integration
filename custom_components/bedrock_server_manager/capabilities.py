"""Describe HTTP capabilities from live access metadata and effective grants."""

import asyncio
from collections.abc import Mapping
from typing import Any

from bsm_api_client import APIError, AuthError

# HA names that differ from the backend operation ID. Maintenance actions use
# their existing routing table so permission checks do not duplicate scope names.
SERVICE_OPERATIONS = {
    "send_command": "send_command",
    "trigger_backup": "create_server_snapshot",
    "restore_backup": "restore_backup",
    "prune_download_cache": "prune_downloads",
    "scan_players": "scan_players",
    "add_global_players": "add_players",
    "set_plugin_enabled": "set_plugin_status",
    "get_plugin_settings": "get_plugin_settings",
    "update_plugin_settings": "update_plugin_settings",
    "reload_plugins": "reload_plugins",
    "trigger_plugin_event": "trigger_plugin_event",
    "get_application_settings": "get_settings",
    "get_server_settings": "get_server_settings",
    "set_server_setting": "set_server_setting",
    "set_global_setting": "set_setting",
    "reload_global_settings": "reload_settings",
    "start_server": "start_server",
    "stop_server": "stop_server",
    "restart_server": "restart_server",
    "update_server": "update_server",
    "install_server": "install_server",
    "delete_server": "delete_server",
    "update_properties": "set_properties",
    "add_to_allowlist": "add_allowlist_players",
    "remove_from_allowlist": "remove_allowlist_players",
    "set_permissions": "set_permissions",
    "add_server_ban": "add_server_ban",
    "remove_server_ban": "remove_server_ban",
    "install_world": "install_world",
    "reset_world": "reset_world",
    "export_world": "export_world",
    "install_addon": "install_addon",
    "enable_addon": "enable_addon",
    "disable_addon": "disable_addon",
    "uninstall_addon": "uninstall_addon",
    "reorder_addons": "reorder_addons",
    "update_addon_subpack": "update_addon_subpack",
    "list_tasks": "list_tasks",
    "get_task": "get_task_status",
    "upload_content": "upload_content_file",
}
RESOURCE_OPERATIONS = {
    "info": "get_system_info",
    "application_settings": "get_settings",
    "global_players": "list_players",
    "available_worlds": "list_available_worlds",
    "available_addons": "list_available_addons",
    "plugins_status": "list_plugins",
    "process_info": "get_server_process_info",
    "server_settings": "get_server_settings",
    "allowlist": "get_allowlist",
    "properties": "get_properties",
    "server_permissions": "get_permissions",
    "server_addons": "list_server_addons",
    "summary": "get_server_summary",
    "server_bans": "get_server_bans",
    "metrics": "get_application_metrics",
    "health": "get_application_health",
    "diagnostics": "get_application_diagnostics",
}


class AccessCapabilities:
    """Keep unknown distinct from denied; never infer token grants from a role."""

    def __init__(self, integration_token: bool = False):
        self.integration_token = integration_token
        self.operations: dict[str, dict[str, Any]] | None = None
        self.permissions: set[str] | None = None
        self.server_permissions: dict[str, set[str]] | None = None
        self.server_permission_names: set[str] | None = None
        self.revision: str | None = None
        self.unavailable = False

    async def refresh(self, api: Any) -> None:
        """Fetch only read endpoints; no trial mutations or unverified JWT decoding."""
        schema = getattr(getattr(api, "discovery", None), "schema", None)
        if not isinstance(schema, Mapping):
            return
        self.operations = {
            operation["operationId"]: operation
            for path in schema.get("paths", {}).values()
            for method, operation in path.items()
            if method.lower()
            in {"get", "put", "post", "delete", "patch", "head", "options"}
            and isinstance(operation, dict)
            and "operationId" in operation
        }
        # Do not keep old grants after an identity endpoint becomes inaccessible.
        self.permissions = None
        self.server_permissions = None
        self.server_permission_names = None
        self.revision = None
        self.unavailable = False
        if "get_account" not in self.operations:
            return
        try:
            async with asyncio.timeout(15):
                await self._refresh_grants(api)
        except AuthError as error:
            if (
                error.status_code != 403
                or error.session_invalid
                or error.mfa_required
                or error.passkey_required
                or error.enrollment_required
                or error.recent_auth_required
            ):
                raise
            self.unavailable = True
        except (APIError, TimeoutError):
            self.unavailable = True

    async def _refresh_grants(self, api: Any) -> None:
        """Load effective identity grants separately from per-server permissions."""
        account = await api.discovery.call("get_account", authenticated=True)
        if isinstance(account, dict) and isinstance(account.get("permissions"), list):
            self.permissions = set(account["permissions"])
            self.revision = account.get("policy_revision")
        if "get_access_policy" in (self.operations or {}):
            policy = await api.discovery.call("get_access_policy", authenticated=True)
            if isinstance(policy, dict) and isinstance(
                policy.get("server_permissions"), list
            ):
                self.server_permission_names = set(policy["server_permissions"])
        if "list_access_servers" in (self.operations or {}):
            rows = await api.discovery.call("list_access_servers", authenticated=True)
            if isinstance(rows, list):
                self.server_permissions = {
                    row["name"]: set(row["permissions"])
                    for row in rows
                    if isinstance(row, dict)
                    and isinstance(row.get("name"), str)
                    and isinstance(row.get("permissions"), list)
                }

    def operation(
        self, operation_id: str, server_name: str | None = None
    ) -> dict[str, Any]:
        """Describe whether grants permit an operation; backend contextual checks still apply."""
        unknown = {"state": "unknown", "missing_permissions": []}
        if self.operations is None:
            return unknown
        if operation_id not in self.operations:
            return {"state": "unsupported", "missing_permissions": []}
        operation = self.operations[operation_id]
        access = operation.get("x-bsm-access")
        if not isinstance(access, dict):
            return unknown
        required = set(access.get("required_permissions", []))
        checks = access.get("additional_checks", [])
        result = {
            "state": "unknown",
            "required_permissions": sorted(required),
            "missing_permissions": [],
            "additional_checks": checks,
        }
        # Public endpoints do not require this credential type to be supported.
        if (
            access.get("classification") == "public"
            and access.get("authentication") == "none"
        ):
            return {**result, "state": "conditional" if checks else "allowed"}
        if self.integration_token and access.get("integration_tokens") == "unsupported":
            return {
                **result,
                "state": "denied",
                "reason": "integration_token_unsupported",
            }
        if self.permissions is None:
            return result
        missing = required - self.permissions
        if missing:
            return {**result, "state": "denied", "missing_permissions": sorted(missing)}
        server_result = self._server_access(access, required, server_name)
        if server_result is None:
            return result
        missing |= server_result
        if missing:
            return {**result, "state": "denied", "missing_permissions": sorted(missing)}
        return {**result, "state": self._granted_state(access, server_name)}

    @staticmethod
    def _granted_state(access: dict, server_name: str | None) -> str:
        conditional = (
            access.get("additional_checks")
            or access.get("classification") in {"contextual", "legacy-role", "unknown"}
            or (access.get("resource_scope") == "server" and server_name is None)
        )
        return "conditional" if conditional else "allowed"

    def _server_access(
        self, access: dict, required: set[str], server_name: str | None
    ) -> set[str] | None:
        if access.get("resource_scope") != "server" or server_name is None:
            return set()
        if self.server_permissions is None or self.server_permission_names is None:
            return None
        return (required & self.server_permission_names) - self.server_permissions.get(
            server_name, set()
        )

    def snapshot(
        self, server_name: str | None = None, *, detailed: bool = False
    ) -> dict[str, Any]:
        """Return safe grants and HA action availability without account identifiers."""
        from .operational_services import ACTIONS

        services = {
            **SERVICE_OPERATIONS,
            **{name: action.operation for name, action in ACTIONS.items()},
        }
        actions = {
            name: self.operation(op, server_name) for name, op in services.items()
        }
        return {
            "known": self.permissions is not None,
            "discovery_unavailable": self.unavailable,
            "policy_revision": self.revision,
            "permissions": (
                sorted(self.permissions) if self.permissions is not None else None
            ),
            "server_permissions": (
                sorted(self.server_permissions.get(server_name, set()))
                if server_name is not None and self.server_permissions is not None
                else None
            ),
            "actions": (
                actions
                if detailed
                else {name: result["state"] for name, result in actions.items()}
            ),
            **(
                {
                    "operations": {
                        name: self.operation(name, server_name)
                        for name in self.operations or {}
                    }
                }
                if detailed
                else {}
            ),
        }
