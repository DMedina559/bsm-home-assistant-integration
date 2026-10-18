import { html, register } from "./base.js";
import { InspectorCard } from "./inspector.js";
class LogsCard extends InspectorCard {
  static title = "Server and application logs";
  static key = "status";
  static properties = {
    application: { state: true },
    text: { state: true },
    limited: { state: true },
  };
  constructor() {
    super();
    this.application = false;
    this.text = "";
  }
  selectedChanged() {
    super.selectedChanged();
    this.text = "";
    this.limited = false;
  }
  async load(older = false) {
    const value = await this.read(
      this.application ? "get_application_log_history" : "get_log_history",
      older && this.result
        ? { before: this.result.start, file_id: this.result.file_id }
        : {},
    );
    if (!value) {
      if (older && this.lastError?.status === 409) {
        this.result = null;
        this.text = "";
        this.feedback = "Log rotated; loaded the current file.";
        await this.load();
      }
      return;
    }
    const text = older ? `${value.data}${this.text}` : value.data;
    this.limited = text.length > 131072;
    this.text = text.slice(-131072);
  }
  render() {
    return this.frame(
      html`${this.readNotice()}${this.selectInput(
          "Log source",
          this.application ? "application" : "server",
          ["server", "application"],
          (value) => {
            this.application = value === "application";
            this.selectedChanged();
          },
        )}
        <div class="actions">
          <button
            ?disabled=${this.loading || !this.available}
            @click=${() => this.load()}
          >
            Load latest</button
          ><button
            ?disabled=${this.loading || !this.available || !this.result?.has_more || this.limited}
            @click=${() => this.load(true)}
          >
            Load older
          </button>
        </div>
        <p class="muted">
          Application logs require administrator access. Log contents are loaded
          only when requested.
        </p>
        ${this.limited ? html`<p class="notice">Display limited to the latest 128 KiB of text. Reload latest to start over.</p>` : ""}
        <pre
          style="white-space:pre-wrap;overflow-wrap:anywhere;max-height:32rem;overflow:auto"
        >
${this.text || "No log page loaded."}</pre>`,
    );
  }
}
register(
  "bsm-logs-card",
  LogsCard,
  "BSM Logs",
  "Read bounded log pages and recover after log rotation.",
);
