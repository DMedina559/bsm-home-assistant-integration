import{g as e,j as l,k as s}from"./shared-7UTSRN4G.js";var i=class extends s{static title="Server allowlist";static key="allowlist_count";static properties={player:{state:!0},ignoreLimit:{state:!0}};constructor(){super(),this.player="",this.ignoreLimit=!1}selectedChanged(){this.player=""}async add(){this.player.trim()&&await this.action("add_to_allowlist",{players:[this.player.trim()],ignores_player_limit:this.ignoreLimit},"Player added.")&&(this.player="")}render(){let a=this.state?.attributes.allowed_players||[];return this.frame(e`<div class="scroll">
          <table>
            <thead>
              <tr>
                <th>Player</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${a.map(t=>e`<tr>
                    <td>${t}</td>
                    <td>
                      ${this.button("Remove","remove_from_allowlist",{players:[t]},{confirm:`Remove ${t} from the allowlist?`})}
                    </td>
                  </tr>`)}
            </tbody>
          </table>
        </div>
        ${this.available&&!a.length?e`<p class="muted">The allowlist is empty.</p>`:""}${this.input("Player name",this.player,t=>this.player=t)}<label
          class="row"
          ><input
            type="checkbox"
            style="width:auto"
            .checked=${this.ignoreLimit}
            ?disabled=${this.busy}
            @change=${t=>this.ignoreLimit=t.target.checked}
          />Ignore player limit</label
        ><button
          ?disabled=${!this.available||this.busy||!this.player.trim()}
          @click=${this.add}
        >
          Add player
        </button>`)}};l("bsm-allowlist-card",i,"BSM Allowlist","Manage players allowed on a server.");
