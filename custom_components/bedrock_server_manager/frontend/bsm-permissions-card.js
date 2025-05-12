import { LitElement, html, css } from "https://unpkg.com/lit-element@^2.0.0/lit-element.js?module";

const DOMAIN = "bedrock_server_manager"; // Your integration domain
const VALID_PERMISSIONS = ["visitor", "member", "operator"];
const _LOGGER = {
    debug: (...args) => console.debug("BSM_PERM_CARD:", ...args),
    info: (...args) => console.info("BSM_PERM_CARD:", ...args),
    warn: (...args) => console.warn("BSM_PERM_CARD:", ...args),
    error: (...args) => console.error("BSM_PERM_CARD:", ...args),
};

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


class BsmPermissionsCard extends LitElement {

  // --- START: UI CONFIG METHODS ---
  static async getConfigElement() {
    // Editor element is defined below in this file
    return document.createElement("bsm-permissions-card-editor");
  }

  static getStubConfig(hass) {
      let defaultGlobalPlayerSensor = "";
      if (hass) {
          const potentialSensors = Object.keys(hass.states).filter(
              (eid) => eid.startsWith("sensor.") &&
                       hass.states[eid].attributes?.integration === DOMAIN &&
                       (eid.includes("known_players") || eid.includes("global_players"))
          );
          if (potentialSensors.length > 0) {
              defaultGlobalPlayerSensor = potentialSensors[0];
              _LOGGER.debug(`StubConfig: Found potential default global players sensor: ${defaultGlobalPlayerSensor}`);
          } else {
              _LOGGER.debug("StubConfig: Could not find a default global players sensor heuristically.");
          }
      }
      return {
        title: "Server Permissions Manager",
        global_players_entity: defaultGlobalPlayerSensor
      };
  }
  // --- END: UI CONFIG METHODS ---


