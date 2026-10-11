import{a as l,c as f,d as h,g as n,j as g,k as _}from"./shared-7UTSRN4G.js";var p=class extends _{static title="Bedrock Server Manager";static properties={layout:{state:!0},operations:{state:!0},cardFeedback:{state:!0}};ports(t){let r=this.hass?.states?.[h(this.hass,t,"level_name")];if(l(r))return"Unavailable";let s=r.attributes.server_properties||{};return[["IPv4",s["server-port"]],["IPv6",s["server-portv6"]]].filter(([,e])=>e!=null&&String(e).trim()!=="").map(([e,a])=>`${e} ${a}`).join(" \xB7 ")||"Unavailable"}constructor(){super(),this.layout="cards",this.operations=new Map,this.cardFeedback=""}static getConfigForm(){let t=super.getConfigForm();return t.schema=t.schema.filter(r=>r.name!=="entity"),t.schema.push({name:"layout",selector:{select:{options:["cards","table"]}}},{name:"sort",selector:{select:{options:["name","status","players"]}}},{name:"monitor_path",selector:{text:{}}},{name:"settings_path",selector:{text:{}}},{name:"entities",selector:{entity:{integration:"bedrock_server_manager",domain:"sensor",multiple:!0}}}),t}value(t,r){let s=this.hass.states[h(this.hass,t,r)];return l(s)?"\u2014":`${s.state}${s.attributes.unit_of_measurement?` ${s.attributes.unit_of_measurement}`:""}`}navigate(t,r="monitor"){let s=this.config[`${r}_paths`]?.[t]||this.config[`${r}_path`];if(typeof s=="string"&&s.startsWith("/")&&!s.startsWith("//")){let e=s.replaceAll("{server}",encodeURIComponent(this.hass.states[t]?.attributes.bsm_server_name||""));history.pushState(null,"",e),window.dispatchEvent(new CustomEvent("location-changed"))}else this.moreInfo(t)}async control(t,r,s={},e=!1){if(this.operations.has(t)||l(this.hass.states[t])||this.hass?.connected===!1)return;if(r==="restart_server"&&!e){this.confirmation={server:t,service:r,data:s};return}let a=this._generation;this.error="",this.cardFeedback="",this.operations=new Map(this.operations).set(t,{message:"Sending request\u2026"});try{if(r==="start"||r==="stop"){let i=h(this.hass,t,"server_control");if(!i||l(this.hass.states[i]))throw Error("Server control is unavailable.");await this.hass.callService("switch",r==="start"?"turn_on":"turn_off",{},{entity_id:i}),a===this._generation&&(this.operations=new Map(this.operations),this.operations.delete(t),this.cardFeedback="Request sent. Waiting for confirmed server state.")}else{let i=await this.responseService(r,s,{entity_id:t});if(a!==this._generation)return;let o=i.results?.find(c=>c.error);if(o)throw Error(o.error.message);let m=!1;for(let c of i.results||[])if(c.result?.task_id){m=!0;let d=`${c.manager_url}:${c.result.task_id}`,u=this.runtime.tasks.get(d)||{id:c.result.task_id,manager_url:c.manager_url,status:"queued",message:"Waiting for task outcome"};this.operations=new Map(this.operations).set(t,{key:d,task:u,message:u.message}),this._watchTask({target:{entity_id:t},task:u}),["completed","failed","cancelled"].includes(u.status)&&this._taskUpdate(u)}m||(this.operations=new Map(this.operations),this.operations.delete(t),this.cardFeedback=i.results?.[0]?.result?.message||"Request acknowledged.")}}catch(i){a===this._generation&&(this.operations=new Map(this.operations),this.operations.delete(t),this.error=i.message||String(i))}}_taskUpdate(t){for(let[r,s]of this.operations)s.key===`${t.manager_url}:${t.id}`&&(this.operations=new Map(this.operations),["completed","failed","cancelled"].includes(t.status)?(this.operations.delete(r),this.cardFeedback=t.message,t.error&&(this.error=t.error.message)):this.operations.set(r,{...s,task:t,message:t.message}));this.operations.size||this._releaseTaskWatchers(),this.requestUpdate()}reconnected(){super.reconnected(),this.operations=new Map(this.operations);for(let[t,r]of this.operations)if(r.task){let s=this.runtime.tasks.get(r.key);s&&this._taskUpdate(s),this.operations.has(t)&&this._watchTask({target:{entity_id:t},task:r.task})}else this.operations.delete(t),this.cardFeedback="Connection changed during the request. Check current server or task state before retrying."}frame(t,r){let s=this.confirmation;return super.frame(n`${t}${this.cardFeedback?n`<small role="status">${this.cardFeedback}</small>`:""}${s?n`<section class="confirm">
              <p>Restart this server and disconnect its players?</p>
              <button
                @click=${()=>{this.confirmation=null,this.control(s.server,s.service,s.data,!0)}}
              >
                Confirm</button
              ><button @click=${()=>this.confirmation=null}>
                Cancel
              </button>
            </section>`:""}`,{...r,confirmationControls:!1})}controls(t,r){let s=h(this.hass,t,"server_control"),e=r.state.toUpperCase()==="RUNNING",a=this.operations.has(t)||l(r)||this.hass?.connected===!1;return n`<div class="actions">
      ${s?n`<button ?disabled=${a||l(this.hass.states[s])} @click=${()=>this.control(t,e?"stop":"start")}>${e?"Stop":"Start"}</button>`:""}<button
        ?disabled=${a}
        @click=${()=>this.control(t,"update_server")}
      >
        Update
      </button>
      <details>
        <summary>More actions</summary>
        ${this.config.settings_path||this.config.settings_paths?.[t]?n`<button @click=${()=>this.navigate(t,"settings")}>Settings</button>`:""}
        <button
          ?disabled=${a}
          @click=${()=>this.control(t,"restart_server")}
        >
          Restart</button
        ><button
          ?disabled=${a}
          @click=${()=>{this.control(t,"trigger_backup",{backup_type:"all"})}}
        >
          Backup</button
        ><button @click=${()=>this.moreInfo(t)}>Details</button>${["level_name","server_permissions_count","allowlist_count"].map(i=>{let o=h(this.hass,t,i);return o?n`<button @click=${()=>this.moreInfo(o)}>
                ${{level_name:"Properties",server_permissions_count:"Permissions",allowlist_count:"Allowlist"}[i]}
              </button>`:""})}
      </details>
    </div>`}render(){let t=f(this.hass,"server","status").filter(([e])=>!this.config.entities?.length||this.config.entities.includes(e));t.sort(([e,a],[i,o])=>this.config.sort==="status"?a.state.localeCompare(o.state):this.config.sort==="players"?Number(this.value(i,"online_players_count"))-Number(this.value(e,"online_players_count")):(a.attributes.bsm_server_name||e).localeCompare(o.attributes.bsm_server_name||i));let r=t.filter(([,e])=>e.state.toUpperCase()==="RUNNING").length,s=this.config.layout==="table";return this.frame(n`<div class="heading">
          <small>${t.length} servers · ${r} running</small>
        </div>
        ${s?n`<div class="scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Server</th>
                      <th>Status</th>
                      <th>Ports</th>
                      <th>Players</th>
                      <th>CPU</th>
                      <th>RAM</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${t.map(([e,a])=>n`<tr>
                          <td>
                            <button @click=${()=>this.navigate(e)}>
                              ${a.attributes.bsm_server_name||a.attributes.friendly_name}
                            </button>
                          </td>
                          <td>${a.state}</td>
                          <td>${this.ports(e)}</td>
                          <td>${this.value(e,"online_players_count")}</td>
                          <td>${this.value(e,"cpu_percent")}</td>
                          <td>${this.value(e,"memory_mb")}</td>
                          <td>${this.controls(e,a)}</td>
                        </tr>`)}
                  </tbody>
                </table>
              </div>`:n`<div class="grid">
                ${t.map(([e,a])=>n`<section class="tile">
                      <div class="heading">
                        <button @click=${()=>this.navigate(e)}>
                          ${a.attributes.bsm_server_name||a.attributes.friendly_name}</button
                        ><small
                          >${l(a)?"Unavailable":a.state}</small
                        >
                      </div>
                      <small
                        >${a.attributes.installed_version||"Version unknown"}</small
                      >
                      <small>Ports: ${this.ports(e)}</small>
                      <div class="grid">
                        <span
                          >Players
                          ${this.value(e,"online_players_count")}</span
                        ><span>CPU ${this.value(e,"cpu_percent")}</span
                        ><span>RAM ${this.value(e,"memory_mb")}</span>
                      </div>
                      ${this.controls(e,a)}
                      ${this.operations.get(e)?.message?n`<small role="status">${this.operations.get(e).message}</small>`:""}
                    </section>`)}
              </div>`}${t.length?"":n`<p>No selected servers are available.</p>`}`,{picker:!1})}};g("bsm-overview-card",p,"BSM Overview","Fleet cards or table with start, stop, update and quick actions.");
