import { LitElement, html, css } from "https://unpkg.com/lit-element@^2.0.0/lit-element.js?module";

const DOMAIN = "bedrock_server_manager"; // Your integration domain
const VALID_PERMISSIONS = ["visitor", "member", "operator"];
const _LOGGER = {
    debug: (...args) => console.debug("BSM_PERM_CARD:", ...args),
    info: (...args) => console.info("BSM_PERM_CARD:", ...args),
    warn: (...args) => console.warn("BSM_PERM_CARD:", ...args),
    error: (...args) => console.error("BSM_PERM_CARD:", ...args),
};

class BsmPermissionsCard extends LitElement {

  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _selectedServerPermsEntityId: { state: true },
      _currentServerPermissions: { state: true }, // List: [{xuid, name, permission_level}]
      _globalPlayers: { state: true },         // List: [{name, xuid, ...}]
      _editData: { state: true }, // Object to stage changes: { "xuid": "level" }

      // For adding a new player/permission
      _newPlayerSelectedXUID: { state: true },
      _newPlayerManualXUID: { state: true },
      _newPlayerManualName: { state: true },
      _newPlayerPermissionLevel: { state: true },

      _isLoading: { state: true },
      _error: { state: true },
      _feedback: { state: true },
    };
  }

  __hass;
  set hass(hass) {
    const oldHass = this.__hass;
    this.__hass = hass;

    if (!hass) {
        this.requestUpdate('_hass', oldHass);
        return;
    }

    // Reload global players if the global_players_entity state has changed.
    if (hass && this.config?.global_players_entity) {
        const globalStateObj = hass.states[this.config.global_players_entity];
        const oldGlobalStateObj = oldHass?.states[this.config.global_players_entity];
        if (globalStateObj && globalStateObj !== oldGlobalStateObj) {
            this._loadGlobalPlayers(globalStateObj);
        }
    }

    // Reload server permissions if the selected server's permissions entity state has changed.
    if (this._selectedServerPermsEntityId) {
      const serverStateObj = hass.states[this._selectedServerPermsEntityId];
      const oldServerStateObj = oldHass?.states[this._selectedServerPermsEntityId];
      const currentAttr = serverStateObj?.attributes?.server_permissions;
      const oldAttr = oldServerStateObj?.attributes?.server_permissions;

      // Check if state object reference changed or if the 'server_permissions' attribute content changed.
      if (serverStateObj && (serverStateObj !== oldServerStateObj || JSON.stringify(currentAttr) !== JSON.stringify(oldAttr))) {
        this._loadServerPermissions(serverStateObj);
      } else if (!serverStateObj && oldServerStateObj) {
         // Handle if the selected entity becomes unavailable
         this._handleServerEntitySelection(null);
         this._error = `Server permissions entity ${this._selectedServerPermsEntityId} not found.`;
      }
    }
    this.requestUpdate('_hass', oldHass);
  }
  get hass() { return this.__hass; }

  constructor() {
    super();
    this._currentServerPermissions = [];
    this._globalPlayers = [];
    this._editData = {};
    this._newPlayerSelectedXUID = "";
    this._newPlayerManualXUID = "";
    this._newPlayerManualName = "";
    this._newPlayerPermissionLevel = VALID_PERMISSIONS[0]; // Default to 'visitor'
    this._isLoading = false;
    this._error = null;
    this._selectedServerPermsEntityId = null;
    this._feedback = "Select a server's permission sensor.";
  }

  setConfig(config) {
    if (!config.global_players_entity || !config.global_players_entity.startsWith("sensor.")) {
      throw new Error("Please define a valid 'global_players_entity' (e.g., sensor.bsm_manager_known_players).");
    }
    this.config = config;
    if (this.hass && this.hass.states[this.config.global_players_entity]) {
        this._loadGlobalPlayers(this.hass.states[this.config.global_players_entity]);
    }
    // No need for `this.requestUpdate()` here if LitElement handles config changes appropriately,
    // but it's safe to keep if there are downstream effects of config not tied to a reactive property.
    // Since _loadGlobalPlayers might change _globalPlayers (reactive), Lit will update.
  }

    _loadGlobalPlayers(stateObj) {
    if (stateObj && stateObj.attributes) {
    const players = stateObj.attributes.global_players_list;
    if (players && Array.isArray(players)) {
    this._globalPlayers = [...players].sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    _LOGGER.debug("Global players loaded:", this._globalPlayers);
    } else {
    _LOGGER.warn("Global players attribute 'global_players_list' missing or not an array.");
    this._globalPlayers = [];
    }
    } else {
    _LOGGER.warn("Global players entity or its attributes missing.");
    this._globalPlayers = [];
    }
    this.requestUpdate("_globalPlayers");
    }

  _handleServerEntitySelection(entityId) {
    if (entityId === this._selectedServerPermsEntityId && entityId !== null) return; // No change or already handled initial null

    if (!entityId || !this.hass) {
      this._selectedServerPermsEntityId = null;
      this._currentServerPermissions = [];
      this._editData = {};
      this._error = null;
      this._feedback = "Select a server's permission sensor.";
      this.requestUpdate(); // Ensure UI resets
      return;
    }

    this._selectedServerPermsEntityId = entityId;
    this._feedback = "Loading server permissions...";
    this._error = null;
    this._currentServerPermissions = [];
    this._editData = {}; // Clear edits for previous server

    const stateObj = this.hass.states[this._selectedServerPermsEntityId];
    if (stateObj) {
        this._loadServerPermissions(stateObj);
        this._feedback = ""; // Clear loading message if successful
    } else {
        this._error = `Selected entity ${this._selectedServerPermsEntityId} not found.`;
        this._feedback = ""; // Clear loading message
    }
    this.requestUpdate(); // Update UI with new selection results
  }

  _loadServerPermissions(stateObj) {
     if (!stateObj?.attributes) {
        this._error = "Selected server permissions entity has no attributes.";
        this._currentServerPermissions = [];
        this._editData = {};
        this.requestUpdate();
        return;
     }
     const permissions = stateObj.attributes.server_permissions;
     if (permissions && Array.isArray(permissions)) {
         // Only update and clear edits if the permissions data has actually changed
         if (JSON.stringify(permissions) !== JSON.stringify(this._currentServerPermissions)) {
             _LOGGER.debug("Loading new server permissions data:", permissions.length);
             this._currentServerPermissions = [...permissions]; // New array for reactivity
             this._editData = {}; // Clear pending edits when server permissions refresh from source
             this._error = null;
             this.requestUpdate(); // Update UI with new permissions
         }
     } else {
        _LOGGER.warn("'server_permissions' attribute missing or invalid.");
        this._error = "'server_permissions' attribute missing or invalid.";
        this._currentServerPermissions = [];
        this._editData = {};
        this.requestUpdate(); // Update UI with error/empty state
     }
  }

  _handlePermissionLevelChange(xuid, newLevel) {
    // Reassign _editData to ensure LitElement detects the change for this complex object
    this._editData = { ...this._editData, [xuid]: newLevel };
    this._feedback = ""; this._error = null;
    // Reassigning reactive properties _editData, _feedback, _error will trigger an update.
    // An explicit this.requestUpdate() is generally not needed here but doesn't hurt.
  }

  _handleNewPlayerSelectedXUIDChange(ev) { this._newPlayerSelectedXUID = ev.target.value; }
  _handleNewPlayerManualXUIDChange(ev) { this._newPlayerManualXUID = ev.target.value.trim(); }
  _handleNewPlayerManualNameChange(ev) { this._newPlayerManualName = ev.target.value; }
  _handleNewPlayerPermissionLevelChange(ev) { this._newPlayerPermissionLevel = ev.target.value; }

  _stageNewPlayerPermission() {
    let xuidToAdd = this._newPlayerSelectedXUID;
    let nameForDisplay = "";

    if (this._newPlayerSelectedXUID) {
        const player = this._globalPlayers.find(p => p.xuid === this._newPlayerSelectedXUID);
        nameForDisplay = player ? player.name : "Unknown (from global)";
        this._newPlayerManualXUID = ""; // Clear manual XUID if global is selected
    } else if (this._newPlayerManualXUID) {
        xuidToAdd = this._newPlayerManualXUID;
        nameForDisplay = this._newPlayerManualName || `XUID: ${xuidToAdd}`;
    } else {
        this._error = "Please select a known player or enter an XUID.";
        this.requestUpdate(); return;
    }

    if (!xuidToAdd) { this._error = "XUID is required."; this.requestUpdate(); return; }
    if (!VALID_PERMISSIONS.includes(this._newPlayerPermissionLevel)) { this._error = "Invalid permission level."; this.requestUpdate(); return; }

    this._editData = { ...this._editData, [xuidToAdd]: this._newPlayerPermissionLevel };
    this._feedback = `Staged permission for ${nameForDisplay} (${xuidToAdd}) to ${this._newPlayerPermissionLevel}. Click 'Save Changes'.`;
    this._error = null;

    // Clear add fields for next entry
    this._newPlayerSelectedXUID = "";
    this._newPlayerManualXUID = "";
    this._newPlayerManualName = "";
    // Optionally reset _newPlayerPermissionLevel or keep last used:
    // this._newPlayerPermissionLevel = VALID_PERMISSIONS[0];
    this.requestUpdate(); // Update UI with staged changes and cleared fields
  }


  async _savePermissions() {
    if (!this._selectedServerPermsEntityId) {
        this._error = "No server selected."; this.requestUpdate(); return;
    }
    if (Object.keys(this._editData).length === 0) {
        this._error = "No changes to save."; this.requestUpdate(); return;
    }

    // Get device_id for the service call.
    // The device_id should be associated with the selected server's permissions entity.
    let targetDeviceId = null;
    const entityState = this.hass.states[this._selectedServerPermsEntityId];

    // Attempt 1: Try to get device_id from the entity's state attributes
    if (entityState?.attributes?.device_id) {
        targetDeviceId = entityState.attributes.device_id;
    }
    // Attempt 2: Fallback to entity registry if not found in state attributes
    if (!targetDeviceId && this.hass.entities) {
        const entityRegEntry = this.hass.entities[this._selectedServerPermsEntityId];
        if (entityRegEntry?.device_id) {
            targetDeviceId = entityRegEntry.device_id;
        }
    }

    if (!targetDeviceId) {
        this._error = `Could not determine device ID for server entity ${this._selectedServerPermsEntityId}. Cannot save permissions.`;
        this.requestUpdate();
        return;
    }

    this._isLoading = true; this._error = null; this._feedback = "Saving permissions...";
    this.requestUpdate();

    try {
        _LOGGER.debug(`Calling ${DOMAIN}.set_permissions for device_id: ${targetDeviceId} with data:`, this._editData);
        await this.hass.callService(DOMAIN, "set_permissions", {
            // Service data requires target, and within target, the device_id
            device_id: targetDeviceId,
            permissions: this._editData // Send the staged changes
        });
        this._feedback = "Permissions update requested. List will refresh on next data poll from the server.";
        this._editData = {}; // Clear staged edits after successful save request
    } catch (err) {
        _LOGGER.error("Error calling set_permissions service:", err);
        this._error = `Error saving permissions: ${err.message || "Unknown error. Check Home Assistant logs."}`;
        this._feedback = "";
    } finally {
        this._isLoading = false;
        this.requestUpdate(); // Ensure UI reflects final state (loading, feedback, error)
    }
  }


  render() {
    if (!this.hass || !this.config) {
      return html`<ha-card>Waiting for Home Assistant and configuration...</ha-card>`;
    }

    // Use a more specific selector type if possible, e.g., {entity: {integration: DOMAIN, device_class: "some_class_for_perms_sensor"}}
    // For now, any sensor from the integration is fine as per original.
    const entitySelectorConfig = { entity: { integration: DOMAIN, domain: "sensor" }};
    const canInteract = this._selectedServerPermsEntityId && !this._isLoading; // Disable interaction while loading *data* or *saving*
    const hasStagedChanges = Object.keys(this._editData).length > 0;

    // Filter out players already in currentServerPermissions or _editData from the "Add New" dropdown
    const existingXuids = new Set([
        ...this._currentServerPermissions.map(p => p.xuid),
        ...Object.keys(this._editData)
    ]);
    const availableGlobalPlayerOptions = this._globalPlayers
        .filter(p => !existingXuids.has(p.xuid))
        .map(p => ({value: p.xuid, label: `${p.name || 'Unnamed Player'} (${p.xuid})`}));


    return html`
      <ha-card header="${this.config.title || "Server Permissions Manager"}">
        <div class="card-content">
          <p>Select the 'Permissioned Players' sensor for the target server.</p>
          <ha-selector
            label="Target Server Permissions Sensor"
            .hass=${this.hass}
            .selector=${entitySelectorConfig}
            .value=${this._selectedServerPermsEntityId}
            @value-changed=${(ev) => this._handleServerEntitySelection(ev.detail.value)}
            .disabled=${this._isLoading}
          ></ha-selector>

          ${this._feedback ? html`<div class="feedback">${this._feedback}</div>` : ""}
          ${this._error ? html`<div class="error">${this._error}</div>` : ""}
          ${this._isLoading && !this._error ? html`<div class="loading"><ha-circular-progress indeterminate size="small"></ha-circular-progress> Loading data...</div>` : ""}


          ${this._selectedServerPermsEntityId ? html`
            <!-- Display/Edit Current Permissions -->
            <div class="section">
              <h4>Current Server Permissions:</h4>
              ${this._currentServerPermissions.length === 0 && Object.keys(this._editData).filter(xuid => !this._currentServerPermissions.find(p=>p.xuid === xuid)).length === 0
                ? html`<p>No permissions set for this server, or not yet loaded.</p>`
                : ''
              }
              ${[
                ...this._currentServerPermissions,
                ...Object.keys(this._editData)
                    .filter(xuid => !this._currentServerPermissions.find(p => p.xuid === xuid))
                    .map(xuid => {
                        const globalPlayer = this._globalPlayers.find(gp => gp.xuid === xuid);
                        return { xuid, name: globalPlayer?.name || this._newPlayerManualName || `XUID: ${xuid}`, permission_level: this._editData[xuid], isNewStaged: true };
                    })
              ]
              .sort((a,b) => (a.name || a.xuid).localeCompare(b.name || b.xuid)) // Sort combined list
              .map(p => {
                const currentLevel = this._editData[p.xuid] || p.permission_level;
                const originalLevel = this._currentServerPermissions.find(cp => cp.xuid === p.xuid)?.permission_level;
                const isModified = p.isNewStaged || (originalLevel && currentLevel !== originalLevel);

                return html`
                <div class="permission-entry ${isModified ? 'modified' : ''}">
                  <span class="player-name" title="XUID: ${p.xuid}">${p.name || p.xuid}${p.isNewStaged ? ' (New)' : ''}</span>
                  <ha-select
                    label="Level"
                    .value=${currentLevel}
                    @selected=${(ev) => this._handlePermissionLevelChange(p.xuid, ev.target.value)}
                    @closed=${(ev) => ev.stopPropagation()}
                    fixedMenuPosition naturalMenuWidth
                    .disabled=${this._isLoading}
                  >
                    ${VALID_PERMISSIONS.map(level => html`<mwc-list-item .value=${level} ?selected=${level === currentLevel}>${level}</mwc-list-item>`)}
                  </ha-select>
                </div>
              `})}
            </div>

            <!-- Add New Player Permission -->
            <div class="section">
              <h4>Add Player Permission:</h4>
              <p class="info">Select a known player OR manually enter XUID. Player name is optional if XUID is manually entered.</p>
              <ha-select
                label="Select Known Player (not yet on this server)"
                .value=${this._newPlayerSelectedXUID}
                @selected=${this._handleNewPlayerSelectedXUIDChange}
                @closed=${(ev) => ev.stopPropagation()}
                fixedMenuPosition naturalMenuWidth
                .disabled=${this._isLoading || !!this._newPlayerManualXUID}
              >
                  ${availableGlobalPlayerOptions.map(opt => html`<mwc-list-item .value=${opt.value}>${opt.label}</mwc-list-item>`)}
              </ha-select>
              <ha-textfield
                label="Player Name (Optional, for new XUID)"
                .value=${this._newPlayerManualName}
                @input=${this._handleNewPlayerManualNameChange}
                .disabled=${this._isLoading || !!this._newPlayerSelectedXUID}
              ></ha-textfield>
              <ha-textfield
                label="Player XUID (If not selected above)"
                .value=${this._newPlayerManualXUID}
                @input=${this._handleNewPlayerManualXUIDChange}
                .disabled=${this._isLoading || !!this._newPlayerSelectedXUID}
                helper="Required if not selecting a known player"
                helperPersistent
              ></ha-textfield>
              <ha-select
                label="Permission Level"
                .value=${this._newPlayerPermissionLevel}
                @selected=${this._handleNewPlayerPermissionLevelChange}
                @closed=${(ev) => ev.stopPropagation()}
                fixedMenuPosition naturalMenuWidth
                .disabled=${this._isLoading}
              >
                  ${VALID_PERMISSIONS.map(level => html`<mwc-list-item .value=${level} ?selected=${level === this._newPlayerPermissionLevel}>${level}</mwc-list-item>`)}
              </ha-select>
              <mwc-button
                label="Stage This Player"
                @click=${this._stageNewPlayerPermission}
                style="margin-top: 16px;"
                .disabled=${this._isLoading || (!this._newPlayerSelectedXUID && !this._newPlayerManualXUID)}
                raised
              ></mwc-button>
            </div>
          ` : ''}
        </div>

        ${this._selectedServerPermsEntityId && hasStagedChanges ? html`
            <div class="card-actions">
                <mwc-button
                    label="Save All Staged Changes"
                    raised
                    .disabled=${this._isLoading || !hasStagedChanges}
                    @click=${this._savePermissions}
                ></mwc-button>
            </div>
        ` : ''}
      </ha-card>
    `;
  }

  static get styles() {
    return css`
      ha-card { display: flex; flex-direction: column; }
      .card-content { padding: 16px; flex-grow: 1; }
      .card-actions { border-top: 1px solid var(--divider-color); padding: 8px 16px; display: flex; justify-content: flex-end; }
      ha-selector, ha-textfield, ha-select { display: block; margin-bottom: 16px; width: 100%; }
      h4 { margin: 24px 0 12px 0; padding-bottom: 4px; border-bottom: 1px solid var(--divider-color); font-weight: 500; font-size: 1.1em; }
      .section { margin-bottom: 24px; }
      .permission-entry { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--divider-color-light, var(--divider-color)); }
      .permission-entry:last-child { border-bottom: none; }
      .permission-entry.modified .player-name { font-weight: bold; color: var(--primary-color); }
      .permission-entry .player-name { flex-grow: 1; margin-right: 16px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .permission-entry ha-select { width: 150px; flex-shrink: 0; }
      .info { font-size: 0.9em; color: var(--secondary-text-color); margin-bottom: 12px; }
      .loading, .error, .feedback { padding: 8px 0; text-align: left; margin-top: 8px; }
      .error { color: var(--error-color); font-weight: bold; }
      .feedback { color: var(--secondary-text-color); font-size: 0.9em; }
      .loading { display: flex; align-items: center; justify-content: center; color: var(--secondary-text-color); }
      .loading ha-circular-progress { margin-right: 8px; }
      mwc-button[raised] { margin-top: 8px; }
      ha-textfield[helperPersistent] { --mdc-text-field-helper-text-padding: 0 16px; }
    `;
  }

  getCardSize() {
    let size = 2; // Base for selector + title
    if (this._selectedServerPermsEntityId) {
        size += 2; // For "Add Player" section base
        size += 1; // For "Current Permissions" header
        const combinedListLength = this._currentServerPermissions.length +
            Object.keys(this._editData).filter(xuid => !this._currentServerPermissions.find(p => p.xuid === xuid)).length;
        size += Math.ceil(combinedListLength / 2); // Approx 0.5 per item
        if (Object.keys(this._editData).length > 0) size +=1; // For save button
    }
    return Math.max(3, Math.ceil(size));
  }
}

customElements.define("bsm-permissions-card", BsmPermissionsCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "bsm-permissions-card",
  name: "BSM Server Permissions Card",
  description: "View and manage player permissions for a selected Bedrock server.",
  preview: true, // Can be true if you have a default config or it can render without config
});

console.info(`%c BSM-PERMISSIONS-CARD %c UPDATED & LOADED %c`, "color: purple; font-weight: bold; background: black", "color: white; font-weight: bold; background: dimgray", "");