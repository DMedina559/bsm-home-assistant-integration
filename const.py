"""Constants for the Minecraft Bedrock Server Manager integration."""

# Domain slug for Home Assistant
DOMAIN = "minecraft_bds_manager"

# Platforms supported by this integration
PLATFORMS = ["sensor", "switch", "button"] # Add more later if needed (e.g., "binary_sensor")

# Configuration keys used in config_flow and config_entry
CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password" # Note: HA stores this securely
CONF_SERVER_NAME = "server_name"

# Default values
DEFAULT_PORT = 11325
DEFAULT_SCAN_INTERVAL_SECONDS = 30 # Default polling frequency

# Attribute keys (optional, but can help consistency)
ATTR_WORLD_NAME = "world_name"
ATTR_INSTALLED_VERSION = "installed_version"
ATTR_PID = "pid"
ATTR_CPU_PERCENT = "cpu_percent"
ATTR_MEMORY_MB = "memory_mb"
ATTR_UPTIME = "uptime"
ATTR_PLAYERS_ONLINE = "players_online" # If your status_info includes player list
ATTR_MAX_PLAYERS = "max_players"       # If your status_info includes max players

# Service names
SERVICE_SEND_COMMAND = "send_command"

# Service field names
FIELD_COMMAND = "command"