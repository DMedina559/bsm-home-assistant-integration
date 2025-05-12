import { LitElement, html, css } from "https://unpkg.com/lit-element@^2.0.0/lit-element.js?module";

const _LOGGER = {
    debug: (...args) => console.debug("BSM_RESTORE_CARD:", ...args),
    info: (...args) => console.info("BSM_RESTORE_CARD:", ...args),
    warn: (...args) => console.warn("BSM_RESTORE_CARD:", ...args),
    error: (...args) => console.error("BSM_RESTORE_CARD:", ...args),
};
const DOMAIN = "bedrock_server_manager";

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

  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _selectedSensorEntityId: { state: true },
      _serverDisplayName: { state: true }, // Attempt to derive or use fallback
      _backupType: { state: true }, // "world", "config", or "unknown"
      _availableBackups: { state: true },
      _selectedBackupFile: { state: true },
      _targetDeviceId: { state: true },
      _isLoading: { state: true },
      _error: { state: true },
      _feedback: { state: true },
    };
  }

  __hass;
  set hass(hass) {
    const oldHass = this.__hass;
    this.__hass = hass;
    if (hass && this._selectedSensorEntityId) {
        const stateObj = hass.states[this._selectedSensorEntityId];
        const oldStateObj = oldHass?.states[this._selectedSensorEntityId];

        // Check if the state object itself or its attributes (generally) changed
        if (stateObj && (stateObj !== oldStateObj ||
            JSON.stringify(stateObj.attributes) !== JSON.stringify(oldStateObj?.attributes))) {
            _LOGGER.debug(`Hass update detected for selected sensor '${this._selectedSensorEntityId}'.`);
            this._processSelectedSensor(stateObj);
        } else if (!stateObj && oldStateObj) {
            _LOGGER.warn(`Selected sensor '${this._selectedSensorEntityId}' disappeared.`);
            this._handleSensorSelection(null); // Reset
            this._error = `Selected sensor ${this._selectedSensorEntityId} is no longer available.`;
        }
    }
    this.requestUpdate('_hass', oldHass);
  }
  get hass() { return this.__hass; }


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
  }

  setConfig(config) {
    this.config = config || {};
    // No specific entities to validate here, user selects from UI.
    // `target_entity_for_device_id` from previous could be a fallback if sensor lacks device_id.
    this.requestUpdate();
  }

  _handleSensorSelection(entityId) {
    if (entityId === this._selectedSensorEntityId && entityId !== null) return;

    if (!entityId) {
      this._selectedSensorEntityId = null;
      this._serverDisplayName = null;
      this._backupType = null;
      this._availableBackups = [];
      this._selectedBackupFile = "";
      this._targetDeviceId = null;
      this._error = null;
      this._feedback = "Select a server's backup list sensor.";
      this.requestUpdate();
      return;
    }

    this._selectedSensorEntityId = entityId;
    this._error = null;
    this._feedback = `Processing sensor ${entityId}...`;
    // Reset dependent state
    this._serverDisplayName = null;
    this._backupType = null;
    this._availableBackups = [];
    this._selectedBackupFile = "";
    this._targetDeviceId = null;
    this.requestUpdate();


    if (this.hass && this.hass.states[entityId]) {
      this._processSelectedSensor(this.hass.states[entityId]);
    } else {
      _LOGGER.warn(`Sensor ${entityId} not found in hass states immediately after selection.`);
      this._feedback = "Waiting for sensor data..."; // hass setter will eventually call _processSelectedSensor
    }
  }

  _processSelectedSensor(stateObj) {
    if (!stateObj || !stateObj.attributes) {
      this._error = `Sensor ${stateObj?.entity_id || this._selectedSensorEntityId} has no state or attributes.`;
      _LOGGER.warn(this._error);
      this._feedback = "";
      // Don't clear _selectedSensorEntityId so user sees the error related to it
      this.requestUpdate();
      return;
    }

    _LOGGER.debug(`Processing attributes for ${stateObj.entity_id}:`, stateObj.attributes);

    // 1. Determine Target Device ID
    this._targetDeviceId = stateObj.attributes.device_id || null;
    if (!this._targetDeviceId && this.hass.entities) { // Fallback to entity registry
        const entityRegEntry = this.hass.entities[stateObj.entity_id];
        if (entityRegEntry?.device_id) {
            this._targetDeviceId = entityRegEntry.device_id;
            _LOGGER.debug("Device ID found via entity registry:", this._targetDeviceId);
        }
    }
    if (!this._targetDeviceId) {
        _LOGGER.warn(`Could not determine device_id for ${stateObj.entity_id}. Restore All will be disabled.`);
        // Don't set _error yet, specific restore might still work if integration doesn't need device_id for it
        // (though BSM usually does)
    }

    // 2. Determine Backup Type and List Attribute
    let foundBackupList = null;
    let determinedBackupType = "unknown"; // Default
    let listAttributeName = "";

    // Try to infer type from attribute keys first
    if (stateObj.attributes.world_backups_list && Array.isArray(stateObj.attributes.world_backups_list)) {
        determinedBackupType = "world";
        listAttributeName = "world_backups_list";
        foundBackupList = stateObj.attributes.world_backups_list;
    } else if (stateObj.attributes.config_backups_list && Array.isArray(stateObj.attributes.config_backups_list)) {
        determinedBackupType = "config";
        listAttributeName = "config_backups_list";
        foundBackupList = stateObj.attributes.config_backups_list;
    } else {
        // If not specific, iterate through generic candidates
        for (const attrKey of BACKUP_LIST_ATTRIBUTE_CANDIDATES) {
            if (stateObj.attributes[attrKey] && Array.isArray(stateObj.attributes[attrKey])) {
                foundBackupList = stateObj.attributes[attrKey];
                listAttributeName = attrKey;
                // Try a simple heuristic for type based on object_id if type is still unknown
                if (stateObj.object_id.includes("world")) determinedBackupType = "world";
                else if (stateObj.object_id.includes("config")) determinedBackupType = "config";
                // else it remains "unknown" or the type determined by a previous specific check
                break;
            }
        }
    }

    if (foundBackupList) {
      this._backupType = determinedBackupType;
      const sortedBackups = [...foundBackupList].sort((a, b) => b.localeCompare(a));
      if (JSON.stringify(sortedBackups) !== JSON.stringify(this._availableBackups)) {
        this._availableBackups = sortedBackups;
        this._selectedBackupFile = this._availableBackups.length > 0 ? this._availableBackups[0] : "";
      }
      _LOGGER.info(`Determined backup type: ${this._backupType}, list from attr: '${listAttributeName}', Count: ${this._availableBackups.length}`);
      this._error = null; // Clear previous error if we found a list
      this._feedback = this._availableBackups.length === 0 ? `No backups found in attribute '${listAttributeName}'.` : "";
    } else {
      this._error = `Could not find a recognized backup list attribute on ${stateObj.entity_id}. Checked: ${BACKUP_LIST_ATTRIBUTE_CANDIDATES.join(", ")}.`;
      _LOGGER.warn(this._error);
      this._availableBackups = [];
      this._selectedBackupFile = "";
      this._backupType = null; // Reset type
      this._feedback = "";
    }

    // 3. Determine Server Display Name (best effort)
    this._serverDisplayName = stateObj.attributes.friendly_name || stateObj.object_id;
    // Attempt to strip common suffixes for a cleaner name if type was inferred
    if (this._backupType === "world" && this._serverDisplayName.endsWith(" World Backups")) {
        this._serverDisplayName = this._serverDisplayName.replace(" World Backups", "");
    } else if (this._backupType === "config" && this._serverDisplayName.endsWith(" Config Backups")) {
        this._serverDisplayName = this._serverDisplayName.replace(" Config Backups", "");
    } else if (this._serverDisplayName.endsWith(" Backups")) {
         this._serverDisplayName = this._serverDisplayName.replace(" Backups", "");
    }
    // Further cleanup generic terms like "Sensor"
    this._serverDisplayName = this._serverDisplayName.replace(/ Sensor$/i, "").trim();


    this.requestUpdate();
  }

  _handleBackupSelect(ev) { this._selectedBackupFile = ev.target.value; }

  async _restoreSelectedBackup() {
    if (!this._targetDeviceId) {
         this._error = "Target Device ID not found for the selected sensor. Cannot send restore command.";
         _LOGGER.error(this._error);
         this.requestUpdate(); return;
    }
    if (!this._selectedBackupFile) { this._error = `No backup file selected.`; this.requestUpdate(); return; }
    if (!this._backupType || this._backupType === "unknown") {
        this._error = "Backup type (world/config) could not be determined for the selected sensor. Cannot restore.";
        _LOGGER.error(this._error + ` Sensor: ${this._selectedSensorEntityId}`);
        this.requestUpdate(); return;
    }

    const serverDisplayName = this._serverDisplayName || "the server";
    if (!confirm(`ARE YOU SURE you want to restore ${this._backupType} backup '${this._selectedBackupFile}' for ${serverDisplayName}? This will overwrite current data.`)) {
      return;
    }

    this._isLoading = true; this._error = null; this._feedback = `Restoring ${this._backupType} from ${this._selectedBackupFile}...`;
    this.requestUpdate();

    try {
      _LOGGER.debug(`Calling ${DOMAIN}.restore_backup. Device: ${this._targetDeviceId}, Type: ${this._backupType}, File: ${this._selectedBackupFile}`);
      await this.hass.callService(DOMAIN, "restore_backup", {
        device_id: this._targetDeviceId,
        restore_type: this._backupType,
        backup_file: this._selectedBackupFile,
      });
      this._feedback = `${this._backupType.charAt(0).toUpperCase() + this._backupType.slice(1)} restore from '${this._selectedBackupFile}' requested.`;
    } catch (err) {
      _LOGGER.error("Error calling restore_backup:", err);
      this._error = `Error restoring ${this._backupType}: ${err.message || "Check logs."}`;
      this._feedback = "";
    } finally {
      this._isLoading = false;
      this.requestUpdate();
    }
  }

  async _restoreLatestAll() {
     if (!this._targetDeviceId) {
         this._error = "Target Device ID not found for the selected sensor. Cannot restore latest all.";
         _LOGGER.error(this._error);
         this.requestUpdate(); return;
    }
    const serverDisplayName = this._serverDisplayName || "the server";
    if (!confirm(`ARE YOU SURE you want to restore the LATEST FULL backup (world & config) for ${serverDisplayName}?`)) {
      return;
    }
    this._isLoading = true; this._error = null; this._feedback = `Restoring latest full backup...`;
    this.requestUpdate();
    try {
        _LOGGER.debug(`Calling ${DOMAIN}.restore_latest_all. Device: ${this._targetDeviceId}`);
        await this.hass.callService(DOMAIN, "restore_latest_all", {
             device_id: this._targetDeviceId
        });
        this._feedback = `Latest full backup restore requested.`;
    } catch (err) {
        _LOGGER.error("Error calling restore_latest_all:", err);
        this._error = `Error restoring latest: ${err.message || "Check logs."}`;
        this._feedback = "";
    } finally {
        this._isLoading = false;
        this.requestUpdate();
    }
  }

  render() {
    if (!this.hass) {
      return html`<ha-card><div class="card-content">Waiting for Home Assistant...</div></ha-card>`;
    }

    const entitySelectorConfig = {
      entity: {
        integration: DOMAIN, // Filter by your integration
        domain: "sensor",    // Only show sensors
      }
    };

    const cardTitle = this.config.title || "Restore Card";
    const serverContextName = this._serverDisplayName || (this._selectedSensorEntityId ? "Selected Sensor" : "No Sensor Selected");
    const backupTypeDisplay = this._backupType && this._backupType !== "unknown" ?
        `${this._backupType.charAt(0).toUpperCase() + this._backupType.slice(1)} Backups` : "Backups";

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
          ></ha-selector>

          ${this._feedback && !this._error ? html`<div class="feedback">${this._feedback}</div>` : ""}
          ${this._error ? html`<div class="error">${this._error}</div>` : ""}
          ${this._isLoading && !this._error ? html`<div class="loading"><ha-circular-progress indeterminate size="small"></ha-circular-progress> Processing...</div>` : ""}

          ${this._selectedSensorEntityId && !this._error && this._backupType ? html`
            <!-- Specific Backup Type Restore Section -->
            <div class="section">
              <h4>${backupTypeDisplay} for ${serverContextName}</h4>
              ${this._availableBackups.length > 0 ? html`
                <ha-select
                    label="Select Backup File"
                    .value=${this._selectedBackupFile}
                    @selected=${this._handleBackupSelect}
                    @closed=${(ev) => ev.stopPropagation()} fixedMenuPosition naturalMenuWidth
                >
                  ${this._availableBackups.map(file => html`<mwc-list-item .value=${file} ?selected=${file === this._selectedBackupFile}>${file}</mwc-list-item>`)}
                </ha-select>
                <mwc-button
                    label="Restore This Backup"
                    raised
                    @click=${this._restoreSelectedBackup}
                    .disabled=${!this._selectedBackupFile || this._isLoading || this._backupType === "unknown"}
                    title=${this._backupType === "unknown" ? "Backup type could not be determined" : `Restore ${this._selectedBackupFile}`}
                ></mwc-button>
                ${this._backupType === "unknown" ? html`<p class="warning">Could not determine if this is a world or config backup. Restore disabled.</p>` : ""}
              ` : html`<p>No backup files found for this sensor, or the list attribute is not recognized.</p>`}
            </div>
          ` : ''}

          <!-- Restore Latest All (only if a target_device_id is resolved) -->
          ${this._targetDeviceId ? html`
            <div class="section">
              <h4>Full Restore (Latest) for ${serverContextName}</h4>
              <p class="info">This attempts to restore the latest world AND configuration files for the server associated with the selected sensor.</p>
              <mwc-button
                label="Restore Latest Full Backup"
                raised
                @click=${this._restoreLatestAll}
                .disabled=${this._isLoading}
              ></mwc-button>
            </div>
          ` : this._selectedSensorEntityId && !this._error ? html`
            <div class="section">
                <h4>Full Restore (Latest)</h4>
                <p class="warning">Cannot perform 'Restore Latest Full Backup' because the device ID for this server could not be determined from the selected sensor.</p>
            </div>
          ` : ''}
        </div>
      </ha-card>
    `;
  }

  static get styles() {
    return css`
      /* ... your styles ... */
      ha-card { display: flex; flex-direction: column; }
      .card-content { padding: 16px; flex-grow: 1; }
      .card-content > p:first-child { margin-top: 0; font-size: 0.9em; color: var(--secondary-text-color); }
      ha-selector, ha-select { display: block; width: 100%; margin-bottom: 16px; }
      mwc-button[raised] { margin-top: 8px; width: 100%; }
      h4 { margin: 24px 0 12px 0; padding-bottom: 4px; border-bottom: 1px solid var(--divider-color); font-weight: 500; font-size: 1.1em; }
      .section { margin-bottom: 24px; }
      .info { font-size: 0.9em; color: var(--secondary-text-color); margin-bottom: 8px; }
      .warning { font-size: 0.9em; color: var(--warning-color); margin-bottom: 8px; font-weight: bold; }
      .loading, .error, .feedback { padding: 8px 0; text-align: left; margin-top: 8px; }
      .error { color: var(--error-color); font-weight: bold; }
      .feedback { color: var(--secondary-text-color); font-size: 0.9em; }
      .loading { display: flex; align-items: center; justify-content: center; color: var(--secondary-text-color); }
      .loading ha-circular-progress { margin-right: 8px; }
    `;
  }

  getCardSize() {
    let size = 2; // Base for selector + title
    if (this._selectedSensorEntityId && !this._error) {
        size += 2; // For the specific backup type section
        size += 1.5; // For restore all section (header + button + info/warning)
    } else {
        size += 1; // For placeholder/error text
    }
    return Math.max(3, Math.ceil(size));
  }
}

customElements.define("bsm-restore-card", BsmRestoreCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "bsm-restore-card",
  name: "Restore Backup Card",
  description: "Restores backups by inspecting attributes of a selected Bedrock server backup sensor.",
  preview: true,
});

console.info(`%c BSM-RESTORE-CARD %c ATTRIBUTE-AWARE LOADED %c`, "color: orange; font-weight: bold; background: black", "color: white; font-weight: bold; background: dimgray", "");