import{a as c,c as g,d as u,g as n,j as f,k as _}from"./shared-7UTSRN4G.js";var p=class extends _{static title="Bedrock Server Manager";static properties={layout:{state:!0},operations:{state:!0},cardFeedback:{state:!0}};constructor(){super(),this.layout="cards",this.operations=new Map,this.cardFeedback=""}static getConfigForm(){let t=super.getConfigForm();return t.schema=t.schema.filter(a=>a.name!=="entity"),t.schema.push({name:"layout",selector:{select:{options:["cards","table"]}}},{name:"sort",selector:{select:{options:["name","status","players"]}}},{name:"monitor_path",selector:{text:{}}},{name:"settings_path",selector:{text:{}}},{name:"entities",selector:{entity:{integration:"bedrock_server_manager",domain:"sensor",multiple:!0}}}),t}value(t,a){let e=this.hass.states[u(this.hass,t,a)];return c(e)?"\u2014":`${e.state}${e.attributes.unit_of_measurement?` ${e.attributes.unit_of_measurement}`:""}`}navigate(t,a="monitor"){let e=this.config[`${a}_paths`]?.[t]||this.config[`${a}_path`];if(typeof e=="string"&&e.startsWith("/")&&!e.startsWith("//")){let s=e.replaceAll("{server}",encodeURIComponent(this.hass.states[t]?.attributes.bsm_server_name||""));history.pushState(null,"",s),window.dispatchEvent(new CustomEvent("location-changed"))}else this.moreInfo(t)}async control(t,a,e={},s=!1){if(this.operations.has(t)||c(this.hass.states[t])||this.hass?.connected===!1)return;if(a==="restart_server"&&!s){this.confirmation={server:t,service:a,data:e};return}let r=this._generation;this.error="",this.cardFeedback="",this.operations=new Map(this.operations).set(t,{message:"Sending request\u2026"});try{if(a==="start"||a==="stop"){let i=u(this.hass,t,"server_control");if(!i||c(this.hass.states[i]))throw Error("Server control is unavailable.");await this.hass.callService("switch",a==="start"?"turn_on":"turn_off",{},{entity_id:i}),r===this._generation&&(this.operations=new Map(this.operations),this.operations.delete(t),this.cardFeedback="Request sent. Waiting for confirmed server state.")}else{let i=await this.responseService(a,e,{entity_id:t});if(r!==this._generation)return;let o=i.results?.find(l=>l.error);if(o)throw Error(o.error.message);let m=!1;for(let l of i.results||[])if(l.result?.task_id){m=!0;let d=`${l.manager_url}:${l.result.task_id}`,h=this.runtime.tasks.get(d)||{id:l.result.task_id,manager_url:l.manager_url,status:"queued",message:"Waiting for task outcome"};this.operations=new Map(this.operations).set(t,{key:d,task:h,message:h.message}),this._watchTask({target:{entity_id:t},task:h}),["completed","failed","cancelled"].includes(h.status)&&this._taskUpdate(h)}m||(this.operations=new Map(this.operations),this.operations.delete(t),this.cardFeedback=i.results?.[0]?.result?.message||"Request acknowledged.")}}catch(i){r===this._generation&&(this.operations=new Map(this.operations),this.operations.delete(t),this.error=i.message||String(i))}}_taskUpdate(t){for(let[a,e]of this.operations)e.key===`${t.manager_url}:${t.id}`&&(this.operations=new Map(this.operations),["completed","failed","cancelled"].includes(t.status)?(this.operations.delete(a),this.cardFeedback=t.message,t.error&&(this.error=t.error.message)):this.operations.set(a,{...e,task:t,message:t.message}));this.operations.size||this._releaseTaskWatchers(),this.requestUpdate()}reconnected(){super.reconnected(),this.operations=new Map(this.operations);for(let[t,a]of this.operations)if(a.task){let e=this.runtime.tasks.get(a.key);e&&this._taskUpdate(e),this.operations.has(t)&&this._watchTask({target:{entity_id:t},task:a.task})}else this.operations.delete(t),this.cardFeedback="Connection changed during the request. Check current server or task state before retrying."}frame(t,a){let e=this.confirmation;return super.frame(n`${t}${this.cardFeedback?n`<small role="status">${this.cardFeedback}</small>`:""}${e?n`<section class="confirm">
              <p>Restart this server and disconnect its players?</p>
              <button
                @click=${()=>{this.confirmation=null,this.control(e.server,e.service,e.data,!0)}}
              >
                Confirm</button
              ><button @click=${()=>this.confirmation=null}>
                Cancel
              </button>
            </section>`:""}`,{...a,confirmationControls:!1})}controls(t,a){let e=u(this.hass,t,"server_control"),s=a.state.toUpperCase()==="RUNNING",r=this.operations.has(t)||c(a)||this.hass?.connected===!1;return n`<div class="actions">
      ${e?n`<button ?disabled=${r||c(this.hass.states[e])} @click=${()=>this.control(t,s?"stop":"start")}>${s?"Stop":"Start"}</button>`:""}<button
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
    </div>`}render(){let t=g(this.hass,"server","status").filter(([s])=>!this.config.entities?.length||this.config.entities.includes(s));t.sort(([s,r],[i,o])=>this.config.sort==="status"?r.state.localeCompare(o.state):this.config.sort==="players"?Number(this.value(i,"online_players_count"))-Number(this.value(s,"online_players_count")):(r.attributes.bsm_server_name||s).localeCompare(o.attributes.bsm_server_name||i));let a=t.filter(([,s])=>s.state.toUpperCase()==="RUNNING").length,e=this.config.layout==="table";return this.frame(n`<div class="heading">
          <small>${t.length} servers · ${a} running</small>
        </div>
        ${e?n`<div class="scroll">
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
                    ${t.map(([s,r])=>n`<tr>
                          <td>
                            <button @click=${()=>this.navigate(s)}>
                              ${r.attributes.bsm_server_name||r.attributes.friendly_name}
                            </button>
                          </td>
                          <td>${r.state}</td>
                          <td>${this.value(s,"online_players_count")}</td>
                          <td>${this.value(s,"cpu_percent")}</td>
                          <td>${this.value(s,"memory_mb")}</td>
                          <td>${this.controls(s,r)}</td>
                        </tr>`)}
                  </tbody>
                </table>
              </div>`:n`<div class="grid">
                ${t.map(([s,r])=>n`<section class="tile">
                      <div class="heading">
                        <button @click=${()=>this.navigate(s)}>
                          ${r.attributes.bsm_server_name||r.attributes.friendly_name}</button
                        ><small
                          >${c(r)?"Unavailable":r.state}</small
                        >
                      </div>
                      <small
                        >${r.attributes.installed_version||"Version unknown"}</small
                      >
                      <div class="grid">
                        <span
                          >Players
                          ${this.value(s,"online_players_count")}</span
                        ><span>CPU ${this.value(s,"cpu_percent")}</span
                        ><span>RAM ${this.value(s,"memory_mb")}</span>
                      </div>
                      ${this.controls(s,r)}
                      ${this.operations.get(s)?.message?n`<small role="status">${this.operations.get(s).message}</small>`:""}
                    </section>`)}
              </div>`}${t.length?"":n`<p>No selected servers are available.</p>`}`,{picker:!1})}};f("bsm-overview-card",p,"BSM Overview","Fleet cards or table with start, stop, update and quick actions.");
