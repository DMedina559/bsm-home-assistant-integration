/** One runtime per HA connection. Entities remain authoritative for server state. */
import { DOMAIN } from "./model.js";
const runtimes = new WeakMap();
const terminal = (task) =>
  ["completed", "failed", "cancelled"].includes(task.status);
const stable = (value) =>
  JSON.stringify(value, (_, item) =>
    item && typeof item === "object" && !Array.isArray(item)
      ? Object.fromEntries(
          Object.entries(item).sort(([a], [b]) => a.localeCompare(b)),
        )
      : item,
  );
export function runtimeFor(hass) {
  const connection = hass.connection;
  if (!runtimes.has(connection))
    runtimes.set(connection, new CardRuntime(connection));
  return runtimes.get(connection);
}
class CardRuntime {
  constructor(connection) {
    this.connection = connection;
    this.owners = new Set();
    this.tasks = new Map();
    this.retired = new Map();
    this.inflight = new Map();
    this.groups = new Map();
    this.generation = 0;
    this.requestGeneration = 0;
    this.ready = () => {
      this.requestGeneration++;
      this.inflight.clear();
      this.emit("reconnect", {});
      for (const group of this.groups.values()) this.poll(group);
    };
    this.visible = () => {
      for (const group of this.groups.values()) {
        clearTimeout(group.timer);
        if (!document.hidden) this.poll(group);
      }
    };
  }
  acquire(listener) {
    this.owners.add(listener);
    if (this.owners.size === 1) this.start();
    return () => {
      this.owners.delete(listener);
      if (!this.owners.size) this.stop();
    };
  }
  start() {
    const generation = ++this.generation;
    this.unsubscribers = [];
    let subscribed = 0;
    for (const [type, event] of [
      ["task", `${DOMAIN}_task_update`],
      ["event", `${DOMAIN}_event`],
    ]) {
      this.connection
        .subscribeEvents((message) => {
          if (generation !== this.generation) return;
          type === "task"
            ? this.accept(message.data)
            : this.emit(type, message.data);
        }, event)
        .then((unsubscribe) => {
          if (generation !== this.generation) unsubscribe();
          else {
            this.unsubscribers.push(unsubscribe);
            if (++subscribed === 2) this.emit("subscription_ok", {});
          }
        })
        .catch(() => {
          if (generation === this.generation)
            this.emit("subscription_error", {});
        });
    }
    this.connection.addEventListener?.("ready", this.ready);
    document.addEventListener("visibilitychange", this.visible);
  }
  stop() {
    this.generation++;
    this.requestGeneration++;
    for (const unsubscribe of this.unsubscribers || []) unsubscribe();
    this.unsubscribers = [];
    this.connection.removeEventListener?.("ready", this.ready);
    document.removeEventListener("visibilitychange", this.visible);
    for (const group of this.groups.values()) clearTimeout(group.timer);
    this.groups.clear();
    this.inflight.clear();
  }
  emit(type, data) {
    for (const listener of this.owners) {
      try {
        listener(type, data);
      } catch (error) {
        console.error("BSM card update failed", error);
      }
    }
  }
  accept(task) {
    if (
      !task ||
      typeof task.id !== "string" ||
      typeof task.manager_url !== "string" ||
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
    const key = `${task.manager_url}:${task.id}`,
      previous = this.tasks.get(key),
      stamped = task.epoch != null || task.revision != null;
    if (
      stamped &&
      (typeof task.epoch !== "string" ||
        !task.epoch.trim() ||
        !Number.isSafeInteger(task.revision) ||
        task.revision < 1)
    )
      return;
    if (previous?.epoch && !stamped) return;
    const retired = this.retired.get(key) || new Set();
    if (
      retired.has(task.epoch) ||
      (previous?.epoch === task.epoch && previous?.revision >= task.revision)
    )
      return;
    if (previous?.epoch && task.epoch && previous.epoch !== task.epoch)
      retired.add(previous.epoch);
    if (!stamped && previous && terminal(previous) && !terminal(task)) return;
    this.retired.set(key, retired);
    this.tasks.delete(key);
    this.tasks.set(key, task);
    if (this.tasks.size > 500) {
      const oldest = this.tasks.keys().next().value;
      this.tasks.delete(oldest);
      this.retired.delete(oldest);
    }
    this.emit("task", task);
  }
  async request(hass, service, data, target) {
    const read =
      service.startsWith("get_") ||
      service.startsWith("list_") ||
      service === "discover_operations";
    const managerReads = new Set([
      "get_application_settings",
      "get_plugin_settings",
      "get_task",
      "list_tasks",
      "discover_operations",
      "get_application_diagnostics",
      "get_subsystem_diagnostics",
      "get_diagnostic_history",
      "get_diagnostic_runs",
      "get_diagnostic_trace",
      "get_diagnostic_report",
      "get_event_activity",
      "list_application_events",
      "get_web_runtime",
      "list_audit_logs",
    ]);
    const manager =
      typeof target.entity_id === "string"
        ? hass.states?.[target.entity_id]?.attributes?.bsm_manager_url
        : null;
    const key = stable([
      service,
      data,
      managerReads.has(service) && manager ? manager : target,
    ]);
    if (read && this.inflight.has(key)) return this.inflight.get(key);
    const generation = this.requestGeneration;
    const request = hass
      .callWS({
        type: "call_service",
        domain: DOMAIN,
        service,
        service_data: data,
        target,
        return_response: true,
      })
      .then((response) => {
        if (generation !== this.requestGeneration)
          throw Error("Connection changed; current data is being reloaded.");
        const result = response.response || {};
        if (service === "list_tasks" || service === "get_task")
          for (const manager of result.managers || [])
            for (const task of manager.task
              ? [manager.task]
              : manager.tasks || [])
              this.accept({ ...task, manager_url: manager.manager_url });
        return result;
      });
    if (read) this.inflight.set(key, request);
    try {
      return await request;
    } finally {
      if (this.inflight.get(key) === request) this.inflight.delete(key);
    }
  }
  watch(hass, target, { managerUrl, taskId, all = false } = {}) {
    const key = managerUrl || stable(target);
    let group = this.groups.get(key);
    if (!group) {
      group = { key, hass, target, watches: new Set(), loading: false };
      this.groups.set(key, group);
    }
    const watch = { taskId, all };
    group.watches.add(watch);
    group.hass = hass;
    if (!group.timer && !group.loading)
      group.timer = setTimeout(() => this.poll(group), 1000);
    return () => {
      if (!group.watches.delete(watch)) return;
      if (!group.watches.size) {
        clearTimeout(group.timer);
        if (this.groups.get(key) === group) this.groups.delete(key);
      }
    };
  }
  async poll(group) {
    if (
      group.loading ||
      document.hidden ||
      this.groups.get(group.key) !== group
    )
      return;
    clearTimeout(group.timer);
    group.loading = true;
    try {
      if ([...group.watches].some((w) => w.all))
        await this.request(group.hass, "list_tasks", {}, group.target);
      const ids = new Set(
        [...group.watches].map((w) => w.taskId).filter(Boolean),
      );
      for (const id of ids) {
        const previous = this.tasks.get(`${group.key}:${id}`);
        if (!previous || !terminal(previous))
          await this.request(
            group.hass,
            "get_task",
            { task_id: id },
            group.target,
          );
      }
      this.emit("poll_ok", { manager_url: group.key });
    } catch (error) {
      this.emit("poll_error", {
        manager_url: group.key,
        message: error.message || String(error),
      });
    } finally {
      group.loading = false;
      if (this.groups.get(group.key) === group && !document.hidden)
        group.timer = setTimeout(() => this.poll(group), 5000);
    }
  }
}
