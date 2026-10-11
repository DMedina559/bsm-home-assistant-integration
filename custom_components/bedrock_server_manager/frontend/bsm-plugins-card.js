import{a as s,j as i,k as l}from"./shared-5SVUCQ5X.js";var a=class extends l{static title="Plugins";static role="manager";static key="plugin_statuses";static getConfigForm(){let t=super.getConfigForm();return t.schema.push({name:"reload_button_entity",selector:{entity:{domain:"button",integration:"bedrock_server_manager"}}}),t}render(){let t=this.state?.attributes.plugins_data||{};return this.frame(s`${Object.entries(t).map(([n,e])=>s`<section class="tile">
            <div class="heading">
              <strong>${e.name||n}</strong
              ><small
                >${e.version||""} ·
                ${e.enabled?"Enabled":"Disabled"}</small
              >
            </div>
            <p class="muted">${e.description||""}</p>
            ${this.button(e.enabled?"Disable":"Enable","set_plugin_enabled",{plugin_name:n,plugin_enabled:!e.enabled},{message:"Plugin state updated."})}
          </section>`)}${this.available&&!Object.keys(t).length?s`<p class="muted">No plugins are loaded.</p>`:""}${this.button("Reload plugins","reload_plugins",{},{message:"Plugins reloaded."})}`)}};i("bsm-plugins-card",a,"BSM Plugins","Inspect and control loaded plugins.");
