// bsm-plugins-card.js
import {
    LitElement,
    html,
    css
} from "https://unpkg.com/lit-element@2.0.1/lit-element.js?module";

const CARD_VERSION = "0.2.0"; // Version of this card
const DOMAIN = "bedrock_server_manager";
const _LOGGER = {
    debug: (...args) => console.debug("BSM_PLUGINS_CARD:", ...args),
    info: (...args) => console.info("BSM_PLUGINS_CARD:", ...args),
    warn: (...args) => console.warn("BSM_PLUGINS_CARD:", ...args),
    error: (...args) => console.error("BSM_PLUGINS_CARD:", ...args),
};

// Helper to fire events
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

class BsmPluginsCard extends LitElement {

    static get properties() {
        return {
            // hass will be provided by Lovelace, no need for custom setter if only reading
            hass: { type: Object },
            config: { type: Object }, // Original card configuration
            _plugins: { state: true }, // Internal state for plugin data
            _managerDeviceId: { state: true }, // Derived from manager_entity
            _error: { state: true },
            _feedback: { state: true },
            _isLoading: { state: true }, // For service calls
        };
    }

    // --- UI CONFIG METHODS ---
    static async getConfigElement() {
        return document.createElement("bsm-plugins-card-editor");
    }

    static getStubConfig(hass) {
        // Try to find a relevant sensor and button
        let defaultManagerSensor = "";
        let defaultReloadButton = "";
        if (hass) {
            const potentialSensors = Object.keys(hass.states).filter(
                (eid) => eid.startsWith("sensor.") &&
                hass.states[eid].attributes?.integration === DOMAIN &&
                (eid.includes("plugin_statuses") || eid.includes("total_plugins"))
            );
            if (potentialSensors.length > 0) {
                defaultManagerSensor = potentialSensors[0];
            }
            const potentialButtons = Object.keys(hass.states).filter(
                (eid) => eid.startsWith("button.") &&
                hass.states[eid].attributes?.integration === DOMAIN &&
                eid.includes("reload_plugins")
            );
            if (potentialButtons.length > 0) {
                defaultReloadButton = potentialButtons[0];
            }
        }
        return {
            title: "Bedrock Server Plugins",
            manager_entity: defaultManagerSensor,
            reload_button_entity: defaultReloadButton,
        };
    }
    // --- END UI CONFIG METHODS ---

    constructor() {
        super();
        this._plugins = {};
        this._error = null;
        this._feedback = null;
        this._isLoading = false;
        this._managerDeviceId = null;
        _LOGGER.debug("BSM Plugins Card constructor finished.");
    }

    setConfig(config) {
        _LOGGER.debug("setConfig called with:", config);
        if (!config.manager_entity) {
            throw new Error("Configuration error: 'manager_entity' is required.");
        }
        if (!config.reload_button_entity) {
            throw new Error("Configuration error: 'reload_button_entity' is required.");
        }
        // Basic validation for entity ID format
        if (typeof config.manager_entity !== 'string' || !config.manager_entity.includes('.')) {
            throw new Error("'manager_entity' must be a valid entity ID (e.g., sensor.my_plugins_sensor).");
        }
        if (typeof config.reload_button_entity !== 'string' || !config.reload_button_entity.includes('.')) {
            throw new Error("'reload_button_entity' must be a valid entity ID (e.g., button.my_reload_button).");
        }

        const oldConfig = this.config;
        this.config = { ...config }; // Store the raw config

        // If hass is already available, try to fetch initial data
        if (this.hass) {
            this._updateDataFromHass(this.hass);
        }
        this.requestUpdate('config', oldConfig);
    }
    
    // This is called by LitElement when `hass` property is set or changes
    updated(changedProperties) {
        if (changedProperties.has('hass') && this.hass) {
            _LOGGER.debug("Hass object updated, re-evaluating data.");
            this._updateDataFromHass(this.hass, changedProperties.get('hass'));
        }
    }

    _updateDataFromHass(newHass, oldHass) {
        if (!this.config || !this.config.manager_entity) {
            this._plugins = {};
            this._managerDeviceId = null;
            this.requestUpdate();
            return;
        }

        const entityId = this.config.manager_entity;
        const stateObj = newHass.states[entityId];
        const oldStateObj = oldHass?.states[entityId];

        if (!stateObj) {
            if (oldStateObj) { // It was there, now it's gone
                this._error = `Entity not found: ${entityId}`;
                this._plugins = {};
                this._managerDeviceId = null;
                _LOGGER.warn(this._error);
            } else if (!this._error) { // Never found, or error cleared
                 this._feedback = `Waiting for entity: ${entityId}`;
            }
            this.requestUpdate();
            return;
        }

        // Clear error/feedback if entity is found
        this._error = null;
        this._feedback = null;
        
        // Get manager device ID from the sensor entity
        const entityReg = newHass.entities?.[entityId];
        this._managerDeviceId = entityReg?.device_id || stateObj.attributes?.device_id || null;
        if (!this._managerDeviceId) {
            _LOGGER.warn(`Could not determine device ID for manager entity ${entityId}. Service calls for toggling plugins might fail.`);
        }


        const newPluginsData = stateObj.attributes?.plugins_data;
        let pluginsChanged = JSON.stringify(newPluginsData || {}) !== JSON.stringify(this._plugins || {});

        if (pluginsChanged) {
            this._plugins = newPluginsData && typeof newPluginsData === 'object' ? { ...newPluginsData } : {};
            _LOGGER.debug("Plugin data updated from sensor:", entityId, "Found plugins:", Object.keys(this._plugins).length);
        }
        
        if (pluginsChanged || !oldHass || (stateObj !== oldStateObj) ) {
             this.requestUpdate();
        }
    }


