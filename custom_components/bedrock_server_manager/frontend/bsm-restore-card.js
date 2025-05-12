import { LitElement, html, css } from "https://unpkg.com/lit-element@^2.0.0/lit-element.js?module";

const _LOGGER = {
    debug: (...args) => console.debug("BSM_RESTORE_CARD:", ...args),
    info: (...args) => console.info("BSM_RESTORE_CARD:", ...args),
    warn: (...args) => console.warn("BSM_RESTORE_CARD:", ...args),
    error: (...args) => console.error("BSM_RESTORE_CARD:", ...args),
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

// Possible attribute names that might contain the backup list
const BACKUP_LIST_ATTRIBUTE_CANDIDATES = [
    "world_backups_list",   // Specific to world
    "config_backups_list",  // Specific to config
    "backup_files",         // Generic
    "files",                // Generic
    "backups_list",         // Generic
    "backups"               // Generic
];

class BsmRestoreCard extends LitElement {

  // --- START: ADDED FOR UI CONFIG ---
  static async getConfigElement() {
    // Editor element is defined below in this file
    return document.createElement("bsm-restore-card-editor");
  }

  static getStubConfig() {
    // Default config when added via UI
    return {
      title: "Restore Backup" // Default title
    };
  }
  // --- END: ADDED FOR UI CONFIG ---


  static get properties() {
    return {
      hass: { type: Object }, // Custom setter/getter used
      config: { type: Object }, // Set via UI/YAML
      _selectedSensorEntityId: { state: true },
      _serverDisplayName: { state: true },
      _backupType: { state: true },
      _availableBackups: { state: true },
      _selectedBackupFile: { state: true },
      _targetDeviceId: { state: true },
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

    let updateNeeded = false;

    if (!hass) {
        if (oldHass) updateNeeded = true;
        if (updateNeeded) this.requestUpdate('_hass', oldHass);
        return;
    }

    if (hass !== oldHass) updateNeeded = true;

    if (this._selectedSensorEntityId) {
        const stateObj = hass.states[this._selectedSensorEntityId];
        const oldStateObj = oldHass?.states[this._selectedSensorEntityId];

        if (stateObj && (stateObj !== oldStateObj ||
            JSON.stringify(stateObj.attributes ?? null) !== JSON.stringify(oldStateObj?.attributes ?? null))) {
            _LOGGER.debug(`Hass update detected for selected sensor '${this._selectedSensorEntityId}'. Processing.`);
            // Capture potentially changed values before processing
            const oldBackupList = this._availableBackups;
            const oldDeviceId = this._targetDeviceId;
            const oldBackupType = this._backupType;
            this._processSelectedSensor(stateObj);
            // Check if relevant state actually changed to trigger update
            if (JSON.stringify(oldBackupList) !== JSON.stringify(this._availableBackups) ||
                oldDeviceId !== this._targetDeviceId ||
                oldBackupType !== this._backupType) {
                 updateNeeded = true;
            }
        } else if (!stateObj && oldStateObj) {
            _LOGGER.warn(`Selected sensor '${this._selectedSensorEntityId}' disappeared.`);
            this._handleSensorSelection(null); // Reset internal state
            this._error = `Selected sensor ${this._selectedSensorEntityId} is no longer available.`;
            updateNeeded = true;
        }
    }

    if (updateNeeded) {
        this.requestUpdate('_hass', oldHass);
    }
  }


  constructor() {
    super();
    this._selectedSensorEntityId = null;
    this._serverDisplayName = null;
    this._backupType = null;
    this._availableBackups = [];
    this._selectedBackupFile = "";
    this._targetDeviceId = null;
    this._isLoading = false;
    this._error = null;
    this._feedback = "Select a server's backup list sensor.";
    _LOGGER.debug("BSM Restore Card constructor finished.");
  }

  setConfig(config) {
    _LOGGER.debug("setConfig called with:", config);
     if (!config) {
      _LOGGER.error("No configuration provided.");
      throw new Error("Invalid configuration");
    }
    const oldConfig = this.config;
    this.config = { ...config };
    // Trigger update mainly for title change
    this.requestUpdate('config', oldConfig);
  }

  _handleSensorSelection(entityId) {
     _LOGGER.debug(`_handleSensorSelection called with entityId: ${entityId}`);
    if (entityId === this._selectedSensorEntityId) return; // No change

    // Reset state when sensor changes or is cleared
    this._selectedSensorEntityId = entityId || null;
    this._serverDisplayName = null;
    this._backupType = null;
    this._availableBackups = [];
    this._selectedBackupFile = "";
    this._targetDeviceId = null;
    this._error = null;
    this._feedback = this._selectedSensorEntityId ? `Processing sensor ${this._selectedSensorEntityId}...` : "Select a server's backup list sensor.";
    this.requestUpdate(); // Show reset state or loading message

    if (!this._selectedSensorEntityId) {
      _LOGGER.debug("Sensor deselected.");
      return;
    }

    if (this.hass && this.hass.states[entityId]) {
      this._processSelectedSensor(this.hass.states[entityId]);
    } else if (this.hass) {
      _LOGGER.warn(`Sensor ${entityId} not found in hass states immediately after selection.`);
      this._feedback = "Waiting for sensor data...";
    } else {
       _LOGGER.warn("Hass not available during sensor selection.");
       this._feedback = "Waiting for Home Assistant data...";
    }
     this.requestUpdate(); // Redundant? Maybe not if hass wasn't ready
  }

  _processSelectedSensor(stateObj) {
    if (!stateObj) { // Basic check if stateObj is null/undefined
        _LOGGER.warn(`_processSelectedSensor called with invalid stateObj for ${this._selectedSensorEntityId}`);
        this._error = `Could not process sensor ${this._selectedSensorEntityId}. State object missing.`;
        this._feedback = "";
        this.requestUpdate();
        return;
    }
    if (!stateObj.attributes) {
      this._error = `Sensor ${stateObj.entity_id} has no attributes.`;
      _LOGGER.warn(this._error);
      this._feedback = "";
      this.requestUpdate();
      return;
    }

    _LOGGER.debug(`Processing attributes for ${stateObj.entity_id}:`, stateObj.attributes);

    // 1. Determine Target Device ID (using the robust method)
    const entityId = stateObj.entity_id;
    const entityRegEntry = this.hass?.entities?.[entityId];
    let deviceId = null;
    const regDeviceId = entityRegEntry?.device_id;
    if (regDeviceId && typeof regDeviceId === 'string' && regDeviceId.trim() !== '') {
        deviceId = regDeviceId.trim();
        _LOGGER.debug("Device ID found via entity registry:", deviceId);
    } else {
        const attrDeviceId = stateObj.attributes?.device_id;
        if (attrDeviceId && typeof attrDeviceId === 'string' && attrDeviceId.trim() !== '') {
            deviceId = attrDeviceId.trim();
             _LOGGER.debug("Device ID found via state attributes:", deviceId);
        } else {
             _LOGGER.warn(`Could not determine device_id for ${entityId}. Restore All will be disabled.`);
        }
    }
    this._targetDeviceId = deviceId; // Store found ID or null

    // 2. Determine Backup Type and List Attribute
    let foundBackupList = null;
    let determinedBackupType = "unknown";
    let listAttributeName = "";
    if (stateObj.attributes.world_backups_list && Array.isArray(stateObj.attributes.world_backups_list)) {
        determinedBackupType = "world";
        listAttributeName = "world_backups_list";
        foundBackupList = stateObj.attributes.world_backups_list;
    } else if (stateObj.attributes.config_backups_list && Array.isArray(stateObj.attributes.config_backups_list)) {
        determinedBackupType = "config";
        listAttributeName = "config_backups_list";
        foundBackupList = stateObj.attributes.config_backups_list;
    } else {
        for (const attrKey of BACKUP_LIST_ATTRIBUTE_CANDIDATES) {
            if (stateObj.attributes[attrKey] && Array.isArray(stateObj.attributes[attrKey])) {
                foundBackupList = stateObj.attributes[attrKey];
                listAttributeName = attrKey;
                const nameHint = (stateObj.attributes.friendly_name || entityId.split('.').pop() || '').toLowerCase();
                if (nameHint.includes("world")) determinedBackupType = "world";
                else if (nameHint.includes("config")) determinedBackupType = "config";
                _LOGGER.debug(`Found generic list in attr '${attrKey}', inferred type: ${determinedBackupType}`);
                break;
            }
        }
    }

    let newError = null;
    let newFeedback = "";
    if (foundBackupList) {
      this._backupType = determinedBackupType;
      // Filter potential null/empty items and sort (descending by name usually best for backups)
      const sortedBackups = foundBackupList
        .filter(item => item && typeof item === 'string' && item.trim() !== '')
        .sort((a, b) => b.localeCompare(a)); // Sort descending

      // Update state only if list actually changed
      if (JSON.stringify(sortedBackups) !== JSON.stringify(this._availableBackups)) {
        this._availableBackups = sortedBackups;
        this._selectedBackupFile = sortedBackups.length > 0 ? sortedBackups[0] : ""; // Default to latest
         _LOGGER.info(`Updated backup list. Type: ${this._backupType}, Attr: '${listAttributeName}', Count: ${this._availableBackups.length}`);
      } else {
          _LOGGER.debug("Backup list unchanged.");
      }
      newFeedback = this._availableBackups.length === 0 ? `No valid backup files found in attribute '${listAttributeName}'.` : "";
    } else {
      newError = `Could not find a recognized backup list attribute on ${stateObj.entity_id}. Checked: ${BACKUP_LIST_ATTRIBUTE_CANDIDATES.join(", ")}.`;
      _LOGGER.warn(newError);
      this._availableBackups = [];
      this._selectedBackupFile = "";
      this._backupType = null;
    }
    // Update error/feedback state together
    this._error = newError;
    this._feedback = newFeedback;


    // 3. Determine Server Display Name (best effort - same logic)
    let displayName = stateObj.attributes.friendly_name || entityId.split('.').pop() || "Unknown Server";
    if (this._backupType === "world" && displayName.toLowerCase().endsWith(" world backups")) {
        displayName = displayName.slice(0, - " World Backups".length);
    } else if (this._backupType === "config" && displayName.toLowerCase().endsWith(" config backups")) {
        displayName = displayName.slice(0, - " Config Backups".length);
    } else if (displayName.toLowerCase().endsWith(" backups")) {
         displayName = displayName.slice(0, - " Backups".length);
    }
    displayName = displayName.replace(/ sensor$/i, "").trim();
    this._serverDisplayName = displayName;

    // No need for requestUpdate here, the hass setter will handle it if needed.
  }

  _handleBackupSelect(ev) { this._selectedBackupFile = ev.target.value; this.requestUpdate(); }

  async _restoreSelectedBackup() {
    if (!this._targetDeviceId) {
         this._error = "Target Device ID not found for the selected sensor. Cannot send restore command.";
         _LOGGER.error(this._error); this.requestUpdate(); return;
    }
    if (!this._selectedBackupFile) { this._error = `No backup file selected.`; this.requestUpdate(); return; }
    if (!this._backupType || this._backupType === "unknown") {
        this._error = "Backup type (world/config) could not be determined for the selected sensor. Cannot restore.";
        _LOGGER.error(this._error + ` Sensor: ${this._selectedSensorEntityId}`); this.requestUpdate(); return;
    }
    const serverDisplayName = this._serverDisplayName || "the server";
    if (!confirm(`ARE YOU SURE you want to restore ${this._backupType} backup '${this._selectedBackupFile}' for ${serverDisplayName}? This may overwrite current data.`)) { // Adjusted confirmation
      return;
    }
    await this._callService("restore_backup",
        { device_id: this._targetDeviceId, restore_type: this._backupType, backup_file: this._selectedBackupFile },
        `${this._backupType.charAt(0).toUpperCase() + this._backupType.slice(1)} restore from '${this._selectedBackupFile}' requested.`
    );
  }

  async _restoreLatestAll() {
     if (!this._targetDeviceId) {
         this._error = "Target Device ID not found for the selected sensor. Cannot restore latest all.";
         _LOGGER.error(this._error); this.requestUpdate(); return;
    }
    const serverDisplayName = this._serverDisplayName || "the server";
    if (!confirm(`ARE YOU SURE you want to restore the LATEST FULL backup (world & config) for ${serverDisplayName}? This may overwrite current data.`)) { // Adjusted confirmation
      return;
    }
     await this._callService("restore_latest_all",
        { device_id: this._targetDeviceId },
        `Latest full backup restore requested.`
    );
  }

  // --- _callService (Reused - same as previous cards) ---
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

  render() {
    if (!this.hass) {
      return html`<ha-card><div class="card-content">Waiting for Home Assistant...</div></ha-card>`;
    }

    const entitySelectorConfig = {
      entity: { integration: DOMAIN, domain: "sensor" }
    };

    const cardTitle = this.config?.title || "Restore Backup"; // Use configured title
    const serverContextName = this._serverDisplayName || (this._selectedSensorEntityId ? "Selected Sensor" : "No Sensor Selected");
    const backupTypeDisplay = this._backupType && this._backupType !== "unknown" ?
        `${this._backupType.charAt(0).toUpperCase() + this._backupType.slice(1)} Backups` : "Backups";

    const canRestoreSelected = !this._isLoading &&
                               this._selectedBackupFile &&
                               this._backupType && this._backupType !== "unknown" &&
                               this._targetDeviceId; // Need device ID too

    const canRestoreLatestAll = !this._isLoading && this._targetDeviceId;

    return html`
      <ha-card header="${cardTitle}">
        <div class="card-content">
          <p>Select a Bedrock Server Manager backup list sensor.</p>
          <ha-selector
            label="Backup List Sensor"
            .hass=${this.hass}
            .selector=${entitySelectorConfig}
            .value=${this._selectedSensorEntityId}
            @value-changed=${(ev) => this._handleSensorSelection(ev.detail.value)}
            .disabled=${this._isLoading}
            required
          ></ha-selector>

          <!-- Status Area -->
          <div class="status-area">
              ${this._feedback && !this._error ? html`<div class="feedback">${this._feedback}</div>` : ""}
              ${this._error ? html`<div class="error">${this._error}</div>` : ""}
              ${this._isLoading && !this._error ? html`<div class="loading"><ha-circular-progress indeterminate size="small"></ha-circular-progress> Processing...</div>` : ""}
          </div>


          ${this._selectedSensorEntityId && !this._error && this._backupType ? html`
            <!-- Specific Backup Type Restore Section -->
            <div class="section">
              <h4>${backupTypeDisplay} for ${serverContextName}</h4>
              ${this._availableBackups.length > 0 ? html`
                <ha-select
                    label="Select Backup File to Restore"
                    .value=${this._selectedBackupFile}
                    @selected=${this._handleBackupSelect}
                    @closed=${(ev) => ev.stopPropagation()}
                    naturalMenuWidth /* Removed fixedMenuPosition based on previous issues */
                    required
                >
                  ${this._availableBackups.map(file => html`<mwc-list-item .value=${file} ?selected=${file === this._selectedBackupFile}>${file}</mwc-list-item>`)}
                </ha-select>
                <mwc-button
                    label="Restore This ${this._backupType || 'Backup'}"
                    @click=${this._restoreSelectedBackup}
                    .disabled=${!canRestoreSelected}
                    title=${!this._targetDeviceId ? "Cannot restore: Device ID missing" :
                             this._backupType === "unknown" ? "Cannot restore: Backup type unknown" :
                             !this._selectedBackupFile ? "Select a backup file" :
                             `Restore ${this._selectedBackupFile}`}
                ></mwc-button>
                ${this._backupType === "unknown" ? html`<p class="warning">Could not determine if this is a world or config backup list. Restore disabled.</p>` : ""}
                ${!this._targetDeviceId ? html`<p class="warning">Could not determine Device ID for this server. Restore disabled.</p>` : ""}
              ` : html`<p class="info">No ${this._backupType !== 'unknown' ? this._backupType : ''} backup files found for this sensor, or the list attribute is not recognized.</p>`}
            </div>
          ` : ''}

          <!-- Restore Latest All Section -->
           <div class="section">
              <h4>Full Restore (Latest) for ${serverContextName}</h4>
              ${this._selectedSensorEntityId && !this._error ? html`
                  <p class="info">This attempts to restore the latest world AND configuration files for the server associated with the selected sensor.</p>
                  <mwc-button
                    label="Restore Latest Full Backup"
                    @click=${this._restoreLatestAll}
                    .disabled=${!canRestoreLatestAll}
                    title=${!canRestoreLatestAll ? "Cannot restore: Device ID missing or still loading" : "Restore latest world and config backup"}
                  ></mwc-button>
                   ${!this._targetDeviceId ? html`<p class="warning">Cannot perform 'Restore Latest Full Backup' because the Device ID for this server could not be determined from the selected sensor.</p>` : ""}
              ` : html `
                 <p class="info">Select a sensor above to enable full restore.</p>
              `}
            </div>

        </div>
      </ha-card>
    `;
  }

  static get styles() {
    return css`
      :host { display: block; }
      ha-card { display: flex; flex-direction: column; height: 100%; }
      .card-content { padding: 16px; flex-grow: 1; }
      .card-content > p:first-child { margin-top: 0; font-size: 0.9em; color: var(--secondary-text-color); }
      ha-selector, ha-select { display: block; width: 100%; margin-bottom: 16px; }
      mwc-button[raised] { margin-top: 8px; width: 100%; }
      h4 { margin: 24px 0 12px 0; padding-bottom: 4px; border-bottom: 1px solid var(--divider-color); font-weight: 500; font-size: 1.1em; }
      .section { margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px dashed var(--divider-color); }
      .section:last-of-type { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
      .status-area { margin-top: 16px; min-height: 1.2em; }
      .info { font-size: 0.9em; color: var(--secondary-text-color); margin-bottom: 8px; }
      .warning { font-size: 0.9em; color: var(--warning-color); margin: 4px 0 8px 0; font-weight: 500;}
      .loading, .error, .feedback { padding: 8px 0; text-align: left; }
      .error { color: var(--error-color); font-weight: bold; }
      .feedback { color: var(--secondary-text-color); font-size: 0.9em; }
      .loading { display: flex; align-items: center; justify-content: center; color: var(--secondary-text-color); }
      .loading ha-circular-progress { margin-right: 8px; }
    `;
  }

  getCardSize() {
    let size = 2; // Base for selector + title
    size += 1; // Status area
    if (this._selectedSensorEntityId && !this._error) {
        if (this._backupType) size += 2; // Specific backup section (header, select, button)
        size += 1.5; // Restore all section (header, button, info/warning)
    } else {
        size += 1; // Placeholder/error text area
    }
    return Math.max(4, Math.ceil(size)); // Min size 4
  }
}

customElements.define("bsm-restore-card", BsmRestoreCard);

// --- START: EDITOR ELEMENT DEFINITION ---
class BsmRestoreCardEditor extends LitElement {
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
customElements.define("bsm-restore-card-editor", BsmRestoreCardEditor);
// --- END: EDITOR ELEMENT DEFINITION ---


// --- WINDOW REGISTRATION ---
window.customCards = window.customCards || [];
window.customCards.push({
  type: "bsm-restore-card",
  name: "BSM Restore Backup Card", // Updated name
  description: "Restores world or config backups for a selected Bedrock server.",
  preview: true,
});

_LOGGER.info(`%c BSM-RESTORE-CARD %c LOADED (incl. editor) %c`, "color: orange; font-weight: bold; background: black", "color: white; font-weight: bold; background: dimgray", "");
// --- END WINDOW REGISTRATION ---