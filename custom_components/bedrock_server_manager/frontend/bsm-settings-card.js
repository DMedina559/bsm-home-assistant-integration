import{a as c,c as l,g,j as p,k as b}from"./shared-5SVUCQ5X.js";var n=(r,e=0,t,s=1,i)=>({type:"number",description:r,min:e,max:t,step:s,unit:i}),f={paths:"Storage locations",retention:"Retention",monitoring:"Monitoring",web:"Web server",lifecycle:"Startup and shutdown",server_info:"Server information",settings:"Server behavior",custom:"Custom settings",plugin_settings:"Plugin settings"},h={paths:"Directories used for servers, backups, downloads, and extensions.",retention:"Previous files to keep. Zero disables automatic cleanup.",monitoring:"Metrics interval changes apply on the next monitoring cycle.",web:"Listener and authentication settings. Listener changes require a restart.",lifecycle:"Limits for startup and cleanup. Request draining changes require a web server restart.",server_info:"Installed state is reported by the server. Choose a target version for updates.",settings:"Automatic actions for this server.",custom:"Additional settings used by your extensions."},m={"monitoring.app_metrics_interval_sec":{...n("Application and system metrics sampling.",1,3600,1,"seconds"),label:"Application metrics interval"},"monitoring.bedrock_metrics_interval_sec":{...n("Resource updates on Bedrock monitor pages.",1,3600,1,"seconds"),label:"Bedrock metrics interval"},"monitoring.process_interval_sec":n("Checks server process state.",1,void 0,1,"seconds"),"monitoring.player_interval_sec":n("Checks connected players.",1,void 0,1,"seconds"),"monitoring.max_retries":n("Retries before a failed process check is reported."),"retention.backups":n("Backups retained per server."),"retention.downloads":n("Downloaded versions retained."),"web.port":n("TCP port for the web server.",1,65535),"web.token_expires_weeks":n("Lifetime of authentication tokens.",1,void 0,1,"weeks"),"web.jwt_secret_key":{type:"password",description:"Signing secret. Changing it invalidates existing tokens."},"server_info.status":{readOnly:!0},"server_info.installed_version":{readOnly:!0},"server_info.server_name":{readOnly:!0},"settings.target_version":{description:"Use LATEST, PREVIEW, or a specific Bedrock version."},"settings.autostart":{type:"boolean",description:"Start this server when the application starts."},"settings.autoupdate":{type:"boolean",description:"Update this server automatically on startup."}};for(let[r,e]of Object.entries({startup_timeout_seconds:"Deadline for each startup stage.",shutdown_timeout_seconds:"Deadline for each shutdown stage.",task_drain_timeout_seconds:"Time for operations to finish before cancellation.",plugin_timeout_seconds:"Time allowed for plugin unload and router cleanup.",cancellation_grace_seconds:"Extra time to handle cancellation.",request_drain_timeout_seconds:"Time to drain HTTP requests before cleanup."}))m[`lifecycle.${r}`]=n(e,1e-6,r==="cancellation_grace_seconds"?30:600,"any","seconds");function _(r){return m[r]??{}}function v(r,e=""){return Object.fromEntries(Object.entries(r||{}).flatMap(([t,s])=>{let i=e?`${e}.${t}`:t;return s&&typeof s=="object"&&!Array.isArray(s)?Object.entries(v(s,i)):[[i,s]]}))}var u=class extends b{static role="manager";static key="bsm_version";static title="Application settings";static properties={loading:{state:!0}};static getConfigForm(){let e=super.getConfigForm();return e.schema.push({name:"scope",selector:{select:{options:["application","server"]}}}),e}connectedCallback(){super.connectedCallback(),this._subscribeChanges()}disconnectedCallback(){this._changesConnection=null,this._unsubscribeChanges?.(),this._unsubscribeChanges=null,super.disconnectedCallback()}async _subscribeChanges(){let e=this.hass?.connection;if(!(!e||!this.isConnected||this._changesConnection===e)){this._unsubscribeChanges?.(),this._changesConnection=e;try{let t=await e.subscribeEvents(s=>{let i=s.data,a=this._managerUrl;if(!a||i?.manager_url!==a)return;let o=i.event||i.topic?.replace("event:","");if(this.config.scope==="server"){let d=i.data?.server_name||i.data?.result?.server_name;if(o!=="after_set_server_setting"||d!==this.state?.attributes.bsm_server_name)return}else if(o!=="after_setting_update")return;this.loading||this.busy?this._reloadPending=!0:this.load(!0)},"bedrock_server_manager_event");!this.isConnected||this._changesConnection!==e?t():this._unsubscribeChanges=t}catch{this._changesConnection===e&&(this._changesConnection=null)}}}normalizeSelection(){if(this.config.scope==="server"){let e=Object.entries(this.hass?.states||{}).find(([t,s])=>s.attributes.bsm_key==="status"&&this.hass.entities?.[t]?.device_id===this.hass.entities?.[this.selection]?.device_id)?.[0];e&&e!==this.selection&&this.select(e)}else super.normalizeSelection()}pick(){if(this.config.scope!=="server")return super.pick();let e=Object.entries(this.hass?.states||{}).filter(([,t])=>t.attributes.bsm_role==="server"&&t.attributes.bsm_key==="status");return this.selectInput("Server",this.selection,[{value:"",label:"Select server"},...e.map(([t,s])=>({value:t,label:s.attributes.bsm_server_name||s.attributes.friendly_name}))],t=>this.select(t))}selectedChanged(){this._loaded="",this.loading=!1,this._managerUrl="",this._reloadPending=!1}syncState(){this._subscribeChanges(),this.available&&this._loaded!==this.selection&&(this._loaded=this.selection,this.load())}async load(e=!1){if(!this.available||this.loading)return;let t=this._generation;this.loading=!0;try{let s=await this.responseService(this.config.scope==="server"?"get_server_settings":"get_application_settings",{});if(t!==this._generation)return;this._managerUrl=s.results?.[0]?.manager_url;let i=v(s.results?.[0]?.result?.settings||{});e?this.draft.update(i):this.draft.reset(i),this.error="",this.revision++}catch(s){t===this._generation&&(this.error=s.message||String(s))}finally{t===this._generation&&(this.loading=!1,this._reloadPending&&!this.busy&&(this._reloadPending=!1,this.load(!0)))}}async save(){if(!this.draft.conflicts.length){for(let[e,t]of Object.entries(this.draft.changes))if(!await this.action(this.config.scope==="server"?"set_server_setting":"set_global_setting",{key:e,value:t}))return;await this.load()}}field(e,t){let s=_(e);if(s.readOnly)return c`<div>
        <small>${l(e)}</small>
        <p>${String(t??"\u2014")}</p>
      </div>`;let i=Array.isArray(t)?"array":typeof t=="boolean"?"boolean":typeof t=="number"?"number":"string",a=o=>{try{this.draft.set(e,g(o,{type:i,minimum:s.min,maximum:s.max})),this.error=""}catch(d){this.error=`${e}: ${d.message}`}this.requestUpdate()};return i==="boolean"?c`<label class="row"
        ><input
          style="width:auto"
          type="checkbox"
          aria-label=${e}
          .checked=${t}
          ?disabled=${this.busy||this.loading}
          @change=${o=>a(o.target.checked)}
        />${l(e)}</label
      >`:i==="array"?c`<label
        >${l(e)}<textarea
          aria-label=${e}
          .value=${JSON.stringify(t,null,2)}
          @change=${o=>a(o.target.value)}
          ?disabled=${this.busy||this.loading}
        ></textarea>
      </label>`:this.input(l(e),t,a,s.type==="password"?"password":i==="number"?"number":"text")}render(){let e=new Map;for(let[t,s]of Object.entries(this.draft.value)){let i=t.split(".")[0];e.has(i)||e.set(i,[]),e.get(i).push([t,s])}return this.frame(c`${this.editNotice()}${[...e].map(([t,s])=>c`<details class="tile" open>
              <summary>${f[t]||l(t)}</summary>
              ${h[t]?c`<small>${h[t]}</small>`:""}
              <div class="grid">
                ${s.map(([i,a])=>this.field(i,a))}
              </div>
            </details>`)}
        <div class="actions">
          <button
            ?disabled=${this.loading||this.busy||!this.available}
            @click=${()=>this.load(!0)}
          >
            Check for updates</button
          ><button
            ?disabled=${this.loading||this.busy||!this.available||!this.draft.dirty||this.draft.conflicts.length||!!this.error}
            @click=${this.save}
          >
            Save settings
          </button>
        </div>
        <small
          >Changes are validated by the backend. Some application settings
          require a restart.</small
        >`)}};p("bsm-settings-card",u,"BSM Settings","Grouped application or server settings with typed values and conflict protection.");
