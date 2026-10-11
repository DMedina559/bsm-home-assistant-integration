import { BsmCard, html, register } from "./base.js";
import {
  settingField,
  settingGroups,
  settingGroupHelp,
} from "./settings-fields.js";
import { label, schemaValue } from "./model.js";
function flatten(value, prefix = "") {
  return Object.fromEntries(
    Object.entries(value || {}).flatMap(([key, item]) => {
      const path = prefix ? `${prefix}.${key}` : key;
      return item && typeof item === "object" && !Array.isArray(item)
        ? Object.entries(flatten(item, path))
        : [[path, item]];
    }),
  );
}
class SettingsCard extends BsmCard {
  static role = "manager";
  static key = "bsm_version";
  static title = "Application settings";
  static properties = { loading: { state: true } };
  static getConfigForm() {
    const form = super.getConfigForm();
    form.schema.push({
      name: "scope",
      selector: { select: { options: ["application", "server"] } },
    });
    return form;
  }
  connectedCallback() {
    super.connectedCallback();
    this._subscribeChanges();
  }
  disconnectedCallback() {
    this._changesConnection = null;
    this._unsubscribeChanges?.();
    this._unsubscribeChanges = null;
    super.disconnectedCallback();
  }
  async _subscribeChanges() {
    const connection = this.hass?.connection;
    if (
      !connection ||
      !this.isConnected ||
      this._changesConnection === connection
    )
      return;
    this._unsubscribeChanges?.();
    this._changesConnection = connection;
    try {
      const unsubscribe = await connection.subscribeEvents((event) => {
        const envelope = event.data;
        const manager = this._managerUrl;
        if (!manager || envelope?.manager_url !== manager) return;
        const name = envelope.event || envelope.topic?.replace("event:", "");
        if (this.config.scope === "server") {
          const server =
            envelope.data?.server_name || envelope.data?.result?.server_name;
          if (
            name !== "after_set_server_setting" ||
            server !== this.state?.attributes.bsm_server_name
          )
            return;
        } else if (name !== "after_setting_update") return;
        if (this.loading || this.busy) this._reloadPending = true;
        else this.load(true);
      }, "bedrock_server_manager_event");
      if (!this.isConnected || this._changesConnection !== connection)
        unsubscribe();
      else this._unsubscribeChanges = unsubscribe;
    } catch {
      if (this._changesConnection === connection)
        this._changesConnection = null;
    }
  }
  normalizeSelection() {
    if (this.config.scope === "server") {
      const id = Object.entries(this.hass?.states || {}).find(
        ([id, s]) =>
          s.attributes.bsm_key === "status" &&
          this.hass.entities?.[id]?.device_id ===
            this.hass.entities?.[this.selection]?.device_id,
      )?.[0];
      if (id && id !== this.selection) this.select(id);
    } else super.normalizeSelection();
  }
  pick() {
    if (this.config.scope !== "server") return super.pick();
    const options = Object.entries(this.hass?.states || {}).filter(
      ([, s]) =>
        s.attributes.bsm_role === "server" && s.attributes.bsm_key === "status",
    );
    return this.selectInput(
      "Server",
      this.selection,
      [
        { value: "", label: "Select server" },
        ...options.map(([id, s]) => ({
          value: id,
          label: s.attributes.bsm_server_name || s.attributes.friendly_name,
        })),
      ],
      (v) => this.select(v),
    );
  }
  selectedChanged() {
    this._loaded = "";
    this.loading = false;
    this._managerUrl = "";
    this._reloadPending = false;
  }
  syncState() {
    this._subscribeChanges();
    if (this.available && this._loaded !== this.selection) {
      this._loaded = this.selection;
      this.load();
    }
  }
  async load(refresh = false) {
    if (!this.available || this.loading) return;
    const generation = this._generation;
    this.loading = true;
    try {
      const response = await this.responseService(
        this.config.scope === "server"
          ? "get_server_settings"
          : "get_application_settings",
        {},
      );
      if (generation !== this._generation) return;
      this._managerUrl = response.results?.[0]?.manager_url;
      const settings = flatten(response.results?.[0]?.result?.settings || {});
      refresh ? this.draft.update(settings) : this.draft.reset(settings);
      this.error = "";
      this.revision++;
    } catch (error) {
      if (generation === this._generation)
        this.error = error.message || String(error);
    } finally {
      if (generation === this._generation) {
        this.loading = false;
        if (this._reloadPending && !this.busy) {
          this._reloadPending = false;
          this.load(true);
        }
      }
    }
  }
  async save() {
    if (this.draft.conflicts.length) return;
    for (const [key, value] of Object.entries(this.draft.changes)) {
      if (
        !(await this.action(
          this.config.scope === "server"
            ? "set_server_setting"
            : "set_global_setting",
          { key, value },
        ))
      )
        return;
    }
    await this.load();
  }
  field(key, value) {
    const field = settingField(key);
    if (field.readOnly)
      return html`<div>
        <small>${label(key)}</small>
        <p>${String(value ?? "—")}</p>
      </div>`;
    const type = Array.isArray(value)
      ? "array"
      : typeof value === "boolean"
        ? "boolean"
        : typeof value === "number"
          ? "number"
          : "string";
    const edit = (value) => {
      try {
        this.draft.set(
          key,
          schemaValue(value, { type, minimum: field.min, maximum: field.max }),
        );
        this.error = "";
      } catch (error) {
        this.error = `${key}: ${error.message}`;
      }
      this.requestUpdate();
    };
    if (type === "boolean")
      return html`<label class="row"
        ><input
          style="width:auto"
          type="checkbox"
          aria-label=${key}
          .checked=${value}
          ?disabled=${this.busy || this.loading}
          @change=${(e) => edit(e.target.checked)}
        />${label(key)}</label
      >`;
    if (type === "array")
      return html`<label
        >${label(key)}<textarea
          aria-label=${key}
          .value=${JSON.stringify(value, null, 2)}
          @change=${(e) => edit(e.target.value)}
          ?disabled=${this.busy || this.loading}
        ></textarea>
      </label>`;
    return this.input(
      label(key),
      value,
      edit,
      field.type === "password"
        ? "password"
        : type === "number"
          ? "number"
          : "text",
    );
  }
  render() {
    const groups = new Map();
    for (const [key, value] of Object.entries(this.draft.value)) {
      const group = key.split(".")[0];
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push([key, value]);
    }
    return this.frame(
      html`${this.editNotice()}${[...groups].map(
          ([group, fields]) =>
            html`<details class="tile" open>
              <summary>${settingGroups[group] || label(group)}</summary>
              ${settingGroupHelp[group] ? html`<small>${settingGroupHelp[group]}</small>` : ""}
              <div class="grid">
                ${fields.map(([key, value]) => this.field(key, value))}
              </div>
            </details>`,
        )}
        <div class="actions">
          <button
            ?disabled=${this.loading || this.busy || !this.available}
            @click=${() => this.load(true)}
          >
            Check for updates</button
          ><button
            ?disabled=${this.loading || this.busy || !this.available || !this.draft.dirty || this.draft.conflicts.length || Boolean(this.error)}
            @click=${this.save}
          >
            Save settings
          </button>
        </div>
        <small
          >Changes are validated by the backend. Some application settings
          require a restart.</small
        >`,
    );
  }
}
register(
  "bsm-settings-card",
  SettingsCard,
  "BSM Settings",
  "Grouped application or server settings with typed values and conflict protection.",
);
