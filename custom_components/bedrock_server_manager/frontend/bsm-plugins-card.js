import{g as s,j as n,k as i}from"./shared-T5QDO26S.js";var t=class extends i{static title="Plugins";static role="manager";static key="plugin_statuses";render(){let a=this.state?.attributes.plugins_data||{};return this.frame(s`${Object.entries(a).map(([l,e])=>s`<section class="tile">
            <div class="heading">
              <strong>${e.name||l}</strong
              ><small
                >${e.version||""} ·
                ${e.enabled?"Enabled":"Disabled"}</small
              >
            </div>
            <p class="muted">${e.description||""}</p>
            ${this.button(e.enabled?"Disable":"Enable","set_plugin_enabled",{plugin_name:l,plugin_enabled:!e.enabled},{message:"Plugin state updated."})}
          </section>`)}${this.available&&!Object.keys(a).length?s`<p class="muted">No plugins are loaded.</p>`:""}${this.button("Reload plugins","reload_plugins",{},{message:"Plugins reloaded."})}`)}};n("bsm-plugins-card",t,"BSM Plugins","Inspect and control loaded plugins.");
