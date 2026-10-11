import{a as s,h as a,i}from"./shared-26346ZH3.js";var e=class extends i{static title="Application health and metrics";static role="manager";static key="bsm_version";static getConfigForm(){let t=super.getConfigForm();return t.schema.push({name:"history_hours",selector:{number:{min:1,max:168,mode:"box"}}}),t}render(){return this.frame(s`<h3>Connection and health</h3>
        <div class="grid">
          ${["connection","websocket","health","lifecycle","database","state","metrics","application_lifecycle","health_checked_at"].map(t=>this.metric(this.stateFor(t)))}
        </div>
        <h3>Application</h3>
        <div class="grid">
          ${["app_cpu_percent","app_ram_mb","background_task_count","uptime_seconds","asyncio_task_count","thread_count","loop_lag_ms"].map(t=>this.metric(this.stateFor(t)))}
        </div>
        <h3>System</h3>
        <div class="grid">
          ${["sys_cpu_percent","sys_ram_percent","sys_ram_mb","sys_ram_total_mb","disk_read_kib_s","disk_write_kib_s","net_rx_kib_s","net_tx_kib_s"].map(t=>this.metric(this.stateFor(t)))}
        </div>
        <p class="muted">
          Additional diagnostic sensors can be enabled on the manager device.
        </p>
        ${this.history(["app_cpu_percent","app_ram_mb","sys_cpu_percent","sys_ram_percent"])}`)}};a("bsm-health-card",e,"BSM Health and Metrics","Separate connection, backend health, application and system metrics.");
