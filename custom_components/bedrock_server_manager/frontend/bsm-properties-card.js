import { LitElement, html, css } from "https://unpkg.com/lit-element@^2.0.0/lit-element.js?module";

// Define _LOGGER or use console
const _LOGGER = {
    debug: (...args) => console.debug("BSM_PROP_CARD:", ...args),
    info: (...args) => console.info("BSM_PROP_CARD:", ...args),
    warn: (...args) => console.warn("BSM_PROP_CARD:", ...args),
    error: (...args) => console.error("BSM_PROP_CARD:", ...args),
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


const EDITABLE_PROPERTIES = [
    "server-name", "level-name", "gamemode", "difficulty", "allow-cheats", "max-players",
    "online-mode", "default-player-permission-level", "view-distance",
    "tick-distance", "level-seed", "texturepack-required",
    "server-port", "server-portv6", "enable-lan-visibility", "allow-list"
];

// Helper function to safely get properties
function getProperty(obj, key, defaultValue = undefined) {
  return obj?.[key] !== undefined && obj?.[key] !== null ? obj[key] : defaultValue;
}


class BsmPropertiesCard extends LitElement {

  // --- UI CONFIG METHODS ---
  static async getConfigElement() {
    return document.createElement("bsm-properties-card-editor");
  }
  static getStubConfig() {
    return { title: "Server Properties" }; // Default title
  }
  // --- END UI CONFIG METHODS ---


  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      // This variable name is fine, but it refers to the sensor holding the properties
      _selectedStatusEntityId: { state: true },
      _currentProperties: { state: true }, // Properties loaded from sensor state's 'server_properties' attribute
      _editValues: { state: true }, // Staged edits
      _isLoading: { state: true },
      _error: { state: true },
      _feedback: { state: true },
    };
  }

  // --- STYLES (Unchanged) ---
  static get styles() {
    return css`
      :host { display: block; }
      ha-card { display: flex; flex-direction: column; height: 100%; }
      .card-content { flex-grow: 1; padding: 16px; }
      .card-actions { border-top: 1px solid var(--divider-color, #e0e0e0); padding: 8px 16px; text-align: right; }
      .property-grid {
        display: grid;
        grid-template-columns: minmax(150px, 1fr) 2fr;
        align-items: center;
        row-gap: 8px;
        column-gap: 16px;
        margin-top: 16px;
      }
      .property-editor {
         display: contents;
      }
       .property-editor > label {
        text-align: left;
        font-size: 0.95em;
        color: var(--primary-text-color);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        padding-right: 8px;
        grid-column: 1;
      }
      .property-editor > ha-selector {
        width: 100%;
        grid-column: 2;
      }
      .feedback-area { margin-top: 16px; min-height: 1.2em; }
      .error { color: var(--error-color); font-weight: bold; }
      .feedback { color: var(--secondary-text-color); font-size: 0.9em; }
      .loading-indicator { display: flex; align-items: center; justify-content: flex-start; gap: 8px; margin-top:16px; color: var(--secondary-text-color); font-size: 0.9em; }
      /* Select the correct selector */
      ha-selector[label="Select Server's Level Name Sensor"] {
        display: block;
        margin-bottom: 16px;
      }
      .property-editor > ha-selector::part(label) {
         display: none;
      }
    `;
  }
  // --- END STYLES ---

  __hass;
  get hass() { return this.__hass; }
  set hass(hass) {
    const oldHass = this.__hass;
    this.__hass = hass;

    let updateNeeded = false;

    if (!hass) {
      _LOGGER.warn("Hass object became undefined.");
      if (oldHass) updateNeeded = true;
      if (updateNeeded) this.requestUpdate('hass', oldHass);
      return;
    }

    if (hass !== oldHass) updateNeeded = true;

    if (this._selectedStatusEntityId) {
      const stateObj = hass.states[this._selectedStatusEntityId];
      const oldStateObj = oldHass?.states[this._selectedStatusEntityId];

      if (stateObj) {
        // --- Compare the nested server_properties attribute ---
        const currentPropsAttr = stateObj.attributes?.server_properties;
        const oldPropsAttr = oldStateObj?.attributes?.server_properties;

        if (JSON.stringify(currentPropsAttr ?? null) !== JSON.stringify(oldPropsAttr ?? null)) {
          _LOGGER.debug("Hass update detected server_properties change for:", this._selectedStatusEntityId);
          const oldProps = this._currentProperties;
          this._loadProperties(stateObj); // Reload properties
          if(JSON.stringify(oldProps ?? {}) !== JSON.stringify(this._currentProperties ?? {})) {
              updateNeeded = true;
          }
        }
        // --- End nested comparison ---
      } else { // Entity disappeared
        if (oldStateObj || (!this._error && this._feedback !== this._initialFeedbackMessage)) {
          _LOGGER.warn("Selected sensor %s disappeared or not found after being selected.", this._selectedStatusEntityId);
          this._resetSelectionRelatedState(
            "",
            `Selected sensor ${this._selectedStatusEntityId} is no longer available.`
          );
          updateNeeded = true;
        }
      }
    } else { // No entity selected
        const isDefaultState = Object.keys(this._currentProperties ?? {}).length === 0 &&
                               !this._error &&
                               (this._feedback === this._initialFeedbackMessage || !this._feedback);
        if (!isDefaultState) {
            _LOGGER.debug("No entity selected. Resetting to default feedback state.");
            this._resetSelectionRelatedState(this._initialFeedbackMessage);
             updateNeeded = true;
        }
    }
    if (updateNeeded) {
        this.requestUpdate('hass', oldHass);
    }
  }



  constructor() {
    super();
    // Adjusted initial message slightly
    this._initialFeedbackMessage = "Select the sensor holding server properties.";
    this._selectedStatusEntityId = null;
    this._isLoading = false;
    this._resetSelectionRelatedState(this._initialFeedbackMessage);
    _LOGGER.debug("BSM Properties Card constructor finished.");
  }


  setConfig(config) {
    _LOGGER.debug("setConfig called with:", config);
    if (!config) {
      _LOGGER.error("No configuration provided.");
      throw new Error("Invalid configuration");
    }
    const oldConfig = this.config;
    this.config = { ...config };
    this.requestUpdate('config', oldConfig);
  }
  // --- END setConfig ---

  // --- _resetSelectionRelatedState (Unchanged) ---
  _resetSelectionRelatedState(feedbackMessage = "", error = null) {
    _LOGGER.debug("Resetting selection-related state. Feedback:", feedbackMessage, "Error:", error);
    this._currentProperties = {};
    this._editValues = {};
    this._error = error;
    this._feedback = feedbackMessage;
  }
  // --- END _resetSelectionRelatedState ---


  _handleEntitySelection(entityId) {
    _LOGGER.debug(`_handleEntitySelection called with entityId: ${entityId}`);
    if (entityId === this._selectedStatusEntityId) {
      _LOGGER.debug("Entity selection unchanged.");
      return;
    }

    this._selectedStatusEntityId = entityId || null;
    this._resetSelectionRelatedState(
        this._selectedStatusEntityId ? "Loading properties..." : this._initialFeedbackMessage,
        null
    );
    this.requestUpdate(); // Show feedback/loading

    if (!this._selectedStatusEntityId) {
      _LOGGER.debug("Entity deselected.");
      return;
    }

    if (!this.hass) {
        _LOGGER.warn("Hass object not available during entity selection.");
        this._error = "Home Assistant data not yet available.";
        this._feedback = "";
        this.requestUpdate();
        return;
    }

    const stateObj = this.hass.states[this._selectedStatusEntityId];
    if (stateObj) {
        _LOGGER.debug("Entity %s found, loading properties.", this._selectedStatusEntityId);
        this._loadProperties(stateObj); // Load properties from the nested attribute
        if (!this._error) this._feedback = ""; // Clear "Loading..." on success
    } else {
        _LOGGER.warn(`Selected entity ${this._selectedStatusEntityId} not found in current HASS states.`);
        this._error = `Selected entity ${this._selectedStatusEntityId} could not be found.`;
        this._feedback = "";
    }
    this.requestUpdate();
  }

  _loadProperties(stateObj) {
     // Check stateObj and attributes exist
     if (!stateObj?.attributes) {
        const entityId = stateObj?.entity_id || this._selectedStatusEntityId;
        _LOGGER.warn("State object missing attributes for %s", entityId);
        this._error = `Selected sensor (${entityId}) has no attributes. Cannot load properties.`;
        this._currentProperties = {}; this._editValues = {};
        return; // Exit, caller will requestUpdate
     }

     // Access the nested 'server_properties' object <<< CORRECT ACCESS
     const properties = stateObj.attributes.server_properties; // Use correct key from screenshot
     _LOGGER.debug(`_loadProperties: Examining 'server_properties' attribute for ${stateObj.entity_id}:`, JSON.stringify(properties));


     if (properties && typeof properties === 'object' && Object.keys(properties).length > 0) {
        // Compare the received nested object with the current state
        const newPropsString = JSON.stringify(properties);
        const currentPropsString = JSON.stringify(this._currentProperties ?? {});

        if (newPropsString !== currentPropsString) {
             _LOGGER.debug("Loading new/updated server_properties from state for %s", stateObj.entity_id);
             this._currentProperties = { ...properties }; // Copy the nested object
             this._editValues = { ...properties }; // Reset edits to match current state
             this._error = null; // Clear previous errors if properties load
        } else {
             _LOGGER.debug("'server_properties' attribute unchanged or edits in progress, not overwriting _editValues for %s", stateObj.entity_id);
        }
     } else {
        // Adjusted warning message for clarity
        _LOGGER.warn("'server_properties' attribute missing, not an object, or empty on %s", stateObj.entity_id);
        this._error = `'server_properties' attribute is missing, invalid, or empty on selected sensor (${stateObj.entity_id}).`;
        this._currentProperties = {}; this._editValues = {};
     }
  }

  _renderPropertySelector(propKey) {
    const currentValue = getProperty(this._currentProperties, propKey);
    const editValue = getProperty(this._editValues, propKey, currentValue);
    let selectorConfig = {};
    let label = propKey.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    switch (propKey) {
        case "server-name": case "level-name": case "level-seed":
            selectorConfig = { text: {} }; break;
        case "gamemode":
            selectorConfig = { select: { options: ["survival", "creative", "adventure", "spectator"], mode: "dropdown" } }; break;
        case "difficulty":
            selectorConfig = { select: { options: ["peaceful", "easy", "normal", "hard"], mode: "dropdown" } }; break;
        case "allow-cheats": case "online-mode": case "texturepack-required": case "enable-lan-visibility": case "allow-list":
            selectorConfig = { boolean: {} }; break;
        case "max-players": case "server-port": case "server-portv6": case "view-distance": case "tick-distance":
            let minVal = 0, maxVal = 65535, stepVal = 1, mode = "box";
            if (propKey === 'max-players') { minVal = 1; maxVal = 200; }
            else if (propKey === 'view-distance') { minVal = 3; maxVal = 32; mode = "slider"; }
            else if (propKey === 'tick-distance') { minVal = 4; maxVal = 12; }
            else if (propKey === 'server-port' || propKey === 'server-portv6') { minVal = 1; maxVal = 65535;}
            selectorConfig = { number: { min: minVal, max: maxVal, step: stepVal, mode: mode } };
            break;
        case "default-player-permission-level":
            selectorConfig = { select: { options: ["visitor", "member", "operator"], mode: "dropdown" } }; break;
        default:
            _LOGGER.warn("Rendering attempted for unknown property key:", propKey);
            return html`<!-- Unknown property: ${propKey} -->`;
    }
    let valueForSelector = editValue;
    if (selectorConfig.boolean) {
        valueForSelector = typeof editValue === 'boolean' ? editValue : String(editValue).toLowerCase() === 'true';
    }
    else if (selectorConfig.number) {
        if (typeof editValue === 'string') {
            const trimmed = editValue.trim();
            const num = Number(trimmed);
            valueForSelector = (trimmed === '' || isNaN(num)) ? undefined : num;
        } else if (typeof editValue !== 'number' || isNaN(editValue)) {
             valueForSelector = undefined;
        }
    }
    else {
        valueForSelector = String(editValue ?? '');
    }
    return html`
      <div class="property-editor" title=${`Current saved value: ${currentValue ?? 'Not set'}`}>
        <label for=${propKey}>${label}</label>
        <ha-selector
          id=${propKey}
          .hass=${this.hass}
          .selector=${selectorConfig}
          .value=${valueForSelector}
          .label=${label}
          @value-changed=${(ev) => this._handleValueChange(propKey, ev.detail.value)}
          ?disabled=${this._isLoading}
        ></ha-selector>
      </div>
    `;
  }

  _handleValueChange(propKey, newValue) {
      _LOGGER.debug(`Value changed for ${propKey}:`, newValue, `(Type: ${typeof newValue})`);
      this._editValues = { ...this._editValues, [propKey]: newValue };
      this._error = null;
      this.requestUpdate('_editValues');
  }

  render() {
    if (!this.hass) {
      return html`<ha-card><div class="card-content">Waiting for Home Assistant...</div></ha-card>`;
    }

    const cardTitle = this.config?.title || "Server Properties Manager";

    // Selector should target sensors potentially holding server_properties
    const entitySelectorConfig = {
      entity: { integration: DOMAIN, domain: "sensor" }
    };

    // Check based on _currentProperties which is loaded from the nested attribute
    const canDisplayProperties = this._selectedStatusEntityId && !this._error && Object.keys(this._currentProperties ?? {}).length > 0;
    let hasChanges = false;
    if (canDisplayProperties) {
        hasChanges = EDITABLE_PROPERTIES.some(key => {
             if (this._currentProperties.hasOwnProperty(key)) {
                 const currentVal = getProperty(this._currentProperties, key);
                 if (this._editValues.hasOwnProperty(key)) {
                     const editedVal = this._editValues[key];
                     return String(currentVal ?? '') !== String(editedVal ?? '');
                 }
             }
             return false;
        });
    }

    return html`
      <ha-card header="${cardTitle}">
        <div class="card-content">
          <ha-selector
            label="Select Server's Level Name Sensor"
            .hass=${this.hass}
            .selector=${entitySelectorConfig}
            .value=${this._selectedStatusEntityId}
            @value-changed=${(ev) => this._handleEntitySelection(ev.detail.value)}
            ?disabled=${this._isLoading}
            required
          ></ha-selector>

          <div class="feedback-area">
            ${!this._isLoading && this._feedback ? html`<div class="feedback">${this._feedback}</div>` : ""}
            ${!this._isLoading && this._error ? html`<div class="error">${this._error}</div>` : ""}
          </div>

          ${canDisplayProperties ? html`
            <div class="property-grid">
                ${EDITABLE_PROPERTIES
                    // Filter checks _currentProperties loaded from nested attribute
                    .filter(propKey => this._currentProperties.hasOwnProperty(propKey))
                    .map(propKey => this._renderPropertySelector(propKey))
                }
            </div>
          ` : ''}

          ${this._isLoading && this._selectedStatusEntityId ? html`<div class="loading-indicator"><ha-circular-progress indeterminate size="small"></ha-circular-progress> Saving changes...</div>` : ""}
        </div>

        ${canDisplayProperties ? html`
            <div class="card-actions">
              <mwc-button
                label="Save Changes"
                .disabled=${!hasChanges || this._isLoading}
                @click=${this._saveProperties}
                title=${!hasChanges ? "No changes detected" : "Save modified properties"}
              ></mwc-button>
            </div>
        ` : ''}
      </ha-card>
    `;
  }
  // --- END REVERTED render ---

  // --- _getTargetDeviceId (Unchanged) ---
  _getTargetDeviceId() {
    if (!this.hass || !this._selectedStatusEntityId) {
        _LOGGER.warn("_getTargetDeviceId: HASS object or selected entity ID is not available.");
        return null;
    }
    const entityId = this._selectedStatusEntityId;
    const stateObj = this.hass.states[entityId];
    const entityRegEntry = this.hass.entities?.[entityId];
    const regDeviceId = entityRegEntry?.device_id;
    if (regDeviceId && typeof regDeviceId === 'string' && regDeviceId.trim() !== '') {
        _LOGGER.debug("_getTargetDeviceId: Found device_id in hass.entities for %s: %s", entityId, regDeviceId);
        return regDeviceId.trim();
    }
    const attrDeviceId = stateObj?.attributes?.device_id;
     if (attrDeviceId && typeof attrDeviceId === 'string' && attrDeviceId.trim() !== '') {
        _LOGGER.debug("_getTargetDeviceId: Found device_id in state attributes for %s: %s", entityId, attrDeviceId);
        return attrDeviceId.trim();
    }
    _LOGGER.error("_getTargetDeviceId: Could not determine a valid device_id for entity %s.", entityId);
    return null;
  }
  // --- END _getTargetDeviceId ---

  // --- _callService (Unchanged) ---
  async _callService(serviceName, serviceData, operationFeedback) {
    this._isLoading = true; this._error = null; this._feedback = "";
    this.requestUpdate();
    try {
      _LOGGER.debug(`Calling ${DOMAIN}.${serviceName} with data: %o`, serviceData);
      await this.hass.callService(DOMAIN, serviceName, serviceData);
      this._feedback = operationFeedback || "Operation successful.";
      return true;
    } catch (err) {
      _LOGGER.error(`Error calling ${DOMAIN}.${serviceName} service:`, err);
       let message = "An unknown error occurred. Check HA logs.";
       if (err instanceof Error) message = err.message;
       else if (typeof err === 'object' && err !== null && err.error) message = err.error;
       else if (typeof err === 'object' && err !== null && err.message) message = err.message;
       else if (typeof err === 'string') message = err;
       this._error = `Error: ${message}`;
      return false;
    } finally {
      this._isLoading = false; this.requestUpdate();
    }
  }
  // --- END _callService ---

  // --- _saveProperties (Unchanged) ---
  async _saveProperties() {
    const targetDeviceId = this._getTargetDeviceId();
    if (!targetDeviceId) {
        this._error = "Error: Could not determine target device ID from the selected sensor.";
        this._feedback = ""; this.requestUpdate(); return;
    }
    const changedProperties = {}; let actuallyChanged = false;
    for (const key of EDITABLE_PROPERTIES) {
        if (this._currentProperties.hasOwnProperty(key)) {
             const originalValue = getProperty(this._currentProperties, key);
             if (this._editValues.hasOwnProperty(key)) {
                 const editedValue = this._editValues[key];
                 if (String(originalValue ?? '') !== String(editedValue ?? '')) {
                     changedProperties[key] = editedValue; actuallyChanged = true;
                 }
             }
        }
    }
    if (!actuallyChanged) {
      this._error = "No changes detected to save."; this._feedback = "";
      this.requestUpdate(); return;
    }
    const success = await this._callService(
        "update_properties", { device_id: targetDeviceId, properties: changedProperties },
        "Properties update requested. Changes will reflect after the next server poll or restart."
    );
    if (success) {
      this._currentProperties = { ...this._currentProperties, ...changedProperties };
      this._editValues = { ...this._currentProperties };
    }
  }
  // --- END _saveProperties ---

  // --- getCardSize (Unchanged) ---
  getCardSize() {
    let numPropsRendered = 0;
    if (this._selectedStatusEntityId && !this._error && Object.keys(this._currentProperties ?? {}).length > 0) {
        numPropsRendered = EDITABLE_PROPERTIES.filter(propKey => this._currentProperties.hasOwnProperty(propKey)).length;
    }
    return Math.max(3, 2 + Math.ceil(numPropsRendered / 2) + (numPropsRendered > 0 ? 1 : 0));
  }
  // --- END getCardSize ---
}

