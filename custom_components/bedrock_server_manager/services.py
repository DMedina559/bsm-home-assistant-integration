# custom_components/bedrock_server_manager/services.py
"""Service handlers for the Bedrock Server Manager integration."""

import asyncio
import inspect
import logging
from typing import Any, Callable, Coroutine, Dict, List

import probatio as vol
from bsm_api_client import (
    APIError,
    AuthError,
    BedrockServerManagerApi,
    CannotConnectError,
    InvalidInputError,
)
from bsm_api_client.models import (
    AddonActionPayload,
    AddonReorderPayload,
    AddonSubpackPayload,
    InstallServerPayload,
)
from homeassistant.components.persistent_notification import async_create
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .action_common import (
    OperationOutcomeError,
    _api_error_details,
    _base_api_call_handler,
)
from .const import (
    CONF_SERVER_NAMES,
    DOMAIN,
    FIELD_AUTOSTART,
    FIELD_AUTOUPDATE,
    FIELD_BACKUP_FILE,
    FIELD_BACKUP_TYPE,
    FIELD_COMMAND,
    FIELD_CONFIRM_DELETE,
    FIELD_DIRECTORY,
    FIELD_EVENT_NAME,
    FIELD_EVENT_PAYLOAD,
    FIELD_FILE_TO_BACKUP,
    FIELD_FILENAME,
    FIELD_IGNORE_PLAYER_LIMIT,
    FIELD_KEEP,
    FIELD_OVERWRITE,
    FIELD_PACK_TYPE,
    FIELD_PACK_UUID,
    FIELD_PERMISSIONS,
    FIELD_PLAYER_NAME,
    FIELD_PLAYERS,
    FIELD_PLUGIN_ENABLED,
    FIELD_PLUGIN_NAME,
    FIELD_PROPERTIES,
    FIELD_REASON,
    FIELD_RESTORE_TYPE,
    FIELD_SERVER_NAME,
    FIELD_SERVER_VERSION,
    FIELD_SETTING_KEY,
    FIELD_SETTING_VALUE,
    FIELD_SUBPACK_NAME,
    FIELD_UUIDS,
    FIELD_XUID,
    SERVICE_ADD_GLOBAL_PLAYERS,
    SERVICE_ADD_SERVER_BAN,
    SERVICE_ADD_TO_ALLOWLIST,
    SERVICE_CONFIGURE_OS_SERVICE,
    SERVICE_DELETE_SERVER,
    SERVICE_DISABLE_ADDON,
    SERVICE_ENABLE_ADDON,
    SERVICE_INSTALL_ADDON,
    SERVICE_INSTALL_SERVER,
    SERVICE_INSTALL_WORLD,
    SERVICE_PRUNE_DOWNLOADS,
    SERVICE_RELOAD_GLOBAL_SETTINGS,
    SERVICE_REMOVE_FROM_ALLOWLIST,
    SERVICE_REMOVE_SERVER_BAN,
    SERVICE_REORDER_ADDONS,
    SERVICE_RESET_WORLD,
    SERVICE_RESTORE_BACKUP,
    SERVICE_RESTORE_LATEST_ALL,
    SERVICE_SCAN_PLAYERS,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_GLOBAL_SETTING,
    SERVICE_SET_PERMISSIONS,
    SERVICE_SET_PLUGIN_ENABLED,
    SERVICE_TRIGGER_BACKUP,
    SERVICE_TRIGGER_PLUGIN_EVENT,
    SERVICE_UNINSTALL_ADDON,
    SERVICE_UPDATE_ADDON_SUBPACK,
    SERVICE_UPDATE_PROPERTIES,
)
from .content_actions import (
    _async_handle_install_addon,
    _async_handle_install_world,
    _async_handle_prune_downloads,
    _async_handle_restore_backup,
    _async_handle_trigger_backup,
)
from .coordinator import json_data
from .data_services import register_data_services, unregister_data_services
from .manager_actions import (
    _async_handle_add_global_players,
    _async_handle_reload_global_settings,
    _async_handle_scan_players,
    _async_handle_set_global_setting,
    _async_handle_set_plugin_enabled,
    _async_handle_trigger_plugin_event,
)
from .reconcile import SERVER_RESOURCES, refresh_after_action
from .responses import action_error, action_response
from .server_actions import (
    _async_handle_add_server_ban,
    _async_handle_add_to_allowlist,
    _async_handle_configure_os_service,
    _async_handle_remove_from_allowlist,
    _async_handle_remove_server_ban,
    _async_handle_restore_latest_all,
    _async_handle_send_command,
    _async_handle_set_permissions,
    _async_handle_update_properties,
)
from .service_schemas import (
    ADD_GLOBAL_PLAYERS_SERVICE_SCHEMA,
    ADD_SERVER_BAN_SERVICE_SCHEMA,
    ADD_TO_ALLOWLIST_SERVICE_SCHEMA,
    CONFIGURE_OS_SERVICE_SCHEMA,
    DELETE_SERVER_SERVICE_SCHEMA,
    DISABLE_ADDON_SERVICE_SCHEMA,
    ENABLE_ADDON_SERVICE_SCHEMA,
    INSTALL_ADDON_SERVICE_SCHEMA,
    INSTALL_SERVER_SERVICE_SCHEMA,
    INSTALL_WORLD_SERVICE_SCHEMA,
    PRUNE_DOWNLOADS_SERVICE_SCHEMA,
    RELOAD_GLOBAL_SETTINGS_SERVICE_SCHEMA,
    REMOVE_FROM_ALLOWLIST_SERVICE_SCHEMA,
    REMOVE_SERVER_BAN_SERVICE_SCHEMA,
    REORDER_ADDONS_SERVICE_SCHEMA,
    RESTORE_BACKUP_SERVICE_SCHEMA,
    RESTORE_LATEST_ALL_SERVICE_SCHEMA,
    SCAN_PLAYERS_SERVICE_SCHEMA,
    SEND_COMMAND_SERVICE_SCHEMA,
    SET_GLOBAL_SETTING_SERVICE_SCHEMA,
    SET_PERMISSIONS_SERVICE_SCHEMA,
    SET_PLUGIN_ENABLED_SERVICE_SCHEMA,
    TARGETING_SCHEMA_FIELDS,
    TRIGGER_BACKUP_SERVICE_SCHEMA,
    TRIGGER_PLUGIN_EVENT_SERVICE_SCHEMA,
    UNINSTALL_ADDON_SERVICE_SCHEMA,
    UPDATE_ADDON_SUBPACK_SERVICE_SCHEMA,
    UPDATE_PROPERTIES_SERVICE_SCHEMA,
)
from .targets import resolve_manager_targets, resolve_server_targets

