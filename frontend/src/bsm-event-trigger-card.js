import { BsmCard, html, register } from "./base.js";
class EventCard extends BsmCard {
  static title = "Trigger plugin event";
  static role = "manager";
  static key = "bsm_version";
  static properties = { eventName: { state: true }, payload: { state: true } };
  constructor() {
    super();
    this.eventName = "";
    this.payload = "{}";
  }
  selectedChanged() {
    this.eventName = "";
    this.payload = "{}";
  }
  async send() {
    try {
      const payload = JSON.parse(this.payload || "{}");
      if (!payload || Array.isArray(payload) || typeof payload !== "object")
        throw Error("Event payload must be a JSON object.");
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
    return this.frame(
      html`${this.input("Event name", this.eventName, (v) => (this.eventName = v))}<label
          >Event payload (JSON)<textarea
            aria-label="Event payload"
            .value=${this.payload}
            ?disabled=${this.busy}
            @input=${(e) => (this.payload = e.target.value)}
          ></textarea></label
        ><button
          ?disabled=${this.busy || !this.available || !this.eventName.trim()}
          @click=${this.send}
        >
          Trigger event
        </button>`,
    );
  }
}
register(
  "bsm-event-trigger-card",
  EventCard,
  "BSM Plugin Event",
  "Trigger plugin events using a validated object payload.",
);
