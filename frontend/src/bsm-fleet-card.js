import { BsmCard, html, register, unavailable } from "./base.js";
import { entities, related } from "./model.js";
class FleetCard extends BsmCard {
  static title = "Bedrock servers";
  static getConfigForm() {
    const form = super.getConfigForm();
    form.schema = form.schema.filter((field) => field.name !== "entity");
    form.schema.push({
      name: "entities",
      selector: {
        entity: {
          integration: "bedrock_server_manager",
          domain: "sensor",
          multiple: true,
        },
      },
    });
    return form;
  }
  render() {
    const servers = entities(this.hass, "server", "status").filter(
      ([id]) =>
        !this.config.entities?.length || this.config.entities.includes(id),
    );
    return this.frame(
      html`<div class="grid">
          ${servers.map(([id, state]) => {
            const players =
                this.hass.states[
                  related(this.hass, id, "online_players_count")
                ],
              cpu = this.hass.states[related(this.hass, id, "cpu_percent")],
              memory = this.hass.states[related(this.hass, id, "memory_mb")];
            return html`<section class="tile">
              <button
                style="width:100%;text-align:left"
                @click=${() => this.moreInfo(id)}
              >
                ${state.attributes.bsm_server_name || state.attributes.friendly_name}
              </button>
              <p>
                ${unavailable(state) ? "Unavailable" : state.state} ·
                ${state.attributes.installed_version || "Version unknown"}
              </p>
              <small
                >Players ${unavailable(players) ? "—" : players.state} · CPU
                ${unavailable(cpu) ? "—" : `${cpu.state}%`} · RAM
                ${unavailable(memory) ? "—" : `${memory.state} ${memory.attributes.unit_of_measurement}`}</small
              >
            </section>`;
          })}
        </div>
        ${!servers.length ? html`<p class="muted">No server status entities are available. Add servers in integration options.</p>` : ""}`,
      { picker: false },
    );
  }
}
register(
  "bsm-fleet-card",
  FleetCard,
  "BSM Fleet",
  "A compact overview of selected servers with native entity details.",
);
