import { BsmCard, html, register } from "./base.js";
class BansCard extends BsmCard {
  static key = "server_bans_count";
  static title = "Server bans";
  static properties = {
    player: { state: true },
    xuid: { state: true },
    reason: { state: true },
  };
  constructor() {
    super();
    this.player = "";
    this.xuid = "";
    this.reason = "";
  }
  selectedChanged() {
    this.player = "";
    this.xuid = "";
    this.reason = "";
  }
  render() {
    return this.frame(
      html`<div class="scroll">
          <table>
            <thead>
              <tr>
                <th>Player</th>
                <th>Reason</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${(this.state?.attributes.server_bans || []).map(
                (ban) =>
                  html`<tr>
                    <td>${ban.player_name || ban.name || ban.xuid}</td>
                    <td>${ban.reason || "—"}</td>
                    <td>
                      ${this.button("Remove ban", "remove_server_ban", { xuid: ban.xuid }, { confirm: `Remove ban for ${ban.player_name || ban.name || ban.xuid}?` })}
                    </td>
                  </tr>`,
              )}
            </tbody>
          </table>
        </div>
        ${this.selectInput(
          "Known player",
          "",
          [
            { value: "", label: "Choose player" },
            ...this.knownPlayers().map((p) => ({
              value: p.xuid,
              label: p.name || p.xuid,
            })),
          ],
          (v) => {
            const player = this.knownPlayers().find((p) => p.xuid === v);
            if (player) {
              this.player = player.name;
              this.xuid = player.xuid;
            }
          },
        )}
        <div class="grid">
          ${this.input("Player name", this.player, (v) => (this.player = v))}${this.input("XUID", this.xuid, (v) => (this.xuid = v))}${this.input("Reason", this.reason, (v) => (this.reason = v))}
        </div>
        <button
          ?disabled=${this.busy || !this.available || !this.player.trim() || !/^\d{16,19}$/.test(this.xuid)}
          @click=${() => this.action("add_server_ban", { player_name: this.player.trim(), xuid: this.xuid, reason: this.reason }, "Ban saved.", { confirm: `Ban ${this.player}?` })}
        >
          Ban player
        </button>`,
    );
  }
}
register(
  "bsm-bans-card",
  BansCard,
  "BSM Bans",
  "Manage server bans using known players and confirmed actions.",
);