    _togglePlugin(pluginName, currentStatus) {
        if (!this.hass || !this._managerDeviceId) {
            this._error = "Cannot toggle plugin: Manager device ID not available.";
            _LOGGER.error(this._error);
            this.requestUpdate();
            return;
        }
        this._isLoading = true;
        this._error = null;
        this._feedback = `Toggling ${pluginName}...`;
        this.requestUpdate();

        this.hass.callService(DOMAIN, "set_plugin_enabled", {
            // device_id targeting is implicit if the service is registered to the device
            // or we can explicitly target if needed: target: { device_id: this._managerDeviceId }
            plugin_name: pluginName,
            plugin_enabled: !currentStatus
        }, { device_id: this._managerDeviceId }) // Corrected Target (4th argument is the ServiceTarget object)
        .then(() => {
            this._feedback = `Plugin '${pluginName}' toggle request sent. State will update via sensor.`;
            _LOGGER.info(`Toggled plugin ${pluginName} to ${!currentStatus} for device ${this._managerDeviceId}`);
        }).catch(err => {
            this._error = `Error toggling plugin '${pluginName}': ${err.message || err}`;
            _LOGGER.error(this._error);
            this._feedback = null;
        }).finally(() => {
            this._isLoading = false;
            this.requestUpdate();
        });
    }

    _reloadPlugins() {
        if (!this.hass || !this.config.reload_button_entity) {
            this._error = "Cannot reload plugins: Reload button entity not configured.";
            _LOGGER.error(this._error);
            this.requestUpdate();
            return;
        }
        this._isLoading = true;
        this._error = null;
        this._feedback = "Reloading plugins...";
        this.requestUpdate();

        this.hass.callService("button", "press", {
            entity_id: this.config.reload_button_entity
        }).then(() => {
             this._feedback = "Plugin reload request sent. Status will update via sensor.";
             _LOGGER.info("Reload plugins button pressed via service call.");
        }).catch(err => {
            this._error = `Error pressing reload plugins button: ${err.message || err}`;
            _LOGGER.error(this._error);
            this._feedback = null;
        }).finally(() => {
            this._isLoading = false;
            this.requestUpdate();
        });
    }

    render() {
        if (!this.config || !this.config.manager_entity || !this.config.reload_button_entity) {
            return html`
                <ha-card header="Bedrock Server Plugins">
                    <div class="card-content">
                        <p>Error: Card not fully configured. Please set 'manager_entity' and 'reload_button_entity'.</p>
                    </div>
                </ha-card>
            `;
        }

        if (!this.hass) {
             return html`<ha-card header="${this.config.title || "Bedrock Server Plugins"}"><div class="card-content">Waiting for Home Assistant...</div></ha-card>`;
        }
        
        const managerState = this.hass.states[this.config.manager_entity];
        if (!managerState) {
             return html`
                <ha-card header="${this.config.title || "Bedrock Server Plugins"}">
                    <div class="card-content">
                        <p>Entity not found: ${this.config.manager_entity}. Please check your configuration.</p>
                        ${this._feedback ? html`<p class="feedback">${this._feedback}</p>` : ""}
                    </div>
                </ha-card>
            `;
        }


        const pluginEntries = Object.entries(this._plugins || {});

        return html`
            <ha-card header="${this.config.title || "Bedrock Server Plugins"}">
                <div class="card-content">
                    ${this._error ? html`<p class="error">${this._error}</p>` : ""}
                    ${this._feedback ? html`<p class="feedback">${this._feedback}</p>` : ""}
                    ${this._isLoading && !this._error && !this._feedback ? html`<p class="feedback">Processing...</p>` : ""}

                    ${pluginEntries.length === 0 && !this._isLoading && !this._error
                        ? html`<p>No plugin data found or no plugins installed.</p>`
                        : pluginEntries.map(([name, details]) => {
                            if (typeof details !== 'object' || details === null) {
                                _LOGGER.warn(`Plugin '${name}' has invalid data:`, details);
                                return html`<div class="plugin-entry error">Plugin '${name}' has invalid data structure.</div>`;
                            }
                            return html`
                                <div class="plugin-entry">
                                    <div class="plugin-info">
                                        <div class="plugin-name">${name}</div>
                                        <div class="plugin-version">v${details.version || 'N/A'}</div>
                                        <div class="plugin-description">${details.description || 'No description.'}</div>
                                    </div>
                                    <ha-switch
                                        .checked=${details.enabled === true}
                                        @change=${() => this._togglePlugin(name, details.enabled)}
                                        .disabled=${this._isLoading}
                                    ></ha-switch>
                                </div>`;
                        })}
                </div>
                <div class="card-actions">
                    <mwc-button 
                        @click=${this._reloadPlugins}
                        .disabled=${this._isLoading}
                        label="Reload All Plugins"
                        raised
                    ></mwc-button>
                </div>
            </ha-card>
        `;
    }

