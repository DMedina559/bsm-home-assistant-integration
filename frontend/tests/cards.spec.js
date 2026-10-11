import { test, expect } from "@playwright/test";
async function mount(page, tag, config) {
  await page.goto("/frontend/tests/fixture.html");
  await page.waitForFunction(() => window.ready);
  await page.evaluate(
    ([tag, config]) => window.mount(tag, config),
    [tag, config],
  );
}

test("live properties preserve edits and block conflicting writes", async ({
  page,
}) => {
  await mount(page, "bsm-properties-card", { entity: "sensor.props" });
  await page.getByLabel("Server name", { exact: true }).fill("Draft");
  await page.evaluate(() =>
    window.push("sensor.props", {
      server_properties: {
        "server-name": "Phone",
        "max-players": "10",
        "allow-cheats": "false",
      },
    }),
  );
  await expect(page.getByLabel("Server name", { exact: true })).toHaveValue(
    "Draft",
  );
  await expect(page.getByText(/Changed elsewhere/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Save properties" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Discard edits and reload" }).click();
  await expect(page.getByLabel("Server name", { exact: true })).toHaveValue(
    "Phone",
  );
});
test("accepted tasks stay pending and expose failure outcomes", async ({
  page,
}) => {
  await mount(page, "bsm-content-card", {
    entity: "sensor.server",
    content_source_sensor_entity: "sensor.worlds",
  });
  await page.evaluate(() => (window.acceptTask = true));
  await page.getByLabel("File", { exact: true }).selectOption("new.mcworld");
  await page.getByRole("button", { name: "Install world" }).click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByText(/Queued:/)).toBeVisible();
  await page.evaluate(() =>
    window.task({
      status: "failed",
      message: "Extraction failed",
      error: { message: "Disk is full" },
    }),
  );
  await expect(page.getByRole("alert")).toContainText("Disk is full");
  await expect(
    page.getByRole("button", { name: "Install world" }),
  ).toBeEnabled();
});
test("task polling recovers a missed websocket outcome", async ({ page }) => {
  await mount(page, "bsm-content-card", {
    entity: "sensor.server",
    content_source_sensor_entity: "sensor.worlds",
  });
  await page.evaluate(() => {
    window.acceptTask = true;
    window.polledTask = {
      id: "task",
      status: "completed",
      message: "Installed",
      epoch: "a",
      revision: 4,
    };
  });
  await page.getByLabel("File", { exact: true }).selectOption("new.mcworld");
  await page.getByRole("button", { name: "Install world" }).click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByText("Completed: Installed")).toBeVisible();
});
test("late action results cannot clear a different server's input", async ({
  page,
}) => {
  await mount(page, "bsm-command-card", { entity: "sensor.server" });
  await page.getByLabel("Command", { exact: true }).fill("say first");
  await page.evaluate(() => (window.delayResponse = true));
  await page.getByRole("button", { name: "Send command" }).click();
  await page.evaluate(() => window.card.select("sensor.other"));
  await page.getByLabel("Command", { exact: true }).fill("say second");
  await page.evaluate(() =>
    window.resolveResponse({ response: { results: [] } }),
  );
  await expect(page.getByLabel("Command", { exact: true })).toHaveValue(
    "say second",
  );
  await expect(page.getByText("Command sent.")).toHaveCount(0);
});
test("unavailable properties retain edits and disable writes", async ({
  page,
}) => {
  await mount(page, "bsm-properties-card", { entity: "sensor.props" });
  await page.getByLabel("Server name", { exact: true }).fill("Draft");
  await page.evaluate(() => window.push("sensor.props", {}, "unavailable"));
  await expect(page.getByLabel("Server name", { exact: true })).toHaveValue(
    "Draft",
  );
  await expect(
    page.getByRole("button", { name: "Save properties" }),
  ).toBeDisabled();
  await expect(page.getByText(/This resource is unavailable/)).toBeVisible();
});
test("typed plugin settings hide undeclared plugins and support server checklists", async ({
  page,
}) => {
  await mount(page, "bsm-plugin-settings-card", { entity: "sensor.manager" });
  await expect(page.getByRole("tab", { name: "Plain" })).toHaveCount(0);
  await page.getByRole("tab", { name: "Backup" }).click();
  await page.getByLabel("Beta", { exact: true }).check();
  await page.getByLabel("Interval", { exact: true }).fill("5");
  await page.getByRole("button", { name: "Save settings" }).click();
  const request = await page.evaluate(() =>
    window.requests.find((r) => r.service === "update_plugin_settings"),
  );
  expect(request.service_data.settings).toEqual({
    servers: ["Alpha", "Beta"],
    enabled: true,
    interval: 5,
  });
});
test("plugin updates preserve conflicting draft fields", async ({ page }) => {
  await mount(page, "bsm-plugin-settings-card", { entity: "sensor.manager" });
  await page.getByRole("tab", { name: "Backup" }).click();
  await page.getByLabel("Interval", { exact: true }).fill("5");
  await page.evaluate(() => {
    window.pluginValues = { servers: ["Alpha"], enabled: true, interval: 8 };
    window.push("sensor.manager", { bsm_settings_revision: 2 });
  });
  await expect(page.getByLabel("Interval", { exact: true })).toHaveValue("5");
  await expect(
    page.getByRole("button", { name: "Save settings" }),
  ).toBeDisabled();
  await expect(page.getByText(/Changed elsewhere/)).toBeVisible();
});
test("permission payloads use the current typed list contract", async ({
  page,
}) => {
  await mount(page, "bsm-permissions-card", { entity: "sensor.perms" });
  await page.getByLabel("Permission for Alex").selectOption("operator");
  await page.getByRole("button", { name: "Save permissions" }).click();
  const request = await page.evaluate(() =>
    window.requests.find((r) => r.service === "set_permissions"),
  );
  expect(request.service_data.permissions).toEqual([
    { name: "Alex", xuid: "1234567890123456", permission_level: "operator" },
  ]);
});
test("HTTP and websocket health remain separate and history uses native cards", async ({
  page,
}) => {
  await mount(page, "bsm-health-card", { entity: "sensor.version" });
  await expect(page.getByText("Connected", { exact: true })).toBeVisible();
  await expect(page.getByText("Offline", { exact: true })).toBeVisible();
  await expect(page.locator("[data-graph]")).toHaveCount(2);
  const graphs = await page
    .locator("[data-graph]")
    .evaluateAll((els) => els.map((el) => JSON.parse(el.dataset.graph)));
  expect(
    graphs.every(
      (graph) => graph.type === "history-graph" && graph.entities.length === 1,
    ),
  ).toBe(true);
});
test("subscriptions are released when dashboard cards disconnect", async ({
  page,
}) => {
  await mount(page, "bsm-command-card", { entity: "sensor.server" });
  await page.evaluate(() => window.card.remove());
  await expect.poll(() => page.evaluate(() => window.unsubscribeCount)).toBe(2);
});
for (const mode of ["light", "dark"])
  test(`all cards fit a mobile dashboard in ${mode} mode`, async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 800 });
    await page.goto("/frontend/tests/fixture.html");
    await page.waitForFunction(() => window.ready);
    if (mode === "dark")
      await page.evaluate(() => document.body.classList.add("dark"));
    for (const [name, entity] of [
      ["fleet", null],
      ["overview", null],
      ["tasks", "sensor.version"],
      ["settings", "sensor.version"],
      ["api", "sensor.version"],
      ["bans", "sensor.bans"],
      ["monitor", "sensor.server"],
      ["health", "sensor.version"],
      ["properties", "sensor.props"],
      ["allowlist", "sensor.allowlist"],
      ["permissions", "sensor.perms"],
      ["addon", "sensor.addons"],
      ["restore", "sensor.backups"],
      ["command", "sensor.server"],
      ["plugins", "sensor.manager"],
      ["plugin-settings", "sensor.manager"],
      ["event-trigger", "sensor.version"],
      ["content", "sensor.server"],
    ]) {
      await page.evaluate(
        ([name, entity]) => window.mount(`bsm-${name}-card`, { entity }),
        [name, entity],
      );
      await expect(page.locator("ha-card")).toBeVisible();
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth),
      ).toBeLessThanOrEqual(360);
    }
  });

