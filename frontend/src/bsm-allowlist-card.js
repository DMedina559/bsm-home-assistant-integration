import { BsmCard, html, register } from "./base.js";
class AllowlistCard extends BsmCard {
  static title = "Server allowlist";
  static key = "allowlist_count";
  static properties = { player: { state: true }, ignoreLimit: { state: true } };
  constructor() {
    super();
    this.player = "";
    this.ignoreLimit = false;
  }
  selectedChanged() {
    this.player = "";
  }
  async add() {
    if (!this.player.trim()) return;
    if (
      await this.action(
        "add_to_allowlist",
        {
          players: [this.player.trim()],
          ignores_player_limit: this.ignoreLimit,
        },
        "Player added.",
      )
    )
      this.player = "";
  }
  render() {
    const players = this.state?.attributes.allowed_players || [];
    return this.frame(
      html`<div class="scroll">
          <table>
            <thead>
              <tr>
                <th>Player</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${players.map(
                (player) =>
                  html`<tr>
                    <td>${player}</td>
                    <td>
                      ${this.button("Remove", "remove_from_allowlist", { players: [player] }, { confirm: `Remove ${player} from the allowlist?` })}
                    </td>
                  </tr>`,
              )}
            </tbody>
          </table>
        </div>
        ${this.available && !players.length ? html`<p class="muted">The allowlist is empty.</p>` : ""}${this.input("Player name", this.player, (v) => (this.player = v))}<label
          class="row"
          ><input
            type="checkbox"
            style="width:auto"
            .checked=${this.ignoreLimit}
            ?disabled=${this.busy}
            @change=${(e) => (this.ignoreLimit = e.target.checked)}
          />Ignore player limit</label
        ><button
          ?disabled=${!this.available || this.busy || !this.player.trim()}
          @click=${this.add}
        >
          Add player
        </button>`,
    );
  }
}
register(
  "bsm-allowlist-card",
  AllowlistCard,
  "BSM Allowlist",
  "Manage players allowed on a server.",
);
