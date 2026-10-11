import { BsmCard, html, register } from "./base.js";
import { schemaValue, label } from "./model.js";
function resolve(schema, root) {
  if (schema?.$ref?.startsWith("#/"))
    return (
      schema.$ref
        .slice(2)
        .split("/")
        .reduce((value, part) => value?.[part], root) || schema
    );
  if (schema?.anyOf)
    return resolve(
      schema.anyOf.find((item) => item.type !== "null") || schema,
      root,
    );
  return schema || {};
}
class PluginSettingsCard extends BsmCard {
  static title = "Plugin settings";
  static role = "manager";
  static key = "plugin_statuses";
  static properties = {
    plugin: { state: true },
    schema: { state: true },
    loading: { state: true },
  };
  constructor() {
    super();
    this.plugin = "";
    this.schema = null;
    this.loading = false;
  }
  selectedChanged() {
    this.plugin = "";
    this.schema = null;
    this.loading = false;
  }
  async load(plugin, refresh = false) {
    if (this.draft.dirty && plugin !== this.plugin) {
      this.error = "Discard or save your edits before switching plugins.";
      return;
    }
    const generation = this._generation,
      request = (this._request = (this._request || 0) + 1);
    this.plugin = plugin;
    this.loading = true;
    this.error = "";
    try {
      const response = await this.responseService("get_plugin_settings", {
        plugin_name: plugin,
      });
      if (generation !== this._generation || request !== this._request) return;
      const manager = response.managers?.[0];
      if (!manager) throw Error("No plugin settings were returned.");
      this.schema = manager.settings_schema || {
        type: "object",
        properties: Object.fromEntries(
          Object.entries(manager.settings).map(([key, value]) => [
            key,
            {
              title: label(key),
              type: Array.isArray(value)
                ? "array"
                : typeof value === "boolean"
                  ? "boolean"
                  : typeof value === "number"
                    ? "number"
                    : value !== null && typeof value === "object"
                      ? "object"
                      : "string",
            },
          ]),
        ),
      };
      if (refresh) this.draft.update(manager.settings);
      else this.draft.reset(manager.settings);
      this.revision++;
    } catch (error) {
      if (generation === this._generation && request === this._request)
        this.error = error.message || String(error);
    } finally {
      if (generation === this._generation && request === this._request)
        this.loading = false;
    }
  }
  syncState() {
    const state = this.state;
    if (
      this.plugin &&
      this.available &&
      state !== this._lastState &&
      !this.busy &&
      !this.loading
    )
      this.load(this.plugin, true);
    this._lastState = state;
  }
  edit(key, value, schema) {
    try {
      this.draft.set(key, schemaValue(value, schema));
      this.error = "";
    } catch (error) {
      this.error = `${label(key)}: ${error.message}`;
    }
    this.requestUpdate();
  }
  field(key, raw) {
    const schema = resolve(raw, this.schema),
      value = this.draft.value[key] ?? schema.default;
    const title = schema.title || label(key),
      description = schema.description;
    const items = resolve(schema.items, this.schema);
    let control;
    if (schema.type === "array" && items.enum)
      control = html`<fieldset ?disabled=${this.busy || this.loading}>
        <legend>${title}</legend>
        ${items.enum.map(
          (option) =>
            html`<label class="row"
              ><input
                style="width:auto"
                type="checkbox"
                aria-label=${String(option)}
                .checked=${(value || []).includes(option)}
                @change=${(e) => {
                  const next = new Set(this.draft.value[key] || []);
                  e.target.checked ? next.add(option) : next.delete(option);
                  this.edit(key, [...next], schema);
                }}
              />${option}</label
            >`,
        )}
      </fieldset>`;
    else if (schema.type === "boolean")
      control = html`<label class="row"
        ><input
          style="width:auto"
          type="checkbox"
          aria-label=${title}
          .checked=${Boolean(value)}
          ?disabled=${this.busy || this.loading}
          @change=${(e) => this.edit(key, e.target.checked, schema)}
        />${title}</label
      >`;
    else if (schema.enum)
      control = this.selectInput(
        title,
        value,
        schema.enum.map((item) => ({
          value: String(item),
          label: String(item),
        })),
        (v) => this.edit(key, v, schema),
      );
    else if (["object", "array"].includes(schema.type))
      control = html`<label
        >${title} (JSON)<textarea
          aria-label=${title}
          .value=${JSON.stringify(value ?? (schema.type === "array" ? [] : {}), null, 2)}
          ?disabled=${this.busy || this.loading}
          @change=${(e) => this.edit(key, e.target.value, schema)}
        ></textarea>
      </label>`;
    else
      control = this.input(
        title,
        value,
        (v) => this.edit(key, v, schema),
        ["number", "integer"].includes(schema.type) ? "number" : "text",
      );
    return html`<div>
      ${control}${description ? html`<small>${description}</small>` : ""}
    </div>`;
  }
  async save() {
    if (this.draft.conflicts.length) return;
    if (
      await this.action(
        "update_plugin_settings",
        { plugin_name: this.plugin, settings: this.draft.value },
        "Plugin settings saved.",
      )
    )
      await this.load(this.plugin);
  }
  render() {
    const plugins = Object.entries(
      this.state?.attributes.plugins_data || {},
    ).filter(([, plugin]) => plugin.has_settings);
    return this.frame(
      html`<div class="tabs row" role="tablist" aria-label="Plugin settings">
          ${plugins.map(([name, plugin]) => html`<button role="tab" aria-selected=${String(name === this.plugin)} ?disabled=${this.busy || this.loading || !this.available} @click=${() => this.load(name)}>${plugin.name || name}</button>`)}
        </div>
        ${this.available && !plugins.length ? html`<p class="muted">No loaded plugins declare settings.</p>` : ""}${this.loading ? html`<p role="status">Loading settings…</p>` : ""}${this.editNotice()}${
          this.schema
            ? html`<div class="grid">
                  ${Object.entries(this.schema.properties || {}).map(([key, schema]) => this.field(key, schema))}
                </div>
                <div class="actions">
                  <button
                    ?disabled=${this.loading || this.busy || !this.available}
                    @click=${() => this.load(this.plugin, true)}
                  >
                    Check for updates</button
                  ><button
                    class="primary"
                    ?disabled=${!this.available || this.loading || this.busy || !this.draft.dirty || this.draft.conflicts.length > 0 || Boolean(this.error)}
                    @click=${this.save}
                  >
                    Save settings
                  </button>
                </div>`
            : this.plugin && !this.loading
              ? html`<p class="muted">
                  This plugin has no editable settings schema.
                </p>`
              : ""
        }`,
    );
  }
}
register(
  "bsm-plugin-settings-card",
  PluginSettingsCard,
  "BSM Plugin Settings",
  "Typed plugin settings with server checklists and backend validation.",
);
