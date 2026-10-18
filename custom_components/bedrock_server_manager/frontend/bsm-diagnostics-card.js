import{b as r}from"./shared-UXCKWJE4.js";import{g as i,h as a,j as o}from"./shared-66JIFLDQ.js";var n=class extends r{static title="Backend diagnostics";static role="manager";static key="bsm_version";static properties={snapshot:{state:!0},baseline:{state:!0},comparison:{state:!0},subsystem:{state:!0},correlation:{state:!0}};constructor(){super(),this.subsystem="",this.correlation=""}selectedChanged(){super.selectedChanged(),this.snapshot=null,this.baseline=null,this.comparison=null,this.subsystem="",this.correlation=""}async collect(){let s=await this.read(this.subsystem?"get_subsystem_diagnostics":"get_application_diagnostics",this.subsystem?{subsystem:this.subsystem}:{});s&&(this.snapshot=s)}async compare(){if(!this.baseline||!this.snapshot)return;let s=await this.read("compare_diagnostic_snapshots",{before:this.baseline,after:this.snapshot},!1);s&&(this.comparison=s)}async download(){let s=await this.read("get_diagnostic_report",{},!1);if(!s)return;let e=URL.createObjectURL(new Blob([JSON.stringify(s,null,2)],{type:"application/json"})),t=document.createElement("a");t.href=e,t.download="bsm-diagnostics.json",t.click(),URL.revokeObjectURL(e),this.feedback="Report downloaded. Review it before sharing."}render(){let s=this.snapshot,e=s?.summary;return this.frame(i`${this.readNotice()}${this.input("Subsystem (blank for all)",this.subsystem,t=>this.subsystem=t)}
        <div class="actions">
          <button
            ?disabled=${this.loading||!this.available}
            @click=${this.collect}
          >
            Collect snapshot</button
          ><button
            ?disabled=${!s||this.loading}
            @click=${()=>{this.baseline=structuredClone(s),this.comparison=null,this.feedback="Baseline captured. Collect another snapshot to compare."}}
          >
            Capture baseline</button
          ><button
            ?disabled=${!this.baseline||!s||this.loading||!this.available}
            @click=${this.compare}
          >
            Compare snapshots</button
          ><button
            ?disabled=${this.loading||!this.available}
            @click=${this.download}
          >
            Download report
          </button>
        </div>
        ${e?i`<h3>Summary</h3>
                <div class="grid">
                  <div class="tile">
                    <strong>Status</strong>${e.status}
                  </div>
                  <div class="tile">
                    <strong>Readiness</strong
                    >${e.ready==null?"Unknown":e.ready?"Ready":"Not ready"}
                  </div>
                  <div class="tile">
                    <strong>Instance</strong>${s.instance_id}
                  </div>
                </div>
                <h3>Findings</h3>
                ${e.findings?.length?a(e.findings):i`<p>No findings reported.</p>`}${e.truncated?i`<p class="notice">Finding details are limited by the backend.</p>`:""}
                <h3>Subsystems</h3>
                ${(s.sections||[]).map(t=>i`<details class="tile">
                      <summary>
                        ${t.name} ·
                        ${t.status}${t.stale?" \xB7 stale":""}
                      </summary>
                      <p>
                        Owner: ${t.owner} · Age:
                        ${t.age_seconds==null?"Unknown":`${t.age_seconds}s`}
                      </p>
                      ${a(t.issues)}${a(t.data)}
                    </details>`)}
                <details>
                  <summary>Collection and persistence</summary>
                  ${a({collection:s.collection,persistence:s.persistence,registry:s.registry})}
                </details>`:""}
        ${this.comparison?i`<h3>Comparison</h3>
                ${a(this.comparison)}`:""}
        <h3>Retained history</h3>
        <div class="actions">
          ${this.readButton("Load history","get_diagnostic_history",{limit:50,...this.subsystem?{subsystem:this.subsystem}:{}})}${this.readButton("Load runs","get_diagnostic_runs",{limit:20})}${this.result?.next_cursor?this.readButton("Next history page","get_diagnostic_history",{limit:50,cursor:this.result.next_cursor,...this.subsystem?{subsystem:this.subsystem}:{}}):""}
        </div>
        ${this.input("Correlation ID",this.correlation,t=>this.correlation=t)}${this.readButton("Load trace","get_diagnostic_trace",{correlation_id:this.correlation,limit:50})}${this.result&&this.result!==s?i`<details open>
                <summary>Requested data</summary>
                ${a(this.result)}
              </details>`:""}`)}};o("bsm-diagnostics-card",n,"BSM Diagnostics","Inspect subsystem findings, retained history, traces and snapshot comparisons on demand.");
