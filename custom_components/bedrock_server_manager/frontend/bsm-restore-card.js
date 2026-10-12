import{a as i,e as l,g as t,j as c,k as p}from"./shared-T5QDO26S.js";var a=class extends p{static title="Restore server backup";static key="world_backups_count";static properties={type:{state:!0},file:{state:!0}};constructor(){super(),this.type="world",this.file=""}selectedChanged(){this.file=""}render(){let e=this.stateFor(`${this.type}_backups_count`)||(this.type==="world"?this.state:null),r=(e?.attributes[`${this.type}_backups_list`]||[]).map(l);return this.frame(t`${this.selectInput("Backup type",this.type,["world","allowlist","properties","permissions"],s=>{this.type=s,this.file=""})}${this.selectInput("Backup file",this.file,[{value:"",label:"Select backup"},...r],s=>this.file=s)}${i(e)?t`<p class="muted">This backup list is unavailable.</p>`:r.length?"":t`<p class="muted">No backups of this type.</p>`}
        <div class="actions">
          <button
            ?disabled=${this.busy||!this.available||i(e)||!this.file}
            @click=${()=>this.action("restore_backup",{restore_type:this.type,backup_file:this.file},"Request accepted.",{confirm:"Restoring replaces current server data. Continue?"})}
          >
            Restore selected backup</button
          >${this.button("Restore latest backups","restore_latest_all",{},{message:"Request accepted.",confirm:"Restore the latest world and configuration backups, replacing current data?"})}
        </div>`)}};c("bsm-restore-card",a,"BSM Restore","Restore selected or latest backups with task feedback.");
