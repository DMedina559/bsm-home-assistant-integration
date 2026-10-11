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
    return this.frame(
      html`<h3>Connection and health</h3>
        <div class="grid">
          ${["connection", "websocket", "health", "lifecycle", "database", "state", "metrics", "application_lifecycle", "health_checked_at"].map((key) => this.metric(this.stateFor(key)))}
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
