// custom_components/bedrock_server_manager/frontend/bsm-content-card.js
import { LitElement, html, css } from "https://unpkg.com/lit-element@^2.0.0/lit-element.js?module";

const _LOGGER = {
    debug: (...args) => console.debug("BSM_INSTALL_CARD:", ...args),
    info: (...args) => console.info("BSM_INSTALL_CARD:", ...args),
    warn: (...args) => console.warn("BSM_INSTALL_CARD:", ...args),
    error: (...args) => console.error("BSM_INSTALL_CARD:", ...args),
};

const DOMAIN = "bedrock_server_manager";

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


// Possible attribute names that might contain the list of available content
const CONTENT_LIST_ATTRIBUTE_CANDIDATES = [
    "available_worlds_list",   // Specific
    "available_addons_list",   // Specific
    "content_files",           // Generic
    "files_list",              // Generic
    "available_files",         // Generic
    "files"                    // Generic
];

class BsmContentInstallerCard extends LitElement {

  // --- START: ADDED FOR UI CONFIG ---
  static async getConfigElement() {
    // The editor element is defined in this same file below.
    return document.createElement("bsm-content-installer-card-editor");
  }

  static getStubConfig() {
    // Default config when added via UI
    return {
      title: "Server Content Installer", // Default title
      // content_source_sensor_entity: "" // Start with no pre-selected entity
    };
  }
  // --- END: ADDED FOR UI CONFIG ---

  static get properties() {
    return {
      hass: { type: Object }, // Custom setter/getter used
      config: { type: Object }, // config is now set via UI/YAML
      _selectedContentSourceSensorId: { state: true }, // Entity ID selected IN THE CARD UI (or pre-filled by config)
      _selectedTargetServerDeviceId: { state: true },
      _installType: { state: true }, // "world", "addon", or "unknown"
      _availableFilesForInstall: { state: true },
      _selectedFileToInstall: { state: true },
      _isLoading: { state: true },
      _error: { state: true },
      _feedback: { state: true },
    };
  }

  __hass;
  get hass() { return this.__hass; }
  set hass(hass) {
    const oldHass = this.__hass;
    this.__hass = hass;

    if (hass && this._selectedContentSourceSensorId) {
        const sourceStateObj = hass.states[this._selectedContentSourceSensorId];
        const oldSourceStateObj = oldHass?.states[this._selectedContentSourceSensorId];

        // Check if state object or its attributes actually changed
        if (sourceStateObj && (sourceStateObj !== oldSourceStateObj ||
            JSON.stringify(sourceStateObj.attributes ?? null) !== JSON.stringify(oldSourceStateObj?.attributes ?? null))) {
            _LOGGER.debug(`Hass update for content source sensor ${this._selectedContentSourceSensorId}`);
            this._processSelectedContentSourceSensor(sourceStateObj);
        } else if (!sourceStateObj && oldSourceStateObj) {
            _LOGGER.warn(`Content source sensor ${this._selectedContentSourceSensorId} disappeared.`);
            // Reset state if the selected sensor disappears
            this._handleContentSourceSensorChange(null); // Reset internal card state
            this._error = `Content source sensor ${this._selectedContentSourceSensorId} is no longer available.`;
        }
    } else if (!this._selectedContentSourceSensorId && this.config?.content_source_sensor_entity) {
        // If hass becomes available AFTER config is set, and the config has a sensor, try to process it
        const configSensorId = this.config.content_source_sensor_entity;
        const configStateObj = hass?.states[configSensorId];
        if (configStateObj) {
            _LOGGER.debug(`Initial processing of configured sensor ${configSensorId} after hass became available.`);
            // Directly set the internal state and process
            this._selectedContentSourceSensorId = configSensorId;
            this._processSelectedContentSourceSensor(configStateObj);
        }
    }

    // Only request update if hass object actually changed reference or was previously undefined
    if (oldHass !== hass) {
        this.requestUpdate('hass', oldHass);
    }
  }

  constructor() {
    super();
    // Initialize internal states - these might be overwritten by setConfig or later interaction
    this._selectedContentSourceSensorId = null;
    this._selectedTargetServerDeviceId = null;
    this._installType = null;
    this._availableFilesForInstall = [];
    this._selectedFileToInstall = "";
    this._isLoading = false;
    this._error = null;
    this._feedback = "Select content source and target server.";
    _LOGGER.debug("BSM Content Installer Card constructor finished.");
  }

