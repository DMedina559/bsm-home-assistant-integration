import { BsmCard, html, register } from "./base.js";
import { responseValue } from "./inspector.js";
import { label } from "./model.js";
const enums = {
  gamemode: ["survival", "creative", "adventure", "spectator"],
  difficulty: ["peaceful", "easy", "normal", "hard"],
  "default-player-permission-level": ["visitor", "member", "operator"],
};
class PropertiesCard extends BsmCard {
  static title = "Server properties";
  static key = "level_name";
  static properties = { raw: { state: true } };
  async loadRaw() {
    const generation = this._generation;
    try {
      const result = responseValue(
        await this.responseService("get_raw_properties", {}),
      );
      if (generation === this._generation) this.raw = result.raw_content;
    } catch (error) {
      if (generation === this._generation) this.error = error.message;
    }
  }
  syncState() {
    if (this.available) {
      this.draft.update(this.state.attributes.server_properties || {});
      this.requestUpdate();
    }
  }
  selectedChanged() {
    this.raw = null;
    this.syncState();
  }
  edit(key, value) {
    this.draft.set(key, value);
    this.requestUpdate();
  }
  async save() {
    if (!this.draft.dirty || this.draft.conflicts.length) return;
    if (
      await this.action(
        "update_properties",
        { properties: this.draft.changes },
        "Properties saved. Some changes require a restart.",
      )
    ) {
      this.draft.reset(this.draft.live);
      this.requestUpdate();
    }
  }
  render() {
    return this.frame(
      html`${this.editNotice()}
        <div class="grid">
          ${Object.entries(this.draft.value).map(([key, value]) => (enums[key] ? this.selectInput(label(key), value, enums[key], (v) => this.edit(key, v)) : ["true", "false"].includes(String(value)) ? this.selectInput(label(key), String(value), ["true", "false"], (v) => this.edit(key, v)) : this.input(label(key), value, (v) => this.edit(key, v))))}
        </div>
        ${this.available && !Object.keys(this.draft.value).length ? html`<p>No properties are available.</p>` : ""}<button
          class="primary"
          ?disabled=${!this.available || this.busy || !this.draft.dirty || this.draft.conflicts.length > 0}
          @click=${this.save}
        >
          Save properties
        </button>
        <div class="actions">
          ${this.button("Validate server", "validate_server", {}, { message: "Server validation completed." })}<button
            ?disabled=${!this.available || this.busy}
            @click=${this.loadRaw}
          >
            View raw properties
          </button>
        </div>
        ${
          this.raw != null
            ? html`<details open>
                <summary>Raw server.properties (read only)</summary>
                <pre style="white-space:pre-wrap;overflow-wrap:anywhere">
${this.raw}</pre>
              </details>`
            : ""
        }`,
    );
  }
}
register(
  "bsm-properties-card",
  PropertiesCard,
  "BSM Properties",
  "Edit server properties with external-change protection.",
);
