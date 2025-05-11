"""Constants for the Bedrock Server Manager integration."""

import json
from pathlib import Path


FRONTEND_URL_BASE = f"/bsm_cards"

# Domain slug for Home Assistant
DOMAIN = "bedrock_server_manager"

# Platforms supported by this integration
PLATFORMS = ["sensor", "switch", "button"]

# Configuration keys used in config_flow and config_entry
CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SERVER_NAME = "server_name"
CONF_SERVER_NAMES = "servers"


CONF_MANAGER_SCAN_INTERVAL = "manager_scan_interval"
DEFAULT_MANAGER_SCAN_INTERVAL_SECONDS = 600

# Default values
DEFAULT_PORT = 11325
DEFAULT_SCAN_INTERVAL_SECONDS = 30

# Attribute keys
ATTR_WORLD_NAME = "world_name"
ATTR_INSTALLED_VERSION = "installed_version"
ATTR_PID = "pid"
ATTR_CPU_PERCENT = "cpu_percent"
ATTR_MEMORY_MB = "memory_mb"
ATTR_UPTIME = "uptime"
ATTR_PLAYERS_ONLINE = "players_online"
ATTR_MAX_PLAYERS = "max_players"
ATTR_ALLOWLISTED_PLAYERS = "allowed_players"
ATTR_SERVER_PROPERTIES = "server_properties"
ATTR_GLOBAL_PLAYERS_LIST = "global_players_list"
ATTR_SERVER_PERMISSIONS_LIST = "server_permissions"
ATTR_WORLD_BACKUPS_LIST = "world_backups_list"
ATTR_CONFIG_BACKUPS_LIST = "config_backups_list"
ATTR_AVAILABLE_WORLDS_LIST = "available_worlds_list"
ATTR_AVAILABLE_ADDONS_LIST = "available_addons_list"


KEY_GLOBAL_PLAYERS = "global_players_count"
KEY_SERVER_PERMISSIONS_COUNT = "server_permissions_count"
KEY_WORLD_BACKUPS_COUNT = "world_backups_count"
KEY_CONFIG_BACKUPS_COUNT = "config_backups_count"
KEY_AVAILABLE_WORLDS_COUNT = "available_worlds_count"
KEY_AVAILABLE_ADDONS_COUNT = "available_addons_count"

# Service names
SERVICE_SEND_COMMAND = "send_command"
SERVICE_PRUNE_DOWNLOADS = "prune_download_cache"
SERVICE_TRIGGER_BACKUP = "trigger_backup"
SERVICE_RESTORE_BACKUP = "restore_backup"
SERVICE_RESTORE_LATEST_ALL = "restore_latest_all"
SERVICE_INSTALL_SERVER = "install_server"
SERVICE_DELETE_SERVER = "delete_server"
SERVICE_ADD_TO_ALLOWLIST = "add_to_allowlist"
SERVICE_REMOVE_FROM_ALLOWLIST = "remove_from_allowlist"
SERVICE_SET_PERMISSIONS = "set_permissions"
SERVICE_UPDATE_PROPERTIES = "update_properties"
SERVICE_INSTALL_WORLD = "install_world"
SERVICE_INSTALL_ADDON = "install_addon"
SERVICE_CONFIGURE_OS_SERVICE = "configure_os_service"
SERVICE_CONFIGURE_OS_SERVICE = "configure_os_service"
SERVICE_ADD_GLOBAL_PLAYERS = "add_global_players"

# Service field names
FIELD_COMMAND = "command"
FIELD_DIRECTORY = "directory"
FIELD_KEEP = "keep"
FIELD_BACKUP_TYPE = "backup_type"
FIELD_FILE_TO_BACKUP = "file_to_backup"
FIELD_RESTORE_TYPE = "restore_type"
FIELD_BACKUP_FILE = "backup_file"
FIELD_SERVER_NAME = "server_name"
FIELD_SERVER_VERSION = "server_version"
FIELD_OVERWRITE = "overwrite"
FIELD_CONFIRM_DELETE = "confirm_deletion"
FIELD_PLAYERS = "players"
FIELD_PLAYER_NAME = "player_name"
FIELD_IGNORE_PLAYER_LIMIT = "ignores_player_limit"
FIELD_PERMISSIONS = "permissions"
FIELD_PROPERTIES = "properties"
FIELD_FILENAME = "filename"
FIELD_AUTOUPDATE = "autoupdate"
FIELD_AUTOSTART = "autostart"


def get_integration_version(integration_name: str = DOMAIN) -> str:
    """Get the version of the integration."""
    try:
        manifest_path = Path(__file__).parent / "manifest.json"
        with open(manifest_path, encoding="utf-8") as manifest_file:
            manifest = json.load(manifest_file)
        return manifest.get("version", "0.0.0-unknown")
    except (FileNotFoundError, json.JSONDecodeError):
        return "0.0.0-error"


INTEGRATION_VERSION = get_integration_version()

# List of JS modules to register
# Add dictionaries for each card JS file
JS_MODULES = [
    {
        "filename": "bsm-command-card.js",
        "version": INTEGRATION_VERSION,  # Link to integration version
        "name": "Send Command Card",  # Friendly name for logging
    },
    {
        "filename": "bsm-properties-card.js",
        "version": INTEGRATION_VERSION,  # Link to integration version
        "name": "Server Properties Card",  # Friendly name for logging
    },
    {
        "filename": "bsm-allowlist-card.js",
        "version": INTEGRATION_VERSION,  # Link to integration version
        "name": "Allowlist Card",  # Friendly name for logging
    },
    {
        "filename": "bsm-permissions-card.js",
        "version": INTEGRATION_VERSION,  # Link to integration version
        "name": "Permissions Card",  # Friendly name for logging
    },
    {
        "filename": "bsm-restore-card.js",
        "version": INTEGRATION_VERSION,  # Link to integration version
        "name": "Restore Card",  # Friendly name for logging
    },
    {
        "filename": "bsm-content-card.js",
        "version": INTEGRATION_VERSION,  # Link to integration version
        "name": "Content Installer Card",  # Friendly name for logging
    },
]
