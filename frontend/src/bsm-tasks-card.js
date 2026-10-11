import { BsmCard, html, register } from "./base.js";
import { label, related } from "./model.js";
import { taskOutcome } from "./task-outcome.js";
class TasksCard extends BsmCard {
  static role = "manager";
  static key = "bsm_version";
  static title = "Background tasks";
  static properties = { loading: { state: true }, filter: { state: true } };
  constructor() {
    super();
    this.filter = "all";
    this.loading = false;
    this.items = new Map();
  }
  selectedChanged() {
    this.items?.clear();
    this._loaded = "";
    this._managerUrl = "";
    clearTimeout(this._refreshTimer);
  }
  disconnectedCallback() {
    clearTimeout(this._refreshTimer);
    super.disconnectedCallback();
  }
  syncState() {
    if (this.available && this._loaded !== this.selection) {
      this._loaded = this.selection;
      this.load();
    }
  }
  managerUrl() {
    const state = this.state;
    return state?.attributes.bsm_manager_url || this._managerUrl;
  }
  _taskUpdate(task) {
    super._taskUpdate(task);
    const accepted = this._taskCache.get(`${task.manager_url}:${task.id}`);
    if (
      accepted !== task ||
      !this.managerUrl() ||
      task.manager_url !== this.managerUrl()
    )
      return;
    this.items.set(task.id, task);
    this.requestUpdate();
  }
  async load() {
    if (this.loading || !this.available) return;
    const generation = this._generation;
    this.loading = true;
    try {
      const response = await this.responseService("list_tasks", {});
      if (generation !== this._generation) return;
      for (const manager of response.managers || []) {
        this._managerUrl = manager.manager_url;
        for (const task of manager.tasks || []) {
          const key = `${manager.manager_url}:${task.id}`;
          this._taskUpdate({ ...task, manager_url: manager.manager_url });
          const accepted = this._taskCache.get(key);
          this.items.set(task.id, accepted);
        }
      }
      this.error = "";
    } catch (error) {
      if (generation === this._generation)
        this.error = error.message || String(error);
    } finally {
      if (generation === this._generation) {
        this.loading = false;
        this.requestUpdate();
        clearTimeout(this._refreshTimer);
        if (this.isConnected)
          this._refreshTimer = setTimeout(() => this.load(), 5000);
      }
    }
  }
  render() {
    const all = [...this.items.values()].sort(
        (a, b) =>
          Number(["completed", "failed", "cancelled"].includes(a.status)) -
          Number(["completed", "failed", "cancelled"].includes(b.status)),
      ),
      active = all.filter(
        (t) => !["completed", "failed", "cancelled"].includes(t.status),
      );
    const shown = all.filter(
      (t) =>
        this.filter === "all" ||
        (this.filter === "active"
          ? active.includes(t)
          : t.status === this.filter),
    );
    return this.frame(
      html`<div class="heading">
          <small>${active.length} active · ${all.length} known</small
          ><button
            ?disabled=${this.loading || !this.available}
            @click=${this.load}
          >
            Refresh tasks
          </button>
        </div>
        ${this.selectInput("Show tasks", this.filter, ["all", "active", "completed", "failed", "cancelled"], (v) => (this.filter = v))}${shown.map(
          (task) =>
            html`<details
              class="tile"
              ?open=${!["completed", "failed", "cancelled"].includes(task.status)}
            >
              <summary>
                ${label(task.status)} · ${task.message || task.id}
              </summary>
              <small>Task ${task.id}</small>${taskOutcome(task)}
            </details>`,
        )}${!shown.length ? html`<p class="muted">${this.loading ? "Loading tasks…" : "No tasks in this view."}</p>` : ""}`,
    );
  }
}
register(
  "bsm-tasks-card",
  TasksCard,
  "BSM Tasks",
  "Live task status, structured outcomes and failures with HTTP recovery.",
);
