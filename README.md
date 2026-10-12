<div style="text-align: center;">
    <img src="https://raw.githubusercontent.com/DMedina559/bsm-frontend/main/frontend/public/image/icon/favicon.svg" alt="BSM Logo" width="150">
</div>

# Bedrock Server Manager - Home Assistant Integration

<p align="center">
  <a href="https://github.com/dmedina559/bsm-home-assistant-integration">
    <img src="https://img.shields.io/badge/HACS-Default-41BDF5.svg?logo=HomeAssistantCommunityStore&logoColor=white" alt="HACS Default Store">
  </a>
  <a href="https://github.com/dmedina559/bsm-home-assistant-integration/releases">
    <img alt="Stable" src="https://img.shields.io/github/v/release/dmedina559/bsm-home-assistant-integration?label=Stable&color=blue">
  </a>
  <a href="https://github.com/dmedina559/bsm-home-assistant-integration/releases">
    <img alt="Pre-Release" src="https://img.shields.io/github/v/release/dmedina559/bsm-home-assistant-integration?include_prereleases&label=Pre-Release&color=red">
  </a>
  <a href="https://github.com/dmedina559/bsm-home-assistant-integration/actions">
    <img alt="Tests" src="https://img.shields.io/github/actions/workflow/status/dmedina559/bsm-home-assistant-integration/hasstest.yaml?label=Tests&event=push">
  </a>
</p>

