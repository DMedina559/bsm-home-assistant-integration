import{b as c,f as g,g as r,j as p,k as f}from"./shared-7UTSRN4G.js";var n=(o,e=0,t,s=1,i)=>({type:"number",description:o,min:e,max:t,step:s,unit:i}),m={paths:"Storage locations",retention:"Retention",monitoring:"Monitoring",web:"Web server",lifecycle:"Startup and shutdown",server_info:"Server information",settings:"Server behavior",custom:"Custom settings",plugin_settings:"Plugin settings"},d={paths:"Directories used for servers, backups, downloads, and extensions.",retention:"Previous files to keep. Zero disables automatic cleanup.",monitoring:"Metrics interval changes apply on the next monitoring cycle.",web:"Listener and authentication settings. Listener changes require a restart.",lifecycle:"Limits for startup and cleanup. Request draining changes require a web server restart.",server_info:"Installed state is reported by the server. Choose a target version for updates.",settings:"Automatic actions for this server.",custom:"Additional settings used by your extensions."},v={"monitoring.app_metrics_interval_sec":{...n("Application and system metrics sampling.",1,3600,1,"seconds"),label:"Application metrics interval"},"monitoring.bedrock_metrics_interval_sec":{...n("Resource updates on Bedrock monitor pages.",1,3600,1,"seconds"),label:"Bedrock metrics interval"},"monitoring.process_interval_sec":n("Checks server process state.",1,void 0,1,"seconds"),"monitoring.player_interval_sec":n("Checks connected players.",1,void 0,1,"seconds"),"monitoring.max_retries":n("Retries before a failed process check is reported."),"retention.backups":n("Backups retained per server."),"retention.downloads":n("Downloaded versions retained."),"web.port":n("TCP port for the web server.",1,65535),"web.token_expires_weeks":n("Lifetime of authentication tokens.",1,void 0,1,"weeks"),"web.jwt_secret_key":{type:"password",description:"Signing secret. Changing it invalidates existing tokens."},"server_info.status":{readOnly:!0},"server_info.installed_version":{readOnly:!0},"server_info.server_name":{readOnly:!0},"settings.target_version":{description:"Use LATEST, PREVIEW, or a specific Bedrock version."},"settings.autostart":{type:"boolean",description:"Start this server when the application starts."},"settings.autoupdate":{type:"boolean",description:"Update this server automatically on startup."}};for(let[o,e]of Object.entries({startup_timeout_seconds:"Deadline for each startup stage.",shutdown_timeout_seconds:"Deadline for each shutdown stage.",task_drain_timeout_seconds:"Time for operations to finish before cancellation.",plugin_timeout_seconds:"Time allowed for plugin unload and router cleanup.",cancellation_grace_seconds:"Extra time to handle cancellation.",request_drain_timeout_seconds:"Time to drain HTTP requests before cleanup."}))v[`lifecycle.${o}`]=n(e,1e-6,o==="cancellation_grace_seconds"?30:600,"any","seconds");function h(o){return v[o]??{}}function b(o,e=""){return Object.fromEntries(Object.entries(o||{}).flatMap(([t,s])=>{let i=e?`${e}.${t}`:t;return s&&typeof s=="object"&&!Array.isArray(s)?Object.entries(b(s,i)):[[i,s]]}))}var u=class extends f{static role="manager";static key="bsm_version";static title="Application settings";static properties={loading:{state:!0},saving:{state:!0},fieldErrors:{state:!0},saveResults:{state:!0}};static getConfigForm(){let e=super.getConfigForm();return e.schema.push({name:"scope",selector:{select:{options:["application","server"]}}}),e}setConfig(e){let t=this.config&&this.config.scope!==e.scope;super.setConfig(e),t&&(this._generation++,this.selectedChanged(),this.draft.reset({}),this.syncState())}_eventUpdate(e){if(!this._managerUrl||e?.manager_url!==this._managerUrl)return;let t=e.event||e.topic?.replace("event:","");if(this.config.scope==="server"){let s=e.data?.server_name||e.data?.result?.server_name;if(t!=="after_set_server_setting"||s!==this.state?.attributes.bsm_server_name)return}else if(t!=="after_setting_update")return;this.loading||this.saving?this._reloadPending=!0:this.load(!0)}reconnected(){super.reconnected(),this.loading=!1,this.saving=!1,this.available&&this.load(!0)}normalizeSelection(){if(this.config.scope==="server"){let e=Object.entries(this.hass?.states||{}).find(([t,s])=>s.attributes.bsm_key==="status"&&this.hass.entities?.[t]?.device_id===this.hass.entities?.[this.selection]?.device_id)?.[0];e&&e!==this.selection&&this.select(e)}else super.normalizeSelection()}pick(){if(this.config.scope!=="server")return super.pick();let e=Object.entries(this.hass?.states||{}).filter(([,t])=>t.attributes.bsm_role==="server"&&t.attributes.bsm_key==="status");return this.selectInput("Server",this.selection,[{value:"",label:"Select server"},...e.map(([t,s])=>({value:t,label:s.attributes.bsm_server_name||s.attributes.friendly_name}))],t=>this.select(t))}selectedChanged(){this._loaded="",this.loading=!1,this._managerUrl="",this._reloadPending=!1,this.fieldErrors={},this.saveResults=[],this.saving=!1}syncState(){let e=this.state?.attributes.bsm_settings_revision;this.available&&this._loaded===this.selection&&e!==this._stateStamp&&(this.loading||this.saving?this._reloadPending=!0:this.load(!0)),this._stateStamp=e,this.available&&this._loaded!==this.selection&&(this._loaded=this.selection,this.load())}async load(e=!1){if(!this.available||this.loading)return;let t=this._generation;this.loading=!0;try{let s=await this.responseService(this.config.scope==="server"?"get_server_settings":"get_application_settings",{});if(t!==this._generation)return;this._managerUrl=s.results?.[0]?.manager_url;let i=b(s.results?.[0]?.result?.settings||{});e?this.draft.update(i):this.draft.reset(i),this.error="",this.revision++}catch(s){t===this._generation&&(this.error=s.message||String(s))}finally{t===this._generation&&(this.loading=!1,this._reloadPending&&!this.busy&&!this.saving&&(this._reloadPending=!1,this.load(!0)))}}async save(){if(this.saving||this.loading||!this.available||this.draft.conflicts.length||Object.keys(this.fieldErrors||{}).length)return;let e=this._generation,t=Object.entries(this.draft.changes);this.saving=!0,this.saveResults=[];for(let[i,a]of t){let l=await this.action(this.config.scope==="server"?"set_server_setting":"set_global_setting",{key:i,value:a});if(e!==this._generation)return;if(this.saveResults=[...this.saveResults,{key:i,success:l,message:l?"Saved":this.error}],!l)break;this.draft.base[i]=structuredClone(a),this.draft.live[i]=structuredClone(a),delete this.draft.changes[i]}if(e!==this._generation)return;this.saving=!1;let s=this.saveResults.find(i=>!i.success);await this.load(!0),e===this._generation&&(s&&(this.error=`${s.key}: ${s.message}. Earlier saved changes remain applied; unsaved edits are retained.`),this.requestUpdate())}input(e,t,s,i="text"){return r`<label
      >${e}<input
        aria-label=${e}
        type=${i}
        .value=${String(t??"")}
        ?disabled=${this.busy||this.loading||this.saving}
        @input=${a=>s(a.target.value)}
    /></label>`}field(e,t){let s=h(e);if(s.readOnly)return r`<div>
        <small>${c(e)}</small>
        <p>${String(t??"\u2014")}</p>
      </div>`;let i=Array.isArray(t)?"array":typeof t=="boolean"?"boolean":typeof t=="number"?"number":"string",a=l=>{try{this.draft.set(e,g(l,{type:i,minimum:s.min,maximum:s.max})),this.fieldErrors={...this.fieldErrors},delete this.fieldErrors[e]}catch(_){this.fieldErrors={...this.fieldErrors,[e]:_.message}}this.requestUpdate()};return i==="boolean"?r`<label class="row"
        ><input
          style="width:auto"
          type="checkbox"
          aria-label=${e}
          .checked=${t}
          ?disabled=${this.busy||this.loading||this.saving}
          @change=${l=>a(l.target.checked)}
        />${c(e)}</label
      >`:i==="array"?r`<label
        >${c(e)}<textarea
          aria-label=${e}
          .value=${JSON.stringify(t,null,2)}
          @change=${l=>a(l.target.value)}
          ?disabled=${this.busy||this.loading||this.saving}
        ></textarea>
      </label>`:this.input(s.label||c(e),t,a,s.type==="password"?"password":i==="number"?"number":"text")}render(){let e=new Map;for(let[t,s]of Object.entries(this.draft.value)){let i=t.split(".")[0];e.has(i)||e.set(i,[]),e.get(i).push([t,s])}return this.frame(r`${this.editNotice()}${[...e].map(([t,s])=>r`<details class="tile" open>
              <summary>${m[t]||c(t)}</summary>
              ${d[t]?r`<small>${d[t]}</small>`:""}
              <div class="grid">
                ${s.map(([i,a])=>r`<div>${this.field(i,a)}${this.fieldErrors?.[i]?r`<small class="error" role="alert">${this.fieldErrors[i]}</small>`:""}</div>`)}
              </div>
            </details>`)}
        <div class="actions">
          <button
            ?disabled=${this.loading||this.busy||this.saving||!this.available}
            @click=${()=>this.load(!0)}
          >
            Check for updates</button
          ><button
            ?disabled=${this.loading||this.busy||this.saving||!this.available||!this.draft.dirty||this.draft.conflicts.length||Object.keys(this.fieldErrors||{}).length}
            @click=${this.save}
          >
            Save settings
          </button>
        </div>
        ${this.saveResults?.length?r`<ul aria-label="Settings save results">
                ${this.saveResults.map(t=>r`<li>${h(t.key).label||c(t.key)}: ${t.success?"Saved":"Failed"}</li>`)}
              </ul>`:""}
        <small
          >Changes are validated by the backend. Some application settings
          require a restart.</small
        >`)}};p("bsm-settings-card",u,"BSM Settings","Grouped application or server settings with typed values and conflict protection.");
