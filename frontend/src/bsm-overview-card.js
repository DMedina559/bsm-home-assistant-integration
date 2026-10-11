import { BsmCard, html, register, unavailable } from "./base.js";
import { entities, related } from "./model.js";
class OverviewCard extends BsmCard {
  static title = "Bedrock Server Manager";
  static properties = {
    layout: { state: true },
    operations: { state: true },
    cardFeedback: { state: true },
  };
  constructor() {
    super();
    this.layout = "cards";
    this.operations = new Map();
    this.cardFeedback = "";
  }
  static getConfigForm() {
    const form = super.getConfigForm();
    form.schema = form.schema.filter((f) => f.name !== "entity");
    form.schema.push(
      { name: "layout", selector: { select: { options: ["cards", "table"] } } },
      {
        name: "sort",
        selector: { select: { options: ["name", "status", "players"] } },
      },
      { name: "monitor_path", selector: { text: {} } },
      { name: "settings_path", selector: { text: {} } },
      {
        name: "entities",
        selector: {
          entity: {
            integration: "bedrock_server_manager",
            domain: "sensor",
            multiple: true,
          },
        },
      },
    );
    return form;
  }
  value(id, key) {
    const state = this.hass.states[related(this.hass, id, key)];
    return unavailable(state)
      ? "—"
      : `${state.state}${state.attributes.unit_of_measurement ? ` ${state.attributes.unit_of_measurement}` : ""}`;
  }
  navigate(id, kind = "monitor") {
    const path =
      this.config[`${kind}_paths`]?.[id] || this.config[`${kind}_path`];
    if (
      typeof path === "string" &&
      path.startsWith("/") &&
      !path.startsWith("//")
    ) {
      const url = path.replaceAll(
        "{server}",
        encodeURIComponent(
          this.hass.states[id]?.attributes.bsm_server_name || "",
        ),
      );
      history.pushState(null, "", url);
      window.dispatchEvent(new CustomEvent("location-changed"));
    } else this.moreInfo(id);
  }
  async control(id, service, data = {}, confirmed = false) {
    if (
      this.operations.has(id) ||
      unavailable(this.hass.states[id]) ||
      this.hass?.connected === false
    )
      return;
    if (service === "restart_server" && !confirmed) {
      this.confirmation = { server: id, service, data };
      return;
    }
    const generation = this._generation;
    this.error = "";
    this.cardFeedback = "";
    this.operations = new Map(this.operations).set(id, {
      message: "Sending request…",
    });
    try {
      if (service === "start" || service === "stop") {
        const run = related(this.hass, id, "server_control");
        if (!run || unavailable(this.hass.states[run]))
          throw Error("Server control is unavailable.");
        await this.hass.callService(
          "switch",
          service === "start" ? "turn_on" : "turn_off",
          {},
          { entity_id: run },
        );
        if (generation === this._generation) {
          this.operations = new Map(this.operations);
          this.operations.delete(id);
          this.cardFeedback =
            "Request sent. Waiting for confirmed server state.";
        }
      } else {
        const response = await this.responseService(service, data, {
          entity_id: id,
        });
        if (generation !== this._generation) return;
        let pending = false;
        for (const result of response.results || [])
          if (result.result?.task_id) {
            pending = true;
            const key = `${result.manager_url}:${result.result.task_id}`;
            const task = this.runtime.tasks.get(key) || {
              id: result.result.task_id,
              manager_url: result.manager_url,
              status: "queued",
              message: "Waiting for task outcome",
            };
            this.operations = new Map(this.operations).set(id, {
              key,
              task,
              message: task.message,
            });
            this._watchTask({ target: { entity_id: id }, task });
            if (["completed", "failed", "cancelled"].includes(task.status))
              this._taskUpdate(task);
          }
        if (!pending) {
          this.operations = new Map(this.operations);
          this.operations.delete(id);
          this.cardFeedback =
            response.results?.[0]?.result?.message || "Request acknowledged.";
        }
      }
    } catch (error) {
      if (generation === this._generation) {
        this.operations = new Map(this.operations);
        this.operations.delete(id);
        this.error = error.message || String(error);
      }
    }
  }
  _taskUpdate(task) {
    for (const [id, operation] of this.operations)
      if (operation.key === `${task.manager_url}:${task.id}`) {
        this.operations = new Map(this.operations);
        if (["completed", "failed", "cancelled"].includes(task.status)) {
          this.operations.delete(id);
          this.cardFeedback = task.message;
          if (task.error) this.error = task.error.message;
        } else
          this.operations.set(id, {
            ...operation,
            task,
            message: task.message,
          });
      }
    if (!this.operations.size) this._releaseTaskWatchers();
    this.requestUpdate();
  }
  reconnected() {
    super.reconnected();
    for (const [id, operation] of this.operations)
      if (operation.task)
        this._watchTask({ target: { entity_id: id }, task: operation.task });
  }
  frame(body, options) {
    const confirmation = this.confirmation;
    const result = super.frame(
      html`${body}${this.cardFeedback ? html`<small role="status">${this.cardFeedback}</small>` : ""}${
        confirmation
          ? html`<section class="confirm">
              <p>Restart this server and disconnect its players?</p>
              <button
                @click=${() => {
                  this.confirmation = null;
                  this.control(
                    confirmation.server,
                    confirmation.service,
                    confirmation.data,
                    true,
                  );
                }}
              >
                Confirm</button
              ><button @click=${() => (this.confirmation = null)}>
                Cancel
              </button>
            </section>`
          : ""
      }`,
      { ...options, confirmationControls: false },
    );
    return result;
  }
  controls(id, state) {
    const run = related(this.hass, id, "server_control"),
      running = state.state.toUpperCase() === "RUNNING",
      blocked =
        this.operations.has(id) ||
        unavailable(state) ||
        this.hass?.connected === false;
    return html`<div class="actions">
      ${run ? html`<button ?disabled=${blocked || unavailable(this.hass.states[run])} @click=${() => this.control(id, running ? "stop" : "start")}>${running ? "Stop" : "Start"}</button>` : ""}<button
        ?disabled=${blocked}
        @click=${() => this.control(id, "update_server")}
      >
        Update
      </button>
      <details>
        <summary>More actions</summary>
        ${this.config.settings_path || this.config.settings_paths?.[id] ? html`<button @click=${() => this.navigate(id, "settings")}>Settings</button>` : ""}
        <button
          ?disabled=${blocked}
          @click=${() => this.control(id, "restart_server")}
        >
          Restart</button
        ><button
          ?disabled=${blocked}
          @click=${() => {
            this.control(id, "trigger_backup", { backup_type: "all" });
          }}
        >
          Backup</button
        ><button @click=${() => this.moreInfo(id)}>Details</button>${[
          "level_name",
          "server_permissions_count",
          "allowlist_count",
        ].map((key) => {
          const entity = related(this.hass, id, key);
          return entity
            ? html`<button @click=${() => this.moreInfo(entity)}>
                ${{ level_name: "Properties", server_permissions_count: "Permissions", allowlist_count: "Allowlist" }[key]}
              </button>`
            : "";
        })}
      </details>
    </div>`;
  }
  render() {
    const servers = entities(this.hass, "server", "status").filter(
      ([id]) =>
        !this.config.entities?.length || this.config.entities.includes(id),
    );
    servers.sort(([a, sa], [b, sb]) =>
      this.config.sort === "status"
        ? sa.state.localeCompare(sb.state)
        : this.config.sort === "players"
          ? Number(this.value(b, "online_players_count")) -
            Number(this.value(a, "online_players_count"))
          : (sa.attributes.bsm_server_name || a).localeCompare(
              sb.attributes.bsm_server_name || b,
            ),
    );
    const running = servers.filter(
      ([, s]) => s.state.toUpperCase() === "RUNNING",
    ).length;
    const table = this.config.layout === "table";
    return this.frame(
      html`<div class="heading">
          <small>${servers.length} servers · ${running} running</small>
        </div>
        ${
          table
            ? html`<div class="scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Server</th>
                      <th>Status</th>
                      <th>Players</th>
                      <th>CPU</th>
                      <th>RAM</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${servers.map(
                      ([id, s]) =>
                        html`<tr>
                          <td>
                            <button @click=${() => this.navigate(id)}>
                              ${s.attributes.bsm_server_name || s.attributes.friendly_name}
                            </button>
                          </td>
                          <td>${s.state}</td>
                          <td>${this.value(id, "online_players_count")}</td>
                          <td>${this.value(id, "cpu_percent")}</td>
                          <td>${this.value(id, "memory_mb")}</td>
                          <td>${this.controls(id, s)}</td>
                        </tr>`,
                    )}
                  </tbody>
                </table>
              </div>`
            : html`<div class="grid">
                ${servers.map(
                  ([id, s]) =>
                    html`<section class="tile">
                      <div class="heading">
                        <button @click=${() => this.navigate(id)}>
                          ${s.attributes.bsm_server_name || s.attributes.friendly_name}</button
                        ><small
                          >${unavailable(s) ? "Unavailable" : s.state}</small
                        >
                      </div>
                      <small
                        >${s.attributes.installed_version || "Version unknown"}</small
                      >
                      <div class="grid">
                        <span
                          >Players
                          ${this.value(id, "online_players_count")}</span
                        ><span>CPU ${this.value(id, "cpu_percent")}</span
                        ><span>RAM ${this.value(id, "memory_mb")}</span>
                      </div>
                      ${this.controls(id, s)}
                      ${this.operations.get(id)?.message ? html`<small role="status">${this.operations.get(id).message}</small>` : ""}
                    </section>`,
                )}
              </div>`
        }${!servers.length ? html`<p>No selected servers are available.</p>` : ""}`,
      { picker: false },
    );
  }
}
register(
  "bsm-overview-card",
  OverviewCard,
  "BSM Overview",
  "Fleet cards or table with start, stop, update and quick actions.",
);
