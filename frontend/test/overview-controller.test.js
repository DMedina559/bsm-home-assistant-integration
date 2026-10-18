import test from "node:test";
import assert from "node:assert/strict";
import { createOverviewController } from "../../custom_components/bedrock_server_manager/frontend/overview-vendor/overview-controller.js";

function setup(callWS, storage) {
  const states = [];
  const controller = createOverviewController({
    storage,
    onChange: (state) => states.push(state),
  });
  const hass = { user: { id: "alice" }, connection: {}, callWS };
  controller.configure(hass, "manager-a");
  controller.start();
  return { controller, states, hass };
}

test("npm API client encodes names and the HA transport preserves them", async () => {
  const calls = [];
  const { controller, states } = setup(async (message) => {
    calls.push(message);
    return message.operation === "list_servers"
      ? { servers: [{ name: "A/B % 雪" }] }
      : { process_info: { pid: 42, memory_mb: 128 } };
  });
  await controller.refresh();
  assert.equal(calls[1].server_name, "A/B % 雪");
  assert.equal(calls[1].entry_id, "manager-a");
  assert.equal(states.at(-1).servers[0].process.pid, 42);
  controller.stop();
});

test("an unavailable server does not hide healthy or stopped servers", async () => {
  const { controller, states } = setup(async (message) => {
    if (message.operation === "list_servers")
      return { servers: [{ name: "offline" }, { name: "failed" }] };
    if (message.server_name === "failed") throw Error("unavailable");
    return { process_info: null };
  });
  await controller.refresh();
  assert.deepEqual(states.at(-1).servers, [
    { name: "offline", process: null },
    { name: "failed", unavailable: true },
  ]);
  controller.stop();
});

test("switching entries cancels work and rejects an old response", async () => {
  let complete;
  const { controller, states, hass } = setup(
    () =>
      new Promise((resolve) => {
        complete = resolve;
      }),
  );
  const old = controller.refresh();
  controller.configure(
    {
      ...hass,
      callWS: async (message) =>
        message.operation === "list_servers"
          ? { servers: [{ name: "new" }] }
          : { process_info: null },
    },
    "manager-b",
  );
  await controller.refresh();
  complete({ servers: [{ name: "old" }] });
  await old;
  assert.equal(states.at(-1).servers[0].name, "new");
  assert.equal(states.at(-1).loading, false);
  controller.stop();
});

test("unmount aborts an unresolved HA read and never publishes its result", async () => {
  const { controller, states } = setup(() => new Promise(() => {}));
  const pending = controller.refresh();
  controller.stop();
  const count = states.length;
  await pending;
  assert.equal(states.length, count);
});

test("preferences persist by HA account and BSM entry", () => {
  const data = new Map();
  const storage = {
    getItem: (key) => data.get(key),
    setItem: (key, value) => data.set(key, value),
    removeItem: (key) => data.delete(key),
  };
  const { controller, states, hass } = setup(async () => {}, storage);
  controller.setRunningOnly(true);
  controller.configure(hass, "manager-b");
  assert.equal(states.at(-1).runningOnly, false);
  controller.configure(hass, "manager-a");
  assert.equal(states.at(-1).runningOnly, true);
  controller.configure({ ...hass, user: { id: "bob" } }, "manager-a");
  assert.equal(states.at(-1).runningOnly, false);
  controller.stop();
});

test("failed refresh retains the last dated snapshot and reports the error", async () => {
  let fail = false;
  const { controller, states } = setup(async () => {
    if (fail) throw Error("Disconnected");
    return { servers: [] };
  });
  await controller.refresh();
  const updated = states.at(-1).updated;
  fail = true;
  await controller.refresh();
  assert.equal(states.at(-1).updated, updated);
  assert.equal(states.at(-1).error, "Disconnected");
  assert.equal(states.at(-1).loading, false);
  controller.stop();
});