test("completed outcomes remain visible and stale task frames cannot rewind them", async ({
  page,
}) => {
  await mount(page, "bsm-command-card", { entity: "sensor.server" });
  await page.evaluate(() => (window.acceptTask = true));
  await page.getByLabel("Command", { exact: true }).fill("say hello");
  await page.getByRole("button", { name: "Send command" }).click();
  await page.evaluate(() =>
    window.task({
      status: "completed",
      message: "Done",
      result: { outcome: "installed", version: "1.21" },
      revision: 4,
    }),
  );
  await page.getByText("Completed outcome · task").click();
  await expect(page.getByText("installed", { exact: true })).toBeVisible();
  await page.evaluate(() =>
    window.task({ status: "running", message: "Old snapshot", revision: 2 }),
  );
  await expect(page.getByText("Completed: Done")).toBeVisible();
});

test("legacy device configuration resolves the proper manager resource", async ({
  page,
}) => {
  await mount(page, "bsm-event-trigger-card", { target_device: "manager" });
  await expect(page.getByLabel("Manager", { exact: true })).toHaveValue(
    "sensor.version",
  );
  await page.getByLabel("Event name").fill("on_custom_event");
  await page.getByRole("button", { name: "Trigger event" }).click();
  const request = await page.evaluate(() =>
    window.requests.find((r) => r.service === "trigger_plugin_event"),
  );
  expect(request.target).toEqual({ entity_id: "sensor.version" });
});

