import { LitElement, html, css } from "https://unpkg.com/lit-element@^2.0.0/lit-element.js?module";

const DOMAIN = "bedrock_server_manager";

const _LOGGER = {
    debug: (...args) => console.debug("BSM_ADDON_CARD:", ...args),
    info: (...args) => console.info("BSM_ADDON_CARD:", ...args),
    warn: (...args) => console.warn("BSM_ADDON_CARD:", ...args),
    error: (...args) => console.error("BSM_ADDON_CARD:", ...args),
};

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

class BsmAddonCard extends LitElement {
  static async getConfigElement() {
    return document.createElement("bsm-addon-card-editor");
  }

  static getStubConfig() {
    return {
      title: "Server Installed Addons",
    };
  }

  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _selectedTargetServerSensorId: { state: true },
      _activeTab: { state: true }, // "behavior" or "resource"
      _isLoading: { state: true },
      _error: { state: true },
      _feedback: { state: true },
      _addons: { state: true },
      _orderChanged: { state: true },
    };
  }

  constructor() {
    super();
    this._selectedTargetServerSensorId = null;
    this._activeTab = "behavior";
    this._isLoading = false;
    this._error = null;
    this._feedback = "Select a target server.";
    this._addons = { behavior_packs: [], resource_packs: [] };
    this._orderChanged = false;
  }

  setConfig(config) {
    if (!config) {
      throw new Error("Invalid configuration");
    }
    this.config = config;
    if (this.config.target_server_sensor_entity && this.config.target_server_sensor_entity !== this._selectedTargetServerSensorId) {
        this._handleTargetServerSensorChange(this.config.target_server_sensor_entity);
    }
  }

  __hass;
  get hass() { return this.__hass; }
  set hass(hass) {
    const oldHass = this.__hass;
    this.__hass = hass;

    if (hass && this._selectedTargetServerSensorId) {
        const sourceStateObj = hass.states[this._selectedTargetServerSensorId];
        const oldSourceStateObj = oldHass?.states[this._selectedTargetServerSensorId];

        if (sourceStateObj && (sourceStateObj !== oldSourceStateObj ||
            JSON.stringify(sourceStateObj.attributes ?? null) !== JSON.stringify(oldSourceStateObj?.attributes ?? null))) {
            this._processSelectedTargetServerSensor(sourceStateObj);
        } else if (!sourceStateObj && oldSourceStateObj) {
            this._handleTargetServerSensorChange(null);
            this._error = `Server sensor ${this._selectedTargetServerSensorId} is no longer available.`;
        }
    } else if (!this._selectedTargetServerSensorId && this.config?.target_server_sensor_entity) {
        const configSensorId = this.config.target_server_sensor_entity;
        const configStateObj = hass?.states[configSensorId];
        if (configStateObj) {
            this._selectedTargetServerSensorId = configSensorId;
            this._processSelectedTargetServerSensor(configStateObj);
        }
    }

    if (oldHass !== hass) {
        this.requestUpdate('hass', oldHass);
    }
  }

  _handleTargetServerSensorChange(entityId) {
    if (entityId === this._selectedTargetServerSensorId) return;

    this._selectedTargetServerSensorId = entityId || null;
    this._error = null;
    this._orderChanged = false;
    this._addons = { behavior_packs: [], resource_packs: [] };

    if (!this._selectedTargetServerSensorId) {
        this._feedback = "Select a target server.";
        this.requestUpdate();
        return;
    }

    this._feedback = `Processing server sensor ${this._selectedTargetServerSensorId}...`;
    this.requestUpdate();

    if (this.hass && this.hass.states[this._selectedTargetServerSensorId]) {
      this._processSelectedTargetServerSensor(this.hass.states[this._selectedTargetServerSensorId]);
    } else {
      this._feedback = "Waiting for sensor data...";
    }
  }

  _processSelectedTargetServerSensor(stateObj) {
    if (!stateObj?.attributes) {
      this._error = `Selected sensor (${stateObj.entity_id}) has missing state or attributes.`;
      this._feedback = "";
      this._addons = { behavior_packs: [], resource_packs: [] };
      this.requestUpdate();
      return;
    }

    if (stateObj.attributes.server_addons_list) {
        const addonsData = stateObj.attributes.server_addons_list;
        
        let bp = (addonsData.behavior_packs || []).map((p) => ({...p, id: p.uuid}));
        let rp = (addonsData.resource_packs || []).map((p) => ({...p, id: p.uuid}));
        
        this._addons = { behavior_packs: bp, resource_packs: rp };
        this._error = null;
        this._feedback = "";
    } else {
        this._error = `Could not load addons. Attribute 'server_addons_list' not found on ${stateObj.entity_id}.`;
        this._addons = { behavior_packs: [], resource_packs: [] };
        this._feedback = "";
    }
    this.requestUpdate();
  }

  async _performAction(serviceName, data, successMsg) {
    if (!this._selectedTargetServerSensorId) return;
    
    // We need device_id for targeting services. We can extract it from the sensor's device ID.
    // Or we use entity_id if the service schema uses TARGETING_SCHEMA_FIELDS correctly with entity_id.
    const serviceData = {
        entity_id: this._selectedTargetServerSensorId,
        ...data
    };

    this._isLoading = true;
    this._error = null;
    this.requestUpdate();

    try {
        await this.hass.callService(DOMAIN, serviceName, serviceData);
        this._feedback = successMsg;
        // Changes should reflect in the sensor automatically.
    } catch (err) {
        let message = "Unknown error";
        if (err instanceof Error) message = err.message;
        else if (err && err.message) message = err.message;
        this._error = `Error: ${message}`;
        this._feedback = "";
    } finally {
        this._isLoading = false;
        this.requestUpdate();
    }
  }

  async handleAddonAction(pack, packType, action) {
    if (action === "uninstall" && !confirm(`Are you sure you want to uninstall ${pack.name}?`)) return;
    const serviceName = action + "_addon";
    await this._performAction(serviceName, { pack_uuid: pack.uuid, pack_type: packType }, `${action} successful.`);
  }

  async handleSubpackChange(pack, packType, newSubpackFolderName) {
    await this._performAction("update_addon_subpack", {
        pack_uuid: pack.uuid,
        pack_type: packType,
        subpack_name: newSubpackFolderName
    }, "Subpack updated.");
  }

  async handleSaveAddonOrder() {
    const listKey = this._activeTab === "behavior" ? "behavior_packs" : "resource_packs";
    const activeUuids = this._addons[listKey]
      .filter((p) => p.status === "ACTIVE" && p.uuid)
      .map((p) => p.uuid);

    if (activeUuids.length > 0) {
      await this._performAction("reorder_addons", {
        pack_type: this._activeTab,
        uuids: activeUuids
      }, "Addon order saved.");
      this._orderChanged = false;
    }
  }

  moveItem(index, direction) {
    const listKey = this._activeTab === "behavior" ? "behavior_packs" : "resource_packs";
    const items = [...this._addons[listKey]];
    
    if (direction === -1 && index > 0) {
        const temp = items[index];
        items[index] = items[index - 1];
        items[index - 1] = temp;
        this._addons = { ...this._addons, [listKey]: items };
        this._orderChanged = true;
    } else if (direction === 1 && index < items.length - 1) {
        const temp = items[index];
        items[index] = items[index + 1];
        items[index + 1] = temp;
        this._addons = { ...this._addons, [listKey]: items };
        this._orderChanged = true;
    }
  }

  renderAddonItem(item, packType, index, totalItems) {
    const isActive = item.status === "ACTIVE";
    const statusColor = isActive ? "var(--success-color, #4CAF50)" : "var(--disabled-text-color, #777)";
    const versionStr = Array.isArray(item.version) ? item.version.join(".") : "Unknown";

    const subpacks = item.subpacks || [];
    const hasSubpacks = subpacks.length > 0;

    let activeSubpack = item.active_subpack;
    if (!activeSubpack || !subpacks.find((sp) => sp.folder_name === activeSubpack)) {
      activeSubpack = hasSubpacks ? subpacks[0].folder_name : "";
    }

    return html`
      <div class="addon-item">
        <div class="addon-header">
          <div class="reorder-controls">
             <mwc-icon-button icon="keyboard_arrow_up" @click=${() => this.moveItem(index, -1)} ?disabled=${index === 0}></mwc-icon-button>
             <mwc-icon-button icon="keyboard_arrow_down" @click=${() => this.moveItem(index, 1)} ?disabled=${index === totalItems - 1}></mwc-icon-button>
          </div>
          <div class="addon-info">
            <h4>${item.name || "Unknown Pack"}</h4>
            <div class="addon-meta">
              <span>v${versionStr}</span>
              <span class="status-indicator">
                <span class="dot" style="background-color: ${statusColor}"></span>
                ${item.status || "UNKNOWN"}
              </span>
            </div>
          </div>
        </div>

        ${isActive && hasSubpacks ? html`
          <div class="subpack-selector">
            <label>Active Subpack:</label>
            <select
              .value=${activeSubpack}
              @change=${(e) => this.handleSubpackChange(item, packType, e.target.value)}
              ?disabled=${this._isLoading}
            >
              ${subpacks.map((sp) => html`<option value="${sp.folder_name}">${sp.name}</option>`)}
            </select>
          </div>
        ` : ""}

        <div class="addon-actions">
          ${isActive ? html`
            <mwc-button label="Disable" @click=${() => this.handleAddonAction(item, packType, "disable")} ?disabled=${this._isLoading}></mwc-button>
          ` : html`
            <mwc-button label="Enable" @click=${() => this.handleAddonAction(item, packType, "enable")} ?disabled=${this._isLoading} class="success-btn"></mwc-button>
          `}
          <mwc-button label="Uninstall" @click=${() => this.handleAddonAction(item, packType, "uninstall")} ?disabled=${this._isLoading} class="danger-btn"></mwc-button>
        </div>
      </div>
    `;
  }

  render() {
    if (!this.hass) { return html`<ha-card>Waiting for Home Assistant...</ha-card>`; }

    const cardTitle = this.config?.title || "Installed Addons";
    const sourceSensorSelectorConfig = { entity: { integration: DOMAIN, domain: "sensor" }};

    const currentList = this._activeTab === "behavior" ? this._addons.behavior_packs : this._addons.resource_packs;

    return html`
      <ha-card header="${cardTitle}">
        <div class="card-content">
          <ha-selector
            label="Server Status Sensor"
            .hass=${this.hass}
            .selector=${sourceSensorSelectorConfig}
            .value=${this._selectedTargetServerSensorId}
            @value-changed=${(ev) => this._handleTargetServerSensorChange(ev.detail.value)}
            helper="Sensor tracking the target server (e.g., status sensor)"
            ?required=${!this._selectedTargetServerSensorId}
          ></ha-selector>

          ${this._selectedTargetServerSensorId ? html`
            <div class="tabs">
              <mwc-button label="Behavior Packs" @click=${() => this._activeTab = "behavior"} ?raised=${this._activeTab === "behavior"}></mwc-button>
              <mwc-button label="Resource Packs" @click=${() => this._activeTab = "resource"} ?raised=${this._activeTab === "resource"}></mwc-button>
            </div>

            <div class="addon-list">
              ${currentList.length > 0 ? html`
                ${currentList.map((item, index) => this.renderAddonItem(item, this._activeTab, index, currentList.length))}
              ` : html`
                <div class="empty-state">No ${this._activeTab} packs installed.</div>
              `}
            </div>

            <div class="save-order-container">
              <mwc-button label="Save Order" @click=${this.handleSaveAddonOrder} ?disabled=${!this._orderChanged || this._isLoading} raised></mwc-button>
            </div>
          ` : ""}

          <div class="status-area">
            ${this._isLoading ? html`<div class="loading"><ha-circular-progress indeterminate size="small"></ha-circular-progress> Processing...</div>` : ""}
            ${!this._isLoading && this._feedback ? html`<div class="feedback">${this._feedback}</div>` : ""}
            ${!this._isLoading && this._error ? html`<div class="error">${this._error}</div>` : ""}
          </div>
        </div>
      </ha-card>
    `;
  }

  static get styles() {
    return css`
      :host { display: block; }
      .card-content { padding: 16px; }
      ha-selector { display: block; width: 100%; margin-bottom: 16px; }
      .tabs { display: flex; gap: 8px; margin-bottom: 16px; border-bottom: 1px solid var(--divider-color); padding-bottom: 8px; }
      .addon-list { display: flex; flex-direction: column; gap: 12px; max-height: 400px; overflow-y: auto; }
      .addon-item { border: 1px solid var(--divider-color); border-radius: 4px; padding: 8px; background: var(--card-background-color, #fff); }
      .addon-header { display: flex; align-items: center; gap: 8px; }
      .reorder-controls { display: flex; flex-direction: column; }
      .reorder-controls mwc-icon-button { --mdc-icon-button-size: 24px; --mdc-icon-size: 20px; }
      .addon-info { flex: 1; overflow: hidden; }
      .addon-info h4 { margin: 0 0 4px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .addon-meta { font-size: 0.85em; color: var(--secondary-text-color); display: flex; gap: 12px; align-items: center; }
      .status-indicator { display: flex; align-items: center; gap: 4px; }
      .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; }
      .subpack-selector { margin-top: 8px; padding: 8px; background: var(--secondary-background-color); border-radius: 4px; display: flex; align-items: center; gap: 8px; font-size: 0.85em; }
      .subpack-selector select { flex: 1; padding: 4px; }
      .addon-actions { margin-top: 8px; display: flex; justify-content: flex-end; gap: 8px; border-top: 1px solid var(--divider-color); padding-top: 8px; }
      .success-btn { --mdc-theme-primary: var(--success-color, #4CAF50); }
      .danger-btn { --mdc-theme-primary: var(--error-color, #F44336); }
      .save-order-container { margin-top: 16px; display: flex; justify-content: flex-end; border-top: 1px solid var(--divider-color); padding-top: 16px; }
      .empty-state { text-align: center; padding: 24px; color: var(--secondary-text-color); font-style: italic; }
      .status-area { margin-top: 16px; min-height: 1.2em; }
      .error { color: var(--error-color); font-weight: bold; }
      .feedback { color: var(--secondary-text-color); font-size: 0.9em; }
      .loading { display: flex; align-items: center; gap: 8px; color: var(--secondary-text-color); }
    `;
  }
}

