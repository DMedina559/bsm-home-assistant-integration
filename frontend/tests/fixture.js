const root = "/custom_components/bedrock_server_manager/frontend/";
await Promise.all(
  [
    "command",
    "properties",
    "allowlist",
    "permissions",
    "content",
    "restore",
    "addon",
    "plugins",
    "event-trigger",
    "fleet",
    "overview",
    "tasks",
    "settings",
    "bans",
    "api",
    "monitor",
    "health",
    "plugin-settings",
  ].map((name) => import(`${root}bsm-${name}-card.js`)),
);
const state = (id, key, role, attrs = {}, value = "0") => ({
  entity_id: id,
  state: value,
  attributes: {
    friendly_name: key.replaceAll("_", " "),
    bsm_key: key,
    bsm_role: role,
    bsm_manager_url: "http://bsm",
    ...attrs,
  },
});
const states = {
  "sensor.server": state(
    "sensor.server",
    "status",
    "server",
    { installed_version: "1.21", bsm_server_name: "Alpha" },
    "INSTALLED",
  ),
  "sensor.other": state(
    "sensor.other",
    "status",
    "server",
    { bsm_server_name: "Beta" },
    "RUNNING",
  ),
  "sensor.props": state(
    "sensor.props",
    "level_name",
    "server",
    {
      server_properties: {
        "server-name": "Alpha",
        "max-players": "10",
        "allow-cheats": "false",
      },
    },
    "World",
  ),
  "sensor.perms": state(
    "sensor.perms",
    "server_permissions_count",
    "server",
    {
      server_permissions: [
        { name: "Alex", xuid: "1234567890123456", permission_level: "member" },
      ],
    },
    "1",
  ),
  "sensor.bans": state(
    "sensor.bans",
    "server_bans_count",
    "server",
    {
      server_bans: [
        {
          player_name: "Blocked",
          xuid: "1234567890123456",
          reason: "Example ban",
        },
      ],
    },
    "1",
  ),
  "sensor.allowlist": state(
    "sensor.allowlist",
    "allowlist_count",
    "server",
    { allowed_players: ["Alex"] },
    "1",
  ),
  "sensor.addons": state(
    "sensor.addons",
    "server_addons_count",
    "server",
    {
      server_addons_list: {
        behavior_packs: [
          { uuid: "one", name: "First", status: "ACTIVE" },
          { uuid: "two", name: "Second", status: "ACTIVE" },
        ],
        resource_packs: [],
      },
    },
    "2",
  ),
  "sensor.backups": state(
    "sensor.backups",
    "world_backups_count",
    "server",
    { world_backups_list: ["world.zip"] },
    "1",
  ),
  "sensor.manager": state(
    "sensor.manager",
    "plugin_statuses",
    "manager",
    {
      plugins_data: {
        backup: { name: "Backup", enabled: true, has_settings: true },
        plain: { name: "Plain", enabled: true, has_settings: false },
      },
    },
    "2",
  ),
  "sensor.version": state(
    "sensor.version",
    "bsm_version",
    "manager",
    {},
    "4.0",
  ),
  "sensor.cpu": state(
    "sensor.cpu",
    "app_cpu_percent",
    "manager",
    { unit_of_measurement: "%" },
    "0",
  ),
  "sensor.ram": state(
    "sensor.ram",
    "app_ram_mb",
    "manager",
    { unit_of_measurement: "MiB" },
    "128",
  ),
  "sensor.api": state(
    "sensor.api",
    "connection",
    "manager",
    { device_class: "connectivity" },
    "on",
  ),
  "sensor.ws": state(
    "sensor.ws",
    "websocket",
    "manager",
    { device_class: "connectivity" },
    "off",
  ),
  "sensor.worlds": state(
    "sensor.worlds",
    "available_worlds_count",
    "manager",
    { available_worlds_list: ["new.mcworld"] },
    "1",
  ),
  "switch.run": state("switch.run", "server_control", "server", {}, "off"),
  "text.target": state("text.target", "target_version", "server", {}, "LATEST"),
};
let listener;
const eventListeners = new Map();
const readyListeners = new Set();
window.readyConnection = () => readyListeners.forEach((cb) => cb());
window.unsubscribeCount = 0;
window.subscriptionCount = 0;
window.requests = [];
window.hass = {
  states,
  entities: Object.fromEntries(
    Object.keys(states).map((id) => [
      id,
      {
        device_id:
          states[id].attributes.bsm_role === "manager" ? "manager" : "server",
      },
    ]),
  ),
  connection: {
    addEventListener: (name, cb) => {
      if (name === "ready") readyListeners.add(cb);
    },
    removeEventListener: (name, cb) => readyListeners.delete(cb),
    subscribeEvents: async (cb, name) => {
      window.subscriptionCount++;
      eventListeners.set(name, cb);
      if (name === "bedrock_server_manager_task_update") listener = cb;
      return () => {
        eventListeners.delete(name);
        window.unsubscribeCount++;
      };
    },
  },
  callService: async (...args) => window.requests.push(args),
  callWS: async (request) => {
    window.requests.push(request);
    if (window.delayResponse)
      return new Promise((resolve) => (window.resolveResponse = resolve));
    if (
      window.fail ||
      (window.failSetting && request.service_data?.key === window.failSetting)
    )
      throw Error("Backend rejected the action");
    if (request.service === "get_plugin_settings")
      return {
        response: {
          managers: [
            {
              manager_url: "http://bsm",
              settings: window.pluginValues || {
                servers: ["Alpha"],
                enabled: true,
                interval: 3,
              },
              settings_schema: {
                type: "object",
                properties: {
                  servers: {
                    type: "array",
                    title: "Servers",
                    items: { $ref: "#/$defs/Server" },
                  },
                  enabled: { type: "boolean", title: "Enabled" },
                  interval: { type: "integer", title: "Interval", minimum: 1 },
                },
                $defs: { Server: { type: "string", enum: ["Alpha", "Beta"] } },
              },
            },
          ],
        },
      };
    if (request.service === "list_tasks")
      return {
        response: {
          managers: [
            {
              manager_url: "http://bsm",
              tasks: window.listedTasks || [
                {
                  id: "task",
                  status: "running",
                  message: "Installing",
                  epoch: "a",
                  revision: 1,
                },
              ],
            },
          ],
        },
      };
    if (
      request.service === "get_application_settings" ||
      request.service === "get_server_settings"
    )
      return {
        response: {
          results: [
            {
              manager_url: "http://bsm",
              result: {
                settings: window.settingsValues || {
                  monitor: { app_interval_seconds: 3 },
                  settings: { autostart: false },
                },
              },
            },
          ],
        },
      };
    if (
      request.service === "set_global_setting" ||
      request.service === "set_server_setting"
    ) {
      window.settingsValues ||= {
        monitor: { app_interval_seconds: 3 },
        settings: { autostart: false },
      };
      const parts = request.service_data.key.split(".");
      let value = window.settingsValues;
      for (const part of parts.slice(0, -1)) value = value[part] ||= {};
      value[parts.at(-1)] = request.service_data.value;
    }
    if (request.service === "get_task")
      return {
        response: {
          managers: [
            {
              manager_url: "http://bsm",
              task: window.polledTask || {
                id: "task",
                status: "running",
                message: "Working",
                epoch: "a",
                revision: 2,
              },
            },
          ],
        },
      };
    return {
      response: {
        results: [
          {
            manager_url: "http://bsm",
            server_name: "Alpha",
            result: window.acceptTask
              ? { task_id: "task", status: "accepted" }
              : { status: "success" },
          },
        ],
      },
    };
  },
};
window.mount = (tag, config = {}) => {
  document.getElementById("mount").replaceChildren();
  const card = document.createElement(tag);
  card.setConfig({ type: `custom:${tag}`, ...config });
  card.hass = window.hass;
  document.getElementById("mount").append(card);
  window.card = card;
  return card.updateComplete;
};
window.push = (id, attributes, state) => {
  window.hass = {
    ...window.hass,
    states: {
      ...window.hass.states,
      [id]: {
        ...window.hass.states[id],
        state: state ?? window.hass.states[id].state,
        attributes: { ...window.hass.states[id].attributes, ...attributes },
      },
    },
  };
  window.card.hass = window.hass;
};
window.task = (data) =>
  listener({
    data: {
      manager_url: "http://bsm",
      id: "task",
      epoch: "a",
      revision: 3,
      ...data,
    },
  });
window.loadCardHelpers = async () => ({
  createCardElement: (config) => {
    const el = document.createElement("section");
    el.dataset.graph = JSON.stringify(config);
    return el;
  },
});
window.ready = true;

window.event = (data) =>
  eventListeners.get("bedrock_server_manager_event")?.({ data });