  setConfig(config) {
    _LOGGER.debug("setConfig called with:", config);
    if (!config) {
        _LOGGER.error("No configuration provided.");
        throw new Error("Invalid configuration");
    }

    const oldConfig = this.config;
    this.config = { ...config }; // Store the received config

    // Determine the initial sensor ID to use in the card's UI.
    // Priority: Configured entity > Previously selected entity (if any) > null
    const initialSensorId = this.config.content_source_sensor_entity || this._selectedContentSourceSensorId || null;

    // If the sensor ID determined from the config is different from the currently
    // selected one in the card's state, update the card's state.
    if (initialSensorId !== this._selectedContentSourceSensorId) {
        _LOGGER.debug(`Setting internal _selectedContentSourceSensorId from config: ${initialSensorId}`);
        this._handleContentSourceSensorChange(initialSensorId); // Use the handler to manage state reset
    } else if (initialSensorId && this.hass && this.hass.states[initialSensorId]) {
        // If the ID is the same, but config might have just been applied,
        // re-process the sensor state in case attributes changed somehow (unlikely but safe)
        // Or if hass wasn't ready before, process now.
        this._processSelectedContentSourceSensor(this.hass.states[initialSensorId]);
    }

    // Trigger a re-render based on the new config (mainly for title)
    this.requestUpdate('config', oldConfig);
  }


  // This method handles changes *within the card's UI* after it's loaded
  _handleContentSourceSensorChange(entityId) {
    _LOGGER.debug(`_handleContentSourceSensorChange called with entityId: ${entityId}`);
    // Prevent infinite loops if the change comes from setConfig setting the same value
    if (entityId === this._selectedContentSourceSensorId) {
        _LOGGER.debug("Content source selection unchanged.");
        return;
    }

    // Clear dependent state when sensor changes or is cleared
    this._selectedContentSourceSensorId = entityId || null;
    this._installType = null;
    this._availableFilesForInstall = [];
    this._selectedFileToInstall = "";
    this._error = null; // Clear previous errors related to content loading
    // Don't reset target server selection: this._selectedTargetServerDeviceId = null;

    if (!this._selectedContentSourceSensorId) {
        _LOGGER.debug("Content source sensor deselected.");
        this._feedback = "Select content source and target server.";
        this.requestUpdate(); // Ensure UI clears sections
        return;
    }

    this._feedback = `Processing content source ${this._selectedContentSourceSensorId}...`;
    this.requestUpdate(); // Show feedback

    // Try processing immediately if hass is available
    if (this.hass && this.hass.states[this._selectedContentSourceSensorId]) {
      this._processSelectedContentSourceSensor(this.hass.states[this._selectedContentSourceSensorId]);
    } else {
      _LOGGER.warn(`Content source sensor ${this._selectedContentSourceSensorId} not found in hass states immediately after selection.`);
      // Hass listener will pick it up when available, or show error if it never appears.
      this._feedback = "Waiting for sensor data...";
    }
  }