customElements.define("bsm-properties-card", BsmPropertiesCard);


// --- EDITOR ELEMENT DEFINITION (Unchanged) ---
class BsmPropertiesCardEditor extends LitElement {
  static get properties() { return { hass: { type: Object }, _config: { type: Object, state: true } }; }
  setConfig(config) { this._config = config; }
  _valueChanged(ev) {
    if (!this._config || !this.hass) return;
    const target = ev.target; const newConfig = { ...this._config };
    const configKey = target.configValue;
    if (target.value === "" && configKey === "title") { delete newConfig[configKey]; }
    else { newConfig[configKey] = target.value; }
    fireEvent(this, "config-changed", { config: newConfig });
  }
  render() {
    if (!this.hass || !this._config) return html``;
    return html`
      <ha-textfield
        label="Card Title (Optional)"
        .value=${this._config.title || ""}
        .configValue=${"title"}
        @input=${this._valueChanged}
        helper="Overrides the default card title"
      ></ha-textfield>
    `;
  }
  static get styles() { return css`ha-textfield { display: block; margin-bottom: 16px; }`; }
}
customElements.define("bsm-properties-card-editor", BsmPropertiesCardEditor);
// --- END EDITOR ELEMENT DEFINITION ---


// --- WINDOW REGISTRATION (Unchanged) ---
window.customCards = window.customCards || [];
window.customCards.push({
  type: "bsm-properties-card",
  name: "Server Properties Card",
  description: "View and edit server.properties for a selected Bedrock server.",
  preview: true,
});
_LOGGER.info(`%c BSM-PROPERTIES-CARD %c LOADED (incl. editor) %c`, "color: blue; font-weight: bold; background: white", "color: white; font-weight: bold; background: dimgray", "");
// --- END WINDOW REGISTRATION ---