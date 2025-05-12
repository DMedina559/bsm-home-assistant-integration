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

// Helper function to fire events (same as before)
const fireEvent = (node, type, detail = {}, options = {}) => {
  const event = new Event(type, {
    bubbles: options.bubbles === undefined ? true : options.bubbles,
    cancelable: Boolean(options.cancelable),
    composed: options.composed === undefined ? true : options.composed,
  });
  event.detail = detail;
  node.dispatchEvent(event);
  return event;
};

class BsmCommandCard extends LitElement {

  static async getConfigElement() {
    // The editor element is defined in this same file below.
    return document.createElement("bsm-command-card-editor");
  }

  static getStubConfig() {
    // Default config when added via UI
    return {
      title: "Send Command" // Default title
      // No device_id or command needed here, they are selected/entered in the card UI
    };
  }

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
      .card-content { flex-grow: 1; padding: 16px; padding-bottom: 8px; /* Added top padding */ }
      .card-actions { border-top: 1px solid var(--divider-color, #e0e0e0); padding: 8px 16px; text-align: right; }
      ha-selector { display: block; margin-bottom: 16px; }
      /* Use specific text selector for command input */
      ha-selector[label^="Command"] { margin-bottom: 8px; } /* Reduce margin below command */
      .feedback-area { margin-top: 8px; /* Adjusted margin */ min-height: 1.2em; /* Reserve space */ }
      .feedback { color: var(--secondary-text-color); font-size: 0.9em; word-wrap: break-word; }
      .error { color: var(--error-color); font-weight: bold; word-wrap: break-word; }
      .loading-indicator { display: flex; align-items: center; justify-content: flex-start; gap: 8px; margin-top: 8px; /* Adjusted margin */ color: var(--secondary-text-color); font-size: 0.9em; }
    `;
  }

  // Internal storage for hass property
  __hass;
  get hass() { return this.__hass; }
  set hass(hass) {
    const oldHass = this.__hass;
    this.__hass = hass;
    if (oldHass !== hass) {
        // No specific hass-dependent state to update here besides triggering render
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

    if (!config) {
        _LOGGER.error("No configuration provided.");
        throw new Error("Invalid configuration");
    }

    const oldConfig = this.config;
    this.config = { ...config }; // Create a shallow copy


    this.requestUpdate('config', oldConfig);
  }

  render() {
    if (!this.hass) {
      return html`<ha-card header="Send Command"><div class="card-content">Waiting for Home Assistant...</div></ha-card>`;
    }

    // Use config.title with fallback (and optional chaining)
    const cardTitle = this.config?.title || "";

    const deviceSelectorConfig = {
      device: {
        integration: DOMAIN // Filter devices provided by your integration
      }
    };

    // Use ha-textfield directly for more control over appearance and events if needed,
    // or keep ha-selector with text type. Let's stick with ha-selector for consistency for now.
    const textSelectorConfig = {
       text: {} // Simple text input config for ha-selector
    };

    // Determine button disabled state
    const isButtonDisabled = !this._commandText?.trim() || !this._selectedDeviceId || this._isLoading;

    return html`
      <ha-card header="${cardTitle}">
        <div class="card-content">

          <ha-selector
            label="Target Server Device"
            .hass=${this.hass}
            .selector=${deviceSelectorConfig}
            .value=${this._selectedDeviceId}
            @value-changed=${this._handleTargetChanged}
            ?disabled=${this._isLoading}
            required /* Optional: Add visual indication */
          ></ha-selector>

          <ha-selector
            label="Command"
            .hass=${this.hass}
            .selector=${textSelectorConfig}
            .value=${this._commandText}
            @value-changed=${this._handleCommandChanged}
            ?disabled=${this._isLoading}
            required /* Optional: Add visual indication */
          ></ha-selector>
          <!-- Alternative using ha-textfield:
          <ha-textfield
            label="Command (do not include a leading '/')"
            .value=${this._commandText}
            @input=${this._handleCommandInput} // Need this handler if using ha-textfield
            ?disabled=${this._isLoading}
            required
            auto-validate // Optional: Use browser validation
          ></ha-textfield>
          -->

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
            .disabled=${isButtonDisabled}
          ></mwc-button>
        </div>
      </ha-card>
    `;
  }

  _clearMessages() {
      this._feedback = "";
      this._error = "";
      // No need to call requestUpdate here if it's called by the parent function
  }

  _handleTargetChanged(ev) {
      ev.stopPropagation();
      this._clearMessages();
      const deviceId = ev.detail.value; // ha-selector for device returns device_id string
      this._selectedDeviceId = deviceId || null;
      _LOGGER.debug("Target device ID selected:", this._selectedDeviceId);
      // LitElement handles property updates; requestUpdate might be needed if button state depended directly
      // this.requestUpdate('_selectedDeviceId'); // Usually not needed unless explicitly calculating something
  }

  _handleCommandChanged(ev) {
      ev.stopPropagation();
      this._clearMessages();
      this._commandText = ev.detail.value || "";
      // LitElement handles property updates
      // this.requestUpdate('_commandText'); // Usually not needed
  }

  /* Example handler if using ha-textfield instead of ha-selector */
  // _handleCommandInput(ev) {
  //   ev.stopPropagation();
  //   this._clearMessages();
  //   this._commandText = ev.target.value || "";
  //   this.requestUpdate('_commandText'); // May need update for button state
  // }

  async _callService(serviceName, serviceData, operationFeedback) {
    this._isLoading = true;
    this._clearMessages(); // Clear previous messages before new operation
    this.requestUpdate(); // Update to show loading indicator

    try {
      _LOGGER.debug(`Calling ${DOMAIN}.${serviceName} with data: %o`, serviceData);
      await this.hass.callService(DOMAIN, serviceName, serviceData);
      this._feedback = operationFeedback || "Operation successful.";
      return true; // Indicate success
    } catch (err) {
      _LOGGER.error(`Error calling ${DOMAIN}.${serviceName} service:`, err);
       // More robust error message parsing
      let message = "An unknown error occurred. Check Home Assistant logs.";
      if (err instanceof Error) {
          message = err.message;
      } else if (typeof err === 'object' && err !== null && err.error) { // HA Core error format
          message = err.error;
      } else if (typeof err === 'object' && err !== null && err.message) { // Frontend error format?
          message = err.message;
      } else if (typeof err === 'string') {
          message = err;
      }
      this._error = `Error: ${message}`;
      return false; // Indicate failure
    } finally {
      this._isLoading = false;
      this.requestUpdate(); // Update to hide loading indicator and show feedback/error
    }
  }

  async _sendCommand() {
    // Use optional chaining and trim() for safer checks
    if (!this._selectedDeviceId) {
        this._error = "Error: Please select a target server device.";
        this._feedback = "";
        this.requestUpdate();
        return;
    }
     if (!this._commandText?.trim()) {
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
        // Provide clearer success feedback
        `Command sent successfully to device ${this._selectedDeviceId}.`
        // Or keep the truncated command if preferred:
        // `Command "${commandToSend.substring(0, 30)}${commandToSend.length > 30 ? '...' : ''}" sent successfully.`
    );

    if (success) {
      this._commandText = ""; // Clear input field on successful send
      // Explicitly request update to clear the text field in the UI
      this.requestUpdate('_commandText');
    }
    // No need for final requestUpdate here, it's handled in _callService's finally block
  }

  // Provide a reasonable default size
  getCardSize() { return 3; }
}

customElements.define("bsm-command-card", BsmCommandCard);

class BsmCommandCardEditor extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      _config: { type: Object, state: true },
    };
  }

  setConfig(config) {
    this._config = config;
  }

  _valueChanged(ev) {
    if (!this._config || !this.hass) {
      return;
    }
    const target = ev.target;
    // Use deep copy only if config might have nested objects you modify,
    // otherwise shallow copy is fine for simple key-value changes.
    const newConfig = { ...this._config };

    const configKey = target.configValue;

    if (target.value === "" && configKey === "title") { // Only delete if it's the optional title
      delete newConfig[configKey];
    } else {
      newConfig[configKey] = target.value;
    }

    fireEvent(this, "config-changed", { config: newConfig });
  }

  render() {
    if (!this.hass || !this._config) {
      return html``;
    }

    // Editor UI: Just the title field
    return html`
      <ha-textfield
        label="Card Title (Optional)"
        .value=${this._config.title || ""}
        .configValue=${"title"}
        @input=${this._valueChanged}
        helper="Overrides the default card title"
        ?helper-persistent=${true} /* Keep helper text visible */
      ></ha-textfield>
    `;
  }

  static get styles() {
    return css`
      ha-textfield {
        display: block;
        margin-bottom: 16px;
      }
    `;
  }
}

customElements.define("bsm-command-card-editor", BsmCommandCardEditor);


// --- Keep the preview registration ---
window.customCards = window.customCards || [];
window.customCards.push({
  type: "bsm-command-card",
  name: "Send Command Card",
  description: "Send a command to a Bedrock Server Manager managed server.",
  preview: true,
});

// --- Use the logger for the final confirmation ---
_LOGGER.info(`%c BSM-COMMAND-CARD %c LOADED (incl. editor) %c`, "color: orange; font-weight: bold; background: black", "color: white; font-weight: bold; background: dimgray", "");