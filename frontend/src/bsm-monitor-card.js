import { BsmCard, html, register, unavailable } from "./base.js";
import { related } from "./model.js";
class MonitorCard extends BsmCard {
  static title = "Server monitor";
  static getConfigForm() {
    const form = super.getConfigForm();
    form.schema.push({
      name: "history_hours",
      selector: { number: { min: 1, max: 168, mode: "box" } },
    });
    return form;
  }
  render() {
    const run = related(this.hass, this.selection, "server_control");
    return this.frame(
      html`<div class="grid">
          ${["status", "online_players_count", "cpu_percent", "memory_mb", "uptime_seconds"].map((key) => this.metric(this.stateFor(key)))}
        </div>
        <div class="actions">
          ${run ? html`<button ?disabled=${this.busy || unavailable(this.hass.states[run])} @click=${() => this.nativeAction("switch", this.hass.states[run].state === "on" ? "turn_off" : "turn_on", run)}>${this.hass.states[run].state === "on" ? "Stop" : "Start"}</button>` : ""}${this.button("Update server", "update_server", {}, { message: "Update request accepted." })}${this.button("Restart", "restart_server", {}, { message: "Restart requested.", confirm: "Restart this server and disconnect its players?" })}${this.button("Backup", "trigger_backup", { backup_type: "all" }, { message: "Request accepted." })}
        </div>
        ${this.entityControl("target_version")}${this.entityControl("autostart")}${this.entityControl("autoupdate")}${this.history(["cpu_percent", "memory_mb", "online_players_count"])}`,
    );
  }
}
register(
  "bsm-monitor-card",
  MonitorCard,
  "BSM Server Monitor",
  "Server controls, metrics and Home Assistant recorder graphs.",
);
