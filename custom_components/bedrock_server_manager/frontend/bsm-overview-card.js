import{a as l,c as d,d as u,g as n,j as _,k as g}from"./shared-EVDKEACZ.js";var p=class extends g{static title="Bedrock Server Manager";static properties={layout:{state:!0},operations:{state:!0},cardFeedback:{state:!0}};constructor(){super(),this.layout="cards",this.operations=new Map,this.cardFeedback=""}static getConfigForm(){let t=super.getConfigForm();return t.schema=t.schema.filter(s=>s.name!=="entity"),t.schema.push({name:"layout",selector:{select:{options:["cards","table"]}}},{name:"sort",selector:{select:{options:["name","status","players"]}}},{name:"monitor_path",selector:{text:{}}},{name:"settings_path",selector:{text:{}}},{name:"entities",selector:{entity:{integration:"bedrock_server_manager",domain:"sensor",multiple:!0}}}),t}value(t,s){let a=this.hass.states[u(this.hass,t,s)];return l(a)?"\u2014":`${a.state}${a.attributes.unit_of_measurement?` ${a.attributes.unit_of_measurement}`:""}`}navigate(t,s="monitor"){let a=this.config[`${s}_paths`]?.[t]||this.config[`${s}_path`];if(typeof a=="string"&&a.startsWith("/")&&!a.startsWith("//")){let e=a.replaceAll("{server}",encodeURIComponent(this.hass.states[t]?.attributes.bsm_server_name||""));history.pushState(null,"",e),window.dispatchEvent(new CustomEvent("location-changed"))}else this.moreInfo(t)}async control(t,s,a={},e=!1){if(this.operations.has(t)||l(this.hass.states[t])||this.hass?.connected===!1)return;if(s==="restart_server"&&!e){this.confirmation={server:t,service:s,data:a};return}let r=this._generation;this.error="",this.cardFeedback="",this.operations=new Map(this.operations).set(t,{message:"Sending request\u2026"});try{if(s==="start"||s==="stop"){let i=u(this.hass,t,"server_control");if(!i||l(this.hass.states[i]))throw Error("Server control is unavailable.");await this.hass.callService("switch",s==="start"?"turn_on":"turn_off",{},{entity_id:i}),r===this._generation&&(this.operations=new Map(this.operations),this.operations.delete(t),this.cardFeedback="Request sent. Waiting for confirmed server state.")}else{let i=await this.responseService(s,a,{entity_id:t});if(r!==this._generation)return;let o=!1;for(let c of i.results||[])if(c.result?.task_id){o=!0;let m=`${c.manager_url}:${c.result.task_id}`,h=this.runtime.tasks.get(m)||{id:c.result.task_id,manager_url:c.manager_url,status:"queued",message:"Waiting for task outcome"};this.operations=new Map(this.operations).set(t,{key:m,task:h,message:h.message}),this._watchTask({target:{entity_id:t},task:h}),["completed","failed","cancelled"].includes(h.status)&&this._taskUpdate(h)}o||(this.operations=new Map(this.operations),this.operations.delete(t),this.cardFeedback=i.results?.[0]?.result?.message||"Request acknowledged.")}}catch(i){r===this._generation&&(this.operations=new Map(this.operations),this.operations.delete(t),this.error=i.message||String(i))}}_taskUpdate(t){for(let[s,a]of this.operations)a.key===`${t.manager_url}:${t.id}`&&(this.operations=new Map(this.operations),["completed","failed","cancelled"].includes(t.status)?(this.operations.delete(s),this.cardFeedback=t.message,t.error&&(this.error=t.error.message)):this.operations.set(s,{...a,task:t,message:t.message}));this.operations.size||this._releaseTaskWatchers(),this.requestUpdate()}reconnected(){super.reconnected();for(let[t,s]of this.operations)s.task&&this._watchTask({target:{entity_id:t},task:s.task})}frame(t,s){let a=this.confirmation;return super.frame(n`${t}${this.cardFeedback?n`<small role="status">${this.cardFeedback}</small>`:""}${a?n`<section class="confirm">
              <p>Restart this server and disconnect its players?</p>
              <button
                @click=${()=>{this.confirmation=null,this.control(a.server,a.service,a.data,!0)}}
              >
                Confirm</button
              ><button @click=${()=>this.confirmation=null}>
                Cancel
              </button>
            </section>`:""}`,{...s,confirmationControls:!1})}controls(t,s){let a=u(this.hass,t,"server_control"),e=s.state.toUpperCase()==="RUNNING",r=this.operations.has(t)||l(s)||this.hass?.connected===!1;return n`<div class="actions">
      ${a?n`<button ?disabled=${r||l(this.hass.states[a])} @click=${()=>this.control(t,e?"stop":"start")}>${e?"Stop":"Start"}</button>`:""}<button
        ?disabled=${r}
        @click=${()=>this.control(t,"update_server")}
      >
        Update
      </button>
      <details>
        <summary>More actions</summary>
        ${this.config.settings_path||this.config.settings_paths?.[t]?n`<button @click=${()=>this.navigate(t,"settings")}>Settings</button>`:""}
        <button
          ?disabled=${r}
          @click=${()=>this.control(t,"restart_server")}
        >
          Restart</button
        ><button
          ?disabled=${r}
          @click=${()=>{this.control(t,"trigger_backup",{backup_type:"all"})}}
        >
          Backup</button
        ><button @click=${()=>this.moreInfo(t)}>Details</button>${["level_name","server_permissions_count","allowlist_count"].map(i=>{let o=u(this.hass,t,i);return o?n`<button @click=${()=>this.moreInfo(o)}>
                ${{level_name:"Properties",server_permissions_count:"Permissions",allowlist_count:"Allowlist"}[i]}
              </button>`:""})}
      </details>
    </div>`}render(){let t=d(this.hass,"server","status").filter(([e])=>!this.config.entities?.length||this.config.entities.includes(e));t.sort(([e,r],[i,o])=>this.config.sort==="status"?r.state.localeCompare(o.state):this.config.sort==="players"?Number(this.value(i,"online_players_count"))-Number(this.value(e,"online_players_count")):(r.attributes.bsm_server_name||e).localeCompare(o.attributes.bsm_server_name||i));let s=t.filter(([,e])=>e.state.toUpperCase()==="RUNNING").length,a=this.config.layout==="table";return this.frame(n`<div class="heading">
          <small>${t.length} servers · ${s} running</small>
        </div>
        ${a?n`<div class="scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Server</th>
                      <th>Status</th>
                      <th>Players</th>
                      <th>CPU</th>
                      <th>RAM</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${t.map(([e,r])=>n`<tr>
                          <td>
                            <button @click=${()=>this.navigate(e)}>
                              ${r.attributes.bsm_server_name||r.attributes.friendly_name}
                            </button>
                          </td>
                          <td>${r.state}</td>
                          <td>${this.value(e,"online_players_count")}</td>
                          <td>${this.value(e,"cpu_percent")}</td>
                          <td>${this.value(e,"memory_mb")}</td>
                          <td>${this.controls(e,r)}</td>
                        </tr>`)}
                  </tbody>
                </table>
              </div>`:n`<div class="grid">
                ${t.map(([e,r])=>n`<section class="tile">
                      <div class="heading">
                        <button @click=${()=>this.navigate(e)}>
                          ${r.attributes.bsm_server_name||r.attributes.friendly_name}</button
                        ><small
                          >${l(r)?"Unavailable":r.state}</small
                        >
                      </div>
                      <small
                        >${r.attributes.installed_version||"Version unknown"}</small
                      >
                      <div class="grid">
                        <span
                          >Players
                          ${this.value(e,"online_players_count")}</span
                        ><span>CPU ${this.value(e,"cpu_percent")}</span
                        ><span>RAM ${this.value(e,"memory_mb")}</span>
                      </div>
                      ${this.controls(e,r)}
                      ${this.operations.get(e)?.message?n`<small role="status">${this.operations.get(e).message}</small>`:""}
                    </section>`)}
              </div>`}${t.length?"":n`<p>No selected servers are available.</p>`}`,{picker:!1})}};_("bsm-overview-card",p,"BSM Overview","Fleet cards or table with start, stop, update and quick actions.");
