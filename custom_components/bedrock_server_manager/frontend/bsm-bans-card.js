import{g as s,j as i,k as r}from"./shared-7UTSRN4G.js";var a=class extends r{static key="server_bans_count";static title="Server bans";static properties={player:{state:!0},xuid:{state:!0},reason:{state:!0}};constructor(){super(),this.player="",this.xuid="",this.reason=""}selectedChanged(){this.player="",this.xuid="",this.reason=""}render(){return this.frame(s`<div class="scroll">
          <table>
            <thead>
              <tr>
                <th>Player</th>
                <th>Reason</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${(this.state?.attributes.server_bans||[]).map(t=>s`<tr>
                    <td>${t.player_name||t.name||t.xuid}</td>
                    <td>${t.reason||"\u2014"}</td>
                    <td>
                      ${this.button("Remove ban","remove_server_ban",{xuid:t.xuid},{confirm:`Remove ban for ${t.player_name||t.name||t.xuid}?`})}
                    </td>
                  </tr>`)}
            </tbody>
          </table>
        </div>
        ${this.selectInput("Known player","",[{value:"",label:"Choose player"},...this.knownPlayers().map(t=>({value:t.xuid,label:t.name||t.xuid}))],t=>{let e=this.knownPlayers().find(n=>n.xuid===t);e&&(this.player=e.name,this.xuid=e.xuid)})}
        <div class="grid">
          ${this.input("Player name",this.player,t=>this.player=t)}${this.input("XUID",this.xuid,t=>this.xuid=t)}${this.input("Reason",this.reason,t=>this.reason=t)}
        </div>
        <button
          ?disabled=${this.busy||!this.available||!this.player.trim()||!/^\d{16,19}$/.test(this.xuid)}
          @click=${()=>this.action("add_server_ban",{player_name:this.player.trim(),xuid:this.xuid,reason:this.reason},"Ban saved.",{confirm:`Ban ${this.player}?`})}
        >
          Ban player
        </button>`)}};i("bsm-bans-card",a,"BSM Bans","Manage server bans using known players and confirmed actions.");
