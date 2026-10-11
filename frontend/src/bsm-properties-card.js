import { BsmCard, html, register } from "./base.js";
import { label } from "./model.js";
const enums = {
  gamemode: ["survival", "creative", "adventure", "spectator"],
  difficulty: ["peaceful", "easy", "normal", "hard"],
  "default-player-permission-level": ["visitor", "member", "operator"],
};
class PropertiesCard extends BsmCard {
  static title = "Server properties";
  static key = "level_name";
  syncState() {
    if (this.available) {
      this.draft.update(this.state.attributes.server_properties || {});
      this.requestUpdate();
    }
  }
  selectedChanged() {
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
        </button>`,
    );
  }
}
register(
  "bsm-properties-card",
  PropertiesCard,
  "BSM Properties",
  "Edit server properties with external-change protection.",
);
