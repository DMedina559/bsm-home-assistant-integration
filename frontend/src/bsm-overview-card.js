import { BsmCard, html, register, unavailable } from "./base.js";
import { entities, related } from "./model.js";
class OverviewCard extends BsmCard {
  static title = "Bedrock Server Manager";
  static properties = { layout: { state: true } };
  constructor() {
    super();
    this.layout = "cards";
  }
  static getConfigForm() {
    const form = super.getConfigForm();
    form.schema = form.schema.filter((f) => f.name !== "entity");
    form.schema.push(
      { name: "layout", selector: { select: { options: ["cards", "table"] } } },
      {
        name: "entities",
        selector: {
          entity: {
            integration: "bedrock_server_manager",
            domain: "sensor",
            multiple: true,
          },
        },
      },
    );
    return form;
  }
  value(id, key) {
    const state = this.hass.states[related(this.hass, id, key)];
    return unavailable(state)
      ? "—"
      : `${state.state}${state.attributes.unit_of_measurement ? ` ${state.attributes.unit_of_measurement}` : ""}`;
  }
  async control(id, service) {
    if (this.busy) return;
    this.select(id);
    await this.action(
      service,
      {},
      "Request accepted.",
      service === "restart_server"
        ? { confirm: "Restart this server and disconnect its players?" }
        : {},
    );
  }
  controls(id, state) {
    const run = related(this.hass, id, "server_control"),
      running = state.state.toUpperCase() === "RUNNING",
      blocked = this.busy || unavailable(state);
    return html`<div class="actions">
      ${run ? html`<button ?disabled=${blocked || unavailable(this.hass.states[run])} @click=${() => this.nativeAction("switch", running ? "turn_off" : "turn_on", run)}>${running ? "Stop" : "Start"}</button>` : ""}<button
        ?disabled=${blocked}
        @click=${() => this.control(id, "update_server")}
      >
        Update
      </button>
      <details>
        <summary>More actions</summary>
        <button
          ?disabled=${blocked}
          @click=${() => this.control(id, "restart_server")}
        >
          Restart</button
        ><button
          ?disabled=${blocked}
          @click=${() => {
            this.select(id);
            this.action("trigger_backup", { backup_type: "all" });
          }}
        >
          Backup</button
        ><button @click=${() => this.moreInfo(id)}>Details</button>${[
          "level_name",
          "server_permissions_count",
          "allowlist_count",
        ].map((key) => {
          const entity = related(this.hass, id, key);
          return entity
            ? html`<button @click=${() => this.moreInfo(entity)}>
                ${{ level_name: "Properties", server_permissions_count: "Permissions", allowlist_count: "Allowlist" }[key]}
              </button>`
            : "";
        })}
      </details>
    </div>`;
  }
  render() {
    const servers = entities(this.hass, "server", "status").filter(
      ([id]) =>
        !this.config.entities?.length || this.config.entities.includes(id),
    );
    const running = servers.filter(
      ([, s]) => s.state.toUpperCase() === "RUNNING",
    ).length;
    const table = this.config.layout === "table";
    return this.frame(
      html`<div class="heading">
          <small>${servers.length} servers · ${running} running</small>
        </div>
        ${
          table
            ? html`<div class="scroll">
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
                    ${servers.map(
                      ([id, s]) =>
                        html`<tr>
                          <td>
                            <button @click=${() => this.moreInfo(id)}>
                              ${s.attributes.bsm_server_name || s.attributes.friendly_name}
                            </button>
                          </td>
                          <td>${s.state}</td>
                          <td>${this.value(id, "online_players_count")}</td>
                          <td>${this.value(id, "cpu_percent")}</td>
                          <td>${this.value(id, "memory_mb")}</td>
                          <td>${this.controls(id, s)}</td>
                        </tr>`,
                    )}
                  </tbody>
                </table>
              </div>`
            : html`<div class="grid">
                ${servers.map(
                  ([id, s]) =>
                    html`<section class="tile">
                      <div class="heading">
                        <button @click=${() => this.moreInfo(id)}>
                          ${s.attributes.bsm_server_name || s.attributes.friendly_name}</button
                        ><small
                          >${unavailable(s) ? "Unavailable" : s.state}</small
                        >
                      </div>
                      <small
                        >${s.attributes.installed_version || "Version unknown"}</small
                      >
                      <div class="grid">
                        <span
                          >Players
                          ${this.value(id, "online_players_count")}</span
                        ><span>CPU ${this.value(id, "cpu_percent")}</span
                        ><span>RAM ${this.value(id, "memory_mb")}</span>
                      </div>
                      ${this.controls(id, s)}
                    </section>`,
                )}
              </div>`
        }${!servers.length ? html`<p>No selected servers are available.</p>` : ""}`,
      { picker: false },
    );
  }
}
register(
  "bsm-overview-card",
  OverviewCard,
  "BSM Overview",
  "Fleet cards or table with start, stop, update and quick actions.",
);
