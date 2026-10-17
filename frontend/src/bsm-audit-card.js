import { html, register } from "./base.js";
import { InspectorCard } from "./inspector.js";
import { outcomeValue } from "./task-outcome.js";
class AuditCard extends InspectorCard {
  static title = "Audit history";
  static role = "manager";
  static key = "bsm_version";
  static properties = { actionFilter: { state: true } };
  constructor() {
    super();
    this.actionFilter = "";
  }
  selectedChanged() {
    super.selectedChanged();
    this.actionFilter = "";
  }
  render() {
    return this.frame(
      html`${this.readNotice()}${this.input("Action filter (exact match)", this.actionFilter, (v) => (this.actionFilter = v))}${this.readButton("Load audit history", "list_audit_logs", { limit: 50, ...(this.actionFilter ? { action: this.actionFilter } : {}) })}
        <p class="muted">
          Administrator access required. The backend returns its full history;
          this view filters it and displays up to 50 records.
        </p>
        ${this.result?.truncated ? html`<p class="notice">Showing a limited selection of ${this.result.total_matches} matching records.</p>` : ""}${this.result ? outcomeValue(this.result.records) : ""}`,
    );
  }
}
register(
  "bsm-audit-card",
  AuditCard,
  "BSM Audit History",
  "Inspect administrator audit records on demand.",
);