This Home Assistant integration connects to your self-hosted [Bedrock Server Manager (BSM)](https://github.com/dmedina559/bedrock-server-manager) API. It allows you to monitor server status, resource usage, and control a wide range of server actions directly from your Home Assistant dashboards and automations. Manage installations, backups, restores, properties, allowlists, permissions, and send console commands with ease.

## Prerequisites

*   Home Assistant 2026.10 or newer (Python 3.14).
*   A running instance of the [Bedrock Server Manager (BSM)](https://github.com/dmedina559/bedrock-server-manager) 4.0.0b5 or newer, with metrics, health, task and revisioned WebSocket contracts.
*   `bsm-api-client` 1.7.0b3 or newer (installed automatically by Home Assistant).
*   The BSM API must be accessible over the network from your Home Assistant instance (know its Host/IP address and Port).
*   API Credentials (Username and Password) configured for your BSM instance.
*   [HACS](https://hacs.xyz/) (Home Assistant Community Store) installed in Home Assistant for the recommended installation method.

## Installation

### Recommended: HACS Installation

>[!tip]
> Easily open the Bedrock Server Manager integration in HACS using this button:
>
> [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dmedina559&repository=bsm-home-assistant-integration&category=integration)

1.  **Ensure HACS is Installed:** If you don't have HACS, install it first from [hacs.xyz](https://hacs.xyz/).
2.  **Install Integration:**
    *   Navigate to **HACS -> Integrations** in Home Assistant.
    *   The "Bedrock Server Manager" integration should appear in your HACS integrations list (you might need to search for it).
    *   Click "Install" and follow the HACS prompts.
3.  **Restart Home Assistant:** After installation via HACS, a restart of Home Assistant is required (Developer Tools -> Server Management -> Restart, or Settings -> System -> Restart).

### Manual Installation

1.  **Download:** Download the `bedrock_server_manager` folder from the `custom_components` directory of the latest [release](https://github.com/dmedina559/bsm-home-assistant-integration/releases) or the main branch of this repository.
2.  **Copy:** Copy the entire `bedrock_server_manager` folder into your Home Assistant `<config>/custom_components/` directory. If the `custom_components` directory doesn't exist, create it. The final path should be `<config>/custom_components/bedrock_server_manager/`.
3.  **Restart Home Assistant:** As above.

## Configuration

Once installed and Home Assistant is restarted, configure the integration via the UI:

> [!tip] 
> Easily add the integration through the Home Assistant UI:
> 
> [![Open your Home Assistant instance and show an integration.](https://my.home-assistant.io/badges/integration.svg)](https://my.home-assistant.io/redirect/integration/?domain=bedrock_server_manager)

1.  Go to **Settings -> Devices & Services**.
2.  Click the **+ Add Integration** button in the bottom right.
3.  Search for "Bedrock Server Manager" and select it.
4.  **Step 1: Connect to Manager**
    *   **Base URL:** The full BSM address, including scheme, port and any proxy path, for example `http://192.168.1.10:11325`.
    *   **API Username & Password:** Credentials for the BSM API.
    *   Click **Submit**.
5.  **Step 2: Select Initial Servers**
    *   A list of Minecraft server instances discovered on your BSM will be shown.
    *   Use the multi-select listbox to choose which servers you want Home Assistant to initially monitor. You can change this selection later via the **CONFIGURE** option on the integration card.
    *   Click **Submit**.
6.  The integration will set up a device for the BSM instance and child devices for each selected Minecraft server.

## Dashboard cards

The integration registers locally bundled cards in dashboards using storage mode. They require no CDN connection. For YAML dashboards, register each desired module manually:

```yaml
resources:
  - url: /bsm_cards/bsm-monitor-card.js
    type: module
  - url: /bsm_cards/bsm-health-card.js
    type: module
```

The card picker includes:

| Card type | Purpose |
| --- | --- |
| `custom:bsm-overview-card` | Server cards or table with start/stop, update and quick actions |
| `custom:bsm-tasks-card` | Active and completed tasks, structured results, errors and raw response |
| `custom:bsm-settings-card` | Grouped application or server settings with typed values |
| `custom:bsm-bans-card` | Manage server bans and select known players |
| `custom:bsm-api-card` | Discover and call core/plugin API operations using SDK validation |
| `custom:bsm-fleet-card` | Compact server overview; click a server to open native entity details |
| `custom:bsm-monitor-card` | Server controls, target version, settings, metrics and native history graphs |
| `custom:bsm-health-card` | API/WebSocket connectivity, health checks, separate app/system metrics and history |
| `custom:bsm-plugin-settings-card` | Plugin tabs, typed settings, server checklists and backend validation |
| `custom:bsm-command-card` | Send a server command |
| `custom:bsm-properties-card` | Edit server properties |
| `custom:bsm-allowlist-card` | Manage allowed players |
| `custom:bsm-permissions-card` | Stage and save player permissions |
| `custom:bsm-restore-card` | Restore a selected backup or latest backups |
| `custom:bsm-content-card` | Install worlds/addons, upload from HA allowed paths and export worlds |
| `custom:bsm-addon-card` | Manage addon status, order and subpacks |
| `custom:bsm-plugins-card` | Plugin status, enable/disable and reload |
| `custom:bsm-event-trigger-card` | Trigger plugin events |

Set the default server or manager with the visual editor's **Entity** field. Select the corresponding resource sensor (for example, a level-name sensor for properties or a plugin-status sensor for plugin settings). Runtime selectors list only matching resources. Entity IDs may be renamed: cards use resource metadata and device relationships, not entity-name conventions.

```yaml
type: custom:bsm-monitor-card
entity: sensor.my_server_status
history_hours: 6
```

All cards support optional `title` and `debug`. History cards support `history_hours` (1–168). The fleet card optionally accepts an `entities` list of server status sensors. The content card accepts `content_source_sensor_entity`. Existing `manager_entity`, `target_server_sensor_entity` and `target_device` configurations remain recognized; use `entity` for new configurations.

Properties, permissions, addon order and plugin settings retain unsaved edits during live updates. Conflicting external changes block saving until edits are discarded and reloaded. Plugin settings include a **Check for updates** action. Plugins without settings stay out of the settings tabs. Restore, world install and addon removal require confirmation.

Task-backed actions stay pending until a terminal outcome arrives. WebSocket events provide live feedback, with task-endpoint polling as a fallback. Switching targets or removing a card releases its task tracking and ignores late responses. Cards use Home Assistant's native recorder graphs, with unlike units on separate graphs. Enable additional diagnostic entities on the manager device to show their measurements.

Large live lists (properties, players, addons, backups and plugin metadata) remain accessible to cards and automations but are excluded from recorder attribute history. Numeric sensor history remains available.

## Features

### Devices

*   **Bedrock Server Manager @ {host}**: A central device representing the BSM API instance. Global actions and sensors are linked here.
*   **Minecraft Server ({server_name})**: A separate device for each selected Minecraft server instance, linked to the Manager device via the "CONFIGURE" option.

### Entities

Entity IDs are typically `platform.server_name_entity_key` (e.g., `sensor.server_name_status`) or `platform.manager_id_entity_key` for global entities.

*   **Sensors (Per Server Device):**
    *   **Status:** Current state (`RUNNING`, `STOPPED`, `INSTALLED`, etc.). *Attributes:* Installed Version and server settings. Properties, player lists and process details are provided by their corresponding sensors.
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
    *   Target: Manager device or one of its entities.
    *   Data: `directory` (string, required), `keep` (integer, optional).
*   **`trigger_backup`**: Triggers a specific backup type.
    *   Target: Server device(s)/entity(s).
    *   Data: `backup_type` (string, required: `all`, `world`, `config`), `file_to_backup` (string, optional, required for `config` type).
*   **`restore_backup`**: Restores a specific backup. **CAUTION: Overwrites data.**
    *   Target: Server device(s)/entity(s).
    *   Data: `restore_type` (string, required: `world`, `properties`, `allowlist`, `permissions`), `backup_file` (string, required: filename relative to server's backup folder).
*   **`restore_latest_all`**: Restores latest full backup. **CAUTION: Overwrites data.**
    *   Target: Server device(s)/entity(s).
    *   Data: None.
*   **`add_to_allowlist`**: Adds players to a server's allowlist.
    *   Target: Server device(s)/entity(s).
    *   Data: `players` (list of strings, required), `ignores_player_limit` (boolean, optional).
*   **`remove_from_allowlist`**: Removes a player from a server's allowlist.
    *   Target: Server device(s)/entity(s).
    *   Data: `players` (list of player names, required).
*   **`set_permissions`**: Sets server-specific player permissions via XUID.
    *   Target: Server device(s)/entity(s).
    *   Data: `permissions` (list, required: `[{"name": "Alex", "xuid": "123", "permission_level": "member"}]`).
*   **`update_properties`**: Updates allowed `server.properties` values.
    *   Target: Server device(s)/entity(s).
    *   Data: `properties` (dictionary, required: `{"key": "value", ...}`).
*   **`install_server`**: Installs a new server instance via the manager.
    *   Target: Manager device or one of its entities.
    *   Data: `server_name` (string, required), `server_version` (string, required), `overwrite` (boolean, optional).
*   **`delete_server`**: Permanently deletes ALL data for a server. **IRREVERSIBLE.**
    *   Target: Server device(s)/entity(s).
    *   Data: `confirm_deletion` (boolean, required: must be `true`).
*   **`configure_os_service`**: Updates server autostart and autoupdate settings; the action name is retained for existing automations.
    *   Target: Server device(s)/entity(s).
    *   Data: `autoupdate` (boolean, required), `autostart` (boolean, optional).
*   **`install_world`**: Installs a `.mcworld` file to a server. **CAUTION: Overwrites current world.**
    *   Target: Server device(s)/entity(s).
    *   Data: `filename` (string, required: relative to manager's `content/worlds`).
*   **`install_addon`**: Installs an `.mcpack`/`.mcaddon` to a server.
    *   Target: Server device(s)/entity(s).
    *   Data: `filename` (string, required: relative to manager's `content/addons`).
*   **`add_global_players`**: Adds/updates players in the manager's global `players.json`.
    *   Target: Manager device or one of its entities.
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

## Metrics, health and live state

The manager device provides separate application and system measurements: CPU, memory, uptime, background operations, asyncio tasks, threads, event loop lag, disk throughput and network throughput. Native units and measurement state classes support Home Assistant history, statistics and dashboard charts. Memory is reported in MiB and throughput in KiB/s; supported units can be changed through Home Assistant entity settings. Detailed diagnostic measurements are disabled by default and can be enabled on the device page.

API and WebSocket connections have separate connectivity entities. An application problem entity and individual lifecycle, database, state and metrics checks distinguish a reachable backend from a degraded application. Health timestamps and lifecycle state are also available.

Live samples follow the backend sampling interval (normally three seconds). The integration's **Health and metrics fallback interval** defaults to 30 seconds and controls HTTP fallback polling and health checks, independently of server and manager polling. Only the latest sample is held in coordinator state; Home Assistant's recorder owns history. Mutation events refresh affected resources, and reconnects reconcile all selected resources. The event subscription also receives new core and custom plugin events. Selected-server resource subscriptions remain explicit. Successful unknown `after_*` events reconcile their named server and manager data (all selected servers if no server is identified); before and failed events do not trigger state refreshes. Revisions and backend epochs prevent older HTTP results from replacing newer WebSocket data.

Selected servers expose editable target versions and native uptime measurements. Plugins have enable switches, including plugins discovered after a reload. `get_plugin_settings` and `update_plugin_settings` actions expose the declared settings schema and validate changes through BSM. Plugins without declared settings cannot use these settings actions.

`list_tasks` and `get_task` support response data containing typed status, result and error snapshots. Live task updates fire `bedrock_server_manager_task_update` events with `manager_url`, `id`, `status`, `message`, `result`, `error`, `epoch` and `revision`. Automations can filter by manager URL and task ID. Core before/after events, custom `ws_event` messages and plugin broadcasts also fire `bedrock_server_manager_event`, retaining the original envelope plus `manager_url`. Filter by `topic` or `event`; event payloads describe operations and are not authoritative entity snapshots. Destructive actions wait for actual task completion before removing Home Assistant devices.

## Development

Use Python 3.14 and install `requirements-test.txt`. The test workflow and type-checking hook use the published `bsm-api-client==1.7.0b3` package, matching the BSM 4.0.0b5 contracts.

```sh
python -m pip install -r requirements-test.txt ../bsm-api-client/packages/bsm-api-client
python -m pytest tests
python -m mypy custom_components/bedrock_server_manager
python -m black --check --workers 1 custom_components tests
python -m isort --check-only custom_components tests
python -m flake8 --jobs 1 custom_components tests
```

### Frontend development

Card source lives in `frontend/src`; the committed modules under `custom_components/bedrock_server_manager/frontend` are the installable HACS resources. Build output includes the shared Lit runtime and its license notices.

```bash
npm ci
npm run build
npm run check:build
npx playwright install chromium
npm test
```

Browser tests cover draft conflicts, unavailable resources, target-switch races, accepted tasks, missed WebSocket outcomes, plugin checklists, typed permission payloads, subscription cleanup and mobile layouts in light/dark themes. Python platform tests exercise real Home Assistant entry setup, entity/device registration, response-capable services, live metrics and unloading; network responses are simulated.

### Overview, tasks and configuration

Use `custom:bsm-overview-card` for fleet controls. `layout: cards` is the default;
`layout: table` provides a compact table. An optional `entities` list restricts the
servers shown. Start remains available for installed and updated servers. More
Actions provides restart, backup and native details for configuration resources.

```yaml
type: grid
columns: 1
square: false
cards:
  - type: custom:bsm-overview-card
    layout: cards
  - type: custom:bsm-tasks-card
    entity: sensor.my_manager_bsm_version
  - type: custom:bsm-health-card
    entity: sensor.my_manager_bsm_version
```

The tasks card loads tasks on selection, receives live updates and polls every five
seconds while mounted. Completed outcomes remain visible when viewed. Filters show
active, completed, failed or cancelled tasks. Results and nested error details use
structured layouts with a raw-response disclosure. The backend exposes no percentage
or task timestamps; the card displays its actual status and message.

Use `custom:bsm-settings-card` with `scope: application` and a manager entity, or
`scope: server` and a server status entity. Boolean and numeric values retain their
JSON types. Application sections and server settings are grouped, external updates
retain drafts, and conflicting edits block saving. Updates are sent individually;
if one fails, earlier successful changes remain applied. Backend validation remains
authoritative. Plugin settings additionally support declared schemas, nested objects,
server checklists, descriptions and numeric bounds.

Response-capable actions include `get_application_settings`, `get_server_settings`,
`set_server_setting`, `discover_operations`, `call_operation`, `upload_content` and
`export_world`. Dynamic calls use an operation ID, optional `path_params`, `query`
and `json_data`; the SDK discovers and validates the contract using the configured
manager credentials. `custom:bsm-api-card` exposes these operations and their request
contracts. Binary responses are not supported by HA action responses. Content uploads require the content-uploader plugin and
read an existing file from a Home Assistant allowed path; they do not upload a browser
file. World export outcomes appear in the task display.

Known configuration mutations refresh only the affected server resources. Reconnects,
terminal task events and unknown plugin mutations retain full refreshes. Runtime API
discovery also lets optional metrics, health and ban endpoints be skipped when absent.

### Card runtime and native settings

Cards on the same Home Assistant connection share one runtime: one pair of BSM event
subscriptions, coalesced concurrent reads, a bounded cache of 500 revision-ordered task
outcomes, and one fallback poll per watched manager. Subscriptions and timers stop when
the last card releases them. Polling pauses while the browser document is hidden and
reconciles when it becomes visible or the connection recovers. No backend credentials,
server state or task results are written to browser storage. HA coordinators and entity
states remain authoritative for backend resources; recorder owns metric history.

Settings saves report success/failure per field, stop on the first failed update and
retain unsaved edits for retry. Field validation errors stay attached to their fields.
Reconnects retain drafts and detect conflicting backend changes.

The overview supports `sort: name`, `status` or `players`, independent busy states for
each server, and optional `monitor_path`/`settings_path` navigation. Paths must be local
HA paths; `{server}` is replaced with the encoded server name. `monitor_paths` and
`settings_paths` optionally map individual server status entity IDs to destinations.
Without a configured destination, server titles open native entity details.

Optional native configuration entities (disabled by default) expose application and
Bedrock metric intervals, startup/shutdown/task-drain timeouts as `number` entities and
server update channels as `select` entities. The channel selector includes LATEST,
PREVIEW and any currently configured exact version; the existing text entity remains
available for arbitrary exact versions. Enable these entities on the manager/server
device to use them in native dashboards and automations. Writes are confirmed through
coordinator refreshes rather than optimistic state.

Resource metadata preserves manager/server identity during outages and distinguishes
`current`, `stale`, `forbidden`, `unsupported`, `unavailable` and `unknown` data. `bsm_updated_at` is
the last locally received successful resource update; it is not a backend task timestamp.
Cards label retained stale data and unsupported resources. Service translations cover
the declared actions and current payload fields.

## Permissions and runtime recovery

Server actions enforce the calling Home Assistant user's read/control permissions on
the selected server entities, including device and area targets. Manager-wide actions
(including dynamic API calls, settings and task queries) require a Home Assistant admin
because they use the integration's shared BSM credentials. Automations without a user
context remain supported. BSM HTTP 403 responses mark individual resources as forbidden;
expired credentials still trigger reauthentication.

Actions acknowledge API acceptance before refreshing entity data in the background.
Multi-target actions retain successful task IDs alongside failed-target outcomes.
Task results remain visible after completion, with a maximum of 500 cached task records
per connection and bounded backend revision history. Unloading an entry cancels its
pending requests and refreshes before closing the transport.

After a connection changes during a request, cards release pending controls and explain
that the outcome needs checking before retrying. Accepted tasks resume tracking rather
than being submitted again. If Home Assistant denies live event subscriptions, cards
show a notice and retain task polling and entity updates. Manager selectors work even
when the application version sensor was previously disabled. Content sources are limited
to the selected server's manager. Diagnostics redact nested and flattened JWT secrets.