_LOGGER = logging.getLogger(__name__)


# --- Service Handler Helper Functions ---


# --- Handlers ---


async def _async_handle_install_server(
    api: BedrockServerManagerApi,
    server_name_to_install: str,
    server_version: str,
    overwrite: bool,
    manager_id: str,
):
    log_context = f"for server '{server_name_to_install}' on manager '{manager_id}'"
    payload = InstallServerPayload(
        server_name=server_name_to_install,
        server_version=server_version,
        overwrite=overwrite,
    )
    try:
        response = await api.servers.async_install_new_server(payload)
        if response.status == "confirm_needed":
            msg = f"Install server {log_context}: Server already exists and overwrite was false. Set 'overwrite: true' to replace it or use the 'delete_server' service first."
            _LOGGER.warning(msg)
            raise ServiceValidationError(msg)
        _LOGGER.info(
            "Successfully requested install %s. API Message: %s",
            log_context,
            response.message or "N/A",
        )
        return response
    except (
        AuthError,
        CannotConnectError,
        APIError,
        ValueError,
        InvalidInputError,
    ) as err:
        error_prefix = f"Install server {log_context}"
        err_msg = (
            err.api_message
            if hasattr(err, "api_message") and err.api_message
            else str(err)
        )
        status_code_msg = (
            f"(Status: {err.status_code})"
            if hasattr(err, "status_code") and err.status_code
            else ""
        )
        full_error_msg = (
            f"{error_prefix}: {type(err).__name__} {status_code_msg} - {err_msg}"
        )
        _LOGGER.error(full_error_msg)
        if isinstance(err, (ValueError, InvalidInputError)):
            raise ServiceValidationError(full_error_msg) from err
        raise HomeAssistantError(full_error_msg) from err
    except Exception as err:
        _LOGGER.exception("Install server %s: Unexpected error.", log_context)
        raise HomeAssistantError(
            f"Install server {log_context}: Unexpected error - {type(err).__name__}"
        ) from err


async def _await_task_completion(api: BedrockServerManagerApi, response):
    """Wait for an accepted destructive operation before changing HA devices."""
    if response.status != "accepted":
        return response
    try:
        async with asyncio.timeout(300):
            while True:
                snapshot = await api.tasks.async_get_task_status(response.task_id)
                if snapshot.status == "completed":
                    result = snapshot.result
                    if isinstance(result, dict) and result.get("status") in {
                        "partial",
                        "skipped",
                        "error",
                        "failed",
                    }:
                        raise OperationOutcomeError(
                            f"Task {snapshot.id}: Operation {result['status']}. {result.get('message') or snapshot.message}",
                            json_data(snapshot),
                        )
                    return snapshot
                if snapshot.status in {"failed", "cancelled"}:
                    raise HomeAssistantError(snapshot.message)
                await asyncio.sleep(2)
    except TimeoutError as error:
        raise HomeAssistantError(
            f"Task {response.task_id} is still pending; check BSM tasks before retrying"
        ) from error


async def _async_handle_delete_server(
    hass: HomeAssistant,
    api: BedrockServerManagerApi,
    server_to_delete: str,
    manager_host_port_id: str,
):
    log_context = f"for server '{server_to_delete}' on manager '{manager_host_port_id}'"
    _LOGGER.critical("EXECUTING IRREVERSIBLE DELETE %s", log_context)
    device_removed_from_ha = False
    try:
        response = await api.servers.async_delete_server(server_name=server_to_delete)
        response = await _await_task_completion(api, response)
        if response and response.status in {"success", "completed"}:
            _LOGGER.info(
                "Manager API confirmed deletion of server '%s'. Attempting HA device removal.",
                server_to_delete,
            )
            device_registry_instance = dr.async_get(hass)
            server_device_unique_value = f"{manager_host_port_id}_{server_to_delete}"
            device_identifier_tuple = (DOMAIN, server_device_unique_value)
            device_to_remove = device_registry_instance.async_get_device(
                identifiers={device_identifier_tuple}
            )
            if device_to_remove:
                _LOGGER.debug(
                    "Removing device '%s' (ID: %s) from HA registry.",
                    device_to_remove.name or device_to_remove.id,
                    device_to_remove.id,
                )
                device_registry_instance.async_remove_device(device_to_remove.id)
                device_removed_from_ha = True
            else:
                _LOGGER.warning(
                    "Could not find HA device for server '%s' (identifier: %s) to remove from registry after API deletion.",
                    server_to_delete,
                    device_identifier_tuple,
                )
            return {
                "status": "success",
                "message": response.message,
                "ha_device_removed": device_removed_from_ha,
                "server_name": server_to_delete,
                "task": json_data(response),
            }
        else:
            msg = f"Manager API did not confirm deletion {log_context}. Response: {response}"
            _LOGGER.error(msg)
            raise HomeAssistantError(msg)
    except (
        AuthError,
        CannotConnectError,
        APIError,
        ValueError,
        InvalidInputError,
    ) as err:
        error_prefix = f"Delete server {log_context}"
        err_msg = (
            err.api_message
            if hasattr(err, "api_message") and err.api_message
            else str(err)
        )
        status_code_msg = (
            f"(Status: {err.status_code})"
            if hasattr(err, "status_code") and err.status_code
            else ""
        )
        full_error_msg = (
            f"{error_prefix}: {type(err).__name__} {status_code_msg} - {err_msg}"
        )
        _LOGGER.error(full_error_msg)
        if isinstance(err, (ValueError, InvalidInputError)):
            raise ServiceValidationError(full_error_msg) from err
        raise HomeAssistantError(full_error_msg) from err
    except HomeAssistantError:
        raise
    except Exception as err:
        _LOGGER.exception("Delete server %s: Unexpected error.", log_context)
        raise HomeAssistantError(
            f"Delete server {log_context}: Unexpected error - {type(err).__name__}"
        ) from err


