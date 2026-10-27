import { BsmCard, html, register } from "./base.js";
import { responseValue } from "./inspector.js";
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
    scope: { state: true },
    serverName: { state: true },
    plugin: { state: true },
    schema: { state: true },
    loading: { state: true },
  };
  constructor() {
    super();
    this.scope = "plugin";
    this.serverName = "";
    this.plugin = "";
    this.schema = null;
    this.loading = false;
  }
  reconnected() {
    super.reconnected();
    this.loading = false;
    if (this.plugin && this.available) this.load(this.plugin, true);
  }
  input(title, value, change, type = "text") {
    return html`<label
      >${title}<input
        aria-label=${title}
        type=${type}
        .value=${String(value ?? "")}
        ?disabled=${this.busy || this.loading}
        @input=${(e) => change(e.target.value)}
    /></label>`;
  }
  selectedChanged() {
    this.serverName = "";
    this.plugin = "";
    this.schema = null;
    this.loading = false;
  }
  _eventUpdate(envelope) {
    if (!this.plugin || envelope?.manager_url !== this._managerUrl) return;
    const name = envelope.event || envelope.topic?.replace("event:", "");
    if (
      [
        "after_plugin_settings_update",
        "after_setting_update",
        "after_set_server_setting",
        "after_restore",
      ].includes(name)
    ) {
      if (this.busy || this.loading) this._reloadPending = true;
      else this.load(this.plugin, true);
    }
  }
  scopeOptions() {
    return {
      scope: this.scope,
      ...(this.scope === "server" ? { server_name: this.serverName } : {}),
    };
  }
  changeScope(scope, serverName = this.serverName) {
    if (this.draft.dirty) {
      this.feedback = "Save or discard your edits before changing scope.";
      return;
    }
    this._request = (this._request || 0) + 1;
    this.scope = scope;
    this.serverName = serverName;
    this.plugin = "";
    this.schema = null;
    this.loading = false;
    this.error = "";
    this.draft.reset({});
  }
  async load(plugin, refresh = false) {
    if (this.scope === "server" && !this.serverName) return;
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
        ...this.scopeOptions(),
      });
      if (generation !== this._generation || request !== this._request) return;
      const manager = response.results
        ? responseValue(response)
        : response.managers?.[0];
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
      if (generation === this._generation && this._reloadPending) {
        this._reloadPending = false;
        this.load(this.plugin, true);
      }
    }
  }
  syncState() {
    const state = this.state;
    const revision = state?.attributes.bsm_settings_revision;
    if (
      this.plugin &&
      this.available &&
      (revision == null
        ? state !== this._lastState
        : revision !== this._lastRevision) &&
      !this.busy &&
      !this.loading
    )
      this.load(this.plugin, true);
    this._lastRevision = revision;
    this._lastState = state;
  }
  edit(key, value, schema) {
    try {
      const parts = key.split(".");
      const top = parts.shift();
      const converted = schemaValue(value, schema);
      if (!parts.length) this.draft.set(top, converted);
      else {
        const next = structuredClone(this.draft.value[top] || {});
        let target = next;
        for (const part of parts.slice(0, -1)) target = target[part] ||= {};
        target[parts.at(-1)] = converted;
        this.draft.set(top, next);
      }
      this.error = "";
    } catch (error) {
      this.error = `${label(key)}: ${error.message}`;
    }
    this.requestUpdate();
  }
  field(key, raw) {
    const schema = resolve(raw, this.schema),
      value =
        key.split(".").reduce((item, part) => item?.[part], this.draft.value) ??
        schema.default;
    const title = schema.title || label(key),
      description = schema.description;
    const items = resolve(schema.items, this.schema);
    let control;
    if (schema.type === "object" && schema.properties)
      control = html`<fieldset ?disabled=${this.busy || this.loading}>
        <legend>${title}</legend>
        <div class="grid">
          ${Object.entries(schema.properties).map(([name, child]) => this.field(`${key}.${name}`, child))}
        </div>
      </fieldset>`;
    else if (schema.type === "array" && items.enum)
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
                  const next = new Set(value || []);
                  e.target.checked ? next.add(option) : next.delete(option);
                  this.edit(key, [...next], schema);
                }}
              />${schema["x-bsm-choice-labels"]?.[option] || option}</label
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
      control = html`<fieldset ?disabled=${this.busy || this.loading}>
        ${this.selectInput(
          title,
          value,
          schema.enum.map((item) => ({
            value: String(item),
            label: String(item),
          })),
          (v) => this.edit(key, v, schema),
        )}
      </fieldset>`;
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
        {
          plugin_name: this.plugin,
          settings: this.draft.value,
          ...this.scopeOptions(),
        },
        "Plugin settings saved.",
      )
    ) {
      if (
        this._lastResponse?.results?.[0]?.warnings?.some(
          (item) => item.code === "refresh_failed",
        )
      ) {
        this.draft.reset(this.draft.value);
        this.requestUpdate();
      } else await this.load(this.plugin);
    }
  }
  render() {
    const plugins = Object.entries(
      this.state?.attributes.plugins_data || {},
    ).filter(
      ([, plugin]) =>
        plugin[
          {
            plugin: "has_settings",
            global: "has_global_settings",
            server: "has_server_settings",
          }[this.scope]
        ],
    );
    const servers = [
      ...new Set(
        Object.values(this.hass?.states || {})
          .filter(
            (s) =>
              s.attributes.bsm_manager_url ===
                this.state?.attributes.bsm_manager_url &&
              s.attributes.bsm_server_name,
          )
          .map((s) => s.attributes.bsm_server_name),
      ),
    ];
    return this.frame(
      html`${this.selectInput(
          "Settings scope",
          this.scope,
          [
            { value: "plugin", label: "Plugin" },
            { value: "global", label: "Global" },
            { value: "server", label: "Server" },
          ],
          (v) => this.changeScope(v),
        )}
        ${this.scope === "server" ? this.selectInput("Server", this.serverName, [{ value: "", label: "Select server" }, ...servers], (v) => this.changeScope(this.scope, v)) : ""}
        <div class="tabs row" role="tablist" aria-label="Plugin settings">
          ${plugins.map(([name, plugin]) => html`<button role="tab" aria-selected=${String(name === this.plugin)} ?disabled=${this.busy || this.loading || !this.available || (this.scope === "server" && !this.serverName)} @click=${() => this.load(name)}>${plugin.name || name}</button>`)}
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
