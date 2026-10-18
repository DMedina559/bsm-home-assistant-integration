"""Typed Home Assistant service input schemas shared by action handlers."""

from typing import Any

import probatio as vol
from homeassistant.const import ATTR_AREA_ID, ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.helpers import config_validation as cv

from .const import (
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
)

# --- Service Schema Definitions ---
TARGETING_SCHEMA_FIELDS: dict[Any, Any] = {
    vol.Optional(ATTR_DEVICE_ID): object,
    vol.Optional(ATTR_ENTITY_ID): object,
    vol.Optional(ATTR_AREA_ID): object,
}

SEND_COMMAND_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_COMMAND): cv.string,
        **TARGETING_SCHEMA_FIELDS,
    }
)
PRUNE_DOWNLOADS_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_DIRECTORY): cv.string,
        vol.Optional(FIELD_KEEP): vol.All(vol.Coerce(int), vol.Range(min=0)),
        **TARGETING_SCHEMA_FIELDS,
    }
)
TRIGGER_BACKUP_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_BACKUP_TYPE): vol.In(["all", "world", "config"]),
        vol.Optional(FIELD_FILE_TO_BACKUP): cv.string,
        **TARGETING_SCHEMA_FIELDS,
    }
)
RESTORE_BACKUP_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_RESTORE_TYPE): vol.In(
            ["world", "allowlist", "properties", "permissions"]
        ),
        vol.Required(FIELD_BACKUP_FILE): cv.string,
        **TARGETING_SCHEMA_FIELDS,
    }
)
RESTORE_LATEST_ALL_SERVICE_SCHEMA = vol.Schema(
    {
        **TARGETING_SCHEMA_FIELDS,
    }
)
INSTALL_SERVER_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_SERVER_NAME): cv.string,
        vol.Required(FIELD_SERVER_VERSION): cv.string,
        vol.Optional(FIELD_OVERWRITE, default=False): cv.boolean,
        **TARGETING_SCHEMA_FIELDS,
    }
)
DELETE_SERVER_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_CONFIRM_DELETE): True,
        **TARGETING_SCHEMA_FIELDS,
    }
)
ADD_TO_ALLOWLIST_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PLAYERS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(FIELD_IGNORE_PLAYER_LIMIT, default=False): cv.boolean,
        **TARGETING_SCHEMA_FIELDS,
    }
)
REMOVE_FROM_ALLOWLIST_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PLAYERS): vol.All(cv.ensure_list, [cv.string]),
        **TARGETING_SCHEMA_FIELDS,
    }
)
ADD_SERVER_BAN_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PLAYER_NAME): cv.string,
        vol.Required(FIELD_XUID): cv.string,
        vol.Optional(FIELD_REASON): cv.string,
        **TARGETING_SCHEMA_FIELDS,
    }
)
REMOVE_SERVER_BAN_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_XUID): cv.string,
        **TARGETING_SCHEMA_FIELDS,
    }
)
SET_PERMISSIONS_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PERMISSIONS): vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required("name"): cv.string,
                        vol.Required("xuid"): cv.string,
                        vol.Required("permission_level"): vol.In(
                            ["visitor", "member", "operator"]
                        ),
                    }
                )
            ],
        ),
        **TARGETING_SCHEMA_FIELDS,
    }
)
UPDATE_PROPERTIES_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PROPERTIES): vol.Schema(
            {cv.string: vol.Any(str, int, bool)}
        ),
        **TARGETING_SCHEMA_FIELDS,
    }
)
INSTALL_WORLD_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_FILENAME): cv.string,
        **TARGETING_SCHEMA_FIELDS,
    }
)
INSTALL_ADDON_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_FILENAME): cv.string,
        **TARGETING_SCHEMA_FIELDS,
    }
)

ENABLE_ADDON_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PACK_UUID): cv.string,
        vol.Required(FIELD_PACK_TYPE): vol.In(["behavior", "resource"]),
        **TARGETING_SCHEMA_FIELDS,
    }
)

DISABLE_ADDON_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PACK_UUID): cv.string,
        vol.Required(FIELD_PACK_TYPE): vol.In(["behavior", "resource"]),
        **TARGETING_SCHEMA_FIELDS,
    }
)

UNINSTALL_ADDON_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PACK_UUID): cv.string,
        vol.Required(FIELD_PACK_TYPE): vol.In(["behavior", "resource"]),
        **TARGETING_SCHEMA_FIELDS,
    }
)

REORDER_ADDONS_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PACK_TYPE): vol.In(["behavior", "resource"]),
        vol.Required(FIELD_UUIDS): vol.All(cv.ensure_list, [cv.string]),
        **TARGETING_SCHEMA_FIELDS,
    }
)

UPDATE_ADDON_SUBPACK_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PACK_UUID): cv.string,
        vol.Required(FIELD_PACK_TYPE): vol.In(["behavior", "resource"]),
        vol.Required(FIELD_SUBPACK_NAME): cv.string,
        **TARGETING_SCHEMA_FIELDS,
    }
)

CONFIGURE_OS_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_AUTOUPDATE): cv.boolean,
        vol.Optional(FIELD_AUTOSTART): cv.boolean,
        **TARGETING_SCHEMA_FIELDS,
    }
)
ADD_GLOBAL_PLAYERS_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PLAYERS): vol.All(
            cv.ensure_list,
            [cv.matches_regex(r"^[a-zA-Z0-9_ .\-']{1,32}:[0-9]{16,19}$")],
        ),
        **TARGETING_SCHEMA_FIELDS,
    }
)
SCAN_PLAYERS_SERVICE_SCHEMA = vol.Schema(
    {
        **TARGETING_SCHEMA_FIELDS,
    }
)

SET_PLUGIN_ENABLED_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_PLUGIN_NAME): cv.string,
        vol.Required(FIELD_PLUGIN_ENABLED): cv.boolean,
        **TARGETING_SCHEMA_FIELDS,
    }
)
TRIGGER_PLUGIN_EVENT_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_EVENT_NAME): cv.string,
        vol.Optional(FIELD_EVENT_PAYLOAD): vol.Schema(dict),
        **TARGETING_SCHEMA_FIELDS,
    }
)

SET_GLOBAL_SETTING_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_SETTING_KEY): cv.string,
        vol.Required(FIELD_SETTING_VALUE): vol.Any(
            str, int, float, bool, list, dict, None
        ),
        **TARGETING_SCHEMA_FIELDS,
    }
)

RELOAD_GLOBAL_SETTINGS_SERVICE_SCHEMA = vol.Schema(
    {
        **TARGETING_SCHEMA_FIELDS,
    }
)
