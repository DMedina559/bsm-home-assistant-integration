import { createOverviewController } from "./overview-controller.js";

const element = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};

class BsmOverviewCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    let storage;
    try {
      storage = window.localStorage;
    } catch {
      /* Memory fallback. */
    }
    this._state = { servers: [] };
    this._controller = createOverviewController({
      storage,
      onChange: (state) => {
        this._state = state;
        this._render();
      },
    });
  }
  static getConfigElement() {
    return document.createElement("bsm-npm-overview-card-editor");
  }
  static getStubConfig() {
    return { title: "Bedrock servers", refresh_interval: 30 };
  }
  setConfig(config) {
    if (
      config.refresh_interval !== undefined &&
      (!Number.isInteger(config.refresh_interval) ||
        config.refresh_interval < 10 ||
        config.refresh_interval > 3600)
    )
      throw Error("refresh_interval must be 10–3600 seconds");
    this._config = {
      title: "Bedrock servers",
      refresh_interval: 30,
      ...config,
    };
    this._sync();
    this._render();
  }
  set hass(hass) {
    const changed =
      this._hass?.connection !== hass.connection ||
      this._hass?.user?.id !== hass.user?.id;
    this._hass = hass;
    if (changed) this._sync();
  }
  connectedCallback() {
    this._sync();
  }
  disconnectedCallback() {
    clearInterval(this._timer);
    this._controller.stop();
  }
  getCardSize() {
    return 3 + Math.ceil(this._state.servers.length / 2);
  }
  _sync() {
    clearInterval(this._timer);
    this._controller.stop();
    if (!this.isConnected || !this._hass || !this._config) return;
    this._controller.configure(this._hass, this._config.entry_id);
    this._controller.start();
    this._controller.refresh();
    this._timer = setInterval(() => {
      if (!document.hidden && this._hass.connected !== false)
        this._controller.refresh();
    }, this._config.refresh_interval * 1000);
  }
  _render() {
    const root = this.shadowRoot;
    root.replaceChildren();
    const style = element(
      "style",
      `
      :host{display:block}ha-card{padding:16px;color:var(--primary-text-color)}
      header,.toolbar,.row{display:flex;align-items:center;justify-content:space-between;gap:12px}
      h2{font-size:20px;margin:0}h3{font-size:16px;margin:0;overflow-wrap:anywhere}
      button{font:inherit;color:var(--primary-color);background:none;border:1px solid var(--divider-color);border-radius:8px;padding:8px;cursor:pointer}
      button:disabled{opacity:.5;cursor:default}.toolbar{margin:16px 0;font-size:14px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(210px,100%),1fr));gap:12px}
      article{border:1px solid var(--divider-color);border-radius:12px;padding:14px}dl{display:grid;grid-template-columns:1fr auto;gap:8px;font-size:14px;margin-bottom:0}dd{margin:0}
      dt,footer{color:var(--secondary-text-color)}footer{font-size:12px;margin-top:14px}.status{font-size:12px;color:var(--secondary-text-color)}.running{color:var(--success-color,#388e3c)}
      .error{color:var(--error-color);font-size:14px}label{display:flex;gap:6px;align-items:center}
    `,
    );
    const card = element("ha-card");
    const header = element("header");
    header.append(element("h2", this._config?.title ?? "Bedrock servers"));
    const refresh = element(
      "button",
      this._state.loading ? "Refreshing…" : "Refresh",
    );
    refresh.disabled = Boolean(
      this._state.loading ||
      !this._config?.entry_id ||
      this._hass?.connected === false,
    );
    refresh.onclick = () => this._controller.refresh();
    header.append(refresh);
    card.append(header);
    if (!this._config?.entry_id)
      card.append(
        element("p", "Choose a BSM integration connection in the card editor."),
      );
    else {
      const toolbar = element("div", undefined, "toolbar");
      const label = element("label");
      const filter = element("input");
      filter.type = "checkbox";
      filter.checked = Boolean(this._state.runningOnly);
      filter.onchange = () => this._controller.setRunningOnly(filter.checked);
      label.append(filter, document.createTextNode("Running only"));
      toolbar.append(
        label,
        element("span", `${this._state.servers.length} monitored`),
      );
      card.append(toolbar);
      const error =
        this._hass?.connected === false
          ? "Home Assistant disconnected. Showing the last snapshot."
          : this._state.error;
      if (error) {
        const alert = element("p", error, "error");
        alert.setAttribute("role", "alert");
        card.append(alert);
      }
      const grid = element("div", undefined, "grid");
      const servers = this._state.servers.filter(
        (server) => !this._state.runningOnly || server.process?.pid,
      );
      for (const server of servers) {
        const tile = element("article");
        const row = element("div", undefined, "row");
        row.append(
          element("h3", server.name),
          element(
            "span",
            server.unavailable
              ? "Unavailable"
              : server.process?.pid
                ? "Running"
                : "Stopped",
            `status ${server.process?.pid ? "running" : ""}`,
          ),
        );
        tile.append(row);
        if (server.process) {
          const stats = element("dl");
          for (const [title, value] of [
            ["CPU", `${Number(server.process.cpu_percent).toFixed(1)}%`],
            ["Memory", `${Number(server.process.memory_mb).toFixed(0)} MiB`],
            ["Uptime", server.process.uptime ?? "—"],
          ])
            stats.append(element("dt", title), element("dd", value));
          tile.append(stats);
        }
        grid.append(tile);
      }
      if (!servers.length && !this._state.loading && !error)
        grid.append(
          element(
            "p",
            this._state.runningOnly
              ? "No running servers."
              : "No servers selected for this integration.",
          ),
        );
      card.append(grid);
      if (this._state.updated)
        card.append(
          element(
            "footer",
            `Last snapshot ${this._state.updated.toLocaleTimeString()}`,
          ),
        );
    }
    root.append(style, card);
  }
}

class BsmOverviewCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }
  set hass(hass) {
    this._hass = hass;
    if (this._connection !== hass.connection) {
      this._connection = hass.connection;
      const connection = hass.connection;
      hass
        .callWS({ type: "bedrock_server_manager/card_entries" })
        .then((entries) => {
          if (connection === this._connection) {
            this._entries = entries;
            this._error = null;
            this._render();
          }
        })
        .catch(() => {
          this._error =
            "Administrator access is required to select a BSM connection.";
          this._render();
        });
    }
    this._render();
  }
  _render() {
    if (!this._config || !this._hass) return;
    this.replaceChildren();
    if (this._error) this.append(element("p", this._error));
    const form = element("ha-form");
    form.hass = this._hass;
    form.data = this._config;
    form.schema = [
      { name: "title", selector: { text: {} } },
      {
        name: "entry_id",
        required: true,
        selector: {
          select: {
            options: (this._entries ?? []).map((entry) => ({
              value: entry.entry_id,
              label: entry.title,
            })),
          },
        },
      },
      {
        name: "refresh_interval",
        selector: {
          number: { min: 10, max: 3600, mode: "box", unit_of_measurement: "s" },
        },
      },
    ];
    form.computeLabel = (schema) =>
      ({
        title: "Title",
        entry_id: "BSM connection",
        refresh_interval: "Refresh interval",
      })[schema.name];
    form.addEventListener("value-changed", (event) => {
      this._config = { ...this._config, ...event.detail.value };
      this.dispatchEvent(
        new CustomEvent("config-changed", {
          detail: { config: this._config },
          bubbles: true,
          composed: true,
        }),
      );
    });
    this.append(form);
  }
}

if (!customElements.get("bsm-npm-overview-card"))
  customElements.define("bsm-npm-overview-card", BsmOverviewCard);
if (!customElements.get("bsm-npm-overview-card-editor"))
  customElements.define("bsm-npm-overview-card-editor", BsmOverviewCardEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "bsm-npm-overview-card"))
  window.customCards.push({
    type: "bsm-npm-overview-card",
    name: "BSM npm Server Overview",
    description:
      "Monitor your Bedrock servers using your Home Assistant connection.",
    preview: true,
  });
