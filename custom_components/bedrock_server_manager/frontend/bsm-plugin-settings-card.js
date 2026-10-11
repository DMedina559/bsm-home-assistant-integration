import{b as u,f,g as n,j as $,k as m}from"./shared-EVDKEACZ.js";function p(d,e){return d?.$ref?.startsWith("#/")?d.$ref.slice(2).split("/").reduce((i,t)=>i?.[t],e)||d:d?.anyOf?p(d.anyOf.find(i=>i.type!=="null")||d,e):d||{}}var b=class extends m{static title="Plugin settings";static role="manager";static key="plugin_statuses";static properties={plugin:{state:!0},schema:{state:!0},loading:{state:!0}};constructor(){super(),this.plugin="",this.schema=null,this.loading=!1}selectedChanged(){this.plugin="",this.schema=null,this.loading=!1}async load(e,i=!1){if(this.draft.dirty&&e!==this.plugin){this.error="Discard or save your edits before switching plugins.";return}let t=this._generation,a=this._request=(this._request||0)+1;this.plugin=e,this.loading=!0,this.error="";try{let l=await this.responseService("get_plugin_settings",{plugin_name:e});if(t!==this._generation||a!==this._request)return;let h=l.managers?.[0];if(!h)throw Error("No plugin settings were returned.");this.schema=h.settings_schema||{type:"object",properties:Object.fromEntries(Object.entries(h.settings).map(([o,r])=>[o,{title:u(o),type:Array.isArray(r)?"array":typeof r=="boolean"?"boolean":typeof r=="number"?"number":r!==null&&typeof r=="object"?"object":"string"}]))},i?this.draft.update(h.settings):this.draft.reset(h.settings),this.revision++}catch(l){t===this._generation&&a===this._request&&(this.error=l.message||String(l))}finally{t===this._generation&&a===this._request&&(this.loading=!1)}}syncState(){let e=this.state;this.plugin&&this.available&&e!==this._lastState&&!this.busy&&!this.loading&&this.load(this.plugin,!0),this._lastState=e}edit(e,i,t){try{let a=e.split("."),l=a.shift(),h=f(i,t);if(!a.length)this.draft.set(l,h);else{let o=structuredClone(this.draft.value[l]||{}),r=o;for(let s of a.slice(0,-1))r=r[s]||={};r[a.at(-1)]=h,this.draft.set(l,o)}this.error=""}catch(a){this.error=`${u(e)}: ${a.message}`}this.requestUpdate()}field(e,i){let t=p(i,this.schema),a=e.split(".").reduce((s,c)=>s?.[c],this.draft.value)??t.default,l=t.title||u(e),h=t.description,o=p(t.items,this.schema),r;return t.type==="object"&&t.properties?r=n`<fieldset ?disabled=${this.busy||this.loading}>
        <legend>${l}</legend>
        <div class="grid">
          ${Object.entries(t.properties).map(([s,c])=>this.field(`${e}.${s}`,c))}
        </div>
      </fieldset>`:t.type==="array"&&o.enum?r=n`<fieldset ?disabled=${this.busy||this.loading}>
        <legend>${l}</legend>
        ${o.enum.map(s=>n`<label class="row"
              ><input
                style="width:auto"
                type="checkbox"
                aria-label=${String(s)}
                .checked=${(a||[]).includes(s)}
                @change=${c=>{let g=new Set(a||[]);c.target.checked?g.add(s):g.delete(s),this.edit(e,[...g],t)}}
              />${s}</label
            >`)}
      </fieldset>`:t.type==="boolean"?r=n`<label class="row"
        ><input
          style="width:auto"
          type="checkbox"
          aria-label=${l}
          .checked=${!!a}
          ?disabled=${this.busy||this.loading}
          @change=${s=>this.edit(e,s.target.checked,t)}
        />${l}</label
      >`:t.enum?r=this.selectInput(l,a,t.enum.map(s=>({value:String(s),label:String(s)})),s=>this.edit(e,s,t)):["object","array"].includes(t.type)?r=n`<label
        >${l} (JSON)<textarea
          aria-label=${l}
          .value=${JSON.stringify(a??(t.type==="array"?[]:{}),null,2)}
          ?disabled=${this.busy||this.loading}
          @change=${s=>this.edit(e,s.target.value,t)}
        ></textarea>
      </label>`:r=this.input(l,a,s=>this.edit(e,s,t),["number","integer"].includes(t.type)?"number":"text"),n`<div>
      ${r}${h?n`<small>${h}</small>`:""}
    </div>`}async save(){this.draft.conflicts.length||await this.action("update_plugin_settings",{plugin_name:this.plugin,settings:this.draft.value},"Plugin settings saved.")&&await this.load(this.plugin)}render(){let e=Object.entries(this.state?.attributes.plugins_data||{}).filter(([,i])=>i.has_settings);return this.frame(n`<div class="tabs row" role="tablist" aria-label="Plugin settings">
          ${e.map(([i,t])=>n`<button role="tab" aria-selected=${String(i===this.plugin)} ?disabled=${this.busy||this.loading||!this.available} @click=${()=>this.load(i)}>${t.name||i}</button>`)}
        </div>
        ${this.available&&!e.length?n`<p class="muted">No loaded plugins declare settings.</p>`:""}${this.loading?n`<p role="status">Loading settings…</p>`:""}${this.editNotice()}${this.schema?n`<div class="grid">
                  ${Object.entries(this.schema.properties||{}).map(([i,t])=>this.field(i,t))}
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
                </p>`:""}`)}};$("bsm-plugin-settings-card",b,"BSM Plugin Settings","Typed plugin settings with server checklists and backend validation.");
