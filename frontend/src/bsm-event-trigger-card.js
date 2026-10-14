import { html, register } from "./base.js";
import { InspectorCard } from "./inspector.js";
import { outcomeValue } from "./task-outcome.js";
class EventCard extends InspectorCard {
  static title = "Plugin events";
  static role = "manager";
  static key = "bsm_version";
  static properties = {
    eventName: { state: true },
    payload: { state: true },
    catalog: { state: true },
    activity: { state: true },
  };
  constructor() {
    super();
    this.eventName = "";
    this.payload = "{}";
    this.catalog = [];
  }
  selectedChanged() {
    super.selectedChanged();
    this.eventName = "";
    this.payload = "{}";
    this.catalog = [];
    this.activity = null;
  }
  async loadCatalog() {
    const result = await this.read("list_application_events", {}, false);
    if (result) this.catalog = result.events || [];
  }
  async loadActivity() {
    const result = await this.read(
      "get_event_activity",
      { limit: 25, ...(this.eventName ? { name: this.eventName } : {}) },
      false,
    );
    if (result) this.activity = result;
  }
  async send() {
    try {
      const payload = JSON.parse(this.payload || "{}");
      if (!payload || Array.isArray(payload) || typeof payload !== "object")
        throw Error("Event payload must be a JSON object.");
      const definition = this.catalog.find(
        (item) => item.name === this.eventName,
      );
      for (const key of definition?.payload_schema?.required || [])
        if (!(key in payload)) throw Error(`Event payload requires '${key}'.`);
      await this.action(
        "trigger_plugin_event",
        { event_name: this.eventName.trim(), event_payload: payload },
        "Plugin event delivered.",
      );
    } catch (error) {
      this.error = error.message;
    }
  }
  render() {
    const definition = this.catalog.find(
      (item) => item.name === this.eventName,
    );
    return this.frame(
      html`${this.readNotice()}
        <div class="actions">
          <button
            ?disabled=${this.loading || !this.available}
            @click=${this.loadCatalog}
          >
            Load event catalog</button
          ><button
            ?disabled=${this.loading || !this.available}
            @click=${this.loadActivity}
          >
            Load event activity
          </button>
        </div>
        ${this.catalog.length ? this.selectInput("Declared custom event", this.eventName, [{ value: "", label: "Choose event" }, ...this.catalog.filter((event) => event.phase === "custom" && event.public).map((event) => ({ value: event.name, label: `${event.name} · ${event.owner}` }))], (v) => (this.eventName = v)) : ""}${this.input("Event name", this.eventName, (v) => (this.eventName = v))}${
          definition
            ? html`<p>${definition.description}</p>
                <details>
                  <summary>Declared payload contract</summary>
                  ${outcomeValue(definition.payload_schema)}
                </details>`
            : ""
        }<label
          >Event payload (JSON)<textarea
            aria-label="Event payload"
            .value=${this.payload}
            ?disabled=${this.busy}
            @input=${(e) => (this.payload = e.target.value)}
          ></textarea></label
        ><button
          ?disabled=${this.busy || this.loading || !this.available || !this.eventName.trim()}
          @click=${this.send}
        >
          Trigger event
        </button>
        <p class="muted">
          The backend validates the full event contract. Catalog and activity
          reads require administrator access.
        </p>
        ${
          this.activity
            ? html`<h3>Delivery activity</h3>
                ${outcomeValue(this.activity)}`
            : ""
        }`,
    );
  }
}
register(
  "bsm-event-trigger-card",
  EventCard,
  "BSM Plugin Event",
  "Discover declared event contracts, trigger plugin events and inspect delivery activity.",
);
