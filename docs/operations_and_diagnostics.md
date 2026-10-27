# Operations and diagnostics

These features use existing BSM 4.0 backend endpoints. They do not require a new
backend release or client regeneration. Missing endpoints produce an unsupported
result; backend permission checks still apply.

## Dashboard cards

| Card | Target | Purpose |
|---|---|---|
| `custom:bsm-diagnostics-card` | Manager | Findings, subsystem freshness, history, runs, traces, comparisons and reports |
| `custom:bsm-event-trigger-card` | Manager | Declared custom events, payload contracts and delivery activity |
| `custom:bsm-logs-card` | Server | Server or administrator application log pages |
| `custom:bsm-audit-card` | Manager | Audit records filtered by exact action |
| `custom:bsm-runtime-card` | Manager | Runtime status and confirmed graceful shutdown |

Details load when requested. Changing targets discards the previous target's data
and ignores late replies. Failed reads retain previous details with a visible
stale, forbidden, unsupported or unavailable status. Reports download as JSON;
review them before sharing. The Home Assistant integration diagnostics download
remains the preferred redacted support artifact.

For comparisons, collect a snapshot, capture its baseline, collect another
snapshot, then compare. History and trace actions accept backend cursors. Full
snapshot comparisons are validated through the backend contract.

Log pages use the backend byte offset and file identity. The log card reloads the
current file if rotation invalidates an older-page request. Display is limited to
128 KiB of text; there is no background log subscription or Recorder log storage.
The audit backend currently returns all records. The action filters and bounds its
response locally; it does not provide backend pagination.

The properties card includes a read-only raw document viewer and server validation.
The backup card can prune archives using configured retention rules and follows the
accepted task to completion. Each plugin has its own confirmed reload action.

## Action responses

All response actions expose `response_schema_version: 1` and `results`, with one
entry per target:

```yaml
response_schema_version: 1
results:
  - manager_url: http://bsm:11325
    server_name: survival
    status: success
    result: {}
    warnings: []
```

Failures include `error.message`, `error.code`, `error.type`, `error.status_code`
when available, `error.retryable`, and sanitized `error.details`. Retryability is
informational; mutations are never automatically replayed. Validation details omit
input values, request bodies and credential keys.

The existing `managers` aliases for plugin settings and task responses are retained.
New automations should use `results[].result`. An accepted settings write followed
by a failed refresh is successful with a `refresh_failed` warning. Refresh before
retrying; the saved change must not be repeated just because its follow-up read failed.

Requested responses preserve individual target failures. Calls without responses
raise errors rather than silently acknowledging failed operations. Existing action
error behavior is preserved for automations that do not request response data.

```yaml
action: bedrock_server_manager.get_diagnostic_history
target:
  entity_id: sensor.bsm_version
data:
  limit: 50
  subsystem: events
response_variable: bsm_history
```

Dedicated actions cover the seven diagnostics endpoints, event catalog/activity,
server/application log history, runtime status/shutdown, audit history, raw
properties, server validation, backup pruning and individual plugin reload.
Use Developer Tools → Actions to inspect fields and selectors. Core and plugin
operations remain available through `discover_operations` and `call_operation`.

## Permissions and shutdown

Interactive administrative actions require a Home Assistant administrator and the
appropriate BSM account permission. Task reads permit users with read access to
the manager's version entity. Server reads require read access to the server target;
mutations require control access. Raw properties and server logs additionally require
BSM moderator access. Settings and diagnostic reads can contain sensitive data and
retain administrator restrictions. HA automations without a user context retain
normal automation privileges; the backend still authenticates every request.

`shutdown_web_runtime` requires `confirm: true`. The runtime card also asks for
confirmation. After acceptance, API and WebSocket disconnection is expected. Start
BSM again using its host/service manager. There is no remote start or task-cancel
control because those endpoints do not exist.

## Optional diagnostic entities

Readiness is a separate, disabled-by-default binary sensor using the existing
health response. Three additional disabled-by-default numeric entities expose:

- Reported diagnostic findings: count of findings in the bounded backend summary.
- Pending event workers: outstanding event worker count.
- WebSocket delivery failures: failed sends in the current backend instance.

Enabling one of those numeric entities adds one diagnostic snapshot request to the
monitor coordinator's polling cycle, shared by all enabled diagnostic consumers.
Only scalar values are retained; full snapshots are not put in entity attributes.
Removing the last consumer stops the extra requests. Unknown or unavailable
measurements remain unavailable instead of becoming zero. Detailed cards remain
on-demand regardless of entity selections.

## Event forwarding and recovery

Integration options include event forwarding and comma-separated exact event names.
Blank names preserve forwarding of all events. Disabling forwarding or filtering
names affects the HA event bus only: internal reconciliation, metrics and task
updates continue. The catalog helps find declared names and payload schemas.

