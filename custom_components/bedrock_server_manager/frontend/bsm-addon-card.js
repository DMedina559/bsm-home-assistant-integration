import{g as n,j as l,k as r}from"./shared-7UTSRN4G.js";var u=class extends r{static title="Installed addons";static key="server_addons_count";static properties={type:{state:!0}};constructor(){super(),this.type="behavior"}syncState(){if(this.available){let t=this.state.attributes.server_addons_list||{};this.draft.update(Object.fromEntries(Object.entries(t).map(([s,e])=>[s,e.map(a=>a.uuid)]))),this.requestUpdate()}}selectedChanged(){this.syncState()}get packs(){let t=`${this.type}_packs`,s=this.state?.attributes.server_addons_list?.[t]||[],e=this.draft.value[t]||[],a=i=>{let d=e.indexOf(i.uuid);return d<0?e.length:d};return[...s].sort((i,d)=>a(i)-a(d))}move(t,s){let e=`${this.type}_packs`,a=[...this.packs];[a[t],a[t+s]]=[a[t+s],a[t]],this.draft.set(e,a.map(i=>i.uuid)),this.requestUpdate()}async save(){if(this.draft.conflicts.length)return;if(await this.action("reorder_addons",{pack_type:this.type,uuids:this.packs.filter(s=>s.status==="ACTIVE").map(s=>s.uuid)},"Addon order saved.")){let s=`${this.type}_packs`,e=this.draft.value[s];delete this.draft.changes[s],this.draft.base[s]=structuredClone(e),this.draft.live[s]=structuredClone(e),this.requestUpdate()}}render(){return this.frame(n`${this.selectInput("Pack type",this.type,["behavior","resource"],t=>this.type=t)}${this.editNotice()}${this.packs.map((t,s)=>n`<section class="tile">
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
            </section>`)}${this.available&&!this.packs.length?n`<p class="muted">No ${this.type} packs installed.</p>`:""}<button
          ?disabled=${this.busy||!this.available||!this.draft.dirty||this.draft.conflicts.length>0}
          @click=${this.save}
        >
          Save addon order
        </button>`)}};l("bsm-addon-card",u,"BSM Addons","Enable, configure and reorder installed addons.");
