// custom_components/bedrock_server_manager/frontend/bsm-allowlist-card.js
import { LitElement, html, css } from "https://unpkg.com/lit-element@^2.0.0/lit-element.js?module";

// Define _LOGGER or use console
const _LOGGER = {
    debug: (...args) => console.debug("BSM_AL_CARD:", ...args),
    info: (...args) => console.info("BSM_AL_CARD:", ...args),
    warn: (...args) => console.warn("BSM_AL_CARD:", ...args),
    error: (...args) => console.error("BSM_AL_CARD:", ...args),
};

const DOMAIN = "bedrock_server_manager";

// Helper function to fire events
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


class BsmAllowlistCard extends LitElement {

  static async getConfigElement() {
    return document.createElement("bsm-allowlist-card-editor");
  }

  static getStubConfig() {
    // Provides a default config when the card is added through the UI
    return {
      title: "Server Allowlist Manager"
    };
  }


  static get properties() {
    return {
      hass: { type: Object }, // Custom setter/getter used
      config: { type: Object },
      _selectedStatusEntityId: { state: true },
      _currentAllowlist: { state: true }, // Array of player name strings
      _newPlayerName: { state: true },
      _addIgnoresLimit: { state: true }, // State for the toggle
      _isLoading: { state: true },
      _error: { state: true },
      _feedback: { state: true },
    };
  }

  static get styles() {
    return css`
      :host { display: block; } /* Ensure the card itself behaves as a block */
      ha-card { display: flex; flex-direction: column; height: 100%; }
      .card-content { padding: 16px; flex-grow: 1; }
      ha-selector { display: block; margin-bottom: 16px; }
      h4 { margin: 16px 0 8px 0; padding-bottom: 4px; border-bottom: 1px solid var(--divider-color); font-weight: 500; }
      .allowlist-section ul { list-style: none; padding: 0; margin: 0; }
      .allowlist-section li { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; }
      .allowlist-section li:not(:last-child) { border-bottom: 1px solid var(--divider-color); }
      .allowlist-section span { flex-grow: 1; margin-right: 8px; word-break: break-all; } /* Added word-break */
      .add-player-container { margin-top: 24px; }
      .add-player-controls { display: flex; align-items: flex-end; gap: 8px; margin-bottom: 8px; }
      .add-player-controls ha-textfield { flex-grow: 1; }
      .add-player-options { display: flex; align-items: center; gap: 8px; cursor: pointer; margin-top: 8px; }
      .add-player-options label { color: var(--secondary-text-color); font-size: 0.9em; user-select: none; } /* Added user-select: none */
      .loading, .error, .feedback { padding: 8px 0; text-align: left; margin-top: 8px; }
      .error { color: var(--error-color); font-weight: bold; }
      .feedback { color: var(--secondary-text-color); font-size: 0.9em; }
      .loading { display: flex; justify-content: center; align-items: center; padding: 16px; gap: 8px; }
      mwc-icon-button { color: var(--secondary-text-color); }
    `;
  }

  // Internal storage for hass property
  __hass;
  get hass() { return this.__hass; }
  set hass(hass) {
    const oldHass = this.__hass;
    this.__hass = hass;

    if (!hass) {
      _LOGGER.warn("Hass object became undefined. Card may not function correctly.");
      this.requestUpdate('hass', oldHass);
      return;
    }

    if (this._selectedStatusEntityId) {
      const stateObj = hass.states[this._selectedStatusEntityId];
      const oldStateObj = oldHass?.states[this._selectedStatusEntityId];

      if (stateObj) { // Entity exists
        const currentAllowlistAttr = stateObj.attributes?.allowed_players;
        const oldAllowlistAttr = oldStateObj?.attributes?.allowed_players;

        // Use optional chaining and nullish coalescing for safer checks
        if (stateObj !== oldStateObj || JSON.stringify(currentAllowlistAttr ?? null) !== JSON.stringify(oldAllowlistAttr ?? null)) {
          _LOGGER.debug("Hass update for selected entity:", this._selectedStatusEntityId);
          this._loadAllowlist(stateObj);
        }
      } else {
        if (oldStateObj || (!this._error && this._feedback !== this._initialFeedbackMessage)) {
          _LOGGER.warn("Allowlist entity %s disappeared or not found after being selected.", this._selectedStatusEntityId);
          this._resetSelectionRelatedState(
            "",
            `Status entity ${this._selectedStatusEntityId} is no longer available or could not be found.`
          );
        }
      }
    } else {
       // Use optional chaining for safer checks
      const isDefaultState = (this._currentAllowlist?.length ?? 0) === 0 &&
                             !this._error &&
                             (this._feedback === this._initialFeedbackMessage || !this._feedback);
      if (!isDefaultState) {
        _LOGGER.debug("No entity selected. Resetting to default feedback state.");
        this._resetSelectionRelatedState(this._initialFeedbackMessage);
      }
    }
    this.requestUpdate('hass', oldHass);
  }