    static get styles() {
        return css`
            .plugin-entry {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 0;
                border-bottom: 1px solid var(--divider-color);
            }
            .plugin-entry:last-child {
                border-bottom: none;
            }
            .plugin-info {
                flex-grow: 1;
                margin-right: 16px;
            }
            .plugin-name {
                font-weight: bold;
            }
            .plugin-version {
                font-size: 0.9em;
                color: var(--secondary-text-color);
            }
            .plugin-description {
                font-size: 0.9em;
                color: var(--primary-text-color);
                margin-top: 4px;
            }
            .card-actions {
                padding: 8px 16px;
                display: flex;
                justify-content: flex-end;
            }
            .error {
                color: var(--error-color);
                font-weight: bold;
                padding: 8px;
            }
            .feedback {
                color: var(--secondary-text-color);
                font-style: italic;
                padding: 8px;
            }
        `;
    }

    getCardSize() {
        const numPlugins = Object.keys(this._plugins || {}).length;
        return 3 + Math.ceil(numPlugins / 2); // Base size + ~0.5 per plugin
    }
}

// --- EDITOR ELEMENT ---
class BsmPluginsCardEditor extends LitElement {
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

        if (target.value === "" && (configKey === "title" || target.required === false)) {
            delete newConfig[configKey];
        } else {
            newConfig[configKey] = target.value;
        }
        fireEvent(this, "config-changed", { config: newConfig });
    }
    
    _selectorChanged(ev) {
        if (!this._config || !this.hass) return;
        ev.stopPropagation(); // Important for ha-selector inside editor
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
        if (!this.hass || !this._config) return html``;

        const managerSensorSelectorConfig = { entity: { integration: DOMAIN, domain: "sensor" }};
        const reloadButtonSelectorConfig = { entity: { integration: DOMAIN, domain: "button" }};

        return html`
            <ha-textfield
                label="Card Title (Optional)"
                .value=${this._config.title || ""}
                .configValue=${"title"}
                @input=${this._valueChanged}
                helper="Overrides the default card title"
            ></ha-textfield>
            <ha-selector
                label="Plugins Sensor (Required)"
                .hass=${this.hass}
                .selector=${managerSensorSelectorConfig}
                .value=${this._config.manager_entity || ""}
                .configValue=${"manager_entity"}
                @value-changed=${this._selectorChanged}
                helper="Sensor holding plugin statuses (e.g., sensor.bsm_total_plugins)"
                required
                ?invalid=${!this._config.manager_entity}
            ></ha-selector>
            <ha-selector
                label="Reload Plugins Button (Required)"
                .hass=${this.hass}
                .selector=${reloadButtonSelectorConfig}
                .value=${this._config.reload_button_entity || ""}
                .configValue=${"reload_button_entity"}
                @value-changed=${this._selectorChanged}
                helper="Button entity for reloading plugins (e.g., button.bsm_reload_plugins)"
                required
                ?invalid=${!this._config.reload_button_entity}
            ></ha-selector>
        `;
    }

    static get styles() {
        return css`
            ha-textfield, ha-selector {
                display: block;
                margin-bottom: 16px;
            }
        `;
    }
}
customElements.define("bsm-plugins-card-editor", BsmPluginsCardEditor);
// --- END EDITOR ELEMENT ---


customElements.define("bsm-plugins-card", BsmPluginsCard);
_LOGGER.info(`%cBSM-PLUGINS-CARD ${CARD_VERSION} IS INSTALLED%c (incl. editor)`, "color: green; font-weight: bold;", "color: green;");

window.customCards = window.customCards || [];
const existingCardIndex = window.customCards.findIndex(card => card.type === "bsm-plugins-card");
if (existingCardIndex === -1) {
    window.customCards.push({
        type: "bsm-plugins-card",
        name: "BSM Plugins Card",
        preview: true,
        description: "A card to manage Bedrock Server Manager plugins."
    });
} else {
    // Optionally update if already exists, e.g., if versioning/hot-reloading
    window.customCards[existingCardIndex] = {
        type: "bsm-plugins-card",
        name: "BSM Plugins Card",
        preview: true,
        description: "A card to manage Bedrock Server Manager plugins."
    };
}
