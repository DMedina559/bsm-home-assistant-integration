import{a as n,b as i,d as h,e as o,j as m,k as d}from"./shared-5SVUCQ5X.js";var l=class extends d{static title="Bedrock Server Manager";static properties={layout:{state:!0}};constructor(){super(),this.layout="cards"}static getConfigForm(){let t=super.getConfigForm();return t.schema=t.schema.filter(a=>a.name!=="entity"),t.schema.push({name:"layout",selector:{select:{options:["cards","table"]}}},{name:"entities",selector:{entity:{integration:"bedrock_server_manager",domain:"sensor",multiple:!0}}}),t}value(t,a){let r=this.hass.states[o(this.hass,t,a)];return i(r)?"\u2014":`${r.state}${r.attributes.unit_of_measurement?` ${r.attributes.unit_of_measurement}`:""}`}async control(t,a){this.busy||(this.select(t),await this.action(a,{},"Request accepted.",a==="restart_server"?{confirm:"Restart this server and disconnect its players?"}:{}))}controls(t,a){let r=o(this.hass,t,"server_control"),e=a.state.toUpperCase()==="RUNNING",s=this.busy||i(a);return n`<div class="actions">
      ${r?n`<button ?disabled=${s||i(this.hass.states[r])} @click=${()=>this.nativeAction("switch",e?"turn_off":"turn_on",r)}>${e?"Stop":"Start"}</button>`:""}<button
        ?disabled=${s}
        @click=${()=>this.control(t,"update_server")}
      >
        Update
      </button>
      <details>
        <summary>More actions</summary>
        <button
          ?disabled=${s}
          @click=${()=>this.control(t,"restart_server")}
        >
          Restart</button
        ><button
          ?disabled=${s}
          @click=${()=>{this.select(t),this.action("trigger_backup",{backup_type:"all"})}}
        >
          Backup</button
        ><button @click=${()=>this.moreInfo(t)}>Details</button>${["level_name","server_permissions_count","allowlist_count"].map(c=>{let u=o(this.hass,t,c);return u?n`<button @click=${()=>this.moreInfo(u)}>
                ${{level_name:"Properties",server_permissions_count:"Permissions",allowlist_count:"Allowlist"}[c]}
              </button>`:""})}
      </details>
    </div>`}render(){let t=h(this.hass,"server","status").filter(([e])=>!this.config.entities?.length||this.config.entities.includes(e)),a=t.filter(([,e])=>e.state.toUpperCase()==="RUNNING").length,r=this.config.layout==="table";return this.frame(n`<div class="heading">
          <small>${t.length} servers · ${a} running</small>
        </div>
        ${r?n`<div class="scroll">
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
                    ${t.map(([e,s])=>n`<tr>
                          <td>
                            <button @click=${()=>this.moreInfo(e)}>
                              ${s.attributes.bsm_server_name||s.attributes.friendly_name}
                            </button>
                          </td>
                          <td>${s.state}</td>
                          <td>${this.value(e,"online_players_count")}</td>
                          <td>${this.value(e,"cpu_percent")}</td>
                          <td>${this.value(e,"memory_mb")}</td>
                          <td>${this.controls(e,s)}</td>
                        </tr>`)}
                  </tbody>
                </table>
              </div>`:n`<div class="grid">
                ${t.map(([e,s])=>n`<section class="tile">
                      <div class="heading">
                        <button @click=${()=>this.moreInfo(e)}>
                          ${s.attributes.bsm_server_name||s.attributes.friendly_name}</button
                        ><small
                          >${i(s)?"Unavailable":s.state}</small
                        >
                      </div>
                      <small
                        >${s.attributes.installed_version||"Version unknown"}</small
                      >
                      <div class="grid">
                        <span
                          >Players
                          ${this.value(e,"online_players_count")}</span
                        ><span>CPU ${this.value(e,"cpu_percent")}</span
                        ><span>RAM ${this.value(e,"memory_mb")}</span>
                      </div>
                      ${this.controls(e,s)}
                    </section>`)}
              </div>`}${t.length?"":n`<p>No selected servers are available.</p>`}`,{picker:!1})}};m("bsm-overview-card",l,"BSM Overview","Fleet cards or table with start, stop, update and quick actions.");
