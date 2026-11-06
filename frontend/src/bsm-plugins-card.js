import { BsmCard, html, register } from "./base.js";
class PluginsCard extends BsmCard {
  static title = "Plugins";
  static role = "manager";
  static key = "plugin_statuses";
  render() {
    const plugins = this.state?.attributes.plugins_data || {};
    return this.frame(
      html`${Object.entries(plugins).map(
        ([name, plugin]) =>
          html`<section class="tile">
            <div class="heading">
              <strong>${plugin.name || name}</strong
              ><small
                >${plugin.version || ""} ·
                ${plugin.enabled ? "Enabled" : "Disabled"} ·
                ${plugin.status || "UNKNOWN"}</small
              >
            </div>
            <p class="muted">${plugin.description || ""}</p>
            <p class="muted">
              Permissions:
              ${plugin.permissions === null || plugin.permissions === undefined ? "Not declared (legacy plugin)" : plugin.permissions.join(", ") || "None"}
            </p>
            <p class="muted">
              Settings:
              ${[plugin.has_settings && "Plugin", plugin.has_global_settings && "Global", plugin.has_server_settings && "Server"].filter(Boolean).join(" · ") || "None"}
            </p>
            ${this.button(plugin.enabled ? "Disable" : "Enable", "set_plugin_enabled", { plugin_name: name, plugin_enabled: !plugin.enabled }, { message: "Plugin state updated." })}
            ${this.button("Reload this plugin", "reload_plugin", { plugin_name: name }, { message: "Plugin reloaded.", confirm: "Reload this plugin? Its current listeners and tasks will be drained." })}
          </section>`,
      )}${this.available && !Object.keys(plugins).length ? html`<p class="muted">No plugins are loaded.</p>` : ""}${this.button("Reload plugins", "reload_plugins", {}, { message: "Plugins reloaded." })}`,
    );
  }
}
register(
  "bsm-plugins-card",
  PluginsCard,
  "BSM Plugins",
  "Inspect and control loaded plugins.",
);
