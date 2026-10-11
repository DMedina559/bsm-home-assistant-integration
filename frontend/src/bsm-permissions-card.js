import { BsmCard, html, register } from "./base.js";
class PermissionsCard extends BsmCard {
  static title = "Server permissions";
  static key = "server_permissions_count";
  static properties = { playerName: { state: true }, xuid: { state: true } };
  static getConfigForm() {
    const form = super.getConfigForm();
    form.schema.push({
      name: "global_players_entity",
      selector: {
        entity: { integration: "bedrock_server_manager", domain: "sensor" },
      },
    });
    return form;
  }
  constructor() {
    super();
    this.playerName = "";
    this.xuid = "";
  }
  syncState() {
    if (this.available) {
      this.draft.update(
        Object.fromEntries(
          (this.state.attributes.server_permissions || []).map((p) => [
            p.xuid,
            p,
          ]),
        ),
      );
      this.requestUpdate();
    }
  }
  selectedChanged() {
    this.playerName = "";
    this.xuid = "";
    this.syncState();
  }
  add() {
    if (!this.playerName.trim() || !/^\d{16,19}$/.test(this.xuid)) {
      this.error = "Enter a player name and a 16–19 digit XUID.";
      return;
    }
    this.draft.set(this.xuid, {
      name: this.playerName.trim(),
      xuid: this.xuid,
      permission_level: "member",
    });
    this.playerName = "";
    this.xuid = "";
    this.requestUpdate();
  }
  choosePlayer(value) {
    const player = this.knownPlayers().find((player) => player.xuid === value);
    if (player) {
      this.playerName = player.name;
      this.xuid = player.xuid;
    }
  }
  async save() {
    if (this.draft.conflicts.length) return;
    if (
      await this.action(
        "set_permissions",
        { permissions: Object.values(this.draft.value) },
        "Permissions saved.",
      )
    ) {
      this.draft.reset(this.draft.live);
      this.requestUpdate();
    }
  }
  render() {
    return this.frame(
      html`${this.editNotice()}
        <div class="scroll">
          <table>
            <thead>
              <tr>
                <th>Player</th>
                <th>Permission</th>
              </tr>
            </thead>
            <tbody>
              ${Object.values(this.draft.value).map(
                (p) =>
                  html`<tr>
                    <td>${p.name || p.xuid}</td>
                    <td>
                      ${this.selectInput(
                        `Permission for ${p.name || p.xuid}`,
                        p.permission_level,
                        ["visitor", "member", "operator"],
                        (v) => {
                          this.draft.set(p.xuid, { ...p, permission_level: v });
                          this.requestUpdate();
                        },
                      )}
                    </td>
                  </tr>`,
              )}
            </tbody>
          </table>
        </div>
        ${this.knownPlayers().length ? this.selectInput("Known player", "", [{ value: "", label: "Choose known player" }, ...this.knownPlayers().map((player) => ({ value: player.xuid, label: player.name || player.xuid }))], (value) => this.choosePlayer(value)) : ""}
        <div class="grid">
          ${this.input("Player name", this.playerName, (v) => (this.playerName = v))}${this.input("XUID", this.xuid, (v) => (this.xuid = v))}
        </div>
        <div class="actions">
          <button ?disabled=${this.busy || !this.available} @click=${this.add}>
            Stage player</button
          ><button
            class="primary"
            ?disabled=${!this.available || this.busy || !this.draft.dirty || this.draft.conflicts.length > 0}
            @click=${this.save}
          >
            Save permissions
          </button>
        </div>`,
    );
  }
}
register(
  "bsm-permissions-card",
  PermissionsCard,
  "BSM Permissions",
  "Stage and save player permissions without losing live edits.",
);
