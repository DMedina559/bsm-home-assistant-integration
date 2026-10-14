import{g as t,j as r,k as n}from"./shared-66JIFLDQ.js";var c=class extends n{static title="Application health and metrics";static role="manager";static key="bsm_version";static getConfigForm(){let a=super.getConfigForm();return a.schema.push({name:"history_hours",selector:{number:{min:1,max:168,mode:"box"}}}),a}render(){let a=this.stateFor("health"),s=a?.attributes||{};return this.frame(t`<h3>Connection and health</h3>
        <div class="grid">
          ${["connection","websocket","health","ready"].map(e=>this.metric(this.stateFor(e)))}
        </div>
        <h3>Health checks</h3>
        ${Object.keys(s.checks||{}).length?t`<div class="grid">${Object.entries(s.checks).map(([e,i])=>t`<div class="tile"><strong>${e}</strong><span>${a.state==="unavailable"?"Unavailable":i.healthy===!0?"Healthy":i.healthy===!1?"Problem":"Unknown"}</span><small>${i.message||""}</small></div>`)}</div>`:t`<p class="muted">Health checks are not available yet.</p>`}
        ${s.lifecycle?t`<p class="muted">Lifecycle: ${s.lifecycle}</p>`:""}
        ${typeof s.checked_at=="number"?t`<p class="muted">Checked ${new Date(s.checked_at*1e3).toLocaleString()}</p>`:""}
        <h3>Optional diagnostics</h3>
        <div class="grid">
          ${["issue_count","event_pending_workers","delivery_failures"].map(e=>this.metric(this.stateFor(e)))}
        </div>
        <h3>Application</h3>
        <div class="grid">
          ${["app_cpu_percent","app_ram_mb","background_task_count","uptime_seconds","asyncio_task_count","thread_count","loop_lag_ms"].map(e=>this.metric(this.stateFor(e)))}
        </div>
        <h3>System</h3>
        <div class="grid">
          ${["sys_cpu_percent","sys_ram_percent","sys_ram_mb","sys_ram_total_mb","disk_read_kib_s","disk_write_kib_s","net_rx_kib_s","net_tx_kib_s"].map(e=>this.metric(this.stateFor(e)))}
        </div>
        <p class="muted">
          Additional diagnostic sensors can be enabled on the manager device.
        </p>
        ${this.history(["app_cpu_percent","app_ram_mb","sys_cpu_percent","sys_ram_percent"])}`)}};r("bsm-health-card",c,"BSM Health and Metrics","Separate connection, backend health, application and system metrics.");