async def _async_handle_reset_world(
    hass: HomeAssistant,
    api: BedrockServerManagerApi,
    server_to_delete: str,
    manager_host_port_id: str,
):
    log_context = f"for server '{server_to_delete}' on manager '{manager_host_port_id}'"
    _LOGGER.critical("EXECUTING IRREVERSIBLE WORLD RESET %s", log_context)

    try:
        response = await api.content.async_reset_server_world(
            server_name=server_to_delete
        )
        response = await _await_task_completion(api, response)
        if response and response.status in {"success", "completed"}:

            return {
                "status": "success",
                "message": response.message,
            }
        else:
            msg = (
                f"Manager API did not confirm reset {log_context}. Response: {response}"
            )
            _LOGGER.error(msg)
            raise HomeAssistantError(msg)
    except (
        AuthError,
        CannotConnectError,
        APIError,
        ValueError,
        InvalidInputError,
    ) as err:
        error_prefix = f"World reset {log_context}"
        err_msg = (
            err.api_message
            if hasattr(err, "api_message") and err.api_message
            else str(err)
        )
        status_code_msg = (
            f"(Status: {err.status_code})"
            if hasattr(err, "status_code") and err.status_code
            else ""
        )
        full_error_msg = (
            f"{error_prefix}: {type(err).__name__} {status_code_msg} - {err_msg}"
        )
        _LOGGER.error(full_error_msg)
        if isinstance(err, (ValueError, InvalidInputError)):
            raise ServiceValidationError(full_error_msg) from err
        raise HomeAssistantError(full_error_msg) from err
    except HomeAssistantError:
        raise
    except Exception as err:
        _LOGGER.exception("World reset %s: Unexpected error.", log_context)
        raise HomeAssistantError(
            f"World reset {log_context}: Unexpected error - {type(err).__name__}"
        ) from err


# --- Target Resolvers and Executors ---


def _action_kwargs(handler: Callable, manager_id: str) -> dict[str, str]:
    """Provide declared manager context without maintaining action-name allowlists."""
    return (
        {"manager_id": manager_id}
        if "manager_id" in inspect.signature(handler).parameters
        else {}
    )


async def _async_forget_deleted_server(
    hass: HomeAssistant, config_entry_id: str, server_name: str
) -> None:
    """Stop monitoring a confirmed deletion and persist its deselection."""
    runtime = hass.data.get(DOMAIN, {}).get(config_entry_id, {})
    if websocket := runtime.get("ws_manager"):
        await websocket.async_remove_server(server_name)
    server_data = runtime.get("servers", {}).pop(server_name, None)
    if server_data and (coordinator := server_data.get("coordinator")):
        await coordinator.async_shutdown()
    entry = hass.config_entries.async_get_entry(config_entry_id)
    if entry and server_name in entry.options.get(CONF_SERVER_NAMES, []):
        hass.config_entries.async_update_entry(
            entry,
            options={
                **entry.options,
                CONF_SERVER_NAMES: [
                    name
                    for name in entry.options[CONF_SERVER_NAMES]
                    if name != server_name
                ],
            },
        )


async def _execute_targeted_service(
    service_call: ServiceCall,
    hass: HomeAssistant,
    handler_coro: Callable[..., Coroutine[Any, Any, Any]],
    *handler_args: Any,
):
    """Run every selected server action and reconcile state even without WebSockets."""
    targets = await resolve_server_targets(service_call, hass)
    contexts = [
        (entry_id, name, hass.data[DOMAIN][entry_id]) for entry_id, name in targets
    ]
    calls = [
        handler_coro(
            data["api"],
            name,
            *handler_args,
            **_action_kwargs(handler_coro, data["manager_identifier"][1]),
        )
        for _, name, data in contexts
    ]
    results = await asyncio.gather(*calls, return_exceptions=True)
    outcomes = []
    for (_, name, data), result in zip(contexts, results):
        if _applied_work(result):
            refresh_after_action(
                data.get("servers", {}).get(name, {}).get("coordinator"),
                SERVER_RESOURCES.get(service_call.service),
            )
        outcomes.append(
            {
                "manager_url": data["manager_identifier"][1],
                "server_name": name,
                **_outcome(result),
            }
        )
    if all(isinstance(result, Exception) for result in results) and not (
        service_call.return_response
        and any(_applied_work(result) for result in results)
    ):
        _raise_action_errors(results)
    return action_response(outcomes)


async def _execute_manager_targeted_service(
    service_call: ServiceCall,
    hass: HomeAssistant,
    handler_coro: Callable[..., Coroutine[Any, Any, Any]],
    *handler_args: Any,
):
    """Supply typed action context and refresh successfully changed manager resources."""
    targets = await resolve_manager_targets(service_call, hass)
    contexts = [hass.data[DOMAIN][entry_id] for entry_id in targets]
    results = await asyncio.gather(
        *(
            handler_coro(
                data["api"],
                *handler_args,
                **_action_kwargs(handler_coro, data["manager_identifier"][1]),
            )
            for data in contexts
        ),
        return_exceptions=True,
    )
    outcomes = []
    for data, result in zip(contexts, results):
        if _applied_work(result):
            for key in ("manager_coordinator", "monitor_coordinator"):
                if (
                    service_call.service
                    in {"set_global_setting", "reload_global_settings"}
                    and key == "manager_coordinator"
                ):
                    refresh_after_action(data.get(key), {"application_settings"})
                else:
                    refresh_after_action(data.get(key))
        outcomes.append(
            {"manager_url": data["manager_identifier"][1], **_outcome(result)}
        )
    if all(isinstance(result, Exception) for result in results) and not (
        service_call.return_response
        and any(_applied_work(result) for result in results)
    ):
        _raise_action_errors(results)
    return action_response(outcomes)


