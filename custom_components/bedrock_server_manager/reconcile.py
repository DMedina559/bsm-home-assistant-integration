"""Share mutation refresh rules between native entities and custom actions."""

SERVER_RESOURCES = {
    "send_command": {"summary"},
    "update_properties": {"properties", "summary"},
    "set_permissions": {"server_permissions"},
    "add_to_allowlist": {"allowlist"},
    "remove_from_allowlist": {"allowlist"},
    "add_server_ban": {"server_bans"},
    "remove_server_ban": {"server_bans"},
    "set_server_setting": {"server_settings", "summary"},
    "configure_os_service": {"server_settings", "summary"},
}


def refresh_after_action(coordinator, resources=None) -> None:
    """Invalidate immediately; reconcile in owned background work after acknowledgement."""
    if coordinator is None:
        return
    runtime = getattr(coordinator.api, "runtime", None)
    if runtime is not None and runtime.closing:
        return
    coordinator.invalidate({}, resources)
    task = coordinator.hass.async_create_task(coordinator.async_request_refresh())
    if runtime is not None:
        runtime.tasks.add(task)
        task.add_done_callback(runtime.tasks.discard)
