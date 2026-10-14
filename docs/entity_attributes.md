# Entity attributes

BSM entities expose native Home Assistant values, not JSON strings. Identity and
freshness stay flat; structured backend data remains under named dictionaries
and lists. `bsm_attribute_schema: 1` identifies this contract.

| Attribute | Meaning |
|---|---|
| `bsm_role` | `manager` or `server` |
| `bsm_key` | Stable entity function |
| `bsm_manager_url` | Configured manager identity |
| `bsm_server_name` | Server identity, on server entities |
| `bsm_resource_state` | Current, stale, unknown, unavailable, unsupported or forbidden observation |
| `bsm_updated_at` | Last successful source update, Unix seconds, or null |
| `bsm_last_error` | Safe resource error, when available |
| `bsm_settings_revision` | Local refresh/invalidation generation, not a database transaction ID |
| `bsm_truncated_attributes` | Detail keys with limited or unsupported data |

Action entities expose identity; resource-backed entities also expose source
freshness. Unavailable entities retain identity/freshness, disable controls and
omit detail data. A known zero or false remains zero or false; missing values do
not become healthy readings.

## Structured details

The server status sensor has `server_settings`, preserving `server_info`,
`settings`, `custom` and other backend fields inside that dictionary. Arbitrary
backend/custom keys never become top-level Home Assistant attributes.
`server_settings_freshness` describes the settings resource independently from
the status sensor's primary resource.

Properties remain under `server_properties`; plugins remain under `plugins_data`.
Existing collection names for players, permissions, addons and backups are
retained. Health keeps lifecycle/readiness summaries flat and detailed `checks`
nested. A check with missing health evidence is not listed as a failed check.

```jinja
{{ state_attr('sensor.survival_status', 'server_settings')['settings']['autostart'] }}
```

Guard against missing/unavailable dictionaries in production templates. Migrate
old `settings_*`, `server_info_*`, `custom_*` and arbitrary top-level setting
lookups to `server_settings`. Identity names and entity unique IDs are retained.
The bundled settings card uses full service responses, so its editor does not
rely on the old flattened attributes.

## Bounds and history

Entity details retain at most 100 entries per container, eight nested levels,
4,096 characters per string and a 2,048-node serialization budget. Truncation is
explicit; counts in entity states are calculated from the complete coordinator
reading. Returned details are independent copies, so modifying attributes does
not mutate coordinator state.

Do not use bounded entity attributes as complete backup/configuration sources.
Use BSM response services or Home Assistant's redacted diagnostics download for
full data. The cards show a partial-data notice when truncation is reported.

Large collections, nested settings, health checks, timestamps, error text,
refresh revisions and truncation markers are excluded from Recorder. Small,
stable identity attributes remain available alongside meaningful state history.
Changing Recorder exclusions does not remove historical rows already recorded.

Downloaded diagnostics and service responses have separate contracts; these
entity bounds do not silently truncate them. Review reports before sharing them.