test("configured selections display their labels on the first render", async ({
  page,
}) => {
  await mount(page, "bsm-plugin-settings-card", { entity: "sensor.manager" });
  await expect(page.getByLabel("Manager", { exact: true })).toHaveValue(
    "sensor.manager",
  );
  await page.getByRole("tab", { name: "Backup" }).click();
  await expect(page.getByLabel("Manager", { exact: true })).toHaveValue(
    "sensor.manager",
  );
});

test("legacy content installer tag remains available", async ({ page }) => {
  await mount(page, "bsm-content-installer-card", {
    entity: "sensor.server",
    content_source_sensor_entity: "sensor.worlds",
  });
  await expect(page.getByLabel("File", { exact: true })).toBeVisible();
  await page.getByLabel("File", { exact: true }).selectOption("new.mcworld");
  await expect(
    page.getByRole("button", { name: "Install world" }),
  ).toBeEnabled();
});
test("metrics fit narrow sections with long manager names", async ({
  page,
}) => {
  await mount(page, "bsm-health-card", { entity: "sensor.version" });
  await page.evaluate(() => {
    window.card.style.width = "300px";
    for (const [id, state] of Object.entries(window.hass.states)) {
      window.push(id, {
        friendly_name:
          "BSM @ https://bsm.home-server.internal Manager Application " + id,
      });
    }
  });
  await expect
    .poll(() =>
      page.evaluate(() => {
        const body = window.card.shadowRoot.querySelector(".body");
        return body.scrollWidth <= body.clientWidth;
      }),
    )
    .toBe(true);
});

