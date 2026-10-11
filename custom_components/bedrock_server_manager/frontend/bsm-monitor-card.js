import{a as e,b as r,e as o,h as a,i}from"./shared-KN4AH6WE.js";var s=class extends i{static title="Server monitor";static getConfigForm(){let t=super.getConfigForm();return t.schema.push({name:"history_hours",selector:{number:{min:1,max:168,mode:"box"}}}),t}render(){let t=o(this.hass,this.selection,"server_control");return this.frame(e`<div class="grid">
          ${["status","online_players_count","cpu_percent","memory_mb","uptime_seconds"].map(n=>this.metric(this.stateFor(n)))}
        </div>
        <div class="actions">
          ${t?e`<button ?disabled=${this.busy||r(this.hass.states[t])} @click=${()=>this.nativeAction("switch",this.hass.states[t].state==="on"?"turn_off":"turn_on",t)}>${this.hass.states[t].state==="on"?"Stop":"Start"}</button>`:""}${this.button("Update server","update_server",{},{message:"Update request accepted."})}${this.button("Restart","restart_server",{},{message:"Restart requested.",confirm:"Restart this server and disconnect its players?"})}${this.button("Backup","trigger_backup",{backup_type:"all"},{message:"Request accepted."})}
        </div>
        ${this.entityControl("target_version")}${this.entityControl("autostart")}${this.entityControl("autoupdate")}${this.history(["cpu_percent","memory_mb","online_players_count"])}`)}};a("bsm-monitor-card",s,"BSM Server Monitor","Server controls, metrics and Home Assistant recorder graphs.");
