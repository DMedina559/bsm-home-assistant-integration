import{a as i,e as c,g as e,j as l,k as p}from"./shared-66JIFLDQ.js";var a=class extends p{static title="Restore server backup";static key="world_backups_count";static properties={type:{state:!0},file:{state:!0}};constructor(){super(),this.type="world",this.file=""}selectedChanged(){this.file=""}render(){let t=this.stateFor(`${this.type}_backups_count`)||(this.type==="world"?this.state:null),r=(t?.attributes[`${this.type}_backups_list`]||[]).map(c);return this.frame(e`${this.selectInput("Backup type",this.type,["world","allowlist","properties","permissions"],s=>{this.type=s,this.file=""})}${this.selectInput("Backup file",this.file,[{value:"",label:"Select backup"},...r],s=>this.file=s)}${i(t)?e`<p class="muted">This backup list is unavailable.</p>`:r.length?"":e`<p class="muted">No backups of this type.</p>`}
        <div class="actions">
          <button
            ?disabled=${this.busy||!this.available||i(t)||!this.file}
            @click=${()=>this.action("restore_backup",{restore_type:this.type,backup_file:this.file},"Request accepted.",{confirm:"Restoring replaces current server data. Continue?"})}
          >
            Restore selected backup</button
          >${this.button("Restore latest backups","restore_latest_all",{},{message:"Request accepted.",confirm:"Restore the latest world and configuration backups, replacing current data?"})}
          ${this.button("Prune old backups","prune_backups",{},{message:"Backup pruning accepted.",confirm:"Prune backups using the server retention settings? Removed backups cannot be recovered."})}
        </div>`)}};l("bsm-restore-card",a,"BSM Restore","Restore selected or latest backups with task feedback.");
