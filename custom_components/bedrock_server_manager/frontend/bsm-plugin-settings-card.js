import{a as y}from"./shared-UXCKWJE4.js";import{b as c,f,g as n,j as $,k as m}from"./shared-66JIFLDQ.js";function p(d,e){return d?.$ref?.startsWith("#/")?d.$ref.slice(2).split("/").reduce((s,t)=>s?.[t],e)||d:d?.anyOf?p(d.anyOf.find(s=>s.type!=="null")||d,e):d||{}}var b=class extends m{static title="Plugin settings";static role="manager";static key="plugin_statuses";static properties={plugin:{state:!0},schema:{state:!0},loading:{state:!0}};constructor(){super(),this.plugin="",this.schema=null,this.loading=!1}reconnected(){super.reconnected(),this.loading=!1,this.plugin&&this.available&&this.load(this.plugin,!0)}input(e,s,t,l="text"){return n`<label
      >${e}<input
        aria-label=${e}
        type=${l}
        .value=${String(s??"")}
        ?disabled=${this.busy||this.loading}
        @input=${a=>t(a.target.value)}
    /></label>`}selectedChanged(){this.plugin="",this.schema=null,this.loading=!1}async load(e,s=!1){if(this.draft.dirty&&e!==this.plugin){this.error="Discard or save your edits before switching plugins.";return}let t=this._generation,l=this._request=(this._request||0)+1;this.plugin=e,this.loading=!0,this.error="";try{let a=await this.responseService("get_plugin_settings",{plugin_name:e});if(t!==this._generation||l!==this._request)return;let h=a.results?y(a):a.managers?.[0];if(!h)throw Error("No plugin settings were returned.");this.schema=h.settings_schema||{type:"object",properties:Object.fromEntries(Object.entries(h.settings).map(([o,r])=>[o,{title:c(o),type:Array.isArray(r)?"array":typeof r=="boolean"?"boolean":typeof r=="number"?"number":r!==null&&typeof r=="object"?"object":"string"}]))},s?this.draft.update(h.settings):this.draft.reset(h.settings),this.revision++}catch(a){t===this._generation&&l===this._request&&(this.error=a.message||String(a))}finally{t===this._generation&&l===this._request&&(this.loading=!1)}}syncState(){let e=this.state,s=e?.attributes.bsm_settings_revision;this.plugin&&this.available&&(s==null?e!==this._lastState:s!==this._lastRevision)&&!this.busy&&!this.loading&&this.load(this.plugin,!0),this._lastRevision=s,this._lastState=e}edit(e,s,t){try{let l=e.split("."),a=l.shift(),h=f(s,t);if(!l.length)this.draft.set(a,h);else{let o=structuredClone(this.draft.value[a]||{}),r=o;for(let i of l.slice(0,-1))r=r[i]||={};r[l.at(-1)]=h,this.draft.set(a,o)}this.error=""}catch(l){this.error=`${c(e)}: ${l.message}`}this.requestUpdate()}field(e,s){let t=p(s,this.schema),l=e.split(".").reduce((i,u)=>i?.[u],this.draft.value)??t.default,a=t.title||c(e),h=t.description,o=p(t.items,this.schema),r;return t.type==="object"&&t.properties?r=n`<fieldset ?disabled=${this.busy||this.loading}>
        <legend>${a}</legend>
        <div class="grid">
          ${Object.entries(t.properties).map(([i,u])=>this.field(`${e}.${i}`,u))}
        </div>
      </fieldset>`:t.type==="array"&&o.enum?r=n`<fieldset ?disabled=${this.busy||this.loading}>
        <legend>${a}</legend>
        ${o.enum.map(i=>n`<label class="row"
              ><input
                style="width:auto"
                type="checkbox"
                aria-label=${String(i)}
                .checked=${(l||[]).includes(i)}
                @change=${u=>{let g=new Set(l||[]);u.target.checked?g.add(i):g.delete(i),this.edit(e,[...g],t)}}
              />${i}</label
            >`)}
      </fieldset>`:t.type==="boolean"?r=n`<label class="row"
        ><input
          style="width:auto"
          type="checkbox"
          aria-label=${a}
          .checked=${!!l}
          ?disabled=${this.busy||this.loading}
          @change=${i=>this.edit(e,i.target.checked,t)}
        />${a}</label
      >`:t.enum?r=n`<fieldset ?disabled=${this.busy||this.loading}>
        ${this.selectInput(a,l,t.enum.map(i=>({value:String(i),label:String(i)})),i=>this.edit(e,i,t))}
      </fieldset>`:["object","array"].includes(t.type)?r=n`<label
        >${a} (JSON)<textarea
          aria-label=${a}
          .value=${JSON.stringify(l??(t.type==="array"?[]:{}),null,2)}
          ?disabled=${this.busy||this.loading}
          @change=${i=>this.edit(e,i.target.value,t)}
        ></textarea>
      </label>`:r=this.input(a,l,i=>this.edit(e,i,t),["number","integer"].includes(t.type)?"number":"text"),n`<div>
      ${r}${h?n`<small>${h}</small>`:""}
    </div>`}async save(){this.draft.conflicts.length||await this.action("update_plugin_settings",{plugin_name:this.plugin,settings:this.draft.value},"Plugin settings saved.")&&(this._lastResponse?.results?.[0]?.warnings?.some(e=>e.code==="refresh_failed")?(this.draft.reset(this.draft.value),this.requestUpdate()):await this.load(this.plugin))}render(){let e=Object.entries(this.state?.attributes.plugins_data||{}).filter(([,s])=>s.has_settings);return this.frame(n`<div class="tabs row" role="tablist" aria-label="Plugin settings">
          ${e.map(([s,t])=>n`<button role="tab" aria-selected=${String(s===this.plugin)} ?disabled=${this.busy||this.loading||!this.available} @click=${()=>this.load(s)}>${t.name||s}</button>`)}
        </div>
        ${this.available&&!e.length?n`<p class="muted">No loaded plugins declare settings.</p>`:""}${this.loading?n`<p role="status">Loading settings…</p>`:""}${this.editNotice()}${this.schema?n`<div class="grid">
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
                </div>`:this.plugin&&!this.loading?n`<p class="muted">
                  This plugin has no editable settings schema.
                </p>`:""}`)}};$("bsm-plugin-settings-card",b,"BSM Plugin Settings","Typed plugin settings with server checklists and backend validation.");
