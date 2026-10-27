import { html, register } from "./base.js";
import { InspectorCard } from "./inspector.js";
import { outcomeValue } from "./task-outcome.js";
class DiagnosticsCard extends InspectorCard {
  static title = "Backend diagnostics";
  static role = "manager";
  static key = "bsm_version";
  static properties = {
    snapshot: { state: true },
    baseline: { state: true },
    comparison: { state: true },
    subsystem: { state: true },
    correlation: { state: true },
  };
  constructor() {
    super();
    this.subsystem = "";
    this.correlation = "";
  }
  selectedChanged() {
    super.selectedChanged();
    this.snapshot = null;
    this.baseline = null;
    this.comparison = null;
    this.subsystem = "";
    this.correlation = "";
  }
  async collect() {
    const value = await this.read(
      this.subsystem
        ? "get_subsystem_diagnostics"
        : "get_application_diagnostics",
      this.subsystem ? { subsystem: this.subsystem } : {},
    );
    if (value) this.snapshot = value;
  }
  async compare() {
    if (!this.baseline || !this.snapshot) return;
    const value = await this.read(
      "compare_diagnostic_snapshots",
      { before: this.baseline, after: this.snapshot },
      false,
    );
    if (value) this.comparison = value;
  }
  async download() {
    const report = await this.read("get_diagnostic_report", {}, false);
    if (!report) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "bsm-diagnostics.json";
    link.click();
    URL.revokeObjectURL(url);
    this.feedback = "Report downloaded. Review it before sharing.";
  }
  render() {
    const snapshot = this.snapshot,
      summary = snapshot?.summary;
    return this.frame(
      html`${this.readNotice()}${this.input("Subsystem (blank for all)", this.subsystem, (v) => (this.subsystem = v))}
        <div class="actions">
          <button
            ?disabled=${this.loading || !this.available}
            @click=${this.collect}
          >
            Collect snapshot</button
          ><button
            ?disabled=${!snapshot || this.loading}
            @click=${() => {
              this.baseline = structuredClone(snapshot);
              this.comparison = null;
              this.feedback =
                "Baseline captured. Collect another snapshot to compare.";
            }}
          >
            Capture baseline</button
          ><button
            ?disabled=${!this.baseline || !snapshot || this.loading || !this.available}
            @click=${this.compare}
          >
            Compare snapshots</button
          ><button
            ?disabled=${this.loading || !this.available}
            @click=${this.download}
          >
            Download report
          </button>
        </div>
        ${
          summary
            ? html`<h3>Summary</h3>
                <div class="grid">
                  <div class="tile">
                    <strong>Status</strong>${summary.status}
                  </div>
                  <div class="tile">
                    <strong>Readiness</strong
                    >${summary.ready == null ? "Unknown" : summary.ready ? "Ready" : "Not ready"}
                  </div>
                  <div class="tile">
                    <strong>Instance</strong>${snapshot.instance_id}
                  </div>
                </div>
                <h3>Findings</h3>
                ${summary.findings?.length ? outcomeValue(summary.findings) : html`<p>No findings reported.</p>`}${summary.truncated ? html`<p class="notice">Finding details are limited by the backend.</p>` : ""}
                <h3>Subsystems</h3>
                ${(snapshot.sections || []).map(
                  (section) =>
                    html`<details class="tile">
                      <summary>
                        ${section.name} ·
                        ${section.status}${section.stale ? " · stale" : ""}
                      </summary>
                      <p>
                        Owner: ${section.owner} · Age:
                        ${section.age_seconds == null ? "Unknown" : `${section.age_seconds}s`}
                      </p>
                      ${outcomeValue(section.issues)}${outcomeValue(section.data)}
                    </details>`,
                )}
                <details>
                  <summary>Collection and persistence</summary>
                  ${outcomeValue({ collection: snapshot.collection, persistence: snapshot.persistence, registry: snapshot.registry })}
                </details>`
            : ""
        }
        ${
          this.comparison
            ? html`<h3>Comparison</h3>
                ${outcomeValue(this.comparison)}`
            : ""
        }
        <h3>Global activity</h3>
        <p class="muted">
          Events across all operations and servers. Use a correlation ID below
          to inspect one chain.
        </p>
        ${this.readButton("Load activity", "get_diagnostic_activity", { limit: 100 })}
        <h3>Retained history</h3>
        <div class="actions">
          ${this.readButton("Load history", "get_diagnostic_history", { limit: 50, ...(this.subsystem ? { subsystem: this.subsystem } : {}) })}${this.readButton("Load runs", "get_diagnostic_runs", { limit: 20 })}${this.result?.next_cursor ? this.readButton("Next history page", "get_diagnostic_history", { limit: 50, cursor: this.result.next_cursor, ...(this.subsystem ? { subsystem: this.subsystem } : {}) }) : ""}
        </div>
        ${this.input("Correlation ID", this.correlation, (v) => (this.correlation = v))}${this.readButton("Load trace", "get_diagnostic_trace", { correlation_id: this.correlation, limit: 50 })}${
          this.result && this.result !== snapshot
            ? html`<details open>
                <summary>Requested data</summary>
                ${outcomeValue(this.result)}
              </details>`
            : ""
        }`,
    );
  }
}
register(
  "bsm-diagnostics-card",
  DiagnosticsCard,
  "BSM Diagnostics",
  "Inspect subsystem findings, retained history, traces and snapshot comparisons on demand.",
);
