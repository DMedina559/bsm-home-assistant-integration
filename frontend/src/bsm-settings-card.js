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
  static properties = {
    loading: { state: true },
    saving: { state: true },
    fieldErrors: { state: true },
    saveResults: { state: true },
  };
  static getConfigForm() {
    const form = super.getConfigForm();
    form.schema.push({
      name: "scope",
      selector: { select: { options: ["application", "server"] } },
    });
    return form;
  }
  setConfig(config) {
    const scopeChanged = this.config && this.config.scope !== config.scope;
    super.setConfig(config);
    if (scopeChanged) {
      this._generation++;
      this.selectedChanged();
      this.draft.reset({});
      this.syncState();
    }
  }
  _eventUpdate(envelope) {
    if (!this._managerUrl || envelope?.manager_url !== this._managerUrl) return;
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
    if (this.loading || this.saving) this._reloadPending = true;
    else this.load(true);
  }
  reconnected() {
    super.reconnected();
    this.loading = false;
    this.saving = false;
    if (this.available) this.load(true);
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
    this.fieldErrors = {};
    this.saveResults = [];
    this.saving = false;
  }
  syncState() {
    const stamp = this.state?.attributes.bsm_settings_revision;
    if (
      this.available &&
      this._loaded === this.selection &&
      stamp !== this._stateStamp
    ) {
      if (this.loading || this.saving) this._reloadPending = true;
      else this.load(true);
    }
    this._stateStamp = stamp;
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
        if (this._reloadPending && !this.busy && !this.saving) {
          this._reloadPending = false;
          this.load(true);
        }
      }
    }
  }
  async save() {
    if (
      this.saving ||
      this.loading ||
      !this.available ||
      this.draft.conflicts.length ||
      Object.keys(this.fieldErrors || {}).length
    )
      return;
    const generation = this._generation,
      changes = Object.entries(this.draft.changes);
    this.saving = true;
    this.saveResults = [];
    for (const [key, value] of changes) {
      const success = await this.action(
        this.config.scope === "server"
          ? "set_server_setting"
          : "set_global_setting",
        { key, value },
      );
      if (generation !== this._generation) return;
      this.saveResults = [
        ...this.saveResults,
        { key, success, message: success ? "Saved" : this.error },
      ];
      if (!success) break;
      this.draft.base[key] = structuredClone(value);
      this.draft.live[key] = structuredClone(value);
      delete this.draft.changes[key];
    }
    if (generation !== this._generation) return;
    this.saving = false;
    const failure = this.saveResults.find((result) => !result.success);
    await this.load(true);
    if (generation !== this._generation) return;
    if (failure)
      this.error = `${failure.key}: ${failure.message}. Earlier saved changes remain applied; unsaved edits are retained.`;
    this.requestUpdate();
  }
  input(title, value, change, type = "text") {
    return html`<label
      >${title}<input
        aria-label=${title}
        type=${type}
        .value=${String(value ?? "")}
        ?disabled=${this.busy || this.loading || this.saving}
        @input=${(event) => change(event.target.value)}
    /></label>`;
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
        this.fieldErrors = { ...this.fieldErrors };
        delete this.fieldErrors[key];
      } catch (error) {
        this.fieldErrors = { ...this.fieldErrors, [key]: error.message };
      }
      this.requestUpdate();
    };
    if (field.enum)
      return this.selectInput(
        field.label || label(key),
        value,
        field.enum,
        edit,
      );
    if (type === "boolean")
      return html`<label class="row"
        ><input
          style="width:auto"
          type="checkbox"
          aria-label=${key}
          .checked=${value}
          ?disabled=${this.busy || this.loading || this.saving}
          @change=${(e) => edit(e.target.checked)}
        />${label(key)}</label
      >`;
    if (type === "array")
      return html`<label
        >${label(key)}<textarea
          aria-label=${key}
          .value=${JSON.stringify(value, null, 2)}
          @change=${(e) => edit(e.target.value)}
          ?disabled=${this.busy || this.loading || this.saving}
        ></textarea>
      </label>`;
    return this.input(
      field.label || label(key),
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
                ${fields.map(([key, value]) => html`<div>${this.field(key, value)}${settingField(key).description ? html`<small>${settingField(key).description}</small>` : ""}${this.fieldErrors?.[key] ? html`<small class="error" role="alert">${this.fieldErrors[key]}</small>` : ""}</div>`)}
              </div>
            </details>`,
        )}
        <div class="actions">
          <button
            ?disabled=${this.loading || this.busy || this.saving || !this.available}
            @click=${() => this.load(true)}
          >
            Check for updates</button
          ><button
            ?disabled=${this.loading || this.busy || this.saving || !this.available || !this.draft.dirty || this.draft.conflicts.length || Object.keys(this.fieldErrors || {}).length}
            @click=${this.save}
          >
            Save settings
          </button>
        </div>
        ${
          this.saveResults?.length
            ? html`<ul aria-label="Settings save results">
                ${this.saveResults.map((result) => html`<li>${settingField(result.key).label || label(result.key)}: ${result.success ? "Saved" : "Failed"}</li>`)}
              </ul>`
            : ""
        }
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
