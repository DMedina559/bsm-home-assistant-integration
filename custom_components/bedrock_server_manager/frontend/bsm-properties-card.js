import { LitElement, html, css } from "https://unpkg.com/lit-element@^2.0.0/lit-element.js?module";

// Define _LOGGER or use console
const _LOGGER = {
    debug: (...args) => console.debug("BSM_PROP_CARD:", ...args),
    info: (...args) => console.info("BSM_PROP_CARD:", ...args),
    warn: (...args) => console.warn("BSM_PROP_CARD:", ...args),
    error: (...args) => console.error("BSM_PROP_CARD:", ...args),
};

const DOMAIN = "bedrock_server_manager";

const EDITABLE_PROPERTIES = [
    "server-name", "level-name", "gamemode", "difficulty", "allow-cheats", "max-players",
    "online-mode", "default-player-permission-level", "view-distance",
    "tick-distance", "level-seed", "texturepack-required",
    "server-port", "server-portv6", "enable-lan-visibility", "allow-list"
];

// Helper function to safely get nested properties (though server_properties is flat here)
function getProperty(obj, key, defaultValue = undefined) {
  return obj && typeof obj === 'object' && key in obj ? obj[key] : defaultValue;
}

class BsmPropertiesCard extends LitElement {

  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _selectedStatusEntityId: { state: true },
      _currentProperties: { state: true },
      _editValues: { state: true },
      _isLoading: { state: true }, // For async operations like saving
      _error: { state: true },
      _feedback: { state: true },
    };
  }

  static get styles() {
    return css`
      :host { display: block; }
      ha-card { display: flex; flex-direction: column; height: 100%; }
      .card-content { flex-grow: 1; padding: 16px; }
      .card-actions { border-top: 1px solid var(--divider-color, #e0e0e0); padding: 8px 16px; text-align: right; }
      .property-editor {
        display: grid;
        grid-template-columns: minmax(150px, 1fr) 2fr; /* Adjusted for better label/control balance */
        align-items: center; /* Vertically align items */
        margin-bottom: 12px; /* Increased spacing */
        column-gap: 16px;
      }
      .property-editor > label {
        text-align: left;
        font-size: 0.95em; /* Slightly larger label */
        color: var(--primary-text-color); /* More prominent label color */
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .property-editor > ha-selector {
        width: 100%; /* Make selector take full width of its grid cell */
      }
      .feedback-area { margin-top: 16px; min-height: 1.2em; }
      .error { color: var(--error-color); font-weight: bold; }
      .feedback { color: var(--secondary-text-color); font-size: 0.9em; }
      .loading-indicator { display: flex; align-items: center; justify-content: flex-start; gap: 8px; margin-top:16px; color: var(--secondary-text-color); font-size: 0.9em; }
      ha-selector { display: block; margin-bottom: 16px; } /* For the main entity selector */
    `;
  }

  __hass;
  set hass(hass) {
    const oldHass = this.__hass;
    this.__hass = hass;

    if (!hass) {
      _LOGGER.warn("Hass object became undefined.");
      this.requestUpdate('hass', oldHass);
      return;
    }

    if (this._selectedStatusEntityId) {
      const stateObj = hass.states[this._selectedStatusEntityId];
      const oldStateObj = oldHass?.states[this._selectedStatusEntityId];

      if (stateObj) { // Entity exists
        const currentPropsAttr = stateObj.attributes?.server_properties;
        const oldPropsAttr = oldStateObj?.attributes?.server_properties; // May be undefined if oldHass or stateObj was undefined

        // Only update if the server_properties attribute itself has changed.
        if (JSON.stringify(currentPropsAttr) !== JSON.stringify(oldPropsAttr)) {
          _LOGGER.debug("Hass update detected server_properties change for:", this._selectedStatusEntityId);
          this._loadProperties(stateObj);
        }
      } else { // Entity does not exist in current hass
        if (oldStateObj || (!this._error && this._feedback !== this._initialFeedbackMessage)) {
          _LOGGER.warn("Status entity %s disappeared or not found after being selected.", this._selectedStatusEntityId);
          this._resetSelectionRelatedState(
            "",
            `Status entity ${this._selectedStatusEntityId} is no longer available.`
          );
        }
      }
    } else { // No entity selected
        const isDefaultState = Object.keys(this._currentProperties).length === 0 &&
                               !this._error &&
                               (this._feedback === this._initialFeedbackMessage || !this._feedback);
        if (!isDefaultState) {
            _LOGGER.debug("No entity selected. Resetting to default feedback state.");
            this._resetSelectionRelatedState(this._initialFeedbackMessage);
        }
    }
    this.requestUpdate('hass', oldHass);
  }
  get hass() { return this.__hass; }

  constructor() {
    super();
    this._initialFeedbackMessage = "Select a server's status sensor to view/edit properties.";
    this._selectedStatusEntityId = null;
    this._isLoading = false;
    this._resetSelectionRelatedState(this._initialFeedbackMessage);
    _LOGGER.debug("BSM Properties Card constructor finished.");
  }

  setConfig(config) {
    _LOGGER.debug("setConfig called with:", config);
    const oldConfig = this.config;
    this.config = config || {};
    this.requestUpdate('config', oldConfig);
  }

  _resetSelectionRelatedState(feedbackMessage = "", error = null) {
    _LOGGER.debug("Resetting selection-related state. Feedback:", feedbackMessage, "Error:", error);
    this._currentProperties = {};
    this._editValues = {};
    this._error = error;
    this._feedback = feedbackMessage;
  }

  _handleEntitySelection(entityId) {
    _LOGGER.debug(`_handleEntitySelection called with entityId: ${entityId}`);

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
    this._resetSelectionRelatedState("Loading properties...", null);
    this.requestUpdate(); // Show "Loading..."

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
        this._loadProperties(stateObj); // This updates _currentProperties, _editValues, _error
        if (!this._error) { // If _loadProperties didn't set an error
            this._feedback = ""; // Clear "Loading properties..."
        }
    } else {
        _LOGGER.warn(`Selected entity ${this._selectedStatusEntityId} not found in current HASS states.`);
        this._resetSelectionRelatedState(
            "",
            `Selected entity ${this._selectedStatusEntityId} could not be found.`
        );
    }
    this.requestUpdate();
  }

  _loadProperties(stateObj) {
     if (!stateObj?.attributes) {
        _LOGGER.warn("State object missing attributes for %s", stateObj.entity_id);
        this._error = `Selected sensor (${stateObj.entity_id}) has no attributes. Cannot load properties.`;
        this._currentProperties = {}; this._editValues = {};
        return;
     }
     const properties = stateObj.attributes.server_properties;
     if (properties && typeof properties === 'object') {
        // Only update if properties actually changed or if editValues is empty (initial load for entity)
        const newPropsString = JSON.stringify(properties);
        const currentPropsString = JSON.stringify(this._currentProperties);

        if (newPropsString !== currentPropsString || Object.keys(this._editValues).length === 0) {
             _LOGGER.debug("Loading new/updated server_properties from state for %s", stateObj.entity_id);
             this._currentProperties = { ...properties };
             this._editValues = { ...properties }; // Reset edits to match current state
             this._error = null; // Clear previous errors if properties load
        } else {
             _LOGGER.debug("server_properties attribute unchanged or edits in progress, not overwriting _editValues for %s", stateObj.entity_id);
        }
     } else {
        _LOGGER.warn("'server_properties' attribute missing or not an object on %s", stateObj.entity_id);
        this._error = `'server_properties' attribute is missing or invalid on selected sensor (${stateObj.entity_id}).`;
        this._currentProperties = {}; this._editValues = {};
     }
  }

  _renderPropertySelector(propKey) {
    const currentValue = getProperty(this._currentProperties, propKey); // Use current value for title
    const editValue = getProperty(this._editValues, propKey, currentValue); // Fallback to current if not in edit
    let selectorConfig = {};
    let label = propKey.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

    // Define selector configurations
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
            let minVal = 0, maxVal = 65535, stepVal = 1; // Defaults
            if (propKey === 'max-players') { minVal = 1; maxVal = 200; } // Common practical max
            else if (propKey === 'view-distance') { minVal = 3; maxVal = 32; } // Bedrock typical range
            else if (propKey === 'tick-distance') { minVal = 4; maxVal = 12; }
            else if (propKey === 'server-port' || propKey === 'server-portv6') { minVal = 1; maxVal = 65535;}
            selectorConfig = { number: { min: minVal, max: maxVal, step: stepVal, mode: "box" } };
            break;
        case "default-player-permission-level":
            selectorConfig = { select: { options: ["visitor", "member", "operator"], mode: "dropdown" } }; break;
        default:
            _LOGGER.warn("Unknown property key for selector:", propKey);
            return html`<div>Unsupported property: ${propKey}</div>`;
    }

    // Prepare value for the selector, ensuring correct type
    let valueForSelector = editValue;
    if (selectorConfig.boolean) {
        valueForSelector = typeof editValue === 'boolean' ? editValue : String(editValue).toLowerCase() === 'true';
    } else if (selectorConfig.number) {
        if (typeof editValue === 'string') {
            const trimmed = editValue.trim();
            if (trimmed === '') {
                valueForSelector = undefined; // Let ha-selector handle empty
            } else {
                const num = Number(trimmed);
                valueForSelector = isNaN(num) ? undefined : num; // If NaN, treat as invalid/empty
            }
        } else if (typeof editValue !== 'number' || isNaN(editValue)) {
             valueForSelector = undefined; // if null, undefined, or already NaN
        }
        // if it's already a valid number, it's fine
    } else if (selectorConfig.select || selectorConfig.text) {
        valueForSelector = String(editValue ?? ''); // Ensure it's a string for text/select
    }


    return html`
      <div class="property-editor" title=${`Current saved value: ${currentValue ?? 'Not set'}`}>
        <label for=${propKey}>${label}</label>
        <ha-selector
          id=${propKey}
          .hass=${this.hass}
          .selector=${selectorConfig}
          .value=${valueForSelector}
          .label=${label} /* Hidden label for accessibility, real label is external */
          @value-changed=${(ev) => this._handleValueChange(propKey, ev.detail.value)}
          ?disabled=${this._isLoading}
        ></ha-selector>
      </div>
    `;
  }

  _handleValueChange(propKey, newValue) {
      _LOGGER.debug(`Value changed for ${propKey}:`, newValue, `(Type: ${typeof newValue})`);
      // Ensure boolean values from ha-selector (which are true booleans) are stored as such
      // For numbers, ha-selector returns numbers or undefined.
      // For text/select, it's strings.
      this._editValues = { ...this._editValues, [propKey]: newValue };
      this._error = null; // Clear error on user input
      // Don't clear general feedback, but specific save feedback will be overwritten on next save
      this.requestUpdate('_editValues'); // Efficiently update only _editValues
  }

  render() {
    if (!this.hass) {
      return html`<ha-card><div class="card-content">Waiting for Home Assistant...</div></ha-card>`;
    }

    const entitySelectorConfig = {
      entity: { integration: DOMAIN, domain: "sensor" }
    };

    const canDisplayProperties = this._selectedStatusEntityId && !this._error && Object.keys(this._currentProperties).length > 0;
    let hasChanges = false;
    if (canDisplayProperties) {
        for (const key of EDITABLE_PROPERTIES) {
            // Compare potentially different types carefully (e.g. boolean true vs string "true")
            const currentVal = getProperty(this._currentProperties, key);
            const editedVal = getProperty(this._editValues, key);
            if (String(currentVal) !== String(editedVal)) { // Simple string comparison for change detection
                hasChanges = true;
                break;
            }
        }
    }

    return html`
      <ha-card header="${this.config.title || "Server Properties Manager"}">
        <div class="card-content">
          <ha-selector
            label="Select Server Status Sensor"
            .hass=${this.hass}
            .selector=${entitySelectorConfig}
            .value=${this._selectedStatusEntityId}
            @value-changed=${(ev) => this._handleEntitySelection(ev.detail.value)}
            ?disabled=${this._isLoading}
          ></ha-selector>

          <div class="feedback-area">
            ${!this._isLoading && this._feedback ? html`<div class="feedback">${this._feedback}</div>` : ""}
            ${!this._isLoading && this._error ? html`<div class="error">${this._error}</div>` : ""}
          </div>

          ${canDisplayProperties ? EDITABLE_PROPERTIES.map(propKey => this._renderPropertySelector(propKey)) : ''}

          ${this._isLoading && this._selectedStatusEntityId ? html`<div class="loading-indicator"><ha-circular-progress indeterminate size="small"></ha-circular-progress> Saving changes...</div>` : ""}
        </div>

        ${canDisplayProperties ? html`
            <div class="card-actions">
              <mwc-button
                label="Save Changes"
                raised
                .disabled=${!hasChanges || this._isLoading}
                @click=${this._saveProperties}
              ></mwc-button>
            </div>
        ` : ''}
      </ha-card>
    `;
  }

  _getTargetDeviceId() {
    // Re-using the robust method from previous examples
    if (!this.hass || !this._selectedStatusEntityId) {
        _LOGGER.warn("_getTargetDeviceId: HASS object or selected entity ID is not available.");
        return null;
    }
    const entityId = this._selectedStatusEntityId;
    const stateObj = this.hass.states[entityId];

    if (stateObj?.attributes?.device_id && typeof stateObj.attributes.device_id === 'string' && stateObj.attributes.device_id.trim() !== '') {
        _LOGGER.debug("_getTargetDeviceId: Found device_id in state attributes for %s: %s", entityId, stateObj.attributes.device_id);
        return stateObj.attributes.device_id.trim();
    }
    if (this.hass.entities?.[entityId]?.device_id && typeof this.hass.entities[entityId].device_id === 'string' && this.hass.entities[entityId].device_id.trim() !== '') {
        _LOGGER.debug("_getTargetDeviceId: Found device_id in hass.entities for %s: %s", entityId, this.hass.entities[entityId].device_id);
        return this.hass.entities[entityId].device_id.trim();
    }
    _LOGGER.error("_getTargetDeviceId: Could not determine a valid device_id for entity %s.", entityId);
    return null;
  }

  async _callService(serviceName, serviceData, operationFeedback) {
    this._isLoading = true;
    this._error = null;
    this._feedback = ""; // Clear previous feedback before showing loading state
    this.requestUpdate();

    try {
      _LOGGER.debug(`Calling ${DOMAIN}.${serviceName} with data: %o`, serviceData);
      await this.hass.callService(DOMAIN, serviceName, serviceData);
      this._feedback = operationFeedback || "Operation successful.";
      return true;
    } catch (err) {
      _LOGGER.error(`Error calling ${DOMAIN}.${serviceName} service:`, err);
      const errorMessage = err.body?.message || err.message || "An unknown error occurred. Check HA logs.";
      this._error = `Error: ${errorMessage}`;
      return false;
    } finally {
      this._isLoading = false;
      this.requestUpdate();
    }
  }

  async _saveProperties() {
    const targetDeviceId = this._getTargetDeviceId();
    if (!targetDeviceId) {
        this._error = "Error: Could not determine target device ID from the selected sensor.";
        this._feedback = "";
        this.requestUpdate();
        return;
    }

    const changedProperties = {};
    let actuallyChanged = false;
    for (const key of EDITABLE_PROPERTIES) {
        const originalValue = getProperty(this._currentProperties, key);
        const editedValue = getProperty(this._editValues, key); // This comes directly from ha-selector, typed

        // Compare carefully. If editedValue is undefined (e.g. cleared number field)
        // and original was some value, it's a change.
        // String comparison is a simple catch-all but consider type differences for robustness if needed.
        // For now, if the string representations differ, assume a change.
        // Or, more robustly, if the key is in _editValues and differs from _currentProperties.
        if (this._editValues.hasOwnProperty(key) && String(originalValue) !== String(editedValue)) {
            // The backend expects string values for most things in server.properties,
            // booleans as "true"/"false", numbers as numbers or strings.
            // Let's send them as they are from _editValues, which should be correctly typed by ha-selector.
            // The BSM integration service call should handle final formatting for server.properties file.
            changedProperties[key] = editedValue;
            actuallyChanged = true;
        }
    }

    if (!actuallyChanged) {
      this._error = "No changes detected to save."; // Should be prevented by button disable, but good check
      this._feedback = "";
      this.requestUpdate();
      return;
    }

    const success = await this._callService(
        "update_properties",
        {
            device_id: targetDeviceId,
            properties: changedProperties
        },
        "Properties update requested. Changes will reflect after the next server poll or restart."
    );

    if (success) {
      // Optimistically update _currentProperties and reset _editValues to match
      this._currentProperties = { ...this._currentProperties, ...changedProperties };
      this._editValues = { ...this._currentProperties };
    }
  }

  getCardSize() {
    let numProps = 0;
    if (this._selectedStatusEntityId && !this._error && Object.keys(this._currentProperties).length > 0) {
        numProps = EDITABLE_PROPERTIES.length;
    }
    // Approx 1 unit for selector, 1 for messages, 0.5 per property pair, 1 for actions
    return Math.max(3, 1 + 1 + Math.ceil(numProps / 2) + (numProps > 0 ? 1 : 0));
  }
}

customElements.define("bsm-properties-card", BsmPropertiesCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "bsm-properties-card",
  name: "Server Properties Card",
  description: "View and edit server.properties for a Bedrock Server Manager server.",
  preview: true,
});

console.info(`%c BSM-PROPERTIES-CARD %c LOADED %c`, "color: blue; font-weight: bold; background: white", "color: white; font-weight: bold; background: dimgray", "");