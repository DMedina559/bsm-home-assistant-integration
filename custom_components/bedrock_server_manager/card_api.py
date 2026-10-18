"""Authenticated, read-only coordinator transport for the npm example card."""

import probatio
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


@callback
def async_register_card_api(hass: HomeAssistant) -> None:
    """Register commands once; resolve loaded entries on every request."""
    marker = f"{DOMAIN}_card_api"
    if hass.data.get(marker):
        return
    websocket_api.async_register_command(hass, websocket_card_entries)
    websocket_api.async_register_command(hass, websocket_card_read)
    hass.data[marker] = True


@websocket_api.websocket_command({probatio.Required("type"): f"{DOMAIN}/card_entries"})
@websocket_api.require_admin
@callback
def websocket_card_entries(hass, connection, msg):
    """List loaded integration entries without exposing connection credentials."""
    loaded = hass.data.get(DOMAIN, {})
    connection.send_result(
        msg["id"],
        [
            {"entry_id": entry.entry_id, "title": entry.title}
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.entry_id in loaded
        ],
    )


@websocket_api.websocket_command(
    {
        probatio.Required("type"): f"{DOMAIN}/card_read",
        probatio.Required("entry_id"): str,
        probatio.Required("operation"): probatio.In(
            ["list_servers", "get_server_process_info"]
        ),
        probatio.Optional("server_name"): str,
    }
)
@websocket_api.require_admin
@callback
def websocket_card_read(hass, connection, msg):
    """Return selected coordinator snapshots; never proxy arbitrary API calls."""
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN:
        connection.send_error(msg["id"], "not_found", "BSM entry not found")
        return
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if data is None or "servers" not in data:
        connection.send_error(msg["id"], "not_loaded", "BSM entry is not loaded")
        return
    servers = data["servers"]
    if msg["operation"] == "list_servers":
        connection.send_result(
            msg["id"],
            {
                "status": "success",
                "servers": [
                    {"name": name, "status": "unknown", "version": "unknown"}
                    for name in servers
                ],
            },
        )
        return
    server = servers.get(msg.get("server_name"))
    coordinator = server.get("coordinator") if server else None
    if coordinator is None:
        connection.send_error(msg["id"], "not_found", "Server is not monitored")
    elif (
        not coordinator.last_update_success
        or coordinator.data is None
        or coordinator.data.get("status") not in ("success", "partial")
        or coordinator.resource_metadata("process_info")["bsm_resource_state"]
        != "current"
    ):
        connection.send_error(msg["id"], "unavailable", "Server snapshot unavailable")
    else:
        process = coordinator.data.get("process_info")
        if hasattr(process, "model_dump"):
            process = process.model_dump(mode="json")
        connection.send_result(
            msg["id"], {"status": "success", "process_info": process}
        )