test("overview controls installed servers and offers a table layout", async ({
  page,
}) => {
  await mount(page, "bsm-overview-card", {
    layout: "table",
    entities: ["sensor.server"],
  });
  await expect(page.getByRole("table")).toBeVisible();
  await page.getByRole("button", { name: "Start", exact: true }).click();
  expect(await page.evaluate(() => window.requests.at(-1))).toEqual([
    "switch",
    "turn_on",
    {},
    { entity_id: "switch.run" },
  ]);
  await page.getByRole("button", { name: "Update", exact: true }).click();
  expect(await page.evaluate(() => window.requests.at(-1).service)).toBe(
    "update_server",
  );
});

test("tasks preserve structured outcomes and reject older HTTP snapshots", async ({
  page,
}) => {
  await mount(page, "bsm-tasks-card", { entity: "sensor.version" });
  await expect(page.getByText("Running · Installing")).toBeVisible();
  await page.evaluate(() =>
    window.task({
      id: "task",
      status: "completed",
      message: "Installed",
      epoch: "a",
      revision: 3,
      result: {
        server_name: "Alpha",
        outcome: "installed",
        details: { files: 12 },
      },
    }),
  );
  await page.getByText("Completed · Installed").click();
  await expect(page.getByText("installed", { exact: true })).toBeVisible();
  await expect(page.getByText("12", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Refresh tasks" }).click();
  await expect(page.getByText("Completed · Installed")).toBeVisible();
  await page.evaluate(() =>
    window.task({
      id: "task",
      manager_url: "http://other",
      status: "failed",
      message: "Wrong manager",
      epoch: "a",
      revision: 4,
      error: { message: "Wrong manager" },
    }),
  );
  await expect(page.getByText("Wrong manager")).toHaveCount(0);
});

test("settings preserve boolean and numeric values and block conflicting saves", async ({
  page,
}) => {
  await mount(page, "bsm-settings-card", { entity: "sensor.version" });
  await page.getByLabel("Monitor.app interval seconds").fill("5");
  await page.getByLabel("settings.autostart").check();
  await page.getByRole("button", { name: "Save settings" }).click();
  const changes = await page.evaluate(() =>
    window.requests
      .filter((r) => r.service === "set_global_setting")
      .map((r) => r.service_data),
  );
  expect(changes).toContainEqual({
    key: "monitor.app_interval_seconds",
    value: 5,
  });
  expect(changes).toContainEqual({ key: "settings.autostart", value: true });
});

test("live application settings detect conflicts without replacing drafts", async ({
  page,
}) => {
  await mount(page, "bsm-settings-card", { entity: "sensor.version" });
  await page.getByLabel("Monitor.app interval seconds").fill("5");
  await page.evaluate(() => {
    window.settingsValues = {
      monitor: { app_interval_seconds: 9 },
      settings: { autostart: false },
    };
    window.event({
      manager_url: "http://bsm",
      event: "after_setting_update",
      data: { result: { status: "success" } },
    });
  });
  await expect(page.getByText(/Changed elsewhere/)).toBeVisible();
  await expect(page.getByLabel("Monitor.app interval seconds")).toHaveValue(
    "5",
  );
  await expect(
    page.getByRole("button", { name: "Save settings" }),
  ).toBeDisabled();
});

test("task failures show structured error details and raw response", async ({
  page,
}) => {
  await mount(page, "bsm-tasks-card", { entity: "sensor.version" });
  await page.getByText("Running · Installing").waitFor();
  await page.evaluate(() =>
    window.task({
      id: "task",
      status: "failed",
      message: "Failed",
      epoch: "a",
      revision: 3,
      error: {
        message: "Disk full",
        code: "storage_error",
        details: { path: "worlds/Alpha" },
      },
    }),
  );
  await page.getByText("Failed · Failed", { exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Disk full");
  await expect(page.getByRole("alert")).toContainText("storage_error");
  await expect(page.getByRole("alert")).toContainText("worlds/Alpha");
  await page.getByText("Raw response").click();
  await expect(page.locator("pre")).toContainText('"revision": 3');
});

test("multiple task cards share subscriptions, requests and ordered outcomes", async ({
  page,
}) => {
  await page.goto("/frontend/tests/fixture.html");
  await page.waitForFunction(() => window.ready);
  await page.evaluate(async () => {
    const mount = document.getElementById("mount");
    window.cards = [0, 1].map(() => {
      const card = document.createElement("bsm-tasks-card");
      card.setConfig({ entity: "sensor.version" });
      card.hass = window.hass;
      mount.append(card);
      return card;
    });
    await Promise.all(window.cards.map((card) => card.updateComplete));
  });
  await expect(page.getByText("Running · Installing")).toHaveCount(2);
  expect(await page.evaluate(() => window.subscriptionCount)).toBe(2);
  expect(
    await page.evaluate(
      () => window.requests.filter((r) => r.service === "list_tasks").length,
    ),
  ).toBe(1);
  await page.evaluate(() =>
    window.task({
      status: "completed",
      message: "Shared outcome",
      revision: 8,
      result: { outcome: "installed" },
    }),
  );
  await expect(page.getByText("Completed · Shared outcome")).toHaveCount(2);
  await page.evaluate(() => window.cards[0].remove());
  expect(await page.evaluate(() => window.unsubscribeCount)).toBe(0);
  await page.evaluate(() => window.cards[1].remove());
  await expect.poll(() => page.evaluate(() => window.unsubscribeCount)).toBe(2);
});

test("switching managers during a task fetch clears loading and ignores the old response", async ({
  page,
}) => {
  await page.goto("/frontend/tests/fixture.html");
  await page.waitForFunction(() => window.ready);
  await page.evaluate(() => {
    window.hass.states["sensor.second"] = {
      ...window.hass.states["sensor.version"],
      entity_id: "sensor.second",
      attributes: {
        ...window.hass.states["sensor.version"].attributes,
        bsm_manager_url: "http://second",
      },
    };
    window.hass.entities["sensor.second"] = { device_id: "second" };
    window.delayResponse = true;
    window.mount("bsm-tasks-card", { entity: "sensor.version" });
  });
  await expect
    .poll(() => page.evaluate(() => typeof window.resolveResponse))
    .toBe("function");
  await page.evaluate(() => {
    window.oldResolve = window.resolveResponse;
    window.delayResponse = false;
    window.card.select("sensor.second");
    window.card.hass = { ...window.hass };
  });
  await expect(
    page.getByRole("button", { name: "Refresh tasks" }),
  ).toBeEnabled();
  await page.evaluate(() =>
    window.oldResolve({
      response: {
        managers: [
          {
            manager_url: "http://bsm",
            tasks: [
              {
                id: "old",
                status: "completed",
                message: "Old manager",
                epoch: "a",
                revision: 9,
              },
            ],
          },
        ],
      },
    }),
  );
  await expect(page.getByText("Completed · Old manager")).toHaveCount(0);
});

test("partial settings saves retain failed edits and identify applied changes", async ({
  page,
}) => {
  await mount(page, "bsm-settings-card", { entity: "sensor.version" });
  await page.getByLabel("Monitor.app interval seconds").fill("5");
  await page.getByLabel("settings.autostart").check();
  await page.evaluate(() => (window.failSetting = "settings.autostart"));
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(page.getByLabel("Settings save results")).toContainText(
    "Monitor.app interval seconds: Saved",
  );
  await expect(page.getByLabel("Settings save results")).toContainText(
    "Settings.autostart: Failed",
  );
  await expect(page.getByRole("alert")).toContainText(
    "unsaved edits are retained",
  );
  expect(await page.evaluate(() => window.card.draft.changes)).toEqual({
    "settings.autostart": true,
  });
  await page.evaluate(() => (window.failSetting = null));
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(
    page.getByText("Unsaved changes.", { exact: false }),
  ).toHaveCount(0);
});

test("overview allows independent server actions and supports monitor navigation", async ({
  page,
}) => {
  await mount(page, "bsm-overview-card", {
    monitor_path: "/dashboard/monitor/{server}",
  });
  await page.evaluate(() => (window.acceptTask = true));
  const tiles = page.locator("section.tile");
  await tiles
    .filter({ hasText: "Alpha" })
    .getByRole("button", { name: "Update", exact: true })
    .click();
  await expect(
    tiles
      .filter({ hasText: "Beta" })
      .getByRole("button", { name: "Update", exact: true }),
  ).toBeEnabled();
  await tiles
    .filter({ hasText: "Beta" })
    .getByRole("button", { name: "Beta", exact: true })
    .click();
  await expect(page).toHaveURL(/\/dashboard\/monitor\/Beta$/);
});

test("reconnect preserves task outcomes and reloads settings without losing edits", async ({
  page,
}) => {
  await mount(page, "bsm-settings-card", { entity: "sensor.version" });
  await page.getByLabel("Monitor.app interval seconds").fill("5");
  await page.evaluate(() => {
    window.settingsValues = {
      monitor: { app_interval_seconds: 8 },
      settings: { autostart: false },
    };
    window.readyConnection();
  });
  await expect(page.getByText(/Changed elsewhere/)).toBeVisible();
  await expect(page.getByLabel("Monitor.app interval seconds")).toHaveValue(
    "5",
  );
  expect(await page.evaluate(() => window.subscriptionCount)).toBe(2);
});

test("task polling pauses when hidden and releases the final manager watch", async ({
  page,
}) => {
  await page.clock.install();
  await mount(page, "bsm-tasks-card", { entity: "sensor.version" });
  await page.getByText("Running · Installing").waitFor();
  const initial = await page.evaluate(
    () => window.requests.filter((r) => r.service === "list_tasks").length,
  );
  await page.evaluate(() => {
    Object.defineProperty(document, "hidden", {
      configurable: true,
      get: () => true,
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await page.clock.fastForward(20000);
  expect(
    await page.evaluate(
      () => window.requests.filter((r) => r.service === "list_tasks").length,
    ),
  ).toBe(initial);
  await page.evaluate(() => {
    Object.defineProperty(document, "hidden", {
      configurable: true,
      get: () => false,
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect
    .poll(() =>
      page.evaluate(
        () => window.requests.filter((r) => r.service === "list_tasks").length,
      ),
    )
    .toBe(initial + 1);
  await page.evaluate(() => window.card.remove());
  const count = await page.evaluate(() => window.requests.length);
  await page.clock.fastForward(20000);
  expect(await page.evaluate(() => window.requests.length)).toBe(count);
});

test("card runtime does not apply an HTTP response from before reconnect", async ({
  page,
}) => {
  await mount(page, "bsm-settings-card", { entity: "sensor.version" });
  await page.getByLabel("Monitor.app interval seconds").fill("5");
  await page.evaluate(() => {
    window.delayResponse = true;
    window.card.load(true);
  });
  await expect
    .poll(() => page.evaluate(() => typeof window.resolveResponse))
    .toBe("function");
  await page.evaluate(() => {
    window.oldResolve = window.resolveResponse;
    window.delayResponse = false;
    window.settingsValues = {
      monitor: { app_interval_seconds: 9 },
      settings: { autostart: false },
    };
    window.readyConnection();
  });
  await expect(page.getByText(/Changed elsewhere/)).toBeVisible();
  await page.evaluate(() =>
    window.oldResolve({
      response: {
        results: [
          {
            manager_url: "http://bsm",
            result: { settings: { monitor: { app_interval_seconds: 1 } } },
          },
        ],
      },
    }),
  );
  expect(
    await page.evaluate(
      () => window.card.draft.live["monitor.app_interval_seconds"],
    ),
  ).toBe(9);
  await expect(page.getByLabel("Monitor.app interval seconds")).toHaveValue(
    "5",
  );
});
