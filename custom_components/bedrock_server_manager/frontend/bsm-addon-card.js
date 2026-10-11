import{g as i,j as l,k as n}from"./shared-EVDKEACZ.js";var d=class extends n{static title="Installed addons";static key="server_addons_count";static properties={type:{state:!0}};constructor(){super(),this.type="behavior"}syncState(){this.available&&(this.draft.update(this.state.attributes.server_addons_list||{}),this.requestUpdate())}selectedChanged(){this.syncState()}get packs(){return this.draft.value[`${this.type}_packs`]||[]}move(t,s){let e=`${this.type}_packs`,a=[...this.packs];[a[t],a[t+s]]=[a[t+s],a[t]],this.draft.set(e,a),this.requestUpdate()}async save(){if(this.draft.conflicts.length)return;await this.action("reorder_addons",{pack_type:this.type,uuids:this.packs.filter(s=>s.status==="ACTIVE").map(s=>s.uuid)},"Addon order saved.")&&this.draft.reset(this.draft.live)}render(){return this.frame(i`${this.selectInput("Pack type",this.type,["behavior","resource"],t=>this.type=t)}${this.editNotice()}${this.packs.map((t,s)=>i`<section class="tile">
              <div class="heading">
                <strong>${t.name||t.uuid}</strong
                ><small>${t.status}</small>
              </div>
              <div class="actions">
                ${this.button(t.status==="ACTIVE"?"Disable":"Enable",t.status==="ACTIVE"?"disable_addon":"enable_addon",{pack_uuid:t.uuid,pack_type:this.type})}${this.button("Uninstall","uninstall_addon",{pack_uuid:t.uuid,pack_type:this.type},{confirm:`Uninstall ${t.name||t.uuid}?`})}<button
                  aria-label=${`Move ${t.name} up`}
                  ?disabled=${this.busy||!this.available||s===0}
                  @click=${()=>this.move(s,-1)}
                >
                  ↑</button
                ><button
                  aria-label=${`Move ${t.name} down`}
                  ?disabled=${this.busy||!this.available||s===this.packs.length-1}
                  @click=${()=>this.move(s,1)}
                >
                  ↓
                </button>
              </div>
              ${t.subpacks?.length?this.selectInput(`Subpack for ${t.name}`,t.active_subpack||"",[{value:"",label:"Default"},...t.subpacks.map(e=>({value:e.folder_name,label:e.name||e.folder_name}))],e=>this.action("update_addon_subpack",{pack_uuid:t.uuid,pack_type:this.type,subpack_name:e})):""}
            </section>`)}${this.available&&!this.packs.length?i`<p class="muted">No ${this.type} packs installed.</p>`:""}<button
          ?disabled=${this.busy||!this.available||!this.draft.dirty||this.draft.conflicts.length>0}
          @click=${this.save}
        >
          Save addon order
        </button>`)}};l("bsm-addon-card",d,"BSM Addons","Enable, configure and reorder installed addons.");