  _processSelectedContentSourceSensor(stateObj) {
    if (!stateObj?.attributes) {
      const sensorId = stateObj?.entity_id || this._selectedContentSourceSensorId;
      this._error = `Selected sensor (${sensorId}) has missing state or attributes. Cannot load content list.`;
      _LOGGER.warn(this._error, "State Object:", stateObj);
      this._feedback = "";
      this._installType = null;
      this._availableFilesForInstall = [];
      this._selectedFileToInstall = "";
      this.requestUpdate();
      return;
    }

    _LOGGER.debug(`Processing attributes for content source ${stateObj.entity_id}:`, stateObj.attributes);

    let foundList = null;
    let determinedInstallType = "unknown";
    let listAttributeName = "";

    // Prioritize specific attributes first
    if (stateObj.attributes.available_worlds_list && Array.isArray(stateObj.attributes.available_worlds_list)) {
        determinedInstallType = "world";
        listAttributeName = "available_worlds_list";
        foundList = stateObj.attributes.available_worlds_list;
    } else if (stateObj.attributes.available_addons_list && Array.isArray(stateObj.attributes.available_addons_list)) {
        determinedInstallType = "addon";
        listAttributeName = "available_addons_list";
        foundList = stateObj.attributes.available_addons_list;
    } else {
        // If not specific, iterate through generic candidates
        for (const attrKey of CONTENT_LIST_ATTRIBUTE_CANDIDATES) {
            // Check if the attribute exists and is a non-empty array
            if (Array.isArray(stateObj.attributes[attrKey]) && stateObj.attributes[attrKey].length > 0) {
                foundList = stateObj.attributes[attrKey];
                listAttributeName = attrKey;
                // Heuristic for type based on object_id or friendly_name if type is still unknown
                const nameHint = (stateObj.attributes.friendly_name || stateObj.entity_id.split('.').pop() || '').toLowerCase();
                if (nameHint.includes("world")) determinedInstallType = "world";
                else if (nameHint.includes("addon") || nameHint.includes("pack")) determinedInstallType = "addon";
                else _LOGGER.warn(`Could not infer type ('world'/'addon') from name hint: '${nameHint}'`);
                _LOGGER.debug(`Found generic list in attribute '${attrKey}', inferred type: ${determinedInstallType}`);
                break; // Stop searching once a list is found
            } else if (stateObj.attributes[attrKey] !== undefined) {
                 _LOGGER.debug(`Attribute '${attrKey}' found but is not a non-empty array:`, stateObj.attributes[attrKey]);
            }
        }
    }

    this._installType = determinedInstallType; // Set determined type ("world", "addon", or "unknown")

    if (foundList) {
      // Filter out any null/undefined/empty strings and sort
      const newList = foundList.filter(item => item && typeof item === 'string' && item.trim() !== '').sort();

      if (JSON.stringify(newList) !== JSON.stringify(this._availableFilesForInstall)) {
          this._availableFilesForInstall = newList;
          // Reset selection only if the list content changes significantly or was empty
          this._selectedFileToInstall = newList.length > 0 ? newList[0] : "";
          _LOGGER.info(`Content source: ${stateObj.entity_id}. Determined type: ${this._installType}, list from attr: '${listAttributeName}', Valid files found: ${newList.length}`);
      } else {
           _LOGGER.debug(`File list from ${listAttributeName} unchanged.`);
      }

      this._error = null; // Clear previous errors
      this._feedback = this._availableFilesForInstall.length === 0 ?
        `No valid files found in sensor ${stateObj.entity_id} (checked attr: ${listAttributeName}).` :
        `Found ${this._installType !== 'unknown' ? this._installType : 'content'} files. Select a target server.`;

    } else {
      _LOGGER.warn(`Could not find a recognized and populated content list attribute on ${stateObj.entity_id}. Checked: ${CONTENT_LIST_ATTRIBUTE_CANDIDATES.join(", ")}`);
      this._error = `Could not load files. No suitable attribute found on ${stateObj.entity_id}.`;
      this._availableFilesForInstall = [];
      this._selectedFileToInstall = "";
      this._installType = null; // Reset type if no list found
      this._feedback = "";
    }
    this.requestUpdate();
  }

  _handleTargetServerChange(ev) {
    ev.stopPropagation(); // Prevent event weirdness if nested
    this._selectedTargetServerDeviceId = ev.detail.value || null;
    // Update feedback based on current state
    if (this._selectedTargetServerDeviceId && this._availableFilesForInstall.length > 0) {
        this._feedback = "Select a file to install.";
    } else if (!this._selectedTargetServerDeviceId) {
        this._feedback = "Select a target server.";
    } // else keep existing feedback/error
    this._error = null; // Clear simple errors like "select target"
    _LOGGER.debug("Target Server Device ID selected:", this._selectedTargetServerDeviceId);
    this.requestUpdate();
  }

  _handleFileToInstallSelect(ev) {
    // For ha-select, the value is usually in ev.target.value
    this._selectedFileToInstall = ev.target.value;
     _LOGGER.debug("File selected:", this._selectedFileToInstall);
    // No need for feedback change here typically
    this.requestUpdate(); // Ensure button state updates
  }