  static get properties() {
    return {
      hass: { type: Object }, // Custom setter/getter used
      config: { type: Object },
      _selectedServerPermsEntityId: { state: true },
      _currentServerPermissions: { state: true },
      _globalPlayers: { state: true },
      _editData: { state: true },
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
  get hass() { return this.__hass; }
  set hass(hass) {
    const oldHass = this.__hass;
    this.__hass = hass;

    let updateNeeded = false;

    if (!hass) {
        if (oldHass) updateNeeded = true;
        if (updateNeeded) this.requestUpdate('hass', oldHass);
        return;
    }

    if (hass !== oldHass) updateNeeded = true;

    // Global Players Update Logic
    const globalPlayersEntityId = this.config?.global_players_entity;
    if (globalPlayersEntityId) {
        const globalStateObj = hass.states[globalPlayersEntityId];
        const oldGlobalStateObj = oldHass?.states[globalPlayersEntityId];
        if (globalStateObj && globalStateObj !== oldGlobalStateObj) {
            const oldGlobalPlayers = this._globalPlayers;
            this._loadGlobalPlayers(globalStateObj);
            if (JSON.stringify(oldGlobalPlayers) !== JSON.stringify(this._globalPlayers)) {
                updateNeeded = true;
            }
        } else if (!globalStateObj && oldGlobalStateObj) {
            _LOGGER.warn(`Global players entity ${globalPlayersEntityId} became unavailable.`);
            this._globalPlayers = [];
            updateNeeded = true;
        }
    } else if (this._globalPlayers?.length > 0) {
        _LOGGER.warn("Global players entity not configured, clearing existing global players list.");
        this._globalPlayers = [];
        updateNeeded = true;
    }

    // Server Permissions Update Logic
    if (this._selectedServerPermsEntityId) {
      const serverStateObj = hass.states[this._selectedServerPermsEntityId];
      const oldServerStateObj = oldHass?.states[this._selectedServerPermsEntityId];
      if (serverStateObj) {
          const currentAttr = serverStateObj.attributes?.server_permissions;
          const oldAttr = oldServerStateObj?.attributes?.server_permissions;
          if (serverStateObj !== oldServerStateObj || JSON.stringify(currentAttr ?? null) !== JSON.stringify(oldAttr ?? null)) {
            const oldServerPerms = this._currentServerPermissions;
            this._loadServerPermissions(serverStateObj);
            if (JSON.stringify(oldServerPerms) !== JSON.stringify(this._currentServerPermissions)) {
                updateNeeded = true;
            }
          }
      } else if (oldServerStateObj) {
         _LOGGER.warn(`Selected server permissions entity ${this._selectedServerPermsEntityId} became unavailable.`);
         this._handleServerEntitySelection(null);
         this._error = `Server permissions entity ${this._selectedServerPermsEntityId} is no longer available.`;
         updateNeeded = true;
      }
    }

    if (updateNeeded) {
        this.requestUpdate('hass', oldHass);
    }
  }


  constructor() {
    super();
    this._currentServerPermissions = [];
    this._globalPlayers = [];
    this._editData = {};
    this._newPlayerSelectedXUID = "";
    this._newPlayerManualXUID = "";
    this._newPlayerManualName = "";
    this._newPlayerPermissionLevel = VALID_PERMISSIONS[0];
    this._isLoading = false;
    this._error = null;
    this._selectedServerPermsEntityId = null;
    this._feedback = "Select a server's permission sensor.";
    _LOGGER.debug("BSM Permissions Card constructor finished.");
  }

  setConfig(config) {
    _LOGGER.debug("setConfig called with:", config);
    if (!config) {
        _LOGGER.error("No configuration provided.");
        throw new Error("Invalid configuration: Config object is missing.");
    }
    if (!config.global_players_entity || typeof config.global_players_entity !== 'string' || !config.global_players_entity.includes('.')) {
      _LOGGER.error("Invalid configuration: 'global_players_entity' is missing or invalid.", config);
      throw new Error("Invalid configuration: 'global_players_entity' is required. Please configure this in the UI editor.");
    }

    const oldConfig = this.config;
    this.config = { ...config };

    if (oldConfig?.global_players_entity !== this.config.global_players_entity) {
        _LOGGER.debug(`Global players entity changed from ${oldConfig?.global_players_entity} to ${this.config.global_players_entity}. Reloading.`);
        this._globalPlayers = [];
        if (this.hass && this.hass.states[this.config.global_players_entity]) {
            this._loadGlobalPlayers(this.hass.states[this.config.global_players_entity]);
        } else if (this.hass) {
             _LOGGER.warn(`Configured global players entity ${this.config.global_players_entity} not found in current hass state.`);
        } else {
             _LOGGER.debug("Hass not available yet, global players will load when hass updates.");
        }
    }
    this.requestUpdate('config', oldConfig);
  }

  _loadGlobalPlayers(stateObj) {
    if (!stateObj?.attributes) {
        _LOGGER.warn(`Global players entity ${stateObj?.entity_id || this.config?.global_players_entity} is missing attributes.`);
        this._globalPlayers = [];
        this.requestUpdate("_globalPlayers");
        return;
    }
    const players = stateObj.attributes.global_players_list;
    let newPlayers = [];
    if (players && Array.isArray(players)) {
        newPlayers = players
            .filter(p => p && typeof p === 'object' && p.xuid && p.name)
            .sort((a, b) => (a.name || "").localeCompare(b.name || ""));
        if (newPlayers.length !== players.length) {
             _LOGGER.warn("Some items in 'global_players_list' attribute were filtered out due to missing 'xuid' or 'name'.", players);
        }
    } else {
        _LOGGER.warn(`Global players attribute 'global_players_list' missing or not an array on ${stateObj.entity_id}.`);
    }
    if (JSON.stringify(newPlayers) !== JSON.stringify(this._globalPlayers)) {
        this._globalPlayers = newPlayers;
        _LOGGER.debug("Global players list updated:", this._globalPlayers.length);
        this.requestUpdate("_globalPlayers");
    } else {
         _LOGGER.debug("Global players list unchanged.");
    }
  }

  _handleServerEntitySelection(entityId) {
    _LOGGER.debug(`_handleServerEntitySelection called with entityId: ${entityId}`);
    if (entityId === this._selectedServerPermsEntityId) {
        _LOGGER.debug("Server entity selection unchanged.");
        return;
    }
    this._selectedServerPermsEntityId = entityId || null;
    this._currentServerPermissions = [];
    this._editData = {};
    this._error = null;
    if (!this._selectedServerPermsEntityId) {
      _LOGGER.debug("Server entity deselected.");
      this._feedback = "Select a server's permission sensor.";
      this.requestUpdate();
      return;
    }
    this._feedback = "Loading server permissions...";
    if (this.hass && this.hass.states[this._selectedServerPermsEntityId]) {
        this._loadServerPermissions(this.hass.states[this._selectedServerPermsEntityId]);
    } else {
        _LOGGER.warn(`Selected server entity ${this._selectedServerPermsEntityId} not found in hass states immediately.`);
        this._feedback = "Waiting for server sensor data...";
    }
    this.requestUpdate();
  }

  _loadServerPermissions(stateObj) {
     if (!stateObj?.attributes) {
        const entityId = stateObj?.entity_id || this._selectedServerPermsEntityId;
        this._error = `Selected server permissions entity (${entityId}) has no attributes.`;
        _LOGGER.warn(this._error, "State Object:", stateObj);
        this._currentServerPermissions = [];
        this._editData = {};
        this._feedback = "";
        this.requestUpdate();
        return;
     }
     const permissions = stateObj.attributes.server_permissions;
     let newPermissions = [];
     if (permissions && Array.isArray(permissions)) {
         newPermissions = permissions.filter(p => p && typeof p === 'object' && p.xuid && VALID_PERMISSIONS.includes(p.permission_level));
         if (newPermissions.length !== permissions.length) {
             _LOGGER.warn("Some items in 'server_permissions' attribute were filtered out due to missing/invalid fields.", permissions);
         }
     } else {
        _LOGGER.warn(`'server_permissions' attribute missing or not an array on ${stateObj.entity_id}.`);
        this._error = `'server_permissions' attribute missing or invalid on ${stateObj.entity_id}.`;
        this._feedback = "";
     }
     if (JSON.stringify(newPermissions) !== JSON.stringify(this._currentServerPermissions)) {
         _LOGGER.debug(`Loading new server permissions data for ${stateObj.entity_id}:`, newPermissions.length);
         this._currentServerPermissions = newPermissions;
         this._editData = {};
         this._error = null;
         this._feedback = "";
         this.requestUpdate();
     } else {
        _LOGGER.debug(`Server permissions for ${stateObj.entity_id} unchanged.`);
        if (this._feedback === "Loading server permissions...") this._feedback = "";
        this.requestUpdate();
     }
  }

  _handlePermissionLevelChange(xuid, newLevel) {
    _LOGGER.debug(`Staging permission change for XUID ${xuid} to ${newLevel}`);
    if (!VALID_PERMISSIONS.includes(newLevel)) {
        _LOGGER.warn(`Invalid permission level selected: ${newLevel}`);
        return;
    }
    this._editData = { ...this._editData, [xuid]: newLevel };
    this._feedback = ""; this._error = null;
    this.requestUpdate('_editData');
  }

  _handleNewPlayerSelectedXUIDChange(ev) {
      this._newPlayerSelectedXUID = ev.target.value;
      if (this._newPlayerSelectedXUID) {
          this._newPlayerManualXUID = "";
          this._newPlayerManualName = "";
      }
      this.requestUpdate();
  }
  _handleNewPlayerManualXUIDChange(ev) {
      this._newPlayerManualXUID = ev.target.value.trim();
      if (this._newPlayerManualXUID) {
          this._newPlayerSelectedXUID = "";
      }
       this.requestUpdate();
  }
  _handleNewPlayerManualNameChange(ev) {
      this._newPlayerManualName = ev.target.value;
      if (this._newPlayerManualName && this._newPlayerSelectedXUID) {
           this._newPlayerSelectedXUID = "";
      }
      this.requestUpdate();
  }
  _handleNewPlayerPermissionLevelChange(ev) {
      this._newPlayerPermissionLevel = ev.target.value;
      this.requestUpdate();
  }

  _stageNewPlayerPermission() {
    let xuidToAdd = "";
    let nameForDisplay = "";
    if (this._newPlayerSelectedXUID) {
        xuidToAdd = this._newPlayerSelectedXUID;
        const player = this._globalPlayers.find(p => p.xuid === xuidToAdd);
        nameForDisplay = player ? player.name : `XUID: ${xuidToAdd}`;
    } else if (this._newPlayerManualXUID) {
        xuidToAdd = this._newPlayerManualXUID;
        if (!xuidToAdd) {
            this._error = "Manual XUID cannot be empty.";
            this.requestUpdate(); return;
        }
        nameForDisplay = this._newPlayerManualName.trim() || `XUID: ${xuidToAdd}`;
    } else {
        this._error = "Please select a known player OR enter a manual XUID.";
        this.requestUpdate(); return;
    }
    if (!VALID_PERMISSIONS.includes(this._newPlayerPermissionLevel)) {
        this._error = "Invalid permission level selected.";
        this.requestUpdate(); return;
    }
    if (this._currentServerPermissions.some(p => p.xuid === xuidToAdd) || this._editData.hasOwnProperty(xuidToAdd)) {
        this._error = `Player with XUID ${xuidToAdd} already has permissions defined or staged for this server. Edit the existing entry instead.`;
        this.requestUpdate(); return;
    }
    this._editData = { ...this._editData, [xuidToAdd]: this._newPlayerPermissionLevel };
    this._feedback = `Staged permission for ${nameForDisplay} (${xuidToAdd}) to ${this._newPlayerPermissionLevel}. Click 'Save Changes' to apply.`;
    this._error = null;
    this._newPlayerSelectedXUID = "";
    this._newPlayerManualXUID = "";
    this._newPlayerManualName = "";
    this._newPlayerPermissionLevel = VALID_PERMISSIONS[0];
    this.requestUpdate();
  }

  async _savePermissions() {
    if (!this._selectedServerPermsEntityId) {
        this._error = "Error: No server selected."; this.requestUpdate(); return;
    }
    if (Object.keys(this._editData).length === 0) {
        this._error = "Error: No changes are staged for saving."; this.requestUpdate(); return;
    }
    this._isLoading = true; this._error = null; this._feedback = "Saving permissions changes...";
    this.requestUpdate();
    let targetDeviceId = null;
    try {
        const entityReg = await this.hass.callWS({ type: "config/entity_registry/get", entity_id: this._selectedServerPermsEntityId });
        targetDeviceId = entityReg?.device_id;
        _LOGGER.debug("Device ID from Entity Registry:", targetDeviceId);
    } catch (e) {
         _LOGGER.warn(`Could not get entity registry info for ${this._selectedServerPermsEntityId}:`, e);
         const entityState = this.hass?.states[this._selectedServerPermsEntityId];
         targetDeviceId = entityState?.attributes?.device_id;
         _LOGGER.debug("Device ID fallback from state attributes:", targetDeviceId);
    }
    if (!targetDeviceId) {
        this._error = `Error: Could not determine the target Device ID for the selected server entity (${this._selectedServerPermsEntityId}). Cannot save permissions. Check entity configuration.`;
        this._isLoading = false;
        this._feedback = "";
        this.requestUpdate();
        return;
    }
    try {
        const serviceData = {
            device_id: targetDeviceId,
            permissions: this._editData
        };
        _LOGGER.debug(`Calling ${DOMAIN}.set_permissions for device_id: ${targetDeviceId} with data:`, serviceData);
        await this.hass.callService(DOMAIN, "set_permissions", serviceData);
        this._feedback = "Permissions update successfully requested. The list will refresh automatically when the server reports the changes.";
        this._editData = {};
    } catch (err) {
        _LOGGER.error("Error calling set_permissions service:", err);
        let message = "An unknown error occurred. Check Home Assistant logs.";
        if (err instanceof Error) {
            message = err.message;
        } else if (typeof err === 'object' && err !== null && err.error) {
            message = err.error;
        } else if (typeof err === 'object' && err !== null && err.message) {
             message = err.message;
        } else if (typeof err === 'string') {
            message = err;
        }
        this._error = `Error saving permissions: ${message}`;
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
    if (!this.config?.global_players_entity) {
         return html`<ha-card>
             <div class="card-content error">
                Configuration Error: 'Global Players Entity' is not set. Please configure this card.
             </div>
         </ha-card>`;
    }
    const cardTitle = this.config.title || "Server Permissions Manager";
    const entitySelectorConfig = {
        entity: { integration: DOMAIN, domain: "sensor" }
    };
    const isLoading = this._isLoading;
    const hasStagedChanges = Object.keys(this._editData).length > 0;
    const canSave = hasStagedChanges && !isLoading;
    const canAddPlayer = !isLoading && (!this._newPlayerSelectedXUID && !this._newPlayerManualXUID.trim() ? false : true);
    const existingXuids = new Set([
        ...this._currentServerPermissions.map(p => p.xuid),
        ...Object.keys(this._editData)
    ]);
    const availableGlobalPlayerOptions = this._globalPlayers
        .filter(p => p.xuid && !existingXuids.has(p.xuid))
        .map(p => ({value: p.xuid, label: `${p.name || 'Unnamed Player'} (${p.xuid})`}));
    const combinedPermissionsList = [
        ...this._currentServerPermissions,
        ...Object.keys(this._editData)
            .filter(xuid => !this._currentServerPermissions.some(p => p.xuid === xuid))
            .map(xuid => {
                const globalPlayer = this._globalPlayers.find(gp => gp.xuid === xuid);
                const manualName = (xuid === this._newPlayerManualXUID) ? this._newPlayerManualName : '';
                return {
                    xuid,
                    name: globalPlayer?.name || manualName || `XUID: ${xuid}`,
                    permission_level: this._editData[xuid],
                    isNewStaged: true
                };
            })
    ]
    .sort((a,b) => (a.name || a.xuid).localeCompare(b.name || b.xuid));

    return html`
      <ha-card header="${cardTitle}">
        <div class="card-content">
          <p>Select the 'Permissioned Players' sensor for the target server.</p>
          <ha-selector
            label="Target Server Permissions Sensor"
            .hass=${this.hass}
            .selector=${entitySelectorConfig}
            .value=${this._selectedServerPermsEntityId}
            @value-changed=${(ev) => this._handleServerEntitySelection(ev.detail.value)}
            .disabled=${isLoading}
            required
          ></ha-selector>
          <div class="status-area">
              ${this._feedback ? html`<div class="feedback">${this._feedback}</div>` : ""}
              ${this._error ? html`<div class="error">${this._error}</div>` : ""}
              ${isLoading ? html`<div class="loading"><ha-circular-progress indeterminate size="small"></ha-circular-progress> Processing...</div>` : ""}
          </div>
          ${this._selectedServerPermsEntityId ? html`
            <div class="section">
              <h4>Current Server Permissions:</h4>
              ${combinedPermissionsList.length === 0
                ? html`<p class="info">No permissions currently set or staged for this server.</p>`
                : ''
              }
              ${combinedPermissionsList.map(p => {
                const currentLevel = this._editData[p.xuid] || p.permission_level;
                const originalPermission = this._currentServerPermissions.find(cp => cp.xuid === p.xuid);
                const originalLevel = originalPermission?.permission_level;
                const isModified = p.isNewStaged || (originalLevel && currentLevel !== originalLevel);
                return html`
                <div class="permission-entry ${isModified ? 'modified' : ''} ${p.isNewStaged ? 'new-staged' : ''}">
                  <span class="player-name" title="XUID: ${p.xuid}">${p.name || p.xuid}${p.isNewStaged ? html` <span class="new-tag">(New - Staged)</span>` : ''}</span>
                  <ha-select class="permission-select"
                    label="Level"
                    .value=${currentLevel}
                    @selected=${(ev) => this._handlePermissionLevelChange(p.xuid, ev.target.value)}
                    @closed=${(ev) => ev.stopPropagation()}
                    naturalMenuWidth
                    .disabled=${isLoading}
                  >
                    ${VALID_PERMISSIONS.map(level => html`<mwc-list-item .value=${level} ?selected=${level === currentLevel}>${level}</mwc-list-item>`)}
                  </ha-select>
                </div>
              `})}
            </div>
            <div class="section add-player-section">
              <h4>Add Player Permission:</h4>
              <p class="info">Select a known player OR manually enter XUID. Player name is optional for manual XUID.</p>
              <ha-select
                label="Select Known Player (not yet on this server)"
                .value=${this._newPlayerSelectedXUID}
                @selected=${this._handleNewPlayerSelectedXUIDChange}
                @closed=${(ev) => ev.stopPropagation()}
                naturalMenuWidth
                .disabled=${isLoading || !!this._newPlayerManualXUID}
                helper=${availableGlobalPlayerOptions.length === 0 ? "No available known players found" : ""}
                ?helper-persistent=${availableGlobalPlayerOptions.length === 0}
              >
                  <mwc-list-item value=""></mwc-list-item>
                  ${availableGlobalPlayerOptions.map(opt => html`<mwc-list-item .value=${opt.value}>${opt.label}</mwc-list-item>`)}
              </ha-select>
              <div class="manual-entry-row">
                  <ha-textfield class="manual-name"
                    label="Player Name (Optional)"
                    .value=${this._newPlayerManualName}
                    @input=${this._handleNewPlayerManualNameChange}
                    .disabled=${isLoading || !!this._newPlayerSelectedXUID}
                  ></ha-textfield>
                  <ha-textfield class="manual-xuid"
                    label="Player XUID (Manual)"
                    .value=${this._newPlayerManualXUID}
                    @input=${this._handleNewPlayerManualXUIDChange}
                    .disabled=${isLoading || !!this._newPlayerSelectedXUID}
                    helper="Required if not selecting known player"
                    ?required=${!this._newPlayerSelectedXUID}
                  ></ha-textfield>
              </div>
              <ha-select
                label="Permission Level for New Player"
                .value=${this._newPlayerPermissionLevel}
                @selected=${this._handleNewPlayerPermissionLevelChange}
                @closed=${(ev) => ev.stopPropagation()}
                naturalMenuWidth
                .disabled=${isLoading}
              >
                  ${VALID_PERMISSIONS.map(level => html`<mwc-list-item .value=${level} ?selected=${level === this._newPlayerPermissionLevel}>${level}</mwc-list-item>`)}
              </ha-select>
              <mwc-button
                label="Stage This Player"
                @click=${this._stageNewPlayerPermission}
                style="margin-top: 16px;"
                .disabled=${!canAddPlayer}
                raised icon=""
              ></mwc-button>
            </div>
          ` : ''}
        </div>
        ${this._selectedServerPermsEntityId && hasStagedChanges ? html`
            <div class="card-actions">
                 <mwc-button
                    label="Save All Staged Changes"
                    raised icon=""
                    .disabled=${!canSave}
                    @click=${this._savePermissions}
                    title=${canSave ? "Saves all highlighted changes" : "No changes staged or currently processing"}
                ></mwc-button>
            </div>
        ` : ''}
      </ha-card>
    `;
  }

  // --- START: CSS STYLES (with latest attempt) ---
  static get styles() {
    return css`
      :host {
        display: block;
        overflow: visible !important; /* <<< TRY FORCING HOST */
      }
      ha-card {
        display: flex;
        flex-direction: column;
        height: 100%;
        overflow: visible !important; /* <<< TRY FORCING HA-CARD */
      }
      .card-content {
        padding: 16px;
        flex-grow: 1;
        /* Keep this too, shouldn't hurt */
        overflow: visible !important;
      }
      .card-actions { border-top: 1px solid var(--divider-color); padding: 8px 16px; display: flex; justify-content: flex-end; }
      ha-selector, ha-textfield, ha-select { display: block; margin-bottom: 16px; width: 100%; }
      ha-select { --mdc-menu-min-width: calc(100% - 32px); /* Adjust if needed */ }
      .status-area { margin-top: 16px; min-height: 1.2em; }
      .loading, .error, .feedback { padding: 8px 0; text-align: left; }
      .error { color: var(--error-color); font-weight: bold; word-wrap: break-word; }
      .feedback { color: var(--secondary-text-color); font-size: 0.9em; word-wrap: break-word; }
      .info { font-size: 0.9em; color: var(--secondary-text-color); margin-bottom: 12px; }
      .loading { display: flex; align-items: center; justify-content: flex-start; color: var(--secondary-text-color); }
      .loading ha-circular-progress { margin-right: 8px; }

      h4 { margin: 24px 0 12px 0; padding-bottom: 4px; border-bottom: 1px solid var(--divider-color); font-weight: 500; font-size: 1.1em; }
      .section {
        margin-bottom: 24px;
        padding-bottom: 16px;
        border-bottom: 1px dashed var(--divider-color);
        position: relative; /* <<< ADDED POSITIONING CONTEXT */
      }
      .section:last-of-type { border-bottom: none; }
      .add-player-section p.info { margin-top: -4px; }

      .permission-entry { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; padding: 8px 4px; border-bottom: 1px solid var(--divider-color-light, #eee); transition: background-color 0.2s ease-in-out; }
      .permission-entry:last-child { border-bottom: none; }
      .permission-entry:hover { background-color: rgba(var(--rgb-primary-text-color), 0.05); }
      .permission-entry.modified { background-color: rgba(var(--rgb-primary-color), 0.08); border-left: 3px solid var(--primary-color); padding-left: 8px; margin-left: -11px; }
      .permission-entry.new-staged { border-left: 3px solid var(--success-color); }
      .permission-entry .player-name { flex-grow: 1; margin-right: 16px; font-size: 1.0em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .permission-entry .new-tag { font-size: 0.8em; color: var(--success-color); font-weight: bold; margin-left: 4px; }
      .permission-entry .permission-select { width: 130px; flex-shrink: 0; flex-grow: 0; margin-bottom: 0; --mdc-theme-primary: var(--primary-text-color); }

      .manual-entry-row { display: flex; gap: 16px; flex-wrap: wrap; }
      .manual-entry-row .manual-name { flex: 1 1 50%; min-width: 150px; }
      .manual-entry-row .manual-xuid { flex: 1 1 50%; min-width: 150px; }

      mwc-button[raised] { margin-top: 8px; }
    `;
  }
  // --- END: CSS STYLES ---

  getCardSize() {
    let size = 2; // Base for title + server selector
    if (this.config?.global_players_entity) {
        size += 1; // Status area
        if (this._selectedServerPermsEntityId) {
            size += 1; // "Current Permissions" header
            const combinedListLength = this._currentServerPermissions.length +
                Object.keys(this._editData).filter(xuid => !this._currentServerPermissions.some(p => p.xuid === xuid)).length;
            size += Math.ceil(combinedListLength * 0.6);
            size += 3; // "Add Player" section
            if (Object.keys(this._editData).length > 0) size +=1;
        }
    } else {
        size = 2; // Just show config error
    }
    return Math.max(4, Math.ceil(size));
  }
}
customElements.define("bsm-permissions-card", BsmPermissionsCard);

// --- START: EDITOR ELEMENT DEFINITION ---
class BsmPermissionsCardEditor extends LitElement {
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
    if (!this._config || !this.hass) return;
    const target = ev.target;
    const newConfig = { ...this._config };
    const configKey = target.configValue;
    if (target.value === "" && configKey === "title") {
        delete newConfig[configKey];
    } else {
        newConfig[configKey] = target.value;
    }
    fireEvent(this, "config-changed", { config: newConfig });
  }

  _selectorChanged(ev) {
     if (!this._config || !this.hass) return;
     ev.stopPropagation();
     const target = ev.target;
     const configKey = target.configValue;
     const newValue = ev.detail.value;
     if (newValue !== this._config[configKey]) {
        const newConfig = { ...this._config };
        newConfig[configKey] = newValue;
        fireEvent(this, "config-changed", { config: newConfig });
     }
  }

  render() {
    if (!this.hass || !this._config) {
      return html``;
    }
    const globalPlayersSelectorConfig = {
      entity: { integration: DOMAIN, domain: "sensor" }
    };
    const isGlobalPlayerEntityMissing = !this._config.global_players_entity;
    return html`
      <ha-textfield
        label="Card Title (Optional)"
        .value=${this._config.title || ""}
        .configValue=${"title"}
        @input=${this._valueChanged}
        helper="Overrides the default card title"
      ></ha-textfield>
      <ha-selector
        label="Global Players Sensor (Required)"
        .hass=${this.hass}
        .selector=${globalPlayersSelectorConfig}
        .value=${this._config.global_players_entity || ""}
        .configValue=${"global_players_entity"}
        @value-changed=${this._selectorChanged}
        helper="Sensor providing the list of global players"
        required
        ?invalid=${isGlobalPlayerEntityMissing}
      ></ha-selector>
      ${isGlobalPlayerEntityMissing ? html`<p class="error-text">This field is required for the card to function.</p>` : ""}
    `;
  }

  static get styles() {
    return css`
      ha-textfield, ha-selector {
        display: block;
        margin-bottom: 16px;
      }
      .error-text {
          color: var(--error-color);
          font-size: 0.9em;
          margin-top: -12px;
          margin-bottom: 8px;
      }
      p { margin-top: 0; }
    `;
  }
}
customElements.define("bsm-permissions-card-editor", BsmPermissionsCardEditor);
// --- END: EDITOR ELEMENT DEFINITION ---

// --- START: WINDOW REGISTRATION ---
window.customCards = window.customCards || [];
window.customCards.push({
  type: "bsm-permissions-card",
  name: "Server Permissions Card",
  description: "View and manage player permissions for a selected Bedrock server.",
  preview: true,
});
_LOGGER.info(`%c BSM-PERMISSIONS-CARD %c LOADED (incl. editor) %c`, "color: purple; font-weight: bold; background: black", "color: white; font-weight: bold; background: dimgray", "");
// --- END: WINDOW REGISTRATION ---