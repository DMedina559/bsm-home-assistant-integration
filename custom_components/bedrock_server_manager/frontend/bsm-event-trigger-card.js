// bsm-event-trigger-card.js
import {
    LitElement,
    html,
    css
} from "https://unpkg.com/lit-element@2.0.1/lit-element.js?module";

const CARD_VERSION = "0.2.0"; // Version of this card
const DOMAIN = "bedrock_server_manager";
const _LOGGER = {
    debug: (...args) => console.debug("BSM_EVENT_CARD:", ...args),
    info: (...args) => console.info("BSM_EVENT_CARD:", ...args),
    warn: (...args) => console.warn("BSM_EVENT_CARD:", ...args),
    error: (...args) => console.error("BSM_EVENT_CARD:", ...args),
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

class BsmEventTriggerCard extends LitElement {

    static get properties() {
        return {
            hass: { type: Object },
            config: { type: Object }, // Raw config
            _eventName: { state: true },
            _eventPayload: { state: true },
            _error: { state: true },
            _feedback: { state: true },
            _isLoading: { state: true },
            // target_device_id is directly from config, not reactive state for the card itself once set
        };
    }

    // --- UI CONFIG METHODS ---
    static async getConfigElement() {
        return document.createElement("bsm-event-trigger-card-editor");
    }

    static getStubConfig(hass) {
         let defaultTargetDevice = "";
         // Attempt to find a BSM device to pre-fill
         if (hass && hass.devices) {
            const bsmDeviceIds = Object.keys(hass.devices).filter(deviceId => 
                hass.devices[deviceId].identifiers.some(ident => ident[0] === DOMAIN) &&
                !hass.devices[deviceId].model?.toLowerCase().includes("server") // Try to get manager, not server
            );
            if (bsmDeviceIds.length > 0) {
                defaultTargetDevice = bsmDeviceIds[0];
            }
         }
        return {
            title: "Trigger BSM Plugin Event",
            target_device: defaultTargetDevice,
        };
    }
    // --- END UI CONFIG METHODS ---

    constructor() {
        super();
        this._eventName = "";
        this._eventPayload = "";
        this._error = null;
        this._feedback = null;
        this._isLoading = false;
        _LOGGER.debug("BSM Event Trigger Card constructor finished.");
    }

    setConfig(config) {
        _LOGGER.debug("setConfig called with:", config);
        if (!config.target_device) {
            throw new Error("Configuration error: 'target_device' (BSM Manager Device ID) is required.");
        }
        if (typeof config.target_device !== 'string' || config.target_device.trim() === '') {
             throw new Error("'target_device' must be a valid, non-empty string.");
        }

        const oldConfig = this.config;
        this.config = { ...config };
        // No specific HASS data to fetch for this card's primary function,
        // but requestUpdate if config changes might affect display (e.g. title)
        this.requestUpdate('config', oldConfig);
    }
    
    // No specific hass property setter needed if not directly observing states for this card

    _handleEventNameChange(e) {
        this._eventName = e.target.value;
        this.requestUpdate("_eventName");
    }

    _handlePayloadChange(e) {
        this._eventPayload = e.target.value;
        this.requestUpdate("_eventPayload");
    }

    _triggerEvent() {
        if (!this.hass) {
            this._error = "Home Assistant connection not available.";
            this._feedback = null; this.requestUpdate(); return;
        }
        if (!this.config.target_device) {
            this._error = "Target BSM device not configured for this card.";
            this._feedback = null; this.requestUpdate(); return;
        }
        if (!this._eventName || this._eventName.trim() === "") {
            this._error = "Event Name is required.";
            this._feedback = null; this.requestUpdate(); return;
        }

        let payloadObject = null;
        if (this._eventPayload && this._eventPayload.trim() !== "") {
            try {
                payloadObject = JSON.parse(this._eventPayload);
            } catch (error) {
                this._error = "Invalid JSON in payload: " + error.message;
                this._feedback = null; this.requestUpdate(); return;
            }
        }

        this._isLoading = true;
        this._error = null;
        this._feedback = `Triggering event '${this._eventName}'...`;
        this.requestUpdate();

        const serviceDataPayload = {
            event_name: this._eventName,
        };
        if (payloadObject !== null) {
            serviceDataPayload.event_payload = payloadObject;
        }
        
        const callOptions = {
            // Corrected: The 4th argument to callService is the ServiceTarget object itself
            device_id: this.config.target_device
        };

        this.hass.callService(DOMAIN, "trigger_plugin_event", serviceDataPayload, callOptions)
            .then(() => {
                this._feedback = `Event '${this._eventName}' triggered successfully on device ${this.config.target_device}.`;
                // Optionally clear fields:
                // this._eventName = ""; 
                // this._eventPayload = "";
            })
            .catch(err => {
                this._error = `Error triggering event: ${err.message || err}`;
                _LOGGER.error(this._error);
                this._feedback = null;
            })
            .finally(() => {
                this._isLoading = false;
                this.requestUpdate();
            });
    }

    render() {
        if (!this.config || !this.config.target_device) {
             return html`
                <ha-card header="Trigger BSM Plugin Event">
                    <div class="card-content error">
                        Error: Card not fully configured. Please set 'target_device'.
                    </div>
                </ha-card>
            `;
        }
        if (!this.hass) {
             return html`<ha-card header="${this.config.title || "Trigger BSM Plugin Event"}"><div class="card-content">Waiting for Home Assistant...</div></ha-card>`;
        }

        return html`
            <ha-card header="${this.config.title || "Trigger BSM Plugin Event"}">
                <div class="card-content">
                    ${this._error ? html`<p class="error">${this._error}</p>` : ""}
                    ${this._feedback ? html`<p class="feedback">${this._feedback}</p>` : ""}
                    ${this._isLoading && !this._error && !this._feedback ? html`<p class="feedback">Processing...</p>` : ""}

                    <ha-textfield
                        label="Event Name (e.g., my_plugin:action)"
                        .value=${this._eventName}
                        @input=${this._handleEventNameChange}
                        required
                        auto-validate="true"
                        pattern=".*\\S.*" 
                        error-message="Event name is required!"
                        .disabled=${this._isLoading}
                    ></ha-textfield>
                    <ha-textarea
                        label="Payload (Optional JSON)"
                        .value=${this._eventPayload}
                        @input=${this._handlePayloadChange}
                        placeholder='{ "key": "value", "count": 10 }'
                        .disabled=${this._isLoading}
                        rows="3"
                    ></ha-textarea>
                </div>
                <div class="card-actions">
                    <mwc-button 
                        @click=${this._triggerEvent} 
                        raised 
                        label="Trigger Event"
                        .disabled=${this._isLoading || !this._eventName || this._eventName.trim() === ""}
                    ></mwc-button>
                </div>
            </ha-card>
        `;
    }

    static get styles() {
        return css`
            ha-textfield, ha-textarea {
                display: block;
                margin-bottom: 16px;
                width: 100%;
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
        return 4; // Approximate size
    }
}


// --- EDITOR ELEMENT ---
class BsmEventTriggerCardEditor extends LitElement {
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

    // Specific handler for device selector if needed, or use generic valueChanged for simple string IDs
    _deviceChanged(ev) {
        if (!this._config || !this.hass) return;
        ev.stopPropagation();
        const newConfig = { ...this._config, target_device: ev.detail.value };
        fireEvent(this, "config-changed", { config: newConfig });
    }


    render() {
        if (!this.hass || !this._config) return html``;

        // Selector for BSM manager devices
        const deviceSelectorConfig = {
            device: { integration: DOMAIN } // Allow selecting any device from this integration
            // We might need to be more specific if server devices also exist under the same integration
            // and we only want to show "manager" devices. This might require filtering logic or
            // a more specific selector if the device model/name indicates it's a manager.
        };

        return html`
            <ha-textfield
                label="Card Title (Optional)"
                .value=${this._config.title || ""}
                .configValue=${"title"}
                @input=${this._valueChanged}
                helper="Overrides the default card title"
            ></ha-textfield>
            <ha-device-picker
                label="Target BSM Manager Device (Required)"
                .hass=${this.hass}
                .value=${this._config.target_device || ""}
                @value-changed=${this._deviceChanged}
                .deviceFilter=${(device) => device.identifiers.some(ident => ident[0] === DOMAIN) && !device.model?.toLowerCase().includes("server")}
                helper="Select the Bedrock Server Manager instance to target."
                required
                ?invalid=${!this._config.target_device}
            ></ha-device-picker>
        `;
    }

    static get styles() {
        return css`
            ha-textfield, ha-device-picker {
                display: block;
                margin-bottom: 16px;
            }
        `;
    }
}
customElements.define("bsm-event-trigger-card-editor", BsmEventTriggerCardEditor);
// --- END EDITOR ELEMENT ---


customElements.define("bsm-event-trigger-card", BsmEventTriggerCard);
_LOGGER.info(`%cBSM-EVENT-TRIGGER-CARD ${CARD_VERSION} IS INSTALLED%c (incl. editor)`, "color: blue; font-weight: bold;", "color: blue;");

window.customCards = window.customCards || [];
const existingCardIndex = window.customCards.findIndex(card => card.type === "bsm-event-trigger-card");
if (existingCardIndex === -1) {
    window.customCards.push({
        type: "bsm-event-trigger-card",
        name: "BSM Event Trigger Card",
        preview: true,
        description: "A card to trigger custom Bedrock Server Manager plugin events."
    });
} else {
    window.customCards[existingCardIndex] = {
        type: "bsm-event-trigger-card",
        name: "BSM Event Trigger Card",
        preview: true,
        description: "A card to trigger custom Bedrock Server Manager plugin events."
    };
}
