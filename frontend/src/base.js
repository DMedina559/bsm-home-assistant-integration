import { LitElement, html, nothing } from "lit";
import { styles } from "./styles.js";
import {
  DOMAIN,
  Draft,
  entities,
  related,
  unavailable,
  label,
  taskError,
  copy,
} from "./model.js";
export { html, nothing, DOMAIN, related, unavailable, label };

export function register(tag, type, name, description) {
  if (!customElements.get(tag)) customElements.define(tag, type);
  window.customCards ||= [];
  if (!window.customCards.some((card) => card.type === tag))
    window.customCards.push({ type: tag, name, description, preview: true });
}
export class BsmCard extends LitElement {
  static properties = {
    hass: { attribute: false },
    config: { state: true },
    selection: { state: true },
    busy: { state: true },
    error: { state: true },
    feedback: { state: true },
    confirmation: { state: true },
    revision: { state: true },
  };
  static styles = styles;
  static role = "server";
  static key = "status";
  static title = "Bedrock Server Manager";
  static getConfigForm() {
    return {
      schema: [
        { name: "title", selector: { text: {} } },
        { name: "entity", selector: { entity: { integration: DOMAIN } } },
        { name: "debug", selector: { boolean: {} } },
      ],
      computeLabel: (field) =>
        field.name === "entity" ? `Default ${this.role}` : label(field.name),
    };
  }
  static getStubConfig(hass) {
    return { entity: entities(hass, this.role, this.key)[0]?.[0] };
  }
  constructor() {
    super();
    this.draft = new Draft();
    this.selection = "";
    this.busy = false;
    this.error = "";
    this.feedback = "";
    this.revision = 0;
    this._generation = 0;
    this._taskCache = new Map();
    this._retiredTaskEpochs = new Map();
    this._tasks = new Map();
  }
  setConfig(config) {
    if (!config || typeof config !== "object")
      throw Error("A card configuration is required.");
    if (
      config.history_hours != null &&
      (!Number.isInteger(config.history_hours) ||
        config.history_hours < 1 ||
        config.history_hours > 168)
    )
      throw Error("History hours must be a whole number from 1 to 168.");
    this.config = { ...config };
    const target =
      config.entity ||
      config.manager_entity ||
      config.target_server_sensor_entity ||
      config.target_device ||
      "";
    if (target !== this.selection) this.select(target);
  }
  getCardSize() {
    return 4;
  }
  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }
  get state() {
    return this.hass?.states?.[this.selection];
  }
  get available() {
    return !unavailable(this.state);
  }
  get target() {
    return this.selection.includes(".")
      ? { entity_id: this.selection }
      : { device_id: this.selection };
  }
  stateFor(key) {
    const id = related(this.hass, this.selection, key);
    return this.hass?.states?.[id];
  }
  select(value) {
    this._generation++;
    this.selection = value || "";
    this.error = "";
    this.feedback = "";
    this.busy = false;
    this.confirmation = null;
    this.draft.reset({});
    this._tasks.clear();
    this.selectedChanged();
  }
  selectedChanged() {}
  connectedCallback() {
    super.connectedCallback();
    this._subscribeTasks();
  }
  disconnectedCallback() {
    super.disconnectedCallback();
    this._generation++;
    this._unsubscribe?.();
    this._unsubscribe = null;
    this._connection = null;
    clearTimeout(this._pollTimer);
    this._tasks.clear();
  }
  updated(changed) {
    if (changed.has("hass")) {
      this.normalizeSelection();
      this._subscribeTasks();
      this.syncState();
    }
  }
  normalizeSelection() {
    if (!this.selection) return;
    let id;
    if (this.selection.includes(".")) {
      if (this.state?.attributes.bsm_key === this.constructor.key) return;
      id = related(this.hass, this.selection, this.constructor.key);
    } else {
      id = entities(
        this.hass,
        this.constructor.role,
        this.constructor.key,
      ).find(
        ([id]) => this.hass.entities?.[id]?.device_id === this.selection,
      )?.[0];
    }
    if (id && id !== this.selection) this.select(id);
  }
  knownPlayers() {
    const device = this.hass?.entities?.[this.selection]?.device_id;
    const parent = this.hass?.devices?.[device]?.via_device_id;
    const explicit =
      this.config.global_players_entity ||
      this.config.global_players_sensor_entity ||
      this.config.global_player_sensor_entity;
    if (explicit)
      return this.hass.states[explicit]?.attributes.global_players_list || [];
    const source = entities(this.hass, "manager", "global_players_count").find(
      ([id]) => this.hass.entities?.[id]?.device_id === parent,
    );
    return source?.[1].attributes.global_players_list || [];
  }
  taskOutcomes() {
    return html`${[...this._tasks.values()]
      .filter(({ task }) => task.status === "completed" && task.result != null)
      .map(
        ({ task }) =>
          html`<details class="tile">
            <summary>Completed outcome · ${task.id}</summary>
            <dl>
              ${Object.entries(
                typeof task.result === "object" && !Array.isArray(task.result)
                  ? task.result
                  : { result: task.result },
              )
                .slice(0, 12)
                .map(
                  ([key, value]) =>
                    html`<dt>${label(key)}</dt>
                      <dd style="overflow-wrap:anywhere;margin:0 0 8px">
                        ${typeof value === "object" ? JSON.stringify(value).slice(0, 1000) : String(value)}
                      </dd>`,
                )}
            </dl>
          </details>`,
      )}`;
  }
  syncState() {}
  async _subscribeTasks() {
    const connection = this.hass?.connection;
    if (!this.isConnected || !connection || this._connection === connection)
      return;
    this._connection = connection;
    this._unsubscribe?.();
    this._unsubscribe = null;
    try {
      const unsubscribe = await connection.subscribeEvents(
        (event) => this._taskUpdate(event.data),
        `${DOMAIN}_task_update`,
      );
      if (!this.isConnected || this._connection !== connection) unsubscribe();
      else this._unsubscribe = unsubscribe;
    } catch {
      if (this._connection === connection) this._connection = null;
    }
  }
  _taskUpdate(task) {
    const cacheKey = `${task.manager_url}:${task.id}`;
    const previous = this._taskCache.get(cacheKey);
    if (
      ![
        "queued",
        "running",
        "cancelling",
        "completed",
        "failed",
        "cancelled",
      ].includes(task.status)
    )
      return;
    const stamped = task.epoch != null || task.revision != null;
    if (
      stamped &&
      (typeof task.epoch !== "string" ||
        !task.epoch.trim() ||
        !Number.isSafeInteger(task.revision) ||
        task.revision < 1)
    )
      return;
    const retired = this._retiredTaskEpochs.get(cacheKey) || new Set();
    if (retired.has(task.epoch)) return;
    if (previous?.epoch === task.epoch && previous.revision >= task.revision)
      return;
    if (previous?.epoch && task.epoch && previous.epoch !== task.epoch)
      retired.add(previous.epoch);
    this._retiredTaskEpochs.set(cacheKey, retired);
    this._taskCache.set(cacheKey, task);
    if (this._taskCache.size > 100) {
      const oldest = this._taskCache.keys().next().value;
      this._taskCache.delete(oldest);
      this._retiredTaskEpochs.delete(oldest);
    }
    const tracked = this._tasks.get(cacheKey);
    if (!tracked || tracked.generation !== this._generation) return;
    tracked.task = task;
    this._showTasks();
  }
  _showTasks() {
    const tasks = [...this._tasks.values()].map((entry) => entry.task);
    const failed = tasks.find((task) =>
      ["failed", "cancelled"].includes(task.status),
    );
    this.error = failed ? taskError(failed) : "";
    this.busy = tasks.some(
      (task) => !["completed", "failed", "cancelled"].includes(task.status),
    );
    this.feedback = tasks
      .map((task) => `${label(task.status)}: ${task.message || task.id}`)
      .join(" · ");
    this.requestUpdate();
  }
  async _pollTasks(generation) {
    if (!this.isConnected || generation !== this._generation || !this.busy)
      return;
    for (const entry of this._tasks.values()) {
      if (["completed", "failed", "cancelled"].includes(entry.task.status))
        continue;
      try {
        const response = await this.responseService(
          "get_task",
          { task_id: entry.task.id },
          entry.target,
        );
        if (generation !== this._generation) return;
        for (const manager of response.managers || [])
          this._taskUpdate({
            manager_url: manager.manager_url,
            ...manager.task,
          });
      } catch {
        /* A connection outage keeps the outcome pending, not successful. */
      }
    }
    if (generation === this._generation && this.busy)
      this._pollTimer = setTimeout(() => this._pollTasks(generation), 3000);
  }
  async responseService(service, data, target = this.target) {
    const response = await this.hass.callWS({
      type: "call_service",
      domain: DOMAIN,
      service,
      service_data: data,
      target,
      return_response: true,
    });
    return response.response || {};
  }
  async action(service, data = {}, message = "Changes saved.", options = {}) {
    if (this.busy || (!options.allowUnavailable && !this.available))
      return false;
    if (options.confirm && !options.confirmed) {
      this.confirmation = {
        service,
        data: copy(data),
        message,
        options,
        target: this.selection,
      };
      return false;
    }
    const generation = this._generation,
      target = { ...this.target };
    this.busy = true;
    this.error = "";
    this.feedback = "Sending request…";
    this._tasks.clear();
    try {
      const response = await this.responseService(service, data, target);
      if (generation !== this._generation) return false;
      for (const result of response.results || []) {
        const id = result.result?.task_id;
        if (!id) continue;
        const key = `${result.manager_url}:${id}`;
        this._tasks.set(key, {
          generation,
          target,
          task: this._taskCache.get(key) || {
            id,
            status: "queued",
            message: "Waiting for task outcome",
          },
        });
      }
      if (this._tasks.size) {
        this._showTasks();
        this._pollTimer = setTimeout(() => this._pollTasks(generation), 1000);
      } else {
        this.busy = false;
        this.feedback =
          (response.results || [])
            .map(({ result }) =>
              result?.status === "skipped"
                ? `Skipped: ${result.message || "No change required."}`
                : result?.message,
            )
            .filter(Boolean)
            .join(" · ") || message;
      }
      if (this.config.debug)
        console.debug("BSM action", service, "acknowledged");
      return true;
    } catch (error) {
      if (generation !== this._generation) return false;
      this.error = error.message || String(error);
      this.feedback = "";
      this.busy = false;
      return false;
    }
  }
  moreInfo(entityId) {
    this.dispatchEvent(
      new CustomEvent("hass-more-info", {
        detail: { entityId },
        bubbles: true,
        composed: true,
      }),
    );
  }
  async nativeAction(domain, service, entityId, data = {}) {
    if (this.busy || unavailable(this.hass?.states?.[entityId])) return false;
    const generation = this._generation;
    this.busy = true;
    this.error = "";
    try {
      await this.hass.callService(domain, service, data, {
        entity_id: entityId,
      });
      if (generation !== this._generation) return false;
      this.feedback =
        "Request sent. State updates when confirmed by the server.";
      return true;
    } catch (error) {
      if (generation === this._generation)
        this.error = error.message || String(error);
      return false;
    } finally {
      if (generation === this._generation) this.busy = false;
    }
  }
  metric(state) {
    if (!state) return nothing;
    const id = state.entity_id;
    const name = state.attributes.friendly_name || id;
    let value = state.state;
    if (state.attributes.device_class === "connectivity")
      value = state.state === "on" ? "Connected" : "Unavailable";
    if (state.attributes.device_class === "problem")
      value = state.state === "on" ? "Problem" : "Healthy";
    if (state.attributes.bsm_key === "websocket")
      value = state.state === "on" ? "Live" : "Offline";
    return html`<button
      class="tile"
      style="text-align:left"
      @click=${() => this.moreInfo(id)}
    >
      <small>${name}</small>
      <div class="value">
        ${unavailable(state) ? "Unavailable" : value}
        ${state.attributes.unit_of_measurement || ""}
      </div>
      ${state.attributes.message ? html`<small>${state.attributes.message}</small>` : nothing}
    </button>`;
  }
  entityControl(key) {
    const id = related(this.hass, this.selection, key),
      state = this.hass?.states?.[id];
    if (!state) return nothing;
    if (id.startsWith("switch."))
      return html`<div class="heading">
        <span>${state.attributes.friendly_name}</span
        ><button
          ?disabled=${this.busy || unavailable(state)}
          @click=${() => this.nativeAction("switch", state.state === "on" ? "turn_off" : "turn_on", id)}
        >
          ${state.state === "on" ? "Disable" : "Enable"}
        </button>
      </div>`;
    return html`<label
      >${state.attributes.friendly_name}<input
        aria-label=${state.attributes.friendly_name}
        .value=${unavailable(state) ? "" : state.state}
        ?disabled=${this.busy || unavailable(state)}
        @change=${(event) => this.nativeAction("text", "set_value", id, { value: event.target.value })}
    /></label>`;
  }
  history(keys) {
    const ids = keys
      .map((key) => related(this.hass, this.selection, key))
      .filter(Boolean);
    const signature = JSON.stringify([ids, this.config.history_hours || 6]);
    if (signature !== this._historySignature) {
      this._historySignature = signature;
      this._graphs = [];
      this._createHistory(ids, signature);
    }
    for (const graph of this._graphs || []) graph.hass = this.hass;
    return html`${this._graphs || []}`;
  }
  async _createHistory(ids, signature) {
    if (!ids.length || !window.loadCardHelpers) return;
    try {
      const helpers = await window.loadCardHelpers();
      if (signature !== this._historySignature || !this.isConnected) return;
      // Keep unlike units on separate native graphs; HA owns history and units.
      this._graphs = ids.map((id) =>
        helpers.createCardElement({
          type: "history-graph",
          entities: [id],
          hours_to_show: this.config.history_hours || 6,
        }),
      );
      this.requestUpdate();
    } catch {
      this.error =
        "History cards could not load. Live metrics remain available.";
    }
  }
  pick() {
    const options = entities(
      this.hass,
      this.constructor.role,
      this.constructor.key,
    );
    return html`<label
      >${label(this.constructor.role)}<select
        aria-label=${label(this.constructor.role)}
        .value=${this.selection}
        ?disabled=${this.busy}
        @change=${(event) => this.select(event.target.value)}
      >
        <option value="">Select ${this.constructor.role}</option>
        ${options.map(([id, state]) => html`<option value=${id} .selected=${id === this.selection}>${state.attributes.friendly_name || id}</option>`)}
      </select></label
    >`;
  }
  button(title, service, data = {}, options = {}) {
    return html`<button
      ?disabled=${this.busy || (!this.available && !options.allowUnavailable)}
      @click=${() => this.action(service, data, options.message || "Changes saved.", options)}
    >
      ${title}
    </button>`;
  }
  input(title, value, change, type = "text") {
    return html`<label
      >${title}<input
        aria-label=${title}
        type=${type}
        .value=${String(value ?? "")}
        ?disabled=${this.busy}
        @input=${(event) => change(event.target.value)}
    /></label>`;
  }
  selectInput(title, value, options, change) {
    return html`<label
      >${title}<select
        aria-label=${title}
        .value=${String(value ?? "")}
        ?disabled=${this.busy}
        @change=${(event) => change(event.target.value)}
      >
        ${options.map((option) => html`<option value=${option.value ?? option} .selected=${String(option.value ?? option) === String(value ?? "")}>${option.label ?? option}</option>`)}
      </select></label
    >`;
  }
  editNotice() {
    return this.draft.dirty
      ? html`<div class="notice" role="status">
          Unsaved
          changes.${this.draft.conflicts.length ? html`<span class="error"> Changed elsewhere: ${this.draft.conflicts.map(label).join(", ")}. Reload before saving.</span>` : nothing}<button
            @click=${() => {
              this.draft.reset(this.draft.live);
              this.requestUpdate();
            }}
          >
            Discard edits and reload
          </button>
        </div>`
      : nothing;
  }
  frame(body, { picker = true } = {}) {
    return html`<ha-card
      ><div class="body">
        <h2>${this.config?.title || this.constructor.title}</h2>
        ${picker ? this.pick() : nothing}
        ${this.selection && !this.available ? html`<p class="notice" role="status">${this.state ? "This resource is unavailable. Controls are disabled until it recovers." : "The configured entity is missing. Choose another resource."}</p>` : nothing}
        ${body}
        <div aria-live="polite" role="status" ?hidden=${!this.feedback}>
          ${this.feedback}
        </div>
        ${this.taskOutcomes()}
        ${this.error ? html`<div class="error" role="alert">${this.error}</div>` : nothing}
        ${
          this.confirmation
            ? html`<section class="confirm" aria-label="Confirm action">
                <p>${this.confirmation.options.confirm}</p>
                <div class="actions">
                  <button
                    @click=${() => {
                      const c = this.confirmation;
                      this.confirmation = null;
                      if (c.target === this.selection)
                        this.action(c.service, c.data, c.message, {
                          ...c.options,
                          confirmed: true,
                        });
                    }}
                  >
                    Confirm</button
                  ><button
                    @click=${() => {
                      this.confirmation = null;
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </section>`
            : nothing
        }
      </div></ha-card
    >`;
  }
}