  async _installContent() {
    // Add checks with user-friendly messages
    if (!this._selectedContentSourceSensorId) { this._error = "Error: Content source sensor not selected."; this.requestUpdate(); return; }
    if (!this._selectedTargetServerDeviceId) { this._error = "Error: Target server device not selected."; this.requestUpdate(); return; }
    if (!this._installType || this._installType === "unknown") { this._error = "Error: Content type (world/addon) could not be determined from the source sensor. Check sensor attributes."; this.requestUpdate(); return; }
    if (!this._selectedFileToInstall) { this._error = "Error: No file selected to install."; this.requestUpdate(); return; }

    const serviceName = this._installType === "world" ? "install_world" : "install_addon";
    const serviceData = {
        device_id: this._selectedTargetServerDeviceId,
        filename: this._selectedFileToInstall
    };

    this._isLoading = true;
    this._error = null;
    this._feedback = `Requesting installation of ${this._installType} '${this._selectedFileToInstall}' on device ${this._selectedTargetServerDeviceId}...`;
    this.requestUpdate();

    try {
        _LOGGER.debug(`Calling ${DOMAIN}.${serviceName} with data:`, serviceData);
        await this.hass.callService(DOMAIN, serviceName, serviceData);
        // Provide more specific success feedback
        this._feedback = `${this._installType.charAt(0).toUpperCase() + this._installType.slice(1)} file '${this._selectedFileToInstall}' installation successfully requested for device ${this._selectedTargetServerDeviceId}.`;
    } catch (err) {
        _LOGGER.error(`Error calling ${serviceName} service:`, err);
        // Parse error message more robustly
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
        this._error = `Error installing ${this._installType}: ${message}`;
        this._feedback = ""; // Clear feedback on error
    } finally {
        this._isLoading = false;
        this.requestUpdate(); // Update UI regardless of success/failure
    }
  }