def _applied_work(result: Any) -> bool:
    """Partial operations and committed-error responses also require refreshes."""
    cause = result.__cause__ if isinstance(result, Exception) else None
    return (
        not isinstance(result, Exception)
        or isinstance(result, OperationOutcomeError)
        or isinstance(cause, APIError)
        and cause.api_code == "operation_incomplete"
    )


def _outcome(result: Any) -> dict:
    """Retain structured failures and partial results alongside successful targets."""
    if not isinstance(result, Exception):
        value = json_data(result)
        status = value.get("status") if isinstance(value, dict) else None
        return {
            "status": status if status in {"partial", "skipped"} else "success",
            "result": value,
            "warnings": [],
        }
    payload: dict[str, Any] = {"error": action_error(result), "status": "failed"}
    if isinstance(result, OperationOutcomeError):
        payload["result"] = result.result
    cause = result if isinstance(result, APIError) else result.__cause__
    if isinstance(cause, APIError):
        payload["error"] = action_error(cause)
        if cause.operation_result is not None:
            payload["result"] = cause.operation_result
    return payload


def _raise_action_errors(results: list[Any]) -> None:
    """Report failed targets to HA instead of silently acknowledging their actions."""
    errors = [str(result) for result in results if isinstance(result, Exception)]
    if errors:
        raise HomeAssistantError("BSM action failed: " + "; ".join(errors))


async def _async_handle_server_lifecycle_action(api, server: str, action: str):
    """Dispatch a fixed lifecycle action and preserve its typed outcome."""
    methods = {
        "update_server": api.servers.async_update_server,
        "restart_server": api.servers.async_restart_server,
    }
    return await _base_api_call_handler(methods[action](server), action, server)


async def async_handle_server_lifecycle_service(call: ServiceCall, hass: HomeAssistant):
    """Expose response-capable server controls for dashboards and automations."""
    return await _execute_targeted_service(
        call, hass, _async_handle_server_lifecycle_action, call.service
    )


async def _async_handle_reload_plugins(api):
    """Reload plugins and return any accepted task identifier."""
    return await _base_api_call_handler(
        api.plugins.async_reload_plugins(), "Reload plugins"
    )


async def async_handle_reload_plugins_service(call: ServiceCall, hass: HomeAssistant):
    """Reload and reconcile plugins on each targeted manager."""
    return await _execute_manager_targeted_service(
        call, hass, _async_handle_reload_plugins
    )


# --- Main Service Handlers ---
async def async_handle_send_command_service(service: ServiceCall, hass: HomeAssistant):
    return await _execute_targeted_service(
        service, hass, _async_handle_send_command, service.data[FIELD_COMMAND]
    )


async def async_handle_prune_downloads_service(
    service: ServiceCall, hass: HomeAssistant
):
    return await _execute_manager_targeted_service(
        service,
        hass,
        _async_handle_prune_downloads,
        service.data[FIELD_DIRECTORY],
        service.data.get(FIELD_KEEP),
    )


async def async_handle_trigger_backup_service(
    service: ServiceCall, hass: HomeAssistant
):
    if service.data[FIELD_BACKUP_TYPE] == "config" and not service.data.get(
        FIELD_FILE_TO_BACKUP
    ):
        raise ServiceValidationError(
            f"'{FIELD_FILE_TO_BACKUP}' is required when '{FIELD_BACKUP_TYPE}' is 'config'."
        )
    return await _execute_targeted_service(
        service,
        hass,
        _async_handle_trigger_backup,
        service.data[FIELD_BACKUP_TYPE],
        service.data.get(FIELD_FILE_TO_BACKUP),
    )


async def async_handle_restore_backup_service(
    service: ServiceCall, hass: HomeAssistant
):
    return await _execute_targeted_service(
        service,
        hass,
        _async_handle_restore_backup,
        service.data[FIELD_RESTORE_TYPE],
        service.data[FIELD_BACKUP_FILE],
    )


async def async_handle_restore_latest_all_service(
    service: ServiceCall, hass: HomeAssistant
):
    return await _execute_targeted_service(
        service, hass, _async_handle_restore_latest_all
    )


async def async_handle_install_server_service(
    service: ServiceCall, hass: HomeAssistant
):
    return await _execute_manager_targeted_service(
        service,
        hass,
        _async_handle_install_server,
        service.data[FIELD_SERVER_NAME],
        service.data[FIELD_SERVER_VERSION],
        service.data[FIELD_OVERWRITE],
    )


async def async_handle_scan_players_service(service: ServiceCall, hass: HomeAssistant):
    return await _execute_manager_targeted_service(
        service, hass, _async_handle_scan_players
    )


async def async_handle_set_plugin_enabled_service(
    service: ServiceCall, hass: HomeAssistant
):
    return await _execute_manager_targeted_service(
        service,
        hass,
        _async_handle_set_plugin_enabled,
        service.data[FIELD_PLUGIN_NAME],
        service.data[FIELD_PLUGIN_ENABLED],
    )


async def async_handle_trigger_plugin_event_service(
    service: ServiceCall, hass: HomeAssistant
):
    return await _execute_manager_targeted_service(
        service,
        hass,
        _async_handle_trigger_plugin_event,
        service.data[FIELD_EVENT_NAME],
        service.data.get(FIELD_EVENT_PAYLOAD),
    )


