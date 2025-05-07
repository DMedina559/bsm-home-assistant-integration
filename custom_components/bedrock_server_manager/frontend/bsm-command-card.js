import { LitElement, html, css } from "https://unpkg.com/lit-element@^2.0.0/lit-element.js?module";

// Define domain
const DOMAIN = "bedrock_server_manager";

// Simple logger using console for debugging in the browser
const _LOGGER = {
    debug: (...args) => console.debug("BSM_CMD_CARD:", ...args),
    info: (...args) => console.info("BSM_CMD_CARD:", ...args),
    warn: (...args) => console.warn("BSM_CMD_CARD:", ...args),
    error: (...args) => console.error("BSM_CMD_CARD:", ...args),
};

class BsmCommandCard extends LitElement {

  static get properties() {
    return {
      hass: { type: Object }, // Custom setter/getter used
      config: { type: Object },
      _selectedDeviceId: { state: true }, // Store the selected device_id string
      _commandText: { state: true },    // Store the command text
      _feedback: { state: true },       // Store feedback messages
      _error: { state: true },          // Store error messages separately for styling
      _isLoading: { state: true },      // For loading state
    };
  }

  static get styles() {
    return css`
      :host { display: block; }
      ha-card { display: flex; flex-direction: column; height: 100%; }
      .card-content { flex-grow: 1; padding-bottom: 8px; }
      .card-actions { border-top: 1px solid var(--divider-color, #e0e0e0); padding: 8px 16px; text-align: right; }
      ha-selector { display: block; margin-bottom: 16px; }
      .feedback-area { margin-top: 16px; min-height: 1.2em; /* Reserve space to prevent layout jumps */ }
      .feedback { color: var(--secondary-text-color); font-size: 0.9em; word-wrap: break-word; }
      .error { color: var(--error-color); font-weight: bold; word-wrap: break-word; }
      .loading-indicator { display: flex; align-items: center; justify-content: flex-start; gap: 8px; margin-top:16px; color: var(--secondary-text-color); font-size: 0.9em; }
    `;
  }

  // Internal storage for hass property
  __hass;
  get hass() { return this.__hass; }
  set hass(hass) {
    const oldHass = this.__hass;
    this.__hass = hass;
    if (oldHass !== hass) {
        this.requestUpdate('hass', oldHass);
    }
  }

  constructor() {
    super();
    this._selectedDeviceId = null;
    this._commandText = "";
    this._feedback = "";
    this._error = "";
    this._isLoading = false;
    _LOGGER.debug("BSM Command Card constructor finished.");
  }

  setConfig(config) {
    _LOGGER.debug("setConfig called with:", config);
    const oldConfig = this.config;
    this.config = config || {};
    this.requestUpdate('config', oldConfig);
  }

  render() {
    if (!this.hass) {
      return html`<ha-card header="Send Command"><div class="card-content">Waiting for Home Assistant...</div></ha-card>`;
    }

    const deviceSelectorConfig = {
      device: {
        integration: DOMAIN
      }
    };

    const textSelectorConfig = {
       text: {} // Simple text input
    };

    return html`
      <ha-card header="${this.config.title || "Send Server Command"}">
        <div class="card-content">

          <ha-selector
            label="Target Server Device"
            .hass=${this.hass}
            .selector=${deviceSelectorConfig}
            .value=${this._selectedDeviceId}
            @value-changed=${this._handleTargetChanged}
            ?disabled=${this._isLoading}
          ></ha-selector>

          <ha-selector
            label="Command (do not include a leading '/') "
            .hass=${this.hass}
            .selector=${textSelectorConfig}
            .value=${this._commandText}
            @value-changed=${this._handleCommandChanged}
            ?disabled=${this._isLoading}
          ></ha-selector>

          <div class="feedback-area">
            ${this._isLoading ? html`<div class="loading-indicator"><ha-circular-progress indeterminate size="small"></ha-circular-progress> Sending command...</div>` : ""}
            ${!this._isLoading && this._feedback ? html`<div class="feedback">${this._feedback}</div>` : ""}
            ${!this._isLoading && this._error ? html`<div class="error">${this._error}</div>` : ""}
          </div>

        </div>
        <div class="card-actions">
          <mwc-button
            raised
            label="Send Command"
            @click=${this._sendCommand}
            .disabled=${!this._commandText.trim() || !this._selectedDeviceId || this._isLoading}
          ></mwc-button>
        </div>
      </ha-card>
    `;
  }

  _clearMessages() {
      this._feedback = "";
      this._error = "";
  }

  _handleTargetChanged(ev) {
      ev.stopPropagation();
      this._clearMessages();
      const deviceId = ev.detail.value; // ha-selector for device returns device_id string
      this._selectedDeviceId = deviceId || null;
      _LOGGER.debug("Target device ID selected:", this._selectedDeviceId);
      // No requestUpdate needed here as LitElement handles property changes automatically
  }

  _handleCommandChanged(ev) {
      ev.stopPropagation();
      this._clearMessages();
      this._commandText = ev.detail.value || "";
      // No requestUpdate needed here
  }

  async _callService(serviceName, serviceData, operationFeedback) {
    this._isLoading = true;
    this._clearMessages(); // Clear previous messages before new operation
    // No need to set _feedback to "Sending..." here, render takes care of it via _isLoading
    this.requestUpdate();

    try {
      _LOGGER.debug(`Calling ${DOMAIN}.${serviceName} with data: %o`, serviceData);
      await this.hass.callService(DOMAIN, serviceName, serviceData);
      this._feedback = operationFeedback || "Operation successful."; // Generic success if specific one isn't provided
      return true; // Indicate success
    } catch (err) {
      _LOGGER.error(`Error calling ${DOMAIN}.${serviceName} service:`, err);
      const errorMessage = err.body?.message || err.message || "An unknown error occurred. Check Home Assistant logs.";
      this._error = `Error: ${errorMessage}`;
      return false; // Indicate failure
    } finally {
      this._isLoading = false;
      this.requestUpdate();
    }
  }

  async _sendCommand() {
    if (!this._selectedDeviceId) {
        this._error = "Error: Please select a target server device.";
        this._feedback = "";
        this.requestUpdate();
        return;
    }
     if (!this._commandText || this._commandText.trim() === "") {
        this._error = "Error: Please enter a command.";
        this._feedback = "";
        this.requestUpdate();
        return;
    }

    const commandToSend = this._commandText.trim();

    const success = await this._callService(
        "send_command",
        {
            device_id: this._selectedDeviceId,
            command: commandToSend,
        },
        `Command "${commandToSend.substring(0, 30)}${commandToSend.length > 30 ? '...' : ''}" sent successfully.`
    );

    if (success) {
      this._commandText = ""; // Clear input field on successful send
    }
  }

  getCardSize() { return 3; }
}

customElements.define("bsm-command-card", BsmCommandCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "bsm-command-card",
  name: "Send Command Card",
  description: "Send a command to a Bedrock Server Manager managed server.",
  preview: true,
});

console.info(`%c BSM-COMMAND-CARD %c LOADED %c`, "color: orange; font-weight: bold; background: black", "color: white; font-weight: bold; background: dimgray", "");