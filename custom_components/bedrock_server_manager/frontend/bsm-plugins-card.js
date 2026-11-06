import{g as s,j as n,k as i}from"./shared-GLIQ3H42.js";var a=class extends i{static title="Plugins";static role="manager";static key="plugin_statuses";render(){let l=this.state?.attributes.plugins_data||{};return this.frame(s`${Object.entries(l).map(([t,e])=>s`<section class="tile">
            <div class="heading">
              <strong>${e.name||t}</strong
              ><small
                >${e.version||""} ·
                ${e.enabled?"Enabled":"Disabled"} ·
                ${e.status||"UNKNOWN"}</small
              >
            </div>
            <p class="muted">${e.description||""}</p>
            <p class="muted">
              Permissions:
              ${e.permissions===null||e.permissions===void 0?"Not declared (legacy plugin)":e.permissions.join(", ")||"None"}
            </p>
            <p class="muted">
              Settings:
              ${[e.has_settings&&"Plugin",e.has_global_settings&&"Global",e.has_server_settings&&"Server"].filter(Boolean).join(" \xB7 ")||"None"}
            </p>
            ${this.button(e.enabled?"Disable":"Enable","set_plugin_enabled",{plugin_name:t,plugin_enabled:!e.enabled},{message:"Plugin state updated."})}
            ${this.button("Reload this plugin","reload_plugin",{plugin_name:t},{message:"Plugin reloaded.",confirm:"Reload this plugin? Its current listeners and tasks will be drained."})}
          </section>`)}${this.available&&!Object.keys(l).length?s`<p class="muted">No plugins are loaded.</p>`:""}${this.button("Reload plugins","reload_plugins",{},{message:"Plugins reloaded."})}`)}};n("bsm-plugins-card",a,"BSM Plugins","Inspect and control loaded plugins.");