async def async_handle_delete_server_service(  # noqa: C901
    service: ServiceCall, hass: HomeAssistant
):
    _LOGGER.warning(
        "Executing delete_server service call. User confirmation was: %s",
        service.data[FIELD_CONFIRM_DELETE],
    )

    try:
        resolved_targets = await resolve_server_targets(service, hass)
    except (HomeAssistantError, ServiceValidationError) as e:
        _LOGGER.error("Failed to resolve targets for delete_server service: %s", e)
        raise

    tasks = []
    processed_targets_for_notification: List[Dict[str, Any]] = []

    for config_entry_id, server_name_to_delete in resolved_targets:
        try:
            entry_data = hass.data[DOMAIN][config_entry_id]
            api_client: BedrockServerManagerApi = entry_data["api"]
            manager_host_port_id = entry_data["manager_identifier"][1]

            tasks.append(
                _async_handle_delete_server(
                    hass, api_client, server_name_to_delete, manager_host_port_id
                )
            )
            processed_targets_for_notification.append(
                {
                    "server_name": server_name_to_delete,
                    "manager_id": manager_host_port_id,
                    "config_entry_id": config_entry_id,
                }
            )
        except KeyError:
            _LOGGER.error(
                "Data missing for config entry %s (server %s) for delete_server service. Skipping.",
                config_entry_id,
                server_name_to_delete,
            )
            processed_targets_for_notification.append(
                {
                    "server_name": server_name_to_delete,
                    "error_queuing": "Missing entry data",
                    "manager_id": "Unknown",
                }
            )
        except Exception:
            _LOGGER.exception(
                "Error queueing delete_server for server %s (entry %s)",
                server_name_to_delete,
                config_entry_id,
            )
            processed_targets_for_notification.append(
                {
                    "server_name": server_name_to_delete,
                    "error_queuing": "Exception during queueing",
                    "manager_id": "Unknown",
                }
            )

    if not tasks and resolved_targets:
        async_create(
            hass,
            "Could not queue deletion for any targeted servers due to setup issues. Check logs.",
            "Minecraft Server Deletion Problem",
            f"bsm_delete_{service.context.id}_queue_fail",
        )
        raise HomeAssistantError("Could not queue any targeted operations")
    if not tasks:
        return

    results = await asyncio.gather(*tasks, return_exceptions=True)

    success_messages: List[str] = []
    failure_messages: List[str] = []

    result_iter = iter(results)
    for target_info in processed_targets_for_notification:
        sname = target_info["server_name"]

        if target_info.get("error_queuing"):
            failure_messages.append(
                f"'{sname}': Failed to queue for deletion ({target_info['error_queuing']})."
            )
            continue

        result_or_exc = next(result_iter)
        if isinstance(result_or_exc, Exception):
            err_msg = (
                result_or_exc.args[0] if result_or_exc.args else str(result_or_exc)
            )
            failure_messages.append(
                f"'{sname}': Failed ({type(result_or_exc).__name__} - {err_msg})."
            )
        elif (
            isinstance(result_or_exc, dict) and result_or_exc.get("status") == "success"
        ):
            await _async_forget_deleted_server(
                hass, target_info["config_entry_id"], sname
            )
            msg = f"'{sname}': API deletion successful."
            if result_or_exc.get("ha_device_removed"):
                msg += " HA device removed."
            else:
                msg += " HA device not found or not removed from HA."
            success_messages.append(msg)
        else:
            failure_messages.append(
                f"'{sname}': API deletion status unclear or failed (Result: {result_or_exc})."
            )

    final_notification_parts = []
    if success_messages:
        final_notification_parts.append(f"Successes: {'; '.join(success_messages)}")
    if failure_messages:
        final_notification_parts.append(f"Failures: {'; '.join(failure_messages)}")

    if not final_notification_parts:
        final_notification_parts.append(
            "No deletion actions were completed or status is unclear. Check logs for details."
        )

    async_create(
        hass=hass,
        message=" ".join(final_notification_parts),
        title="Minecraft Server Deletion Results",
        notification_id=f"bsm_delete_results_{service.context.id}",
    )
    if failure_messages:
        raise HomeAssistantError("; ".join(failure_messages))


async def async_handle_add_to_allowlist_service(
    service: ServiceCall, hass: HomeAssistant
):
    return await _execute_targeted_service(
        service,
        hass,
        _async_handle_add_to_allowlist,
        service.data[FIELD_PLAYERS],
        service.data[FIELD_IGNORE_PLAYER_LIMIT],
    )


async def async_handle_remove_from_allowlist_service(
    service: ServiceCall, hass: HomeAssistant
):
    return await _execute_targeted_service(
        service,
        hass,
        _async_handle_remove_from_allowlist,
        service.data[FIELD_PLAYERS],
    )


async def async_handle_add_server_ban_service(
    service: ServiceCall, hass: HomeAssistant
):
    return await _execute_targeted_service(
        service,
        hass,
        _async_handle_add_server_ban,
        service.data[FIELD_PLAYER_NAME],
        service.data[FIELD_XUID],
        service.data.get(FIELD_REASON),
    )


async def async_handle_remove_server_ban_service(
    service: ServiceCall, hass: HomeAssistant
):
    return await _execute_targeted_service(
        service,
        hass,
        _async_handle_remove_server_ban,
        service.data[FIELD_XUID],
    )


async def async_handle_set_permissions_service(
    service: ServiceCall, hass: HomeAssistant
):
    return await _execute_targeted_service(
        service, hass, _async_handle_set_permissions, service.data[FIELD_PERMISSIONS]
    )