OpenAPI capabilities refresh after a backend WebSocket reconnect or version change.
Settings revisions are resource-specific so unrelated changes do not unnecessarily
reload an editor. Existing credential recovery, scoped refreshes and polling fallback
remain active.

## Portable backups and restores

The **BSM Backups and Restore** card (`custom:bsm-restore-card`) uses the portable
`.bsmbackup` archive API. Refresh the list on demand; an unloaded list is distinct
from an empty list. Create a world backup, select individual components, capture
the full server directory, or use global defaults. World backups already include
packs installed inside the world. Component names and labels come from the live
backend schema; there is no separate server-pack flag.

Inspect an archive, select the included components, and choose **Review restore**.
Inspection and planning run as tracked tasks. The completed review supplies the
required token; only then does the card offer a confirmed restore. Changing the
archive, selection, recovery key, manager, or connection invalidates that review.
A dry run validates an isolated restore without modifying the live server.
Verification, pin/unpin, recovery drills, pruning and restore-journal recovery use
tracked tasks too. Verification after creation follows the global backend setting
and is disabled by default. A recovery drill tests an isolated restore; it does not
replace the live server.

Native response actions include `list_server_snapshots`, `create_server_snapshot`,
`inspect_server_snapshot`, `plan_snapshot_restore`, `restore_server_snapshot`,
`dry_run_server_restore`, `manage_server_snapshot`, `get_backup_health`,
`get_restore_recovery`, `recover_server_backup`, `prepare_backup_copy`,
`cleanup_backup_destination`, `download_backup_recovery_report`, `list_backup_keys`
and explicitly confirmed `rotate_backup_key`. A destination cleanup without a
token is a preview; a reviewed token authorizes cleanup. Backup-copy preparation
creates a stopped target; review its restore separately.

`import_server_snapshot` and `download_server_snapshot` transfer archives between
BSM and a `file_path` on the Home Assistant host inside an allowed directory.
Downloads stream to disk and require a new filename. These paths are not browser
uploads/downloads. Optional `recovery_key` values are only needed when BSM does not
have the archive's key; the card keeps them in memory and clears them on target
changes. Emergency recovery kits and decrypted archive exports remain available
through the BSM frontend. Review and safeguard credentials before sharing files.
The existing category backup actions remain available for existing automations.

## Scheduler and timezones

Add `custom:bsm-scheduler-card` for the manager. Load schedules on demand, edit
backup/verify schedules, select weekdays, configure catch-up and staggering, and
inspect next-run times, last errors and run history. Discovered plugin task types
also appear in the task selector; their options remain a JSON object.

Automations can call `list_schedules`, `save_schedule`, and `delete_schedule`.
`save_schedule` accepts `schedule_id` and a `configuration` object matching the
backend schema. Use an IANA timezone such as `America/Los_Angeles`, not `PDT`.
The backend handles daylight saving and reports timezone database availability.
The application timezone (`general.timezone`) and backup defaults are editable in
the application settings card. Stored timestamps retain their offsets; the cards
show run and archive dates in the browser's local timezone.

## Scoped plugin settings and activity

The plugin settings card offers **Plugin**, **Global**, and **Server** scopes.
Only plugins declaring the corresponding model appear. Server scope also needs a
server name. Unsaved edits block switching scopes; refreshes retain edits and flag
conflicts. `get_plugin_settings` and `update_plugin_settings` accept optional
`scope` (default `plugin`) and `server_name` (required only for `server`). Both the
save and follow-up read use the same scope, so a refresh failure never replays a
successful save. Existing plugin-local actions are unchanged.

New scope fields and plugin capability flags use live API discovery, avoiding
field loss or rejection in the installed SDK's older generated models. New
maintenance actions likewise validate against the connected backend. Unsupported
actions return a structured error instead of falling back to a different operation.

The diagnostics card's **Load activity** action shows global events across
operations and servers. `get_diagnostic_activity` supports name, owner, status,
phase, server, source, operation, sequence and correlation filters. Existing
subsystem snapshots, reports, history and health views include the scheduler and
timezone checks reported by BSM without hardcoding a list of subsystem names.
Custom and plugin settings, including recovery keys, are redacted from integration
diagnostic exports.

Scheduler controls use the `control_schedule` action with `schedule_id`, `action`
(`run_now`, `pause`, `resume`, `retry`) and optional `revision` from the listing.
The card confirms immediate runs and retries, refreshes after controls, shows
pending attempts separately from calendar occurrences, and protects unsaved forms
when switching entries. New schedules start paused. Leave timezone blank to inherit
the BSM application timezone; existing schedules retain their stored timezone.
Run acknowledgement is not completion: inspect recent runs for the outcome.
