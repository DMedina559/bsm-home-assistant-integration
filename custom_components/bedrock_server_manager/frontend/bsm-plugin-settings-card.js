import{a,c as u,g as b,h as f,i as m}from"./shared-26346ZH3.js";function g(h,e){return h?.$ref?.startsWith("#/")?h.$ref.slice(2).split("/").reduce((s,t)=>s?.[t],e)||h:h?.anyOf?g(h.anyOf.find(s=>s.type!=="null")||h,e):h||{}}var p=class extends m{static title="Plugin settings";static role="manager";static key="plugin_statuses";static properties={plugin:{state:!0},schema:{state:!0},loading:{state:!0}};constructor(){super(),this.plugin="",this.schema=null,this.loading=!1}selectedChanged(){this.plugin="",this.schema=null,this.loading=!1}async load(e,s=!1){if(this.draft.dirty&&e!==this.plugin){this.error="Discard or save your edits before switching plugins.";return}let t=this._generation,n=this._request=(this._request||0)+1;this.plugin=e,this.loading=!0,this.error="";try{let l=await this.responseService("get_plugin_settings",{plugin_name:e});if(t!==this._generation||n!==this._request)return;let d=l.managers?.[0];if(!d)throw Error("No plugin settings were returned.");this.schema=d.settings_schema||{type:"object",properties:Object.fromEntries(Object.entries(d.settings).map(([o,r])=>[o,{title:u(o),type:Array.isArray(r)?"array":typeof r=="boolean"?"boolean":typeof r=="number"?"number":r!==null&&typeof r=="object"?"object":"string"}]))},s?this.draft.update(d.settings):this.draft.reset(d.settings),this.revision++}catch(l){t===this._generation&&n===this._request&&(this.error=l.message||String(l))}finally{t===this._generation&&n===this._request&&(this.loading=!1)}}syncState(){let e=this.state;this.plugin&&this.available&&e!==this._lastState&&!this.busy&&!this.loading&&this.load(this.plugin,!0),this._lastState=e}edit(e,s,t){try{this.draft.set(e,b(s,t)),this.error=""}catch(n){this.error=`${u(e)}: ${n.message}`}this.requestUpdate()}field(e,s){let t=g(s,this.schema),n=this.draft.value[e]??t.default,l=t.title||u(e),d=t.description,o=g(t.items,this.schema),r;return t.type==="array"&&o.enum?r=a`<fieldset ?disabled=${this.busy||this.loading}>
        <legend>${l}</legend>
        ${o.enum.map(i=>a`<label class="row"
              ><input
                style="width:auto"
                type="checkbox"
                aria-label=${String(i)}
                .checked=${(n||[]).includes(i)}
                @change=${$=>{let c=new Set(this.draft.value[e]||[]);$.target.checked?c.add(i):c.delete(i),this.edit(e,[...c],t)}}
              />${i}</label
            >`)}
      </fieldset>`:t.type==="boolean"?r=a`<label class="row"
        ><input
          style="width:auto"
          type="checkbox"
          aria-label=${l}
          .checked=${!!n}
          ?disabled=${this.busy||this.loading}
          @change=${i=>this.edit(e,i.target.checked,t)}
        />${l}</label
      >`:t.enum?r=this.selectInput(l,n,t.enum.map(i=>({value:String(i),label:String(i)})),i=>this.edit(e,i,t)):["object","array"].includes(t.type)?r=a`<label
        >${l} (JSON)<textarea
          aria-label=${l}
          .value=${JSON.stringify(n??(t.type==="array"?[]:{}),null,2)}
          ?disabled=${this.busy||this.loading}
          @change=${i=>this.edit(e,i.target.value,t)}
        ></textarea>
      </label>`:r=this.input(l,n,i=>this.edit(e,i,t),["number","integer"].includes(t.type)?"number":"text"),a`<div>
      ${r}${d?a`<small>${d}</small>`:""}
    </div>`}async save(){this.draft.conflicts.length||await this.action("update_plugin_settings",{plugin_name:this.plugin,settings:this.draft.value},"Plugin settings saved.")&&await this.load(this.plugin)}render(){let e=Object.entries(this.state?.attributes.plugins_data||{}).filter(([,s])=>s.has_settings);return this.frame(a`<div class="tabs row" role="tablist" aria-label="Plugin settings">
          ${e.map(([s,t])=>a`<button role="tab" aria-selected=${String(s===this.plugin)} ?disabled=${this.busy||this.loading||!this.available} @click=${()=>this.load(s)}>${t.name||s}</button>`)}
        </div>
        ${this.available&&!e.length?a`<p class="muted">No loaded plugins declare settings.</p>`:""}${this.loading?a`<p role="status">Loading settings…</p>`:""}${this.editNotice()}${this.schema?a`<div class="grid">
                  ${Object.entries(this.schema.properties||{}).map(([s,t])=>this.field(s,t))}
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
                </div>`:this.plugin&&!this.loading?a`<p class="muted">
                  This plugin has no editable settings schema.
                </p>`:""}`)}};f("bsm-plugin-settings-card",p,"BSM Plugin Settings","Typed plugin settings with server checklists and backend validation.");
