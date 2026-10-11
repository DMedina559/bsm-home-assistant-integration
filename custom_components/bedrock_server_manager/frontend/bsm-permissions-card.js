import{g as s,j as a,k as r}from"./shared-EVDKEACZ.js";var i=class extends r{static title="Server permissions";static key="server_permissions_count";static properties={playerName:{state:!0},xuid:{state:!0}};static getConfigForm(){let t=super.getConfigForm();return t.schema.push({name:"global_players_entity",selector:{entity:{integration:"bedrock_server_manager",domain:"sensor"}}}),t}constructor(){super(),this.playerName="",this.xuid=""}syncState(){this.available&&(this.draft.update(Object.fromEntries((this.state.attributes.server_permissions||[]).map(t=>[t.xuid,t]))),this.requestUpdate())}selectedChanged(){this.playerName="",this.xuid="",this.syncState()}add(){if(!this.playerName.trim()||!/^\d{16,19}$/.test(this.xuid)){this.error="Enter a player name and a 16\u201319 digit XUID.";return}this.draft.set(this.xuid,{name:this.playerName.trim(),xuid:this.xuid,permission_level:"member"}),this.playerName="",this.xuid="",this.requestUpdate()}choosePlayer(t){let e=this.knownPlayers().find(n=>n.xuid===t);e&&(this.playerName=e.name,this.xuid=e.xuid)}async save(){this.draft.conflicts.length||await this.action("set_permissions",{permissions:Object.values(this.draft.value)},"Permissions saved.")&&(this.draft.reset(this.draft.live),this.requestUpdate())}render(){return this.frame(s`${this.editNotice()}
        <div class="scroll">
          <table>
            <thead>
              <tr>
                <th>Player</th>
                <th>Permission</th>
              </tr>
            </thead>
            <tbody>
              ${Object.values(this.draft.value).map(t=>s`<tr>
                    <td>${t.name||t.xuid}</td>
                    <td>
                      ${this.selectInput(`Permission for ${t.name||t.xuid}`,t.permission_level,["visitor","member","operator"],e=>{this.draft.set(t.xuid,{...t,permission_level:e}),this.requestUpdate()})}
                    </td>
                  </tr>`)}
            </tbody>
          </table>
        </div>
        ${this.knownPlayers().length?this.selectInput("Known player","",[{value:"",label:"Choose known player"},...this.knownPlayers().map(t=>({value:t.xuid,label:t.name||t.xuid}))],t=>this.choosePlayer(t)):""}
        <div class="grid">
          ${this.input("Player name",this.playerName,t=>this.playerName=t)}${this.input("XUID",this.xuid,t=>this.xuid=t)}
        </div>
        <div class="actions">
          <button ?disabled=${this.busy||!this.available} @click=${this.add}>
            Stage player</button
          ><button
            class="primary"
            ?disabled=${!this.available||this.busy||!this.draft.dirty||this.draft.conflicts.length>0}
            @click=${this.save}
          >
            Save permissions
          </button>
        </div>`)}};a("bsm-permissions-card",i,"BSM Permissions","Stage and save player permissions without losing live edits.");
