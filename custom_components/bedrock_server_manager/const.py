"""Constants for the Bedrock Server Manager integration."""

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