async def async_handle_reset_world_service(  # noqa: C901
    service: ServiceCall, hass: HomeAssistant
):
    _LOGGER.warning(
        "Executing reset_world service call. User confirmation was: %s",
        service.data[FIELD_CONFIRM_DELETE],
    )

    try:
        resolved_targets = await resolve_server_targets(service, hass)
    except (HomeAssistantError, ServiceValidationError) as e:
        _LOGGER.error("Failed to resolve targets for reset_world service: %s", e)
        raise

    tasks = []
    processed_targets_for_notification: List[Dict[str, Any]] = []

    for config_entry_id, server_name_to_delete in resolved_targets:
        try:
            entry_data = hass.data[DOMAIN][config_entry_id]
            api_client: BedrockServerManagerApi = entry_data["api"]
            manager_host_port_id = entry_data["manager_identifier"][1]

            tasks.append(
                _async_handle_reset_world(
                    hass, api_client, server_name_to_delete, manager_host_port_id
                )
            )
            processed_targets_for_notification.append(
                {
                    "server_name": server_name_to_delete,
                    "manager_id": manager_host_port_id,
                    "config_entry_id": config_entry_id,
                }
            )
        except KeyError:
            _LOGGER.error(
                "Data missing for config entry %s (server %s) for reset_world service. Skipping.",
                config_entry_id,
                server_name_to_delete,
            )
            processed_targets_for_notification.append(
                {
                    "server_name": server_name_to_delete,
                    "error_queuing": "Missing entry data",
                    "manager_id": "Unknown",
                }
            )
        except Exception:
            _LOGGER.exception(
                "Error queueing reset_world for server %s (entry %s)",
                server_name_to_delete,
                config_entry_id,
            )
            processed_targets_for_notification.append(
                {
                    "server_name": server_name_to_delete,
                    "error_queuing": "Exception during queueing",
                    "manager_id": "Unknown",
                }
            )

    if not tasks and resolved_targets:
        async_create(
            hass,
            "Could not queue reset for any targeted servers due to setup issues. Check logs.",
            "Minecraft Server Reset Problem",
            f"bsm_reset_{service.context.id}_queue_fail",
        )
        raise HomeAssistantError("Could not queue any targeted operations")
    if not tasks:
        return

    results = await asyncio.gather(*tasks, return_exceptions=True)

    success_messages: List[str] = []
    failure_messages: List[str] = []

    result_iter = iter(results)
    for target_info in processed_targets_for_notification:
        sname = target_info["server_name"]

        if target_info.get("error_queuing"):
            failure_messages.append(
                f"'{sname}': Failed to queue for reset ({target_info['error_queuing']})."
            )
            continue

        result_or_exc = next(result_iter)
        if isinstance(result_or_exc, Exception):
            err_msg = (
                result_or_exc.args[0] if result_or_exc.args else str(result_or_exc)
            )
            failure_messages.append(
                f"'{sname}': Failed ({type(result_or_exc).__name__} - {err_msg})."
            )
        elif (
            isinstance(result_or_exc, dict) and result_or_exc.get("status") == "success"
        ):
            msg = f"'{sname}': API reset successful."
            success_messages.append(msg)
        else:
            failure_messages.append(
                f"'{sname}': API reset status unclear or failed (Result: {result_or_exc})."
            )

    final_notification_parts = []
    if success_messages:
        final_notification_parts.append(f"Successes: {'; '.join(success_messages)}")
    if failure_messages:
        final_notification_parts.append(f"Failures: {'; '.join(failure_messages)}")

    if not final_notification_parts:
        final_notification_parts.append(
            "No reset actions were completed or status is unclear. Check logs for details."
        )

    async_create(
        hass=hass,
        message=" ".join(final_notification_parts),
        title="Minecraft Server Reset Results",
        notification_id=f"bsm_reset_results_{service.context.id}",
    )
    if failure_messages:
        raise HomeAssistantError("; ".join(failure_messages))


async def async_handle_update_properties_service(
    service: ServiceCall, hass: HomeAssistant
):
    return await _execute_targeted_service(
        service, hass, _async_handle_update_properties, service.data[FIELD_PROPERTIES]
    )


async def async_handle_install_world_service(service: ServiceCall, hass: HomeAssistant):
    return await _execute_targeted_service(
        service, hass, _async_handle_install_world, service.data[FIELD_FILENAME]
    )


async def _async_handle_enable_addon(
    api: BedrockServerManagerApi, server: str, pack_uuid: str, pack_type: str
):
    payload = AddonActionPayload.model_validate(
        {"pack_uuid": pack_uuid, "pack_type": pack_type}
    )
    return await _base_api_call_handler(
        api.content.async_enable_server_addon(server, payload), "Enable addon", server
    )


async def _async_handle_disable_addon(
    api: BedrockServerManagerApi, server: str, pack_uuid: str, pack_type: str
):
    payload = AddonActionPayload.model_validate(
        {"pack_uuid": pack_uuid, "pack_type": pack_type}
    )
    return await _base_api_call_handler(
        api.content.async_disable_server_addon(server, payload), "Disable addon", server
    )


async def _async_handle_uninstall_addon(
    api: BedrockServerManagerApi, server: str, pack_uuid: str, pack_type: str
):
    payload = AddonActionPayload.model_validate(
        {"pack_uuid": pack_uuid, "pack_type": pack_type}
    )
    return await _base_api_call_handler(
        api.content.async_uninstall_server_addon(server, payload),
        "Uninstall addon",
        server,
    )


async def _async_handle_reorder_addons(
    api: BedrockServerManagerApi, server: str, pack_type: str, uuids: list[str]
):
    payload = AddonReorderPayload.model_validate(
        {"pack_type": pack_type, "uuids": uuids}
    )
    return await _base_api_call_handler(
        api.content.async_reorder_server_addon(server, payload),
        "Reorder addons",
        server,
    )


async def _async_handle_update_addon_subpack(
    api: BedrockServerManagerApi,
    server: str,
    pack_uuid: str,
    pack_type: str,
    subpack_name: str,
):
    payload = AddonSubpackPayload.model_validate(
        {"pack_uuid": pack_uuid, "pack_type": pack_type, "subpack_name": subpack_name}
    )
    return await _base_api_call_handler(
        api.content.async_update_server_addon_subpack(server, payload),
        "Update addon subpack",
        server,
    )


async def async_handle_enable_addon_service(service: ServiceCall, hass: HomeAssistant):
    return await _execute_targeted_service(
        service,
        hass,
        _async_handle_enable_addon,
        service.data[FIELD_PACK_UUID],
        service.data[FIELD_PACK_TYPE],
    )


async def async_handle_disable_addon_service(service: ServiceCall, hass: HomeAssistant):
    return await _execute_targeted_service(
        service,
        hass,
        _async_handle_disable_addon,
        service.data[FIELD_PACK_UUID],
        service.data[FIELD_PACK_TYPE],
    )


async def async_handle_uninstall_addon_service(
    service: ServiceCall, hass: HomeAssistant
):
    return await _execute_targeted_service(
        service,
        hass,
        _async_handle_uninstall_addon,
        service.data[FIELD_PACK_UUID],
        service.data[FIELD_PACK_TYPE],
    )


