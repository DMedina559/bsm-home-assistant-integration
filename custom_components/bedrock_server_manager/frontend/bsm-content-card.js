import { LitElement, html, css } from "https://unpkg.com/lit-element@^2.0.0/lit-element.js?module";

const _LOGGER = {
    debug: (...args) => console.debug("BSM_INSTALL_CARD:", ...args),
    info: (...args) => console.info("BSM_INSTALL_CARD:", ...args),
    warn: (...args) => console.warn("BSM_INSTALL_CARD:", ...args),
    error: (...args) => console.error("BSM_INSTALL_CARD:", ...args),
};

const DOMAIN = "bedrock_server_manager";

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

  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _selectedContentSourceSensorId: { state: true }, // Single sensor for content
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
  set hass(hass) {
    const oldHass = this.__hass;
    this.__hass = hass;

    if (hass && this._selectedContentSourceSensorId) {
        const sourceStateObj = hass.states[this._selectedContentSourceSensorId];
        const oldSourceStateObj = oldHass?.states[this._selectedContentSourceSensorId];
        if (sourceStateObj && (sourceStateObj !== oldSourceStateObj ||
            JSON.stringify(sourceStateObj.attributes) !== JSON.stringify(oldSourceStateObj?.attributes))) {
            _LOGGER.debug(`Hass update for content source sensor ${this._selectedContentSourceSensorId}`);
            this._processSelectedContentSourceSensor(sourceStateObj);
        } else if (!sourceStateObj && oldSourceStateObj) {
            _LOGGER.warn(`Content source sensor ${this._selectedContentSourceSensorId} disappeared.`);
            this._handleContentSourceSensorChange(null); // Reset
            this._error = `Content source sensor ${this._selectedContentSourceSensorId} is no longer available.`;
        }
    }
    this.requestUpdate('_hass', oldHass);
  }
  get hass() { return this.__hass; }


  constructor() {
    super();
    this._selectedContentSourceSensorId = null;
    this._selectedTargetServerDeviceId = null;
    this._installType = null; // Determined from sensor
    this._availableFilesForInstall = [];
    this._selectedFileToInstall = "";
    this._isLoading = false;
    this._error = null;
    this._feedback = "Select content source and target server.";
  }

  setConfig(config) {
    this.config = config || {};
    // Allow pre-configuration of the content source sensor
    if (config.content_source_sensor_entity) {
        this._selectedContentSourceSensorId = config.content_source_sensor_entity;
        if (this.hass && this.hass.states[this._selectedContentSourceSensorId]) {
            this._processSelectedContentSourceSensor(this.hass.states[this._selectedContentSourceSensorId]);
        }
    }
    this.requestUpdate();
  }

  _handleContentSourceSensorChange(entityId) {
    if (entityId === this._selectedContentSourceSensorId && entityId !== null) return;

    if (!entityId) {
        this._selectedContentSourceSensorId = null;
        this._installType = null;
        this._availableFilesForInstall = [];
        this._selectedFileToInstall = "";
        this._error = null;
        this._feedback = "Select content source and target server.";
        this.requestUpdate();
        return;
    }

    this._selectedContentSourceSensorId = entityId;
    this._error = null;
    this._feedback = `Processing content source ${entityId}...`;
    // Reset dependent state
    this._installType = null;
    this._availableFilesForInstall = [];
    this._selectedFileToInstall = "";
    this.requestUpdate();

    if (this.hass && this.hass.states[entityId]) {
      this._processSelectedContentSourceSensor(this.hass.states[entityId]);
    } else {
      _LOGGER.warn(`Content source sensor ${entityId} not found in hass states immediately.`);
      this._feedback = "Waiting for sensor data...";
    }
  }

  _processSelectedContentSourceSensor(stateObj) {
    if (!stateObj || !stateObj.attributes) {
      this._error = `Sensor ${stateObj?.entity_id || this._selectedContentSourceSensorId} has no state or attributes.`;
      _LOGGER.warn(this._error);
      this._feedback = "";
      this.requestUpdate();
      return;
    }

    _LOGGER.debug(`Processing attributes for content source ${stateObj.entity_id}:`, stateObj.attributes);

    let foundList = null;
    let determinedInstallType = "unknown";
    let listAttributeName = "";

    // Try to infer type and find list from attribute keys
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
            if (stateObj.attributes[attrKey] && Array.isArray(stateObj.attributes[attrKey])) {
                foundList = stateObj.attributes[attrKey];
                listAttributeName = attrKey;
                // Heuristic for type based on object_id or friendly_name if type is still unknown
                const nameHint = (stateObj.attributes.friendly_name || stateObj.object_id).toLowerCase();
                if (nameHint.includes("world")) determinedInstallType = "world";
                else if (nameHint.includes("addon") || nameHint.includes("pack")) determinedInstallType = "addon";
                break;
            }
        }
    }

    this._installType = determinedInstallType; // Set determined type

    if (foundList) {
      const newList = [...foundList].sort();
      this._availableFilesForInstall = newList;
      this._selectedFileToInstall = this._availableFilesForInstall.length > 0 ? this._availableFilesForInstall[0] : "";
      this._error = null;
      this._feedback = this._availableFilesForInstall.length === 0 ?
        `No files found in sensor ${stateObj.entity_id} (checked attr: ${listAttributeName}).` :
        `Found ${this._installType} files. Select a target server.`;
      _LOGGER.info(`Content source: ${stateObj.entity_id}. Determined type: ${this._installType}, list from attr: '${listAttributeName}', Count: ${this._availableFilesForInstall.length}`);
    } else {
      _LOGGER.warn(`Could not find a recognized content list attribute on ${stateObj.entity_id}. Checked: ${CONTENT_LIST_ATTRIBUTE_CANDIDATES.join(", ")}`);
      this._error = `Could not load files. Attribute not found on ${stateObj.entity_id}.`;
      this._availableFilesForInstall = [];
      this._selectedFileToInstall = "";
      this._installType = null; // Reset type
      this._feedback = "";
    }
    this.requestUpdate();
  }

  _handleTargetServerChange(ev) {
    this._selectedTargetServerDeviceId = ev.detail.value;
    this._feedback = (this._selectedTargetServerDeviceId && this._availableFilesForInstall.length > 0) ? "Select a file to install." : this._feedback;
    this._error = null;
    _LOGGER.debug("Target Server Device ID selected:", this._selectedTargetServerDeviceId);
    this.requestUpdate();
  }

  _handleFileToInstallSelect(ev) {
    this._selectedFileToInstall = ev.target.value;
    this.requestUpdate(); // Ensure button state updates
  }

  async _installContent() {
    if (!this._selectedTargetServerDeviceId) { this._error = "Please select a target server."; this.requestUpdate(); return; }
    if (!this._installType || this._installType === "unknown") { this._error = "Content type (world/addon) could not be determined from the source sensor."; this.requestUpdate(); return; }
    if (!this._selectedFileToInstall) { this._error = "Please select a file to install."; this.requestUpdate(); return; }

    const serviceName = this._installType === "world" ? "install_world" : "install_addon";

    this._isLoading = true; this._error = null; this._feedback = `Installing ${this._installType} '${this._selectedFileToInstall}'...`;
    this.requestUpdate();

    try {
        _LOGGER.debug(`Calling ${DOMAIN}.${serviceName}. Device: ${this._selectedTargetServerDeviceId}, File: ${this._selectedFileToInstall}`);
        await this.hass.callService(DOMAIN, serviceName, {
            device_id: this._selectedTargetServerDeviceId,
            filename: this._selectedFileToInstall
        });
        this._feedback = `${this._installType.charAt(0).toUpperCase() + this._installType.slice(1)} '${this._selectedFileToInstall}' installation requested.`;
    } catch (err) {
        _LOGGER.error(`Error calling ${serviceName} service:`, err);
        this._error = `Error installing ${this._installType}: ${err.message || "Check logs."}`;
        this._feedback = "";
    } finally {
        this._isLoading = false;
        this.requestUpdate();
    }
  }


  render() {
    if (!this.hass) { return html`<ha-card>Waiting for Home Assistant...</ha-card>`; }

    const targetServerSelectorConfig = { device: { integration: DOMAIN } };
    const sourceSensorSelectorConfig = { entity: { integration: DOMAIN, domain: "sensor" }};

    const canInstall = this._selectedTargetServerDeviceId &&
                       this._selectedFileToInstall &&
                       this._installType && this._installType !== "unknown" &&
                       !this._isLoading;

    const installTypeDisplay = this._installType && this._installType !== "unknown" ?
                                this._installType.charAt(0).toUpperCase() + this._installType.slice(1) : "Content";

    return html`
      <ha-card header="${this.config.title || "Content Installer"}">
        <div class="card-content">
          <h4>1. Select Available Content Source</h4>
          <ha-selector
            label="Available Content List Sensor"
            .hass=${this.hass}
            .selector=${sourceSensorSelectorConfig}
            .value=${this._selectedContentSourceSensorId}
            @value-changed=${(ev) => this._handleContentSourceSensorChange(ev.detail.value)}
            helper="Sensor listing available .mcworld, .mcpack, etc."
          ></ha-selector>

          ${this._selectedContentSourceSensorId ? html`
            <h4>2. Select Target Server</h4>
            <ha-selector
              label="Target Server Device"
              .hass=${this.hass}
              .selector=${targetServerSelectorConfig}
              .value=${this._selectedTargetServerDeviceId}
              @value-changed=${this._handleTargetServerChange}
            ></ha-selector>
          ` : ''}

          ${this._selectedContentSourceSensorId && this._selectedTargetServerDeviceId && this._installType ? html`
            <h4>3. Select File to Install (${installTypeDisplay})</h4>
            ${this._availableFilesForInstall.length > 0 ? html`
              <ha-select
                  label="Select File"
                  .value=${this._selectedFileToInstall}
                  @selected=${this._handleFileToInstallSelect}
                  @closed=${(ev) => ev.stopPropagation()} fixedMenuPosition naturalMenuWidth
                  .disabled=${this._isLoading || this._installType === "unknown"}
              >
                  ${this._availableFilesForInstall.map(file => html`<mwc-list-item .value=${file}>${file}</mwc-list-item>`)}
              </ha-select>
              ${this._installType === "unknown" ? html`<p class="warning">Could not determine content type (World/Addon) from the source sensor. Installation may fail or be incorrect.</p>` : ""}
            ` : html`<p class="info">No files found in the selected content source sensor, or list attribute not recognized.</p>`}
          ` : ''}


          ${this._feedback && !this._error ? html`<div class="feedback">${this._feedback}</div>` : ""}
          ${this._error ? html`<div class="error">${this._error}</div>` : ""}
          ${this._isLoading ? html`<div class="loading"><ha-circular-progress indeterminate size="small"></ha-circular-progress> Processing...</div>` : ""}
        </div>

        <div class="card-actions">
            <mwc-button
                label="Install ${installTypeDisplay}"
                raised
                icon="mdi:toy-brick-plus-outline"
                @click=${this._installContent}
                .disabled=${!canInstall}
            ></mwc-button>
        </div>
      </ha-card>
    `;
  }

  static get styles() {
    return css`
      ha-card { display: flex; flex-direction: column; }
      .card-content { padding: 16px; flex-grow: 1; }
      .card-actions { border-top: 1px solid var(--divider-color); padding: 8px 16px; display:flex; justify-content: flex-end; }
      ha-selector, ha-select { display: block; width: 100%; margin-bottom: 16px; }
      h4 { margin: 24px 0 12px 0; padding-bottom: 4px; border-bottom: 1px solid var(--divider-color); font-weight: 500; font-size: 1.1em;}
      .loading, .error, .feedback { padding: 8px 0; text-align: left; margin-top: 8px; }
      .error { color: var(--error-color); font-weight: bold; }
      .feedback { color: var(--secondary-text-color); font-size: 0.9em; }
      .info { font-size: 0.9em; color: var(--disabled-text-color); margin-top: -8px; margin-bottom: 16px; }
      .warning { font-size: 0.9em; color: var(--warning-color); margin-bottom: 8px; }
      .loading { display: flex; align-items: center; justify-content: center; color: var(--secondary-text-color); }
      .loading ha-circular-progress { margin-right: 8px; }
    `;
  }

  getCardSize() {
    let size = 2; // Title, source selector
    if (this._selectedContentSourceSensorId) size += 1; // Target server selector
    if (this._selectedContentSourceSensorId && this._selectedTargetServerDeviceId && this._installType) size += 1; // File selector
    size += 1; // Actions
    return Math.max(4, Math.ceil(size));
  }
}

customElements.define("bsm-content-installer-card", BsmContentInstallerCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "bsm-content-installer-card",
  name: "BSM Content Installer (Single Source)",
  description: "Installs content from a selected manager-provided list sensor to a Bedrock server.",
  preview: true,
});

console.info(`%c BSM-CONTENT-INSTALLER-CARD %c SINGLE-SOURCE LOADED %c`, "color: teal; font-weight: bold; background: black", "color: white; font-weight: bold; background: dimgray", "");