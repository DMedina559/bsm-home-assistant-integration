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
The restore card can prune backups using configured retention rules and follows the
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
