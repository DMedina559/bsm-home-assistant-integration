<div style="text-align: center;">
    <img src="https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/bedrock_server_manager/web/static/image/icon/favicon.svg" alt="BSM Logo" width="150">
</div>

# Bedrock Server Manager - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/v/release/dmedina559/bsm-home-assistant-integration)](https://github.com/dmedina559/bsm-home-assistant-integration/releases/latest)
[![License](https://img.shields.io/github/license/dmedina559/bsm-home-assistant-integration)](LICENSE)

This Home Assistant integration connects to your self-hosted [Bedrock Server Manager (BSM)](https://github.com/dmedina559/bedrock-server-manager) API. It allows you to monitor server status, resource usage, and control a wide range of server actions directly from your Home Assistant dashboards and automations. Manage installations, backups, restores, properties, allowlists, permissions, and send console commands with ease.

## Prerequisites

*   Home Assistant installation (Version 2024.x or later recommended).
*   A running instance of the [Bedrock Server Manager (BSM)](https://github.com/dmedina559/bedrock-server-manager) application.
*   The BSM API must be accessible over the network from your Home Assistant instance (know its Host/IP address and Port).
*   API Credentials (Username and Password) configured for your BSM instance.
*   [HACS](https://hacs.xyz/) (Home Assistant Community Store) installed in Home Assistant for the recommended installation method.

## Installation

### Recommended: HACS Installation

* Easily add the Bedrock Server Manager integration to HACS using this button:

    [![image](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dmedina559&repository=bsm-home-assistant-integration&category=integration)

1.  **Ensure HACS is Installed:** If you don't have HACS, install it first from [hacs.xyz](https://hacs.xyz/).
2.  **Add Custom Repository:**

    *Manually add the custom repository to HACS if the button above doesn't work:*
    *   Open HACS in Home Assistant.
    *   Go to "Integrations".
    *   Click the three dots menu (⋮) in the top right and select "Custom repositories".
    *   In the "Repository" field, enter the URL of this GitHub repository: `https://github.com/dmedina559/bsm-home-assistant-integration`.
    *   Select "Integration" as the category.
    *   Click "Add".
3.  **Install Integration:**
    *   The "Bedrock Server Manager" integration should now appear in your HACS integrations list (you might need to search for it).
    *   Click "Install" and follow the HACS prompts.
4.  **Restart Home Assistant:** After installation via HACS, a restart of Home Assistant is required (Developer Tools -> Server Management -> Restart, or Settings -> System -> Restart).

### Manual Installation

1.  **Download:** Download the `bedrock_server_manager` folder from the `custom_components` directory of the latest [release](https://github.com/YOUR_USERNAME/YOUR_BSM_HA_INTEGRATION_REPO/releases) or the main branch of this repository.
2.  **Copy:** Copy the entire `bedrock_server_manager` folder into your Home Assistant `<config>/custom_components/` directory. If the `custom_components` directory doesn't exist, create it. The final path should be `<config>/custom_components/bedrock_server_manager/`.
3.  **Restart Home Assistant:** As above.

## Configuration

Once installed and Home Assistant is restarted, configure the integration via the UI:

1.  Go to **Settings -> Devices & Services**.
2.  Click the **+ Add Integration** button in the bottom right.
3.  Search for "Bedrock Server Manager" and select it.
4.  **Step 1: Connect to Manager**
    *   **Host / IP Address:** The address of your BSM instance.
    *   **Port:** The port BSM API is listening on (defaults to 11325).
    *   **API Username & Password:** Credentials for the BSM API.
    *   Click **Submit**.
5.  **Step 2: Select Initial Servers**
    *   A list of Minecraft server instances discovered on your BSM will be shown.
    *   Use the multi-select listbox to choose which servers you want Home Assistant to initially monitor. You can change this selection later via the **CONFIGURE** option on the integration card.
    *   Click **Submit**.
6.  The integration will set up a device for the BSM instance and child devices for each selected Minecraft server.

## Lovelace Custom Cards

This integration provides the backend entities and services. To create a more user-friendly interface in your dashboards, custom Lovelace cards are available:


- ### Send Server Commands
- ### Server Properties Manager
- ### Server Allowlist Manager
- ### Server Permissions Manager
- ### Server Restore Card
- ### Server Content Installer

## Features

### Devices

*   **Bedrock Server Manager @ {host}**: A central device representing the BSM API instance. Global actions and sensors are linked here.
*   **Minecraft Server ({server_name})**: A separate device for each selected Minecraft server instance, linked to the Manager device via the "CONFIGURE" option.

### Entities

Entity IDs are typically `platform.server_name_entity_key` (e.g., `sensor.server_name_status`) or `platform.manager_id_entity_key` for global entities.

*   **Sensors (Per Server Device):**
    *   **Status:** Current state (`Running`, `Stopped`, etc.). *Attributes:* World Name, Installed Version, Allowlisted Players (list of names), All Server Properties (dictionary), PID, Uptime (when running).
    *   **CPU Usage:** CPU percentage (%). *Attributes:* PID, Uptime (when running).
    *   **Memory Usage:** Memory usage (MiB).
    *   **Permissioned Players:** Count of players in the server's `permissions.json`. *Attributes:* Full list of permissioned players with XUIDs and levels.
    *   **World Backups:** Count of available world backups. *Attributes:* List of world backup filenames.
    *   **Config Backups:** Count of available config backups. *Attributes:* List of config backup filenames.
*   **Sensors (Manager Device):**
    *   **Known Players:** Count of players in the global `players.json`. *Attributes:* Full list of global players with XUIDs and any stored notes.
    *   **Available Worlds:** Count of `.mcworld` files in the manager's content directory. *Attributes:* List of available world filenames.
    *   **Available Addons:** Count of `.mcpack`/`.mcaddon` files in the manager's content directory. *Attributes:* List of available addon filenames.
*   **Switch (Per Server Device):**
    *   **Server Control:** Start/Stop the server. Reflects running state.
*   **Buttons (Per Server Device):**
    *   **Restart:** Restarts the server.
    *   **Update:** Initiates server update process.
    *   **Backup:** Triggers a full backup (`backup_type: all`).
    *   **Export World:** Exports the server's current world.
    *   **Prune Backups:** Prunes old backups for this server.
*   **Buttons (Manager Device):**
    *   **Scan Player Logs:** Triggers manager to scan player logs.

### Services

All services use the domain `bedrock_server_manager`.

*   **`send_command`**: Sends a console command.
    *   Target: Server device(s)/entity(s).
    *   Data: `command` (string, required).
*   **`prune_download_cache`**: Prunes global download cache.
    *   Target: None.
    *   Data: `directory` (string, required), `keep` (integer, optional).
*   **`trigger_backup`**: Triggers a specific backup type.
    *   Target: Server device(s)/entity(s).
    *   Data: `backup_type` (string, required: `all`, `world`, `config`), `file_to_backup` (string, optional, required for `config` type).
*   **`restore_backup`**: Restores a specific backup. **CAUTION: Overwrites data.**
    *   Target: Server device(s)/entity(s).
    *   Data: `restore_type` (string, required: `world`, `config`), `backup_file` (string, required: filename relative to server's backup folder).
*   **`restore_latest_all`**: Restores latest full backup. **CAUTION: Overwrites data.**
    *   Target: Server device(s)/entity(s).
    *   Data: None.
*   **`add_to_allowlist`**: Adds players to a server's allowlist.
    *   Target: Server device(s)/entity(s).
    *   Data: `players` (list of strings, required), `ignores_player_limit` (boolean, optional).
*   **`remove_from_allowlist`**: Removes a player from a server's allowlist.
    *   Target: Server device(s)/entity(s).
    *   Data: `player_name` (string, required).
*   **`set_permissions`**: Sets server-specific player permissions via XUID.
    *   Target: Server device(s)/entity(s).
    *   Data: `permissions` (dictionary, required: `{"XUID": "level", ...}`).
*   **`update_properties`**: Updates allowed `server.properties` values.
    *   Target: Server device(s)/entity(s).
    *   Data: `properties` (dictionary, required: `{"key": "value", ...}`).
*   **`install_server`**: Installs a new server instance via the manager.
    *   Target: None.
    *   Data: `server_name` (string, required), `server_version` (string, required), `overwrite` (boolean, optional).
*   **`delete_server`**: Permanently deletes ALL data for a server. **IRREVERSIBLE.**
    *   Target: Server device(s)/entity(s).
    *   Data: `confirm_deletion` (boolean, required: must be `true`).
*   **`configure_os_service`**: Configures OS service settings for a server.
    *   Target: Server device(s)/entity(s).
    *   Data: `autoupdate` (boolean, required), `autostart` (boolean, optional, Linux only).
*   **`install_world`**: Installs a `.mcworld` file to a server. **CAUTION: Overwrites current world.**
    *   Target: Server device(s)/entity(s).
    *   Data: `filename` (string, required: relative to manager's `content/worlds`).
*   **`install_addon`**: Installs an `.mcpack`/`.mcaddon` to a server.
    *   Target: Server device(s)/entity(s).
    *   Data: `filename` (string, required: relative to manager's `content/addons`).
*   **`add_global_players`**: Adds/updates players in the manager's global `players.json`.
    *   Target: None.
    *   Data: `players` (list of strings, required: `"PlayerName:PlayerXUID"` format).

## Options / Reconfiguration

After adding the integration, click **CONFIGURE** on its card in Devices & Services to:
*   Update API Credentials.
*   Select/Deselect Servers to Monitor by Home Assistant.
*   Update Polling Interval for individual server status.
*   Update Polling Interval for global manager data.

Changes trigger an automatic reload of the integration.

## Troubleshooting

*   **Errors during Setup/Load:** Check Home Assistant logs (Settings -> System -> Logs) for messages related to `bedrock_server_manager`. Verify BSM API access, credentials, port, and domain name consistency (underscores only in code/directory). Ensure `/api/servers` and `/api/info` endpoints exist on your BSM.
*   **Entities Unavailable:** Check HA logs for coordinator errors. Ensure BSM is running.
*   **Custom Card Issues:** Clear browser cache thoroughly after updating card JS files or HA. Check browser's developer console (F12) for JavaScript errors.
*   **Debug Logging:** Add to `configuration.yaml` and restart HA:
    ```yaml
    logger:
      logs:
        custom_components.bedrock_server_manager: debug
    ```