customElements.define("bsm-addon-card", BsmAddonCard);

class BsmAddonCardEditor extends LitElement {
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

    if (target.value === "") {
       if (configKey === "title") delete newConfig[configKey];
       else newConfig[configKey] = "";
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
        if (newValue === "" || newValue === null) newConfig[configKey] = "";
        else newConfig[configKey] = newValue;
        fireEvent(this, "config-changed", { config: newConfig });
     }
  }

  render() {
    if (!this.hass || !this._config) return html``;

    const sourceSensorSelectorConfig = {
      entity: { integration: DOMAIN, domain: "sensor" }
    };

    return html`
      <ha-textfield
        label="Card Title (Optional)"
        .value=${this._config.title || ""}
        .configValue=${"title"}
        @input=${this._valueChanged}
      ></ha-textfield>

      <ha-selector
        label="Target Server Sensor"
        .hass=${this.hass}
        .selector=${sourceSensorSelectorConfig}
        .value=${this._config.target_server_sensor_entity || ""}
        .configValue=${"target_server_sensor_entity"}
        @value-changed=${this._selectorChanged}
      ></ha-selector>
    `;
  }

  static get styles() {
    return css`
      ha-textfield, ha-selector { display: block; margin-bottom: 16px; }
    `;
  }
}

customElements.define("bsm-addon-card-editor", BsmAddonCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "bsm-addon-card",
  name: "Installed Addons",
  description: "Manage installed behavior and resource packs on a Bedrock server.",
  preview: true,
});
