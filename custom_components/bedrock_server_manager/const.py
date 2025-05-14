# custom_components/bedrock_server_manager/const.py
"""Constants for the Bedrock Server Manager integration."""

import json
from pathlib import Path

# --- Frontend Card URL Base ---
FRONTEND_URL_BASE = "/bsm_cards"  # Used by frontend.py to register JS modules

# --- Integration Domain ---
DOMAIN = "bedrock_server_manager"

# --- Supported Platforms ---
PLATFORMS = [
    "sensor",
    "switch",
    "button",
]  # Add "binary_sensor", "select", etc., if used

# --- Configuration Keys (used in config_flow.py, options_flow.py, and config_entry) ---
CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_USE_SSL = "use_ssl"  # For enabling HTTPS connection to BSM API
CONF_SERVER_NAMES = "servers"  # Key for list of selected server names in

# --- Scan Interval Configuration Keys (used in options_flow.py) ---
CONF_MANAGER_SCAN_INTERVAL = "manager_scan_interval"  # For global/manager-level data
CONF_SERVER_SCAN_INTERVAL = (
    "scan_interval"  # Generic name for server-specific scan interval in options
)

# --- Default Values ---
DEFAULT_PORT = 11325  # Default BSM API port
DEFAULT_MANAGER_SCAN_INTERVAL_SECONDS = 600  # 10 minutes for manager-level data
DEFAULT_SCAN_INTERVAL_SECONDS = 30  # For individual server data updates

# --- Attribute Keys (used for entity states and attributes) ---
ATTR_WORLD_NAME = "world_name"
ATTR_INSTALLED_VERSION = "installed_version"
ATTR_PID = "pid"
ATTR_CPU_PERCENT = "cpu_percent"
ATTR_MEMORY_MB = "memory_mb"
ATTR_UPTIME = "uptime"
ATTR_PLAYERS_ONLINE = (
    "players_online"  # This would likely be derived or require another API call
)
ATTR_MAX_PLAYERS = "max_players"  # Typically from server.properties
ATTR_ALLOWLISTED_PLAYERS = "allowed_players"  # Full list from allowlist.json
ATTR_SERVER_PROPERTIES = "server_properties"  # Full dict from server.properties
ATTR_GLOBAL_PLAYERS_LIST = "global_players_list"  # Full list of known players
ATTR_SERVER_PERMISSIONS_LIST = "server_permissions"  # Full list from permissions.json
ATTR_WORLD_BACKUPS_LIST = "world_backups_list"
ATTR_CONFIG_BACKUPS_LIST = "config_backups_list"
ATTR_AVAILABLE_WORLDS_LIST = "available_worlds_list"  # From BSM content dir
ATTR_AVAILABLE_ADDONS_LIST = "available_addons_list"  # From BSM content dir

# --- State/Key Constants  ---
KEY_GLOBAL_PLAYERS_COUNT = "global_players_count"
KEY_SERVER_PERMISSIONS_COUNT = "server_permissions_count"
KEY_WORLD_BACKUPS_COUNT = "world_backups_count"
KEY_CONFIG_BACKUPS_COUNT = "config_backups_count"
KEY_AVAILABLE_WORLDS_COUNT = "available_worlds_count"
KEY_AVAILABLE_ADDONS_COUNT = "available_addons_count"
KEY_LEVEL_NAME = "level_name"
KEY_ALLOWLIST_COUNT = "allowlist_count"

# --- Service Names (used in services.yaml and services.py) ---
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
SERVICE_ADD_GLOBAL_PLAYERS = "add_global_players"
SERVICE_SCAN_PLAYERS = "scan_players"  # Added based on client method async_scan_players

# --- Service Field Names (used in service calls and services.yaml schema) ---
FIELD_COMMAND = "command"
FIELD_DIRECTORY = "directory"
FIELD_KEEP = "keep"
FIELD_BACKUP_TYPE = "backup_type"
FIELD_FILE_TO_BACKUP = "file_to_backup"
FIELD_RESTORE_TYPE = "restore_type"
FIELD_BACKUP_FILE = "backup_file"
FIELD_SERVER_NAME = (
    "server_name"  # Often used as target_entity for server-specific services
)
FIELD_SERVER_VERSION = "server_version"
FIELD_OVERWRITE = "overwrite"
FIELD_CONFIRM_DELETE = (
    "confirm_deletion"  # For delete_server service, crucial safety check
)
FIELD_PLAYERS = "players"  # List of player names or player data strings
FIELD_PLAYER_NAME = "player_name"  # Single player name
FIELD_IGNORE_PLAYER_LIMIT = "ignores_player_limit"
FIELD_PERMISSIONS = "permissions"  # Dict of XUID:level
FIELD_PROPERTIES = "properties"  # Dict of server properties
FIELD_FILENAME = "filename"  # For world/addon install, backup restore
FIELD_AUTOUPDATE = "autoupdate"  # For OS service config
FIELD_AUTOSTART = "autostart"  # For OS service config (Linux)


# --- Integration Version Helper ---
def get_integration_version(integration_domain: str = DOMAIN) -> str:
    """
    Get the version of the integration from its manifest.json.
    Uses the integration_domain to find the correct manifest if this code
    were ever used in a context with multiple custom components.
    """
    try:
        # Path resolves to <config>/custom_components/bedrock_server_manager/manifest.json
        manifest_path = Path(__file__).parent / "manifest.json"
        with open(manifest_path, encoding="utf-8") as manifest_file:
            manifest_content = json.load(manifest_file)
        return manifest_content.get("version", "0.0.0-unknown")
    except FileNotFoundError:
        _LOGGER.error("Manifest.json not found for %s integration.", integration_domain)
        return "0.0.0-manifest_missing"
    except (json.JSONDecodeError, TypeError) as err:
        _LOGGER.error("Error parsing manifest.json for %s: %s", integration_domain, err)
        return "0.0.0-manifest_error"
    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.error(
            "Unexpected error getting integration version for %s: %s",
            integration_domain,
            err,
        )
        return "0.0.0-unexpected_error"


INTEGRATION_VERSION = get_integration_version()

# --- List of JS Modules for Frontend Cards ---
JS_MODULES = [
    {
        "filename": "bsm-command-card.js",
        "version": INTEGRATION_VERSION,
        "name": "BSM Send Command Card",
    },
    {
        "filename": "bsm-properties-card.js",
        "version": INTEGRATION_VERSION,
        "name": "BSM Server Properties Card",
    },
    {
        "filename": "bsm-allowlist-card.js",
        "version": INTEGRATION_VERSION,
        "name": "BSM Allowlist Card",
    },
    {
        "filename": "bsm-permissions-card.js",
        "version": INTEGRATION_VERSION,
        "name": "BSM Permissions Card",
    },
    {
        "filename": "bsm-restore-card.js",
        "version": INTEGRATION_VERSION,
        "name": "BSM Restore Card",
    },
    {
        "filename": "bsm-content-card.js",
        "version": INTEGRATION_VERSION,
        "name": "BSM Content Installer Card",
    },
]
