import { html, register } from "./base.js";
import { InspectorCard } from "./inspector.js";
import { outcomeValue } from "./task-outcome.js";
class RuntimeCard extends InspectorCard {
  static title = "Web runtime";
  static role = "manager";
  static key = "bsm_version";
  static properties = { shutdownAccepted: { state: true } };
  selectedChanged() {
    super.selectedChanged();
    this.shutdownAccepted = false;
  }
  async action(service, data, message, options) {
    const success = await super.action(service, data, message, options);
    if (success && service === "shutdown_web_runtime")
      this.shutdownAccepted = true;
    return success;
  }
  render() {
    return this.frame(
      html`${this.readNotice()}${this.readButton("Load runtime status", "get_web_runtime")}${this.result ? outcomeValue(this.result) : ""}
        <p class="muted">
          Administrator access required. Shutdown stops the web runtime.
          Starting it again requires access to the host or service manager.
        </p>
        ${this.shutdownAccepted ? html`<p class="notice" role="status">Shutdown accepted. API and WebSocket disconnection is expected.</p>` : this.button("Shut down web runtime", "shutdown_web_runtime", { confirm: true }, { message: "Shutdown accepted. Disconnection is expected.", confirm: "Stop the BSM web runtime? API access will disconnect. You must restart it from the host or service manager." })}`,
    );
  }
}
register(
  "bsm-runtime-card",
  RuntimeCard,
  "BSM Web Runtime",
  "Inspect runtime state and request a confirmed graceful shutdown.",
);
