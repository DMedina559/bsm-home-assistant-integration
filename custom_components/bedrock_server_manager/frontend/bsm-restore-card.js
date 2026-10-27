import{a as u,b as d}from"./shared-7NSZLO6S.js";import{g as i,h as c,j as h}from"./shared-3LOQBGQY.js";var l=class extends d{static title="Server backups";static key="world_backups_count";static properties={filePath:{state:!0},recoveryKey:{state:!0},backups:{state:!0},backupId:{state:!0},mode:{state:!0},components:{state:!0},choices:{state:!0},manifest:{state:!0},plan:{state:!0},selectedComponents:{state:!0}};constructor(){super(),this.resetBackupState()}resetBackupState(){this.filePath="",this.recoveryKey="",this.backups=null,this.backupId="",this.mode="default",this.components=[],this.choices=[],this.manifest=null,this.plan=null,this.selectedComponents=[],this._handled=new Set}selectedChanged(){super.selectedChanged(),this.resetBackupState()}reconnected(){super.reconnected(),this.plan=null}chooseBackup(t){this.backupId=t,this.manifest=null,this.plan=null,this.selectedComponents=[]}async refresh(){let t=this._generation,s=await this.read("list_server_snapshots",{});if(!(!s||t!==this._generation)){this.backups=s.backups||[],this.backups.some(e=>e.backup_id===this.backupId)||this.chooseBackup("");try{let e=u(await this.responseService("discover_operations",{}));if(t!==this._generation)return;let o=e.operations.find(n=>n.operation_id==="create_server_snapshot")?.request_body?.content?.["application/json"]?.schema?.properties?.components,r=o?.anyOf?.find(n=>n.type==="array")||o;this.choices=(r?.items?.enum||[]).map(n=>({value:n,label:r?.["x-bsm-choice-labels"]?.[n]||n})),this.components.length||(this.components=r?.["x-bsm-default-components"]||[])}catch(e){t===this._generation&&(this.error=e.message)}}}_showTasks(){super._showTasks();for(let{task:t}of this._tasks.values())if(!(t.status!=="completed"||this._handled.has(t.id))){if(this._handled.add(t.id),t.result?.backup?.backup_id){let s=t.result.backup;this.backups=[s,...(this.backups||[]).filter(e=>e.backup_id!==s.backup_id)]}t.result?.backup?.backup_id===this.backupId&&(this.manifest=t.result.backup.manifest,this.selectedComponents=Object.entries(this.manifest?.components||{}).filter(([,s])=>s==="included").map(([s])=>s),this.plan=null),t.result?.plan?.backup_id===this.backupId&&(this.plan=t.result.plan)}}selectionFields(t,s,e){return i`<fieldset ?disabled=${this.busy||this.loading}>
      <legend>Components</legend>
      ${t.map(a=>i`<label class="row"><input style="width:auto" type="checkbox" .checked=${s.includes(a.value)} @change=${o=>e(o.target.checked?[...s,a.value]:s.filter(r=>r!==a.value))} />${a.label}</label>`)}
    </fieldset>`}async action(t,...s){let e=this._generation,a=await super.action(t,...s);return a&&e===this._generation&&t==="restore_server_snapshot"&&(this.plan=null),a}credential(){return this.recoveryKey?{recovery_key:this.recoveryKey}:{}}requestData(){return{backup_id:this.backupId,components:this.selectedComponents,...this.credential()}}render(){let t=this.busy||this.loading||!this.available,s=Object.entries(this.manifest?.components||{}).filter(([,e])=>e==="included").map(([e])=>({value:e,label:e}));return this.frame(i`${this.readNotice()}
        <div class="actions">
          <button ?disabled=${t} @click=${this.refresh}>
            Refresh backups</button
          >${this.readButton("Backup health","get_backup_health")}${this.readButton("Recovery status","get_restore_recovery")}
        </div>
        <h3>Create backup</h3>
        ${this.selectInput("Backup contents",this.mode,[{value:"default",label:"Global defaults"},{value:"world",label:"World"},{value:"selected",label:"Selected components"},{value:"full",label:"Full server directory"}],e=>this.mode=e)}
        ${this.mode==="selected"?this.selectionFields(this.choices,this.components,e=>this.components=e):""}
        <button
          ?disabled=${t||this.mode==="selected"&&!this.components.length}
          @click=${()=>this.action("create_server_snapshot",this.mode==="default"?{}:{mode:this.mode,...this.mode==="selected"?{components:this.components}:{}},"Backup requested.")}
        >
          Create backup
        </button>
        <h3>Saved backups</h3>
        ${this.backups===null?i`<p class="muted">Load backups to see available archives.</p>`:this.backups.length?this.selectInput("Backup",this.backupId,[{value:"",label:"Select backup"},...this.backups.map(e=>({value:e.backup_id,label:`${e.label||e.filename} \xB7 ${e.created_at?new Date(e.created_at).toLocaleString():"Unknown time"} \xB7 ${e.verification?.status||"unverified"}`}))],e=>this.chooseBackup(e)):i`<p>No backups available.</p>`}
        ${this.backupId?i`<div class="actions"><button ?disabled=${t} @click=${()=>this.action("inspect_server_snapshot",{backup_id:this.backupId,...this.credential()},"Inspection requested.")}>Inspect</button>${["verify","pin","unpin","drill"].map(e=>i`<button ?disabled=${t} @click=${()=>this.action("manage_server_snapshot",{backup_id:this.backupId,action:e,...this.credential()},"Request accepted.")}>${{verify:"Verify",pin:"Pin",unpin:"Unpin",drill:"Recovery drill"}[e]}</button>`)}</div>`:""}
        ${this.manifest?i`<h3>Restore selection</h3>
                ${this.selectionFields(s,this.selectedComponents,e=>{this.selectedComponents=e,this.plan=null})}
                <div class="actions">
                  <button
                    ?disabled=${t||!this.selectedComponents.length}
                    @click=${()=>{this.plan=null,this.action("plan_snapshot_restore",this.requestData(),"Review requested.")}}
                  >
                    Review restore</button
                  ><button
                    ?disabled=${t||!this.selectedComponents.length}
                    @click=${()=>this.action("dry_run_server_restore",this.requestData(),"Dry run requested.")}
                  >
                    Dry run
                  </button>
                </div>`:""}
        ${this.plan?i`<h3>Restore review</h3>
                ${c({...this.plan,token:void 0})}<button
                  ?disabled=${t}
                  @click=${()=>{let e=this.plan;this.action("restore_server_snapshot",{backup_id:e.backup_id,components:e.components,token:e.token,...this.credential()},"Restore requested.",{confirm:"Restore the reviewed components? Current data will be replaced and the server may stop and restart."})}}
                >
                  Restore reviewed components
                </button>`:""}
        <details>
          <summary>Files and recovery key</summary>
          <form @submit=${e=>e.preventDefault()}>
            ${this.input("File path on Home Assistant",this.filePath,e=>this.filePath=e)}
            ${this.input("Recovery key (optional)",this.recoveryKey,e=>{this.recoveryKey=e,this.plan=null},"password")}
            <p class="muted">
              Use an allowed Home Assistant directory. Downloads need a new
              filename. A recovery key is only needed when the BSM host does not
              have the archive key.
            </p>
            <div class="actions">
              <button
                type="button"
                ?disabled=${t||!this.filePath}
                @click=${()=>this.action("import_server_snapshot",{file_path:this.filePath,...this.credential()},"Import requested.")}
              >
                Import archive</button
              ><button
                type="button"
                ?disabled=${t||!this.filePath||!this.backupId}
                @click=${()=>this.action("download_server_snapshot",{backup_id:this.backupId,file_path:this.filePath},"Archive saved on Home Assistant.")}
              >
                Export archive
              </button>
            </div>
          </form>
        </details>
        <div class="actions">
          ${this.button("Prune backups","prune_backups",{},{confirm:"Prune unprotected backups using retention settings? Removed backups cannot be recovered."})}${this.button("Retry recovery","recover_server_backup",{},{confirm:"Retry restore journal recovery? Stop the server first; recovery can roll back server data."})}
        </div>
        <details>
          <summary>Health and recovery details</summary>
          ${c(this.result)}
        </details>`)}};h("bsm-restore-card",l,"BSM Backups and Restore","Create component backups, inspect archives, verify, and review restores before applying.");
