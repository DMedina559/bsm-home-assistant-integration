import { BsmCard, html, register } from "./base.js";
class PluginsCard extends BsmCard {
  static title = "Plugins";
  static role = "manager";
  static key = "plugin_statuses";
  static getConfigForm() {
    const form = super.getConfigForm();
    form.schema.push({
      name: "reload_button_entity",
      selector: {
        entity: { domain: "button", integration: "bedrock_server_manager" },
      },
    });
    return form;
  }
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
                ${plugin.enabled ? "Enabled" : "Disabled"}</small
              >
            </div>
            <p class="muted">${plugin.description || ""}</p>
            ${this.button(plugin.enabled ? "Disable" : "Enable", "set_plugin_enabled", { plugin_name: name, plugin_enabled: !plugin.enabled }, { message: "Plugin state updated." })}
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