  render() {
    if (!this.hass) { return html`<ha-card>Waiting for Home Assistant...</ha-card>`; }

    // Use configured title or default
    const cardTitle = this.config?.title || "";

    const targetServerSelectorConfig = { device: { integration: DOMAIN } };
    // Selector for the content source sensor - allow any sensor from the domain
    const sourceSensorSelectorConfig = { entity: { integration: DOMAIN, domain: "sensor" }};
    // Alternatively, be more specific if possible (e.g., filter by attribute, though this isn't standard)
    // const sourceSensorSelectorConfig = { entity: { integration: DOMAIN, domain: "sensor", /* attribute: 'available_worlds_list' OR 'available_addons_list' - NOT standard selector syntax */ }};

    // Determine button disabled state more clearly
    const isInstallPossible = this._selectedContentSourceSensorId &&
                              this._selectedTargetServerDeviceId &&
                              this._selectedFileToInstall &&
                              this._installType && this._installType !== "unknown";
    const isButtonDisabled = !isInstallPossible || this._isLoading;

    // More user-friendly display name for the type
    const installTypeDisplay = this._installType && this._installType !== "unknown" ?
                                this._installType.charAt(0).toUpperCase() + this._installType.slice(1) : "Content";

    return html`
      <ha-card header="${cardTitle}">
        <div class="card-content">
          <h4>1. Select Available Content Source</h4>
          <ha-selector
            label="Available Content List Sensor"
            .hass=${this.hass}
            .selector=${sourceSensorSelectorConfig}
            .value=${this._selectedContentSourceSensorId} /* Reflects internal state */
            @value-changed=${(ev) => this._handleContentSourceSensorChange(ev.detail.value)}
            helper="Sensor listing available .mcworld, .mcpack, etc. (e.g., from FileList sensor)"
            ?required=${!this._selectedContentSourceSensorId} /* Show required if not selected */
          ></ha-selector>

          <!-- Section 2: Only show if a source sensor is selected -->
          ${this._selectedContentSourceSensorId ? html`
            <h4>2. Select Target Server</h4>
            <ha-selector
              label="Target Server Device"
              .hass=${this.hass}
              .selector=${targetServerSelectorConfig}
              .value=${this._selectedTargetServerDeviceId}
              @value-changed=${this._handleTargetServerChange}
              ?required=${!this._selectedTargetServerDeviceId}
            ></ha-selector>
          ` : ''}

          <!-- Section 3: Only show if source and target are selected AND install type is known -->
          ${this._selectedContentSourceSensorId && this._selectedTargetServerDeviceId && this._installType ? html`
            <h4>3. Select File to Install (${installTypeDisplay})</h4>
            ${this._availableFilesForInstall.length > 0 ? html`
              <ha-select
                  label="Select File"
                  .value=${this._selectedFileToInstall} /* Bind to internal state */
                  @selected=${this._handleFileToInstallSelect} /* Use standard event */
                  @closed=${(ev) => ev.stopPropagation()} /* Prevent closing bubbling */
                  fixedMenuPosition naturalMenuWidth
                  ?required=${!this._selectedFileToInstall}
                  ?disabled=${this._isLoading || this._installType === "unknown"}
              >
                  <!-- Ensure items have value property -->
                  ${this._availableFilesForInstall.map(file => html`<mwc-list-item .value=${file}>${file}</mwc-list-item>`)}
              </ha-select>
              ${this._installType === "unknown" ? html`<p class="warning">Warning: Could not determine content type (World/Addon) from the source sensor's attributes or name. Installation may fail or use the wrong service call. Ensure sensor has 'available_worlds_list', 'available_addons_list', or a name hint.</p>` : ""}
            ` : html`<p class="info">No compatible files found in the selected content source sensor, or the list attribute (e.g., 'available_worlds_list') was not found or empty.</p>`}
          ` : ''}


          <!-- Feedback/Error Area -->
          <div class="status-area">
            ${this._isLoading ? html`<div class="loading"><ha-circular-progress indeterminate size="small"></ha-circular-progress> Processing...</div>` : ""}
            ${!this._isLoading && this._feedback ? html`<div class="feedback">${this._feedback}</div>` : ""}
            ${!this._isLoading && this._error ? html`<div class="error">${this._error}</div>` : ""}
          </div>
        </div>

        <!-- Actions Area -->
        <div class="card-actions">
            <mwc-button
                label="Install ${installTypeDisplay}"
                raised
                @click=${this._installContent}
                .disabled=${isButtonDisabled}
                title=${isButtonDisabled ? "Please complete all selections above" : `Install ${this._selectedFileToInstall || 'content'}`}
            ></mwc-button>
        </div>
      </ha-card>
    `;
  }

  static get styles() {
    return css`
      :host { display: block; } /* Ensure host takes space */
      ha-card { display: flex; flex-direction: column; height: 100%; }
      .card-content { padding: 16px; flex-grow: 1; }
      .card-actions { border-top: 1px solid var(--divider-color); padding: 8px 16px; display:flex; justify-content: flex-end; }
      ha-selector, ha-select { display: block; width: 100%; margin-bottom: 16px; }
      ha-select { /* Ensure dropdown appears correctly */ --mdc-menu-min-width: calc(100% - 32px); /* Adjust as needed */ }
      h4 { margin: 24px 0 12px 0; padding-bottom: 4px; border-bottom: 1px solid var(--divider-color); font-weight: 500; font-size: 1.1em;}
      .status-area { margin-top: 16px; min-height: 1.2em; /* Prevent layout jumps */ }
      .loading, .error, .feedback { padding: 8px 0; text-align: left; }
      .error { color: var(--error-color); font-weight: bold; word-wrap: break-word; }
      .feedback { color: var(--secondary-text-color); font-size: 0.9em; word-wrap: break-word; }
      .info { font-size: 0.9em; color: var(--disabled-text-color); margin-top: -8px; margin-bottom: 16px; }
      .warning { font-size: 0.9em; color: var(--warning-color); margin-bottom: 8px; padding: 8px; background-color: rgba(var(--rgb-warning-color), 0.1); border-left: 2px solid var(--warning-color); border-radius: 2px;}
      .loading { display: flex; align-items: center; justify-content: flex-start; /* Align left */ color: var(--secondary-text-color); }
      .loading ha-circular-progress { margin-right: 8px; }
    `;
  }

  // Calculate size based on visible sections
  getCardSize() {
    let size = 1; // Base for title
    size += 1; // Source selector
    if (this._selectedContentSourceSensorId) size += 1; // Target server selector
    if (this._selectedContentSourceSensorId && this._selectedTargetServerDeviceId && this._installType) {
        size += 1; // File selector (+ potential warning/info)
    }
    size += 1; // Status area
    size += 1; // Actions
    return Math.max(4, Math.ceil(size));
  }
}

customElements.define("bsm-content-installer-card", BsmContentInstallerCard);


// --- START: DEFINE THE EDITOR ELEMENT ---

class BsmContentInstallerCardEditor extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      _config: { type: Object, state: true },
    };
  }

  setConfig(config) {
    // Store the current config state internally
    this._config = config;
  }

  // Generic handler for simple value changes (like text fields)
  _valueChanged(ev) {
    if (!this._config || !this.hass) return;

    const target = ev.target;
    const newConfig = { ...this._config }; // Create a copy

    const configKey = target.configValue; // Get the key from the element property

    if (target.value === "") {
      // If the value is empty, remove the key (for optional fields like title)
      // Don't remove the entity key if cleared, just set to empty string or null
       if (configKey === "title") {
           delete newConfig[configKey];
       } else {
           // Keep the key but set to empty (or null if preferred)
           // This prevents the selector from defaulting back if temporarily cleared
           newConfig[configKey] = "";
       }
    } else {
      newConfig[configKey] = target.value;
    }

    fireEvent(this, "config-changed", { config: newConfig });
  }

  // Specific handler for ha-selector changes
  _selectorChanged(ev) {
     if (!this._config || !this.hass) return;
     ev.stopPropagation(); // Stop event propagation

     const target = ev.target; // The ha-selector element
     const configKey = target.configValue; // Get the key ('content_source_sensor_entity')
     const newValue = ev.detail.value; // The new entity_id or value

     // Only update and fire if the value actually changed
     if (newValue !== this._config[configKey]) {
        const newConfig = { ...this._config };
        if (newValue === "" || newValue === null) {
            // Either delete the key or set to empty string/null based on preference
            // Setting to empty string allows clearing the selector
            newConfig[configKey] = "";
            // delete newConfig[configKey]; // Alternative: remove key if cleared
        } else {
            newConfig[configKey] = newValue;
        }
        fireEvent(this, "config-changed", { config: newConfig });
     }
  }


  render() {
    if (!this.hass || !this._config) {
      return html``; // Render nothing until hass and config are available
    }

    // Selector configuration for the content source sensor in the editor
    const sourceSensorSelectorConfig = {
      entity: {
        integration: DOMAIN,
        domain: "sensor"
        // Potentially add more filters here if sensors can be identified better,
        // e.g., by a specific device class or attribute presence, though selectors
        // don't directly support attribute filtering well.
      }
    };

    return html`
      <ha-textfield
        label="Card Title (Optional)"
        .value=${this._config.title || ""}
        .configValue=${"title"}
        @input=${this._valueChanged}
        helper="Overrides the default card title"
      ></ha-textfield>

      <ha-selector
        label="Content Source Sensor (Optional)"
        .hass=${this.hass}
        .selector=${sourceSensorSelectorConfig}
        .value=${this._config.content_source_sensor_entity || ""} /* Bind to config value */
        .configValue=${"content_source_sensor_entity"} /* Custom prop to identify config key */
        @value-changed=${this._selectorChanged} /* Use specific handler */
        helper="Pre-select the sensor providing the content list"
      ></ha-selector>
    `;
  }

  static get styles() {
    // Basic styling for the editor elements
    return css`
      ha-textfield, ha-selector {
        display: block;
        margin-bottom: 16px;
      }
    `;
  }
}

customElements.define("bsm-content-installer-card-editor", BsmContentInstallerCardEditor);

// --- END: DEFINE THE EDITOR ELEMENT ---


// --- Keep the preview registration ---
window.customCards = window.customCards || [];
window.customCards.push({
  type: "bsm-content-installer-card",
  name: "Content Installer", // Simplified name slightly
  description: "Installs worlds or addons from a selected list sensor to a Bedrock server.",
  preview: true, // Preview should be okay as basic structure is shown
});

_LOGGER.info(`%c BSM-CONTENT-INSTALLER-CARD %c LOADED (incl. editor) %c`, "color: teal; font-weight: bold; background: black", "color: white; font-weight: bold; background: dimgray", "");