async def async_handle_reorder_addons_service(
    service: ServiceCall, hass: HomeAssistant
):
    return await _execute_targeted_service(
        service,
        hass,
        _async_handle_reorder_addons,
        service.data[FIELD_PACK_TYPE],
        service.data[FIELD_UUIDS],
    )


async def async_handle_update_addon_subpack_service(
    service: ServiceCall, hass: HomeAssistant
):
    return await _execute_targeted_service(
        service,
        hass,
        _async_handle_update_addon_subpack,
        service.data[FIELD_PACK_UUID],
        service.data[FIELD_PACK_TYPE],
        service.data[FIELD_SUBPACK_NAME],
    )


async def async_handle_install_addon_service(service: ServiceCall, hass: HomeAssistant):
    return await _execute_targeted_service(
        service, hass, _async_handle_install_addon, service.data[FIELD_FILENAME]
    )


async def async_handle_configure_os_service_service(
    service: ServiceCall, hass: HomeAssistant
):
    """Keep the existing action name while updating typed server settings."""
    payload: Dict[str, bool] = {FIELD_AUTOUPDATE: service.data[FIELD_AUTOUPDATE]}
    if FIELD_AUTOSTART in service.data:
        payload[FIELD_AUTOSTART] = service.data[FIELD_AUTOSTART]
    return await _execute_targeted_service(
        service, hass, _async_handle_configure_os_service, payload
    )


async def async_handle_add_global_players_service(
    service: ServiceCall, hass: HomeAssistant
):
    return await _execute_manager_targeted_service(
        service, hass, _async_handle_add_global_players, service.data[FIELD_PLAYERS]
    )


async def async_handle_set_global_setting_service(
    service: ServiceCall, hass: HomeAssistant
):
    return await _execute_manager_targeted_service(
        service,
        hass,
        _async_handle_set_global_setting,
        service.data[FIELD_SETTING_KEY],
        service.data[FIELD_SETTING_VALUE],
    )


async def async_handle_reload_global_settings_service(
    service: ServiceCall, hass: HomeAssistant
):
    return await _execute_manager_targeted_service(
        service,
        hass,
        _async_handle_reload_global_settings,
    )


# --- Service Registration/Removal ---
async def async_register_services(hass: HomeAssistant) -> None:
    """Register services with Home Assistant."""
    register_data_services(hass)
    service_mapping: dict[
        str, tuple[Callable[..., Coroutine[Any, Any, Any]], vol.Schema]
    ] = {
        SERVICE_RESET_WORLD: (
            async_handle_reset_world_service,
            DELETE_SERVER_SERVICE_SCHEMA,
        ),
        SERVICE_SCAN_PLAYERS: (
            async_handle_scan_players_service,
            SCAN_PLAYERS_SERVICE_SCHEMA,
        ),
        SERVICE_SEND_COMMAND: (
            async_handle_send_command_service,
            SEND_COMMAND_SERVICE_SCHEMA,
        ),
        SERVICE_PRUNE_DOWNLOADS: (
            async_handle_prune_downloads_service,
            PRUNE_DOWNLOADS_SERVICE_SCHEMA,
        ),
        SERVICE_TRIGGER_BACKUP: (
            async_handle_trigger_backup_service,
            TRIGGER_BACKUP_SERVICE_SCHEMA,
        ),
        SERVICE_RESTORE_BACKUP: (
            async_handle_restore_backup_service,
            RESTORE_BACKUP_SERVICE_SCHEMA,
        ),
        SERVICE_RESTORE_LATEST_ALL: (
            async_handle_restore_latest_all_service,
            RESTORE_LATEST_ALL_SERVICE_SCHEMA,
        ),
        SERVICE_INSTALL_SERVER: (
            async_handle_install_server_service,
            INSTALL_SERVER_SERVICE_SCHEMA,
        ),
        SERVICE_DELETE_SERVER: (
            async_handle_delete_server_service,
            DELETE_SERVER_SERVICE_SCHEMA,
        ),
        SERVICE_ADD_TO_ALLOWLIST: (
            async_handle_add_to_allowlist_service,
            ADD_TO_ALLOWLIST_SERVICE_SCHEMA,
        ),
        SERVICE_REMOVE_FROM_ALLOWLIST: (
            async_handle_remove_from_allowlist_service,
            REMOVE_FROM_ALLOWLIST_SERVICE_SCHEMA,
        ),
        SERVICE_ADD_SERVER_BAN: (
            async_handle_add_server_ban_service,
            ADD_SERVER_BAN_SERVICE_SCHEMA,
        ),
        SERVICE_REMOVE_SERVER_BAN: (
            async_handle_remove_server_ban_service,
            REMOVE_SERVER_BAN_SERVICE_SCHEMA,
        ),
        SERVICE_SET_PERMISSIONS: (
            async_handle_set_permissions_service,
            SET_PERMISSIONS_SERVICE_SCHEMA,
        ),
        SERVICE_UPDATE_PROPERTIES: (
            async_handle_update_properties_service,
            UPDATE_PROPERTIES_SERVICE_SCHEMA,
        ),
        SERVICE_INSTALL_WORLD: (
            async_handle_install_world_service,
            INSTALL_WORLD_SERVICE_SCHEMA,
        ),
        SERVICE_ENABLE_ADDON: (
            async_handle_enable_addon_service,
            ENABLE_ADDON_SERVICE_SCHEMA,
        ),
        SERVICE_DISABLE_ADDON: (
            async_handle_disable_addon_service,
            DISABLE_ADDON_SERVICE_SCHEMA,
        ),
        SERVICE_UNINSTALL_ADDON: (
            async_handle_uninstall_addon_service,
            UNINSTALL_ADDON_SERVICE_SCHEMA,
        ),
        SERVICE_REORDER_ADDONS: (
            async_handle_reorder_addons_service,
            REORDER_ADDONS_SERVICE_SCHEMA,
        ),
        SERVICE_UPDATE_ADDON_SUBPACK: (
            async_handle_update_addon_subpack_service,
            UPDATE_ADDON_SUBPACK_SERVICE_SCHEMA,
        ),
        SERVICE_INSTALL_ADDON: (
            async_handle_install_addon_service,
            INSTALL_ADDON_SERVICE_SCHEMA,
        ),
        SERVICE_CONFIGURE_OS_SERVICE: (
            async_handle_configure_os_service_service,
            CONFIGURE_OS_SERVICE_SCHEMA,
        ),
        SERVICE_ADD_GLOBAL_PLAYERS: (
            async_handle_add_global_players_service,
            ADD_GLOBAL_PLAYERS_SERVICE_SCHEMA,
        ),
        SERVICE_SET_PLUGIN_ENABLED: (
            async_handle_set_plugin_enabled_service,
            SET_PLUGIN_ENABLED_SERVICE_SCHEMA,
        ),
        SERVICE_TRIGGER_PLUGIN_EVENT: (
            async_handle_trigger_plugin_event_service,
            TRIGGER_PLUGIN_EVENT_SERVICE_SCHEMA,
        ),
        SERVICE_SET_GLOBAL_SETTING: (
            async_handle_set_global_setting_service,
            SET_GLOBAL_SETTING_SERVICE_SCHEMA,
        ),
        SERVICE_RELOAD_GLOBAL_SETTINGS: (
            async_handle_reload_global_settings_service,
            RELOAD_GLOBAL_SETTINGS_SERVICE_SCHEMA,
        ),
    }

    service_mapping.update(
        {
            "update_server": (
                async_handle_server_lifecycle_service,
                vol.Schema(TARGETING_SCHEMA_FIELDS),
            ),
            "restart_server": (
                async_handle_server_lifecycle_service,
                vol.Schema(TARGETING_SCHEMA_FIELDS),
            ),
            "reload_plugins": (
                async_handle_reload_plugins_service,
                vol.Schema(TARGETING_SCHEMA_FIELDS),
            ),
        }
    )

    for service_name, (handler, schema) in service_mapping.items():
        if not hass.services.has_service(DOMAIN, service_name):

            async def service_wrapper_closure(
                call: ServiceCall, captured_handler=handler
            ):
                _LOGGER.debug(
                    "Service call '%s.%s' received, dispatching to %s.",
                    call.domain,
                    call.service,
                    captured_handler.__name__,
                )
                try:
                    result = await captured_handler(call, hass)
                    return result or {"results": []}
                except ServiceValidationError as sve:
                    _LOGGER.warning(
                        "Service validation error in %s for %s.%s: %s",
                        captured_handler.__name__,
                        call.domain,
                        call.service,
                        sve,
                    )
                    raise
                except HomeAssistantError as hae:
                    _LOGGER.error(
                        "HomeAssistantError in %s for %s.%s: %s",
                        captured_handler.__name__,
                        call.domain,
                        call.service,
                        hae,
                    )
                    raise
                except Exception as exc:
                    _LOGGER.exception(
                        "Unexpected error in service handler %s for %s.%s",
                        captured_handler.__name__,
                        call.domain,
                        call.service,
                    )
                    raise HomeAssistantError(
                        f"Unexpected error executing service {call.domain}.{call.service}: {type(exc).__name__} - {exc}"
                    ) from exc

            hass.services.async_register(
                DOMAIN,
                service_name,
                service_wrapper_closure,
                schema=schema,
                supports_response=SupportsResponse.OPTIONAL,
            )
            _LOGGER.debug("Registered service: %s.%s", DOMAIN, service_name)


