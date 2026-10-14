import { BsmCard, html, register } from "./base.js";
class HealthCard extends BsmCard {
  static title = "Application health and metrics";
  static role = "manager";
  static key = "bsm_version";
  static getConfigForm() {
    const form = super.getConfigForm();
    form.schema.push({
      name: "history_hours",
      selector: { number: { min: 1, max: 168, mode: "box" } },
    });
    return form;
  }
  render() {
    const health = this.stateFor("health");
    const details = health?.attributes || {};
    return this.frame(
      html`<h3>Connection and health</h3>
        <div class="grid">
          ${["connection", "websocket", "health", "ready"].map((key) => this.metric(this.stateFor(key)))}
        </div>
        <h3>Health checks</h3>
        ${Object.keys(details.checks || {}).length ? html`<div class="grid">${Object.entries(details.checks).map(([name, check]) => html`<div class="tile"><strong>${name}</strong><span>${health.state === "unavailable" ? "Unavailable" : check.healthy === true ? "Healthy" : check.healthy === false ? "Problem" : "Unknown"}</span><small>${check.message || ""}</small></div>`)}</div>` : html`<p class="muted">Health checks are not available yet.</p>`}
        ${details.lifecycle ? html`<p class="muted">Lifecycle: ${details.lifecycle}</p>` : ""}
        ${typeof details.checked_at === "number" ? html`<p class="muted">Checked ${new Date(details.checked_at * 1000).toLocaleString()}</p>` : ""}
        <h3>Optional diagnostics</h3>
        <div class="grid">
          ${["issue_count", "event_pending_workers", "delivery_failures"].map((key) => this.metric(this.stateFor(key)))}
        </div>
        <h3>Application</h3>
        <div class="grid">
          ${["app_cpu_percent", "app_ram_mb", "background_task_count", "uptime_seconds", "asyncio_task_count", "thread_count", "loop_lag_ms"].map((key) => this.metric(this.stateFor(key)))}
        </div>
        <h3>System</h3>
        <div class="grid">
          ${["sys_cpu_percent", "sys_ram_percent", "sys_ram_mb", "sys_ram_total_mb", "disk_read_kib_s", "disk_write_kib_s", "net_rx_kib_s", "net_tx_kib_s"].map((key) => this.metric(this.stateFor(key)))}
        </div>
        <p class="muted">
          Additional diagnostic sensors can be enabled on the manager device.
        </p>
        ${this.history(["app_cpu_percent", "app_ram_mb", "sys_cpu_percent", "sys_ram_percent"])}`,
    );
  }
}
register(
  "bsm-health-card",
  HealthCard,
  "BSM Health and Metrics",
  "Separate connection, backend health, application and system metrics.",
);
