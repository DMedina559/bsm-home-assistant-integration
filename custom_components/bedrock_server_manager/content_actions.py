"Typed SDK content actions for HA services."

import logging
from typing import Optional

from bsm_api_client import BedrockServerManagerApi
from bsm_api_client.models import (
    BackupActionPayload,
    FileNamePayload,
    PruneDownloadsPayload,
    RestoreActionPayload,
)

from .action_common import _base_api_call_handler

_LOGGER = logging.getLogger(__name__)


async def _async_handle_prune_downloads(
    api: BedrockServerManagerApi, directory: str, keep: Optional[int], manager_id: str
):
    payload = PruneDownloadsPayload(directory=directory, keep=keep)
    return await _base_api_call_handler(
        api.application.async_prune_downloads(payload), "Prune downloads", manager_id
    )


async def _async_handle_trigger_backup(
    api: BedrockServerManagerApi,
    server: str,
    backup_type: str,
    file_to_backup: Optional[str],
):
    payload = BackupActionPayload(
        backup_type=backup_type, file_to_backup=file_to_backup
    )
    return await _base_api_call_handler(
        api.content.async_trigger_server_backup(server, payload),
        "Trigger backup",
        server,
    )


async def _async_handle_restore_backup(
    api: BedrockServerManagerApi, server: str, restore_type: str, backup_file: str
):
    payload = RestoreActionPayload(restore_type=restore_type, backup_file=backup_file)
    return await _base_api_call_handler(
        api.content.async_restore_server_backup(server, payload),
        "Restore backup",
        server,
    )


async def _async_handle_install_world(
    api: BedrockServerManagerApi, server: str, filename: str
):
    payload = FileNamePayload(filename=filename)
    return await _base_api_call_handler(
        api.content.async_install_server_world(server, payload), "Install world", server
    )


async def _async_handle_install_addon(
    api: BedrockServerManagerApi, server: str, filename: str
):
    payload = FileNamePayload(filename=filename)
    return await _base_api_call_handler(
        api.content.async_install_server_addon(server, payload), "Install addon", server
    )