async def async_remove_services(hass: HomeAssistant) -> None:
    """Remove previously registered services."""
    domain_data = hass.data.get(DOMAIN)
    is_last_entry = True
    if domain_data:
        is_last_entry = not any(
            not entry_id.startswith("_") for entry_id in domain_data
        )

    if is_last_entry:
        _LOGGER.info(
            "Last BSM config entry unloaded or no entries active. Removing all BSM services."
        )
        unregister_data_services(hass)
        services_to_unregister = [
            SERVICE_RESET_WORLD,
            SERVICE_SCAN_PLAYERS,
            "update_server",
            "restart_server",
            "reload_plugins",
            SERVICE_SEND_COMMAND,
            SERVICE_PRUNE_DOWNLOADS,
            SERVICE_TRIGGER_BACKUP,
            SERVICE_RESTORE_BACKUP,
            SERVICE_RESTORE_LATEST_ALL,
            SERVICE_INSTALL_SERVER,
            SERVICE_DELETE_SERVER,
            SERVICE_ADD_TO_ALLOWLIST,
            SERVICE_REMOVE_FROM_ALLOWLIST,
            SERVICE_ADD_SERVER_BAN,
            SERVICE_REMOVE_SERVER_BAN,
            SERVICE_SET_PERMISSIONS,
            SERVICE_UPDATE_PROPERTIES,
            SERVICE_INSTALL_WORLD,
            SERVICE_ENABLE_ADDON,
            SERVICE_DISABLE_ADDON,
            SERVICE_UNINSTALL_ADDON,
            SERVICE_REORDER_ADDONS,
            SERVICE_UPDATE_ADDON_SUBPACK,
            SERVICE_INSTALL_ADDON,
            SERVICE_CONFIGURE_OS_SERVICE,
            SERVICE_ADD_GLOBAL_PLAYERS,
            SERVICE_SET_PLUGIN_ENABLED,
            SERVICE_TRIGGER_PLUGIN_EVENT,
            SERVICE_SET_GLOBAL_SETTING,
            SERVICE_RELOAD_GLOBAL_SETTINGS,
        ]
        for service_name in services_to_unregister:
            if hass.services.has_service(DOMAIN, service_name):
                _LOGGER.debug("Removing service: %s.%s", DOMAIN, service_name)
                hass.services.async_remove(DOMAIN, service_name)

        if domain_data:
            domain_data.pop("_services_registered", None)
            if not domain_data:
                hass.data.pop(DOMAIN, None)
    else:
        _LOGGER.debug(
            "Other BSM config entries still loaded. Services will not be removed."
        )


__all__ = ["_base_api_call_handler", "_api_error_details"]
