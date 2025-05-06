<div style="text-align: center;">
    <img src="https://github.com/DMedina559/bedrock-server-manager/blob/main/bedrock_server_manager/web/static/image/icon/favicon.svg" alt="ICON" width="200" height="200">
</div>

# Home Assistant Integration Bedrock Server Manager

<!-- [![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs) -->

Connect Home Assistant with your [Bedrock Server Manager](https://github.com/dmedina559/bedrock-server-manager). Monitor server status, resource usage, and control server actions like start, stop, restart, backups, restores, and send commands directly from Home Assistant dashboards and automations.

## Prerequisites

*   Home Assistant installation (Version 2023.x or later recommended).
*   A running instance of the Bedrock Server Manager (BSM) application.
*   The BSM API must be accessible over the network from your Home Assistant instance (know the Host/IP address and Port).
*   Credentials (Username and Password) configured for the BSM API.
*   [HACS](https://hacs.xyz/) (Home Assistant Community Store) installed in Home Assistant (Recommended installation method).

## Installation

### Recommended: HACS Installation

* Easily add the Bedrock Server Manager integration to HACS using this button:

    [![image](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dmedina559&repository=bsm-home-assistant-integration&category=integration)

1.  **Add Custom Repository:**
    *   Open HACS in Home Assistant (usually in the sidebar).
    *   Go to "Integrations".
    *   Click the three dots menu (⋮) in the top right and select "Custom repositories".
    *   In the "Repository" field, enter the URL `https://github.com/dmedina559/bsm-home-assistant-integration`
    *   Select "Integration" as the category.
    *   Click "Add".
2.  **Install:**
    *   Close the custom repositories dialog.
    *   Search for "Bedrock Server Manager"
    *   Click "Install".
    *   Follow the prompts to install the integration.
3.  **Restart Home Assistant:** After installation via HACS, restart Home Assistant (Developer Tools -> Server Management -> Restart).

### Manual Installation

1.  **Download:** Download the latest release or clone the repository.
2.  **Copy:** Copy the entire `./custom_components/bedrock_server_manager` folder, into your Home Assistant `/config/custom_components/` directory. Create `custom_components` if it doesn't exist.
3.  **Restart Home Assistant:** Restart Home Assistant (Developer Tools -> Server Management -> Restart).

## Configuration

Configuration is done entirely through the Home Assistant UI after installation.

1.  Go to **Settings -> Devices & Services**.
2.  Click **+ Add Integration**.
3.  Search for "Bedrock Server Manager" and select it.
4.  **Step 1: Connect to Manager**
    *   Enter the **Host / IP Address** of your BSM instance.
    *   Enter the **Port** the BSM API is listening on (defaults to 11325).
    *   Enter the **API Username** configured for BSM.
    *   Enter the **API Password** configured for BSM.
    *   Click **Submit**. The integration will attempt to connect, authenticate, and discover manageable servers.
5.  **Step 2: Select Initial Servers**
    *   If the connection is successful, you will see a dropdown menu where you can select which Minecraft servers you want to add to Home Assistant.
    *   Select the servers you wish to initially monitor and control from Home Assistant. You can select none initially and add (or remove) them later via the "Configure" option.
    *   Click **Submit**.
6.  The integration will be set up, creating devices and entities for the selected servers.

## Features

This integration creates devices in Home Assistant to represent your manager and servers:

### Devices

*   **BSM @ {host}**: A central hub device representing the Bedrock Server Manager API instance itself. Global actions are linked here.
*   **{server_name}**: A separate device for each Minecraft server instance you selected during setup or configuration. These are linked to the main BSM device.

### Entities

Entities are linked to their corresponding **Server Device** unless otherwise noted:

*   **Sensor:**
    *   `sensor.{server_name}_status`: Shows the current state (`Running`, `Stopped`, `Unknown`, `Not Found`).
    *   `sensor.{server_name}_cpu_usage`: CPU percentage used by the server process (%). Requires `psutil` on manager host.
    *   `sensor.{server_name}_memory_usage`: Memory used by the server process (MiB). Requires `psutil` on manager host.
*   **Switch:**
    *   `switch.{server_name}_server`: Allows starting (`turn_on`) and stopping (`turn_off`) the server. Reflects the running state.
*   **Button (Server Specific):**
    *   `button.{server_name}_restart`: Restarts the Minecraft server process.
    *   `button.{server_name}_update`: Checks for and applies updates to the server based on manager config.
    *   `button.{server_name}_backup`: Triggers a full backup (`backup_type: all`) for the server.
    *   `button.{server_name}_export_world`: Exports the current server world to a `.mcworld` file.
    *   `button.{server_name}_prune_backups`: Prunes old backups for this server based on manager settings.
*   **Button (Manager Global - Linked to `BSM @ {host}` device):**
    *   `button.bedrock_server_manager_{host_port_id}_scan_player_logs`: Triggers the manager to scan player logs.

### Services

Services allow for more control via automations and scripts.

*   **`bedrock_server_manager.send_command`**:
    *   Sends a console command to specific server(s).
    *   **Target:** Server device(s) or entity(s) (e.g., `entity_id: sensor.{server_name}_status`).
    *   **Data:**
        *   `command` (Required, string): The command to send (e.g., `say Hello`).

*   **`bedrock_server_manager.prune_download_cache`**:
    *   Prunes the global download cache on the manager host.
    *   **Target:** None required (global action, targets the BSM instance itself).
    *   **Data:**
        *   `directory` (Required, string): Absolute path to the download cache directory on the manager host.
        *   `keep` (Optional, integer): Number of newest files to keep (uses manager default if omitted).

*   **`bedrock_server_manager.trigger_backup`**:
    *   Triggers a specific type of backup for target server(s).
    *   **Target:** Server device(s) or entity(s).
    *   **Data:**
        *   `backup_type` (Required, string): `all`, `world`, or `config`.
        *   `file_to_backup` (Optional, string): Relative path required only if `backup_type` is `config`.

*   **`bedrock_server_manager.restore_backup`**:
    *   Restores a specific backup file for target server(s). **CAUTION: Overwrites data.**
    *   **Target:** Server device(s) or entity(s).
    *   **Data:**
        *   `restore_type` (Required, string): `world` or `config`.
        *   `backup_file` (Required, string): Full path to the backup file on the manager host.

*   **`bedrock_server_manager.restore_latest_all`**:
    *   Restores the latest full backup for target server(s). **CAUTION: Overwrites data.**
    *   **Target:** Server device(s) or entity(s).
    *   **Data:** None.

*   **`bedrock_server_manager.add_to_allowlist`**:
    *   Adds player(s) to the allowlist for target server(s).
    *   **Target:** Server device(s) or entity(s).
    *   **Data:**
        *   `players` (Required, list of strings): Gamertags to add.
        *   `ignores_player_limit` (Optional, boolean, default `false`).

*   **`bedrock_server_manager.remove_from_allowlist`**:
    *   Removes a player from the allowlist for target server(s).
    *   **Target:** Server device(s) or entity(s).
    *   **Data:**
        *   `player_name` (Required, string): Gamertag to remove.

*   **`bedrock_server_manager.set_permissions`**:
    *   Sets permission levels for player(s) via XUID for target server(s).
    *   **Target:** Server device(s) or entity(s).
    *   **Data:**
        *   `permissions` (Required, dictionary): `{"XUID1": "level", "XUID2": "level", ...}`. Valid levels: `visitor`, `member`, `operator`.

*   **`bedrock_server_manager.update_properties`**:
    *   Updates allowed `server.properties` values for target server(s).
    *   **Target:** Server device(s) or entity(s).
    *   **Data:**
        *   `properties` (Required, dictionary): `{"property-key": "value", ...}`. See BSM docs for allowed keys.

*   **`bedrock_server_manager.install_server`**:
    *   Installs a new server instance via the manager.
    *   **Target:** None required (global action).
    *   **Data:**
        *   `server_name` (Required, string): Desired unique name.
        *   `server_version` (Required, string): `LATEST`, `PREVIEW`, or specific version `x.y.z`.
        *   `overwrite` (Optional, boolean, default `false`).

*   **`bedrock_server_manager.delete_server`**:
    *   Permanently deletes ALL data for target server instance(s). **IRREVERSIBLE - USE EXTREME CAUTION.**
    *   **Target:** Server device(s) or entity(s).
    *   **Data:**
        *   `confirm_deletion` (Required, boolean: must be `true`).

*   **`bedrock_server_manager.configure_os_service`**:
    *   Configures OS-specific service settings for target server(s).
    *   **Target:** Server device(s) or entity(s).
    *   **Data:**
        *   `autoupdate` (Required, boolean): Enable/disable autoupdate.
        *   `autostart` (Optional, boolean): (Linux Only) Enable/disable autostart via systemd user service.

*   **`bedrock_server_manager.install_world`**:
    *   Installs a `.mcworld` file into the target server, replacing the current world. **CAUTION: Overwrites data.**
    *   **Target:** Server device(s) or entity(s).
    *   **Data:**
        *   `filename` (Required, string): The `.mcworld` filename (e.g., `MyBackup.mcworld`) relative to the manager's `content/worlds` directory.

*   **`bedrock_server_manager.install_addon`**:
    *   Installs an `.mcaddon` or `.mcpack` file into the target server.
    *   **Target:** Server device(s) or entity(s).
    *   **Data:**
        *   `filename` (Required, string): The `.mcaddon` or `.mcpack` filename (e.g., `MyAwesomeAddon.mcaddon`) relative to the manager's `content/addons` directory.

## Options / Reconfiguration

After adding the integration, you can change settings without removing and re-adding:

1.  Go to **Settings -> Devices & Services**.
2.  Find the "Bedrock Server Manager" integration entry.
3.  Click **CONFIGURE**.
4.  A menu will appear allowing you to:
    *   **Update API Credentials:** Change the username and password used to connect to the BSM API.
    *   **Select Servers to Monitor:** Add or remove servers from the list that Home Assistant monitors and creates entities for.
    *   **Update Polling Interval:** Change how frequently Home Assistant polls the BSM API for the status of *running* servers.

Changes typically require the integration to reload automatically.

## Troubleshooting

*   **Errors during Setup:** Check the Home Assistant logs (Settings -> System -> Logs -> Load Full Logs) for messages related to `bedrock_server_manager`, `config_flow`, or `api`. Ensure the BSM API is running and accessible from Home Assistant, and that credentials are correct.
*   **Entities Unavailable:** If entities become unavailable, check the HA logs for connection errors or API errors reported by the coordinator. Verify the BSM application is running. The "Status" sensor might show "Unknown" or "Not Found" based on the error.
*   **Debug Logging:** To enable detailed logging, add the following to your `configuration.yaml`:
    ```yaml
    logger:
      logs:
        custom_components.bedrock_server_manager: debug
    ```
    Then restart Home Assistant.