  constructor() {
    super();
    this._initialFeedbackMessage = "Select a server's allowlist sensor.";
    this._selectedStatusEntityId = null;
    this._isLoading = false;
    this._addIgnoresLimit = false;
    this._resetSelectionRelatedState(this._initialFeedbackMessage);
    _LOGGER.debug("BSM Allowlist Card constructor finished.");
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


  _resetSelectionRelatedState(feedbackMessage = "", error = null) {
    _LOGGER.debug("Resetting selection-related state. Feedback:", feedbackMessage, "Error:", error);
    this._currentAllowlist = [];
    this._newPlayerName = "";
    this._addIgnoresLimit = false;
    this._error = error;
    this._feedback = feedbackMessage;
  }

  _handleEntitySelection(entityId) {
    _LOGGER.debug(`_handleEntitySelection called with entityId: ${entityId}`);

    // Use nullish coalescing for safety
    if (entityId === this._selectedStatusEntityId) {
      _LOGGER.debug("Entity selection unchanged.");
      return;
    }

    if (!entityId) {
      _LOGGER.debug("Entity deselected via selector.");
      this._selectedStatusEntityId = null;
      this._resetSelectionRelatedState(this._initialFeedbackMessage);
      this.requestUpdate();
      return;
    }

    this._selectedStatusEntityId = entityId;
    this._resetSelectionRelatedState("Loading allowlist...", null);

    if (!this.hass) {
        _LOGGER.warn("Hass object not available during entity selection.");
        this._error = "Home Assistant data not yet available. Please wait or refresh.";
        this._feedback = "";
        this.requestUpdate();
        return;
    }

    const stateObj = this.hass.states[this._selectedStatusEntityId];
    if (stateObj) {
        _LOGGER.debug("Entity %s found, loading allowlist.", this._selectedStatusEntityId);
        this._loadAllowlist(stateObj);
        if (!this._error) {
            this._feedback = "";
        }
    } else {
        _LOGGER.warn(`Selected entity ${this._selectedStatusEntityId} not found in current HASS states.`);
        this._resetSelectionRelatedState(
            "",
            `Selected entity ${this._selectedStatusEntityId} could not be found. Please check the entity ID.`
        );
    }
    this.requestUpdate();
  }

  _loadAllowlist(stateObj) {
     // Use optional chaining
     if (!stateObj?.attributes) {
        _LOGGER.warn("State object missing attributes for %s", stateObj?.entity_id ?? 'unknown entity');
        this._error = `Selected sensor (${stateObj?.entity_id ?? 'unknown entity'}) has no attributes needed for allowlist.`;
        this._feedback = "";
        this._currentAllowlist = [];
        return;
     }
     // Use optional chaining and nullish coalescing
     const allowlist = stateObj.attributes.allowed_players;
     if (allowlist && Array.isArray(allowlist)) {
         if (JSON.stringify(allowlist) !== JSON.stringify(this._currentAllowlist ?? [])) {
             _LOGGER.debug("Loading new allowlist for %s: %o", stateObj.entity_id, allowlist);
             this._currentAllowlist = [...allowlist];
             this._error = null;
         }
     } else {
        _LOGGER.warn("'allowed_players' attribute missing or not an array on %s", stateObj.entity_id);
        this._error = `'allowed_players' attribute missing or invalid on selected sensor (${stateObj.entity_id}).`;
        this._feedback = "";
        this._currentAllowlist = [];
     }
  }

  _handleAddInput(ev) {
      this._newPlayerName = ev.target.value;
      if (this._error) this._error = "";
      // Request update to potentially re-enable/disable add button
      this.requestUpdate('_newPlayerName');
  }

  _handleIgnoreLimitToggle(ev) {
      this._addIgnoresLimit = ev.target.checked;
      _LOGGER.debug("Ignores Player Limit toggle changed:", this._addIgnoresLimit);
  }

  _getTargetDeviceId() {
    if (!this.hass || !this._selectedStatusEntityId) {
        _LOGGER.warn("_getTargetDeviceId: HASS object or selected entity ID is not available.");
        return null;
    }

    const entityId = this._selectedStatusEntityId;
    let deviceId = null;

    // 1. Try from state object attributes (using optional chaining)
    const stateObj = this.hass.states[entityId];
    const deviceIdFromAttr = stateObj?.attributes?.device_id;
    if (typeof deviceIdFromAttr === 'string' && deviceIdFromAttr.trim() !== '') {
        deviceId = deviceIdFromAttr.trim();
        _LOGGER.debug("_getTargetDeviceId: Found device_id in state attributes for %s: %s", entityId, deviceId);
        return deviceId;
    } else if (stateObj?.attributes && 'device_id' in stateObj.attributes) {
        // Log if device_id is present but not a valid string
        _LOGGER.warn("_getTargetDeviceId: 'device_id' found in state attributes for %s, but it's not a non-empty string: %o", entityId, deviceIdFromAttr);
    }

    // 2. Fallback: Try from hass.entities (entity registry)
    // Use optional chaining for safety
    const entityRegistryEntry = this.hass.entities?.[entityId];
    const deviceIdFromRegistry = entityRegistryEntry?.device_id;
    if (typeof deviceIdFromRegistry === 'string' && deviceIdFromRegistry.trim() !== '') {
        deviceId = deviceIdFromRegistry.trim();
        _LOGGER.debug("_getTargetDeviceId: Found device_id in hass.entities for %s: %s", entityId, deviceId);
        return deviceId;
    } else if (entityRegistryEntry && 'device_id' in entityRegistryEntry) {
        // Log if device_id is present in entity registry data but not a valid string
         _LOGGER.warn("_getTargetDeviceId: 'device_id' found in hass.entities for %s, but it's not a non-empty string: %o", entityId, deviceIdFromRegistry);
    }

    _LOGGER.error(
        "_getTargetDeviceId: Could not determine a valid device_id for entity %s. " +
        "Checked state attributes (%s) and hass.entities (%s). State object: %O. Entity registry entry: %O",
        entityId,
        stateObj?.attributes ? 'attributes present' : 'state or attributes missing',
        entityRegistryEntry ? 'registry entry present' : 'registry entry missing',
        stateObj ?? "N/A",
        entityRegistryEntry ?? "N/A"
    );
    return null;
  }

  async _callService(serviceName, serviceData, operationFeedback) {
    this._isLoading = true;
    this._error = null;
    this._feedback = operationFeedback;
    this.requestUpdate();

    try {
      _LOGGER.debug(`Calling ${DOMAIN}.${serviceName} with data: %o`, serviceData);
      await this.hass.callService(DOMAIN, serviceName, serviceData);
      return true;
    } catch (err) {
      _LOGGER.error(`Error calling ${DOMAIN}.${serviceName} service:`, err);
      // More robust error message parsing
      let message = "An unknown error occurred. Check Home Assistant logs.";
      if (err instanceof Error) {
          message = err.message;
      } else if (typeof err === 'object' && err !== null && err.error) {
          message = err.error; // Handle HA specific error objects if applicable
      } else if (typeof err === 'string') {
          message = err;
      }
      this._error = `Error performing operation: ${message}`;
      this._feedback = "";
      return false;
    } finally {
      this._isLoading = false;
      // Ensure UI updates after async operation
      this.requestUpdate();
    }
  }

  async _addPlayer() {
    const targetDeviceId = this._getTargetDeviceId();
    if (!targetDeviceId) {
      this._error = "Cannot add player: Target device ID for the selected server is missing or invalid. Please check the sensor entity's configuration and attributes in Home Assistant.";
      this._feedback = "";
      this.requestUpdate();
      return;
    }
    // Use optional chaining and nullish coalescing for player name checks
    const playerName = this._newPlayerName?.trim() ?? "";
    if (!playerName) {
      this._error = "Please enter a player name to add.";
      this._feedback = "";
      this.requestUpdate();
      return;
    }
     // Use optional chaining and nullish coalescing
    if (this._currentAllowlist?.includes(playerName)) {
        this._error = `'${playerName}' is already on the allowlist.`;
        this._feedback = "";
        this.requestUpdate();
        return;
    }

    const success = await this._callService(
      "add_to_allowlist",
      {
        device_id: targetDeviceId,
        players: [playerName],
        ignores_player_limit: this._addIgnoresLimit
      },
      `Adding '${playerName}'...`
    );

    if (success) {
      this._feedback = `Request sent to add '${playerName}'. The allowlist will update shortly via sensor state.`;
      this._newPlayerName = "";
      // Manually clear the text field visually if needed, although value binding should handle it
      const textField = this.shadowRoot?.querySelector('.add-player-controls ha-textfield');
      if (textField) textField.value = "";
    }
    // Ensure UI updates after state change
    this.requestUpdate();
  }

  async _removePlayer(playerName) {
    if (!playerName) return;

    const targetDeviceId = this._getTargetDeviceId();
    if (!targetDeviceId) {
      this._error = "Cannot remove player: Target device ID for the selected server is missing or invalid. Please check the sensor entity's configuration and attributes in Home Assistant.";
      this._feedback = "";
      this.requestUpdate();
      return;
    }

    const success = await this._callService(
      "remove_from_allowlist",
      {
        device_id: targetDeviceId,
        player_name: playerName
      },
      `Removing '${playerName}'...`
    );

    if (success) {
      this._feedback = `Request sent to remove '${playerName}'. The allowlist will update shortly via sensor state.`;
    }
    // Ensure UI updates after state change
    this.requestUpdate();
  }

  render() {
    if (!this.hass) {
      return html`<ha-card><div class="card-content">Waiting for Home Assistant connection...</div></ha-card>`;
    }

    // Use config.title with fallback
    const cardTitle = this.config?.title || "";

    const entitySelectorConfig = {
      entity: { integration: DOMAIN, domain: "sensor", attribute: "allowed_players" }
    };

    // Use optional chaining and nullish coalescing
    const isPlayerNameInvalid = !(this._newPlayerName?.trim() ?? "");
    const isPlayerAlreadyAdded = this._currentAllowlist?.includes(this._newPlayerName?.trim() ?? "") ?? false;

    return html`
      <ha-card header="${cardTitle}">
        <div class="card-content">
          <ha-selector
            .label=${this._selectedStatusEntityId ? "Selected Server Allowlist Sensor" : "Select Server Allowlist Sensor"}
            .hass=${this.hass}
            .selector=${entitySelectorConfig}
            .value=${this._selectedStatusEntityId}
            @value-changed=${(ev) => this._handleEntitySelection(ev.detail.value)}
          ></ha-selector>

          ${this._isLoading ? html`<div class="loading"><ha-circular-progress indeterminate size="small"></ha-circular-progress> Processing...</div>` : ""}
          ${this._feedback && !this._isLoading ? html`<div class="feedback">${this._feedback}</div>` : ""}
          ${this._error && !this._isLoading ? html`<div class="error">${this._error}</div>` : ""}

          ${this._selectedStatusEntityId && !this._error && !this._isLoading ? html`
            <div class="allowlist-section">
              <h4>Current Allowlist (${this._currentAllowlist?.length ?? 0}):</h4>
              ${(this._currentAllowlist?.length ?? 0) === 0 ? html`<p>Allowlist is empty.</p>` : ''}
              <ul>
                ${(this._currentAllowlist ?? []).map(playerName => html`
                  <li>
                    <span>${playerName}</span>
                    <mwc-icon-button
                      title="Remove ${playerName}"
                      @click=${() => this._removePlayer(playerName)}
                      .disabled=${this._isLoading}
                    >
                      <ha-icon icon="mdi:account-remove-outline"></ha-icon>
                    </mwc-icon-button>
                  </li>
                `)}
              </ul>
            </div>

            <div class="add-player-container">
                <h4>Add Player:</h4>
                <div class="add-player-controls">
                   <ha-textfield
                     label="Player Name to Add"
                     .value=${this._newPlayerName ?? ""}
                     @input=${this._handleAddInput}
                     ?disabled=${this._isLoading}
                     .helper=${isPlayerAlreadyAdded ? "This player is already on the allowlist." : ""}
                     ?helper-persistent=${isPlayerAlreadyAdded}
                     required
                     auto-validate
                     pattern="^[^\\s]+(\\s+[^\\s]+)*$"
                     validationMessage="Player name cannot be empty or have leading/trailing/multiple spaces."
                   ></ha-textfield>
                   <mwc-button
                     label="Add"
                     raised
                     @click=${this._addPlayer}
                     .disabled=${isPlayerNameInvalid || isPlayerAlreadyAdded || this._isLoading}
                   ></mwc-button>
                </div>
                <div class="add-player-options">
                   <ha-switch
                      .checked=${this._addIgnoresLimit}
                      @change=${this._handleIgnoreLimitToggle}
                      ?disabled=${this._isLoading}
                    >
                    </ha-switch>
                    <label @click=${(e) => { e.preventDefault(); if (!this._isLoading) this.shadowRoot.querySelector('.add-player-options ha-switch')?.click(); }}>
                       Ignores Player Limit
                    </label>
                </div>
             </div>
          ` : ''}
          ${this._selectedStatusEntityId && !this._error && this._isLoading ? html`
            <div><!-- Placeholder while loading to prevent layout shift if content would disappear --></div>
          ` : ''}
        </div>
      </ha-card>
    `;
  }

  getCardSize() {
     let size = 2; // Base size for title + selector
     if (this._selectedStatusEntityId && !this._error) {
       size += 1; // For the "Add Player" section title + input
       if (this._currentAllowlist?.length > 0) {
           // Allocate space based on number of players shown
           size += Math.ceil((this._currentAllowlist.length + 1) / 4); // +1 for header, roughly 4 per row height
       } else {
           size += 1; // For the "empty" message + header
       }
       size += 1; // For the add button + toggle area
     } else if (this._error || this._feedback || this._isLoading) {
         size += 1; // Space for status messages
     }
     return Math.max(3, Math.ceil(size)); // Minimum size 3
  }
}

customElements.define("bsm-allowlist-card", BsmAllowlistCard);


class BsmAllowlistCardEditor extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      _config: { type: Object, state: true }, // Internal state for config object
    };
  }

  setConfig(config) {
    // Called by HA editor UI with the current card config
    this._config = config;
  }

  // Handles changes in the editor inputs
  _valueChanged(ev) {
    if (!this._config || !this.hass) {
      return;
    }
    const target = ev.target;
    const newConfig = { ...this._config }; // Create a copy

    // Get the config key from the element's configValue property
    const configKey = target.configValue;

    // Update the value in the new config object
    if (target.value === "") {
      // If the value is empty, remove the key (for optional fields like title)
      delete newConfig[configKey];
    } else {
      newConfig[configKey] = target.value;
    }

    // Fire the event to let HA know the config has changed
    fireEvent(this, "config-changed", { config: newConfig });
  }

  render() {
    if (!this.hass || !this._config) {
      return html``; // Render nothing until hass and config are available
    }

    // Render the editor UI (a simple text field for the title)
    return html`
      <ha-textfield
        label="Card Title (Optional)"
        .value=${this._config.title || ""}
        .configValue=${"title"}
        @input=${this._valueChanged}
      ></ha-textfield>
    `;
  }

  static get styles() {
    // Basic styling for the editor element
    return css`
      ha-textfield {
        display: block;
        margin-bottom: 16px;
      }
    `;
  }
}

customElements.define("bsm-allowlist-card-editor", BsmAllowlistCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "bsm-allowlist-card",
  name: "Server Allowlist Card",
  description: "View and manage the allowlist for a selected Bedrock server.",
  preview: true, // Optional: Set to false if preview doesn't work well without hass
});

// --- Use the logger for the final confirmation ---
_LOGGER.info("%c BSM-ALLOWLIST-CARD %c LOADED (incl. editor) %c", "color: green; font-weight: bold; background: black", "color: white; font-weight: bold; background: dimgray", "");