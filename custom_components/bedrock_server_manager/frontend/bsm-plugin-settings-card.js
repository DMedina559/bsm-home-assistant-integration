import{a as _}from"./shared-7NSZLO6S.js";import{b as c,f,g as n,j as m,k as v}from"./shared-3LOQBGQY.js";function p(o,t){return o?.$ref?.startsWith("#/")?o.$ref.slice(2).split("/").reduce((a,e)=>a?.[e],t)||o:o?.anyOf?p(o.anyOf.find(a=>a.type!=="null")||o,t):o||{}}var b=class extends v{static title="Plugin settings";static role="manager";static key="plugin_statuses";static properties={scope:{state:!0},serverName:{state:!0},plugin:{state:!0},schema:{state:!0},loading:{state:!0}};constructor(){super(),this.scope="plugin",this.serverName="",this.plugin="",this.schema=null,this.loading=!1}reconnected(){super.reconnected(),this.loading=!1,this.plugin&&this.available&&this.load(this.plugin,!0)}input(t,a,e,s="text"){return n`<label
      >${t}<input
        aria-label=${t}
        type=${s}
        .value=${String(a??"")}
        ?disabled=${this.busy||this.loading}
        @input=${r=>e(r.target.value)}
    /></label>`}selectedChanged(){this.serverName="",this.plugin="",this.schema=null,this.loading=!1}_eventUpdate(t){if(!this.plugin||t?.manager_url!==this._managerUrl)return;let a=t.event||t.topic?.replace("event:","");["after_plugin_settings_update","after_setting_update","after_set_server_setting","after_restore"].includes(a)&&(this.busy||this.loading?this._reloadPending=!0:this.load(this.plugin,!0))}scopeOptions(){return{scope:this.scope,...this.scope==="server"?{server_name:this.serverName}:{}}}changeScope(t,a=this.serverName){if(this.draft.dirty){this.feedback="Save or discard your edits before changing scope.";return}this._request=(this._request||0)+1,this.scope=t,this.serverName=a,this.plugin="",this.schema=null,this.loading=!1,this.error="",this.draft.reset({})}async load(t,a=!1){if(this.scope==="server"&&!this.serverName)return;if(this.draft.dirty&&t!==this.plugin){this.error="Discard or save your edits before switching plugins.";return}let e=this._generation,s=this._request=(this._request||0)+1;this.plugin=t,this.loading=!0,this.error="";try{let r=await this.responseService("get_plugin_settings",{plugin_name:t,...this.scopeOptions()});if(e!==this._generation||s!==this._request)return;let h=r.results?_(r):r.managers?.[0];if(!h)throw Error("No plugin settings were returned.");this.schema=h.settings_schema||{type:"object",properties:Object.fromEntries(Object.entries(h.settings).map(([u,l])=>[u,{title:c(u),type:Array.isArray(l)?"array":typeof l=="boolean"?"boolean":typeof l=="number"?"number":l!==null&&typeof l=="object"?"object":"string"}]))},a?this.draft.update(h.settings):this.draft.reset(h.settings),this.revision++}catch(r){e===this._generation&&s===this._request&&(this.error=r.message||String(r))}finally{e===this._generation&&s===this._request&&(this.loading=!1),e===this._generation&&this._reloadPending&&(this._reloadPending=!1,this.load(this.plugin,!0))}}syncState(){let t=this.state,a=t?.attributes.bsm_settings_revision;this.plugin&&this.available&&(a==null?t!==this._lastState:a!==this._lastRevision)&&!this.busy&&!this.loading&&this.load(this.plugin,!0),this._lastRevision=a,this._lastState=t}edit(t,a,e){try{let s=t.split("."),r=s.shift(),h=f(a,e);if(!s.length)this.draft.set(r,h);else{let u=structuredClone(this.draft.value[r]||{}),l=u;for(let i of s.slice(0,-1))l=l[i]||={};l[s.at(-1)]=h,this.draft.set(r,u)}this.error=""}catch(s){this.error=`${c(t)}: ${s.message}`}this.requestUpdate()}field(t,a){let e=p(a,this.schema),s=t.split(".").reduce((i,d)=>i?.[d],this.draft.value)??e.default,r=e.title||c(t),h=e.description,u=p(e.items,this.schema),l;return e.type==="object"&&e.properties?l=n`<fieldset ?disabled=${this.busy||this.loading}>
        <legend>${r}</legend>
        <div class="grid">
          ${Object.entries(e.properties).map(([i,d])=>this.field(`${t}.${i}`,d))}
        </div>
      </fieldset>`:e.type==="array"&&u.enum?l=n`<fieldset ?disabled=${this.busy||this.loading}>
        <legend>${r}</legend>
        ${u.enum.map(i=>n`<label class="row"
              ><input
                style="width:auto"
                type="checkbox"
                aria-label=${String(i)}
                .checked=${(s||[]).includes(i)}
                @change=${d=>{let g=new Set(s||[]);d.target.checked?g.add(i):g.delete(i),this.edit(t,[...g],e)}}
              />${e["x-bsm-choice-labels"]?.[i]||i}</label
            >`)}
      </fieldset>`:e.type==="boolean"?l=n`<label class="row"
        ><input
          style="width:auto"
          type="checkbox"
          aria-label=${r}
          .checked=${!!s}
          ?disabled=${this.busy||this.loading}
          @change=${i=>this.edit(t,i.target.checked,e)}
        />${r}</label
      >`:e.enum?l=n`<fieldset ?disabled=${this.busy||this.loading}>
        ${this.selectInput(r,s,e.enum.map(i=>({value:String(i),label:String(i)})),i=>this.edit(t,i,e))}
      </fieldset>`:["object","array"].includes(e.type)?l=n`<label
        >${r} (JSON)<textarea
          aria-label=${r}
          .value=${JSON.stringify(s??(e.type==="array"?[]:{}),null,2)}
          ?disabled=${this.busy||this.loading}
          @change=${i=>this.edit(t,i.target.value,e)}
        ></textarea>
      </label>`:l=this.input(r,s,i=>this.edit(t,i,e),["number","integer"].includes(e.type)?"number":"text"),n`<div>
      ${l}${h?n`<small>${h}</small>`:""}
    </div>`}async save(){this.draft.conflicts.length||await this.action("update_plugin_settings",{plugin_name:this.plugin,settings:this.draft.value,...this.scopeOptions()},"Plugin settings saved.")&&(this._lastResponse?.results?.[0]?.warnings?.some(t=>t.code==="refresh_failed")?(this.draft.reset(this.draft.value),this.requestUpdate()):await this.load(this.plugin))}render(){let t=Object.entries(this.state?.attributes.plugins_data||{}).filter(([,e])=>e[{plugin:"has_settings",global:"has_global_settings",server:"has_server_settings"}[this.scope]]),a=[...new Set(Object.values(this.hass?.states||{}).filter(e=>e.attributes.bsm_manager_url===this.state?.attributes.bsm_manager_url&&e.attributes.bsm_server_name).map(e=>e.attributes.bsm_server_name))];return this.frame(n`${this.selectInput("Settings scope",this.scope,[{value:"plugin",label:"Plugin"},{value:"global",label:"Global"},{value:"server",label:"Server"}],e=>this.changeScope(e))}
        ${this.scope==="server"?this.selectInput("Server",this.serverName,[{value:"",label:"Select server"},...a],e=>this.changeScope(this.scope,e)):""}
        <div class="tabs row" role="tablist" aria-label="Plugin settings">
          ${t.map(([e,s])=>n`<button role="tab" aria-selected=${String(e===this.plugin)} ?disabled=${this.busy||this.loading||!this.available||this.scope==="server"&&!this.serverName} @click=${()=>this.load(e)}>${s.name||e}</button>`)}
        </div>
        ${this.available&&!t.length?n`<p class="muted">No loaded plugins declare settings.</p>`:""}${this.loading?n`<p role="status">Loading settings…</p>`:""}${this.editNotice()}${this.schema?n`<div class="grid">
                  ${Object.entries(this.schema.properties||{}).map(([e,s])=>this.field(e,s))}
                </div>
                <div class="actions">
                  <button
                    ?disabled=${this.loading||this.busy||!this.available}
                    @click=${()=>this.load(this.plugin,!0)}
                  >
                    Check for updates</button
                  ><button
                    class="primary"
                    ?disabled=${!this.available||this.loading||this.busy||!this.draft.dirty||this.draft.conflicts.length>0||!!this.error}
                    @click=${this.save}
                  >
                    Save settings
                  </button>
                </div>`:this.plugin&&!this.loading?n`<p class="muted">
                  This plugin has no editable settings schema.
                </p>`:""}`)}};m("bsm-plugin-settings-card",b,"BSM Plugin Settings","Typed plugin settings with server checklists and backend validation.");
