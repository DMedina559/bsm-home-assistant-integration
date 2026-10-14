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
  await page.getByLabel("Application metrics interval").fill("5");
  await page.getByLabel("settings.autostart").check();
  await page.getByRole("button", { name: "Save settings" }).click();
  const changes = await page.evaluate(() =>
    window.requests
      .filter((r) => r.service === "set_global_setting")
      .map((r) => r.service_data),
  );
  expect(changes).toContainEqual({
    key: "monitoring.app_metrics_interval_sec",
    value: 5,
  });
  expect(changes).toContainEqual({ key: "settings.autostart", value: true });
});

test("live application settings detect conflicts without replacing drafts", async ({
  page,
}) => {
  await mount(page, "bsm-settings-card", { entity: "sensor.version" });
  await page.getByLabel("Application metrics interval").fill("5");
  await page.evaluate(() => {
    window.settingsValues = {
      monitoring: { app_metrics_interval_sec: 9 },
      settings: { autostart: false },
    };
    window.event({
      manager_url: "http://bsm",
      event: "after_setting_update",
      data: { result: { status: "success" } },
    });
  });
  await expect(page.getByText(/Changed elsewhere/)).toBeVisible();
  await expect(page.getByLabel("Application metrics interval")).toHaveValue(
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
  await page.getByLabel("Application metrics interval").fill("5");
  await page.getByLabel("settings.autostart").check();
  await page.evaluate(() => (window.failSetting = "settings.autostart"));
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(page.getByLabel("Settings save results")).toContainText(
    "Application metrics interval: Saved",
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
  await page.getByLabel("Application metrics interval").fill("5");
  await page.evaluate(() => {
    window.settingsValues = {
      monitoring: { app_metrics_interval_sec: 8 },
      settings: { autostart: false },
    };
    window.readyConnection();
  });
  await expect(page.getByText(/Changed elsewhere/)).toBeVisible();
  await expect(page.getByLabel("Application metrics interval")).toHaveValue(
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
  await page.getByLabel("Application metrics interval").fill("5");
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
      monitoring: { app_metrics_interval_sec: 9 },
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
            result: {
              settings: { monitoring: { app_metrics_interval_sec: 1 } },
            },
          },
        ],
      },
    }),
  );
  expect(
    await page.evaluate(
      () => window.card.draft.live["monitoring.app_metrics_interval_sec"],
    ),
  ).toBe(9);
  await expect(page.getByLabel("Application metrics interval")).toHaveValue(
    "5",
  );
});

test("reconnect releases an unacknowledged command without replaying it", async ({
  page,
}) => {
  await mount(page, "bsm-command-card", { entity: "sensor.server" });
  await page.getByLabel("Command", { exact: true }).fill("say pending");
  await page.evaluate(() => (window.delayResponse = true));
  await page.getByRole("button", { name: "Send command" }).click();
  await expect(
    page.getByRole("button", { name: "Send command" }),
  ).toBeDisabled();
  await page.evaluate(() => {
    window.oldResponse = window.resolveResponse;
    window.delayResponse = false;
    window.readyConnection();
  });
  await expect(
    page.getByRole("button", { name: "Send command" }),
  ).toBeEnabled();
  await expect(
    page.getByText(/Check current server or task state/),
  ).toBeVisible();
  await page.evaluate(() => window.oldResponse({ response: { results: [] } }));
  await expect(page.getByLabel("Command", { exact: true })).toHaveValue(
    "say pending",
  );
  expect(
    await page.evaluate(
      () => window.requests.filter((r) => r.service === "send_command").length,
    ),
  ).toBe(1);
});

test("manager selectors recover when the version entity is disabled", async ({
  page,
}) => {
  await page.goto("/frontend/tests/fixture.html");
  await page.waitForFunction(() => window.ready);
  await page.evaluate(() => {
    delete window.hass.states["sensor.version"];
    window.mount("bsm-tasks-card", {});
  });
  await expect(page.getByLabel("Manager", { exact: true })).toContainText(
    /plugin statuses/,
  );
  await page
    .getByLabel("Manager", { exact: true })
    .selectOption("sensor.manager");
  expect(await page.evaluate(() => window.card.selection)).toBe(
    "sensor.manager",
  );
});

test("denied live subscriptions show a polling fallback notice", async ({
  page,
}) => {
  await page.goto("/frontend/tests/fixture.html");
  await page.waitForFunction(() => window.ready);
  await page.evaluate(() => {
    window.hass.connection.subscribeEvents = async () => {
      throw Error("Unauthorized");
    };
    window.mount("bsm-command-card", { entity: "sensor.server" });
  });
  await expect(
    page.getByText(/Live event subscription unavailable/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Send command" }),
  ).toBeDisabled();
  await page.getByLabel("Command", { exact: true }).fill("say allowed");
  await expect(
    page.getByRole("button", { name: "Send command" }),
  ).toBeEnabled();
});

test("task cards and shared history stay bounded", async ({ page }) => {
  await mount(page, "bsm-tasks-card", { entity: "sensor.version" });
  await page.evaluate(() => {
    for (let i = 0; i < 700; i++)
      window.task({ id: `task-${i}`, status: "completed", revision: 1 });
  });
  expect(await page.evaluate(() => window.card.items.size)).toBeLessThanOrEqual(
    500,
  );
  expect(
    await page.evaluate(() => window.card.runtime.tasks.size),
  ).toBeLessThanOrEqual(500);
});

test("reconnect releases pending overview actions", async ({ page }) => {
  await mount(page, "bsm-overview-card", {});
  await page.evaluate(() => (window.delayResponse = true));
  const button = page
    .locator("section.tile")
    .filter({ hasText: "Alpha" })
    .getByRole("button", { name: "Update", exact: true });
  await button.click();
  await expect(button).toBeDisabled();
  await page.evaluate(() => {
    window.delayResponse = false;
    window.readyConnection();
  });
  await expect(button).toBeEnabled();
  await expect(
    page.getByText(/Check current server or task state/),
  ).toBeVisible();
});

for (const [tag, entity] of [
  ["bsm-plugin-settings-card", "sensor.manager"],
  ["bsm-api-card", "sensor.version"],
]) {
  test(`${tag} recovers loading after reconnect`, async ({ page }) => {
    await page.goto("/frontend/tests/fixture.html");
    await page.waitForFunction(() => window.ready);
    await page.evaluate(
      ([tag, entity]) => {
        window.delayResponse = true;
        window.mount(tag, { entity });
      },
      [tag, entity],
    );
    if (tag === "bsm-plugin-settings-card")
      await page.getByRole("tab", { name: "Backup" }).click();
    await expect
      .poll(() => page.evaluate(() => window.card.loading))
      .toBe(true);
    await page.evaluate(() => {
      window.delayResponse = false;
      window.readyConnection();
    });
    await expect
      .poll(() => page.evaluate(() => window.card.loading))
      .toBe(false);
  });
}

test("content sources cannot cross manager boundaries", async ({ page }) => {
  await page.goto("/frontend/tests/fixture.html");
  await page.waitForFunction(() => window.ready);
  await page.evaluate(() => {
    window.hass.states["sensor.worlds"].attributes.bsm_manager_url =
      "http://other-manager";
    window.mount("bsm-content-card", {
      entity: "sensor.server",
      content_source_sensor_entity: "sensor.worlds",
    });
  });
  await expect(page.getByLabel("File", { exact: true })).not.toContainText(
    "new.mcworld",
  );
  await expect(page.getByRole("button", { name: "Install world" })).toHaveCount(
    0,
  );
});

for (const layout of ["cards", "table"]) {
  test(`overview ${layout} shows live configured ports`, async ({ page }) => {
    await mount(page, "bsm-overview-card", { layout });
    await page.evaluate(() =>
      window.push("sensor.props", {
        server_properties: { "server-port": "19140", "server-portv6": "19141" },
      }),
    );
    await expect(
      page.getByText(/IPv4 19140 · IPv6 19141/).first(),
    ).toBeVisible();
    await page.evaluate(() =>
      window.push("sensor.props", {
        server_properties: { "server-port": "19150", "server-portv6": "19151" },
      }),
    );
    await expect(
      page.getByText(/IPv4 19150 · IPv6 19151/).first(),
    ).toBeVisible();
  });
}

test("addon metadata remains live during an unsaved order edit", async ({
  page,
}) => {
  await mount(page, "bsm-addon-card", { entity: "sensor.addons" });
  await page.getByRole("button", { name: "Move Second up" }).click();
  await page.evaluate(() =>
    window.push("sensor.addons", {
      server_addons_list: {
        behavior_packs: [
          { uuid: "one", name: "First", status: "ACTIVE" },
          {
            uuid: "two",
            name: "Second",
            status: "INACTIVE",
            subpacks: [{ folder_name: "high", name: "High" }],
            active_subpack: "high",
          },
        ],
        resource_packs: [],
      },
    }),
  );
  await expect(page.getByText("INACTIVE", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Subpack for Second")).toHaveValue("high");
  await expect(
    page.getByRole("button", { name: "Save addon order" }),
  ).toBeEnabled();
  await expect(page.getByText(/Changed elsewhere/)).toHaveCount(0);
  await expect(page.locator("section.tile strong").first()).toHaveText(
    "Second",
  );
  await page.evaluate(() =>
    window.push("sensor.addons", {
      server_addons_list: {
        behavior_packs: [
          { uuid: "two", name: "Second", status: "ACTIVE" },
          { uuid: "one", name: "First", status: "ACTIVE" },
          { uuid: "three", name: "New pack", status: "ACTIVE" },
        ],
        resource_packs: [],
      },
    }),
  );
  await expect(page.getByText("New pack", { exact: true })).toBeVisible();
  await expect(page.getByText(/Changed elsewhere/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Save addon order" }),
  ).toBeDisabled();
});

test("HTTP recovery restores property controls while preserving unsaved edits", async ({
  page,
}) => {
  await mount(page, "bsm-properties-card", { entity: "sensor.props" });
  await page
    .getByLabel("Server name", { exact: true })
    .fill("Draft after outage");
  await page.evaluate(() =>
    window.push(
      "sensor.props",
      { bsm_resource_state: "unavailable" },
      "unavailable",
    ),
  );
  await expect(
    page.getByRole("button", { name: "Save properties" }),
  ).toBeDisabled();
  await page.evaluate(() => window.readyConnection());
  await expect(
    page.getByRole("button", { name: "Save properties" }),
  ).toBeDisabled();
  await expect(page.getByLabel("Server name", { exact: true })).toHaveValue(
    "Draft after outage",
  );
  await page.evaluate(() =>
    window.push("sensor.props", { bsm_resource_state: "current" }, "Alpha"),
  );
  await expect(
    page.getByRole("button", { name: "Save properties" }),
  ).toBeEnabled();
  await expect(page.getByLabel("Server name", { exact: true })).toHaveValue(
    "Draft after outage",
  );
});

test("health card displays consolidated checks without individual check entities", async ({
  page,
}) => {
  await mount(page, "bsm-health-card", { entity: "sensor.version" });
  await page.evaluate(() => {
    window.hass = {
      ...window.hass,
      states: {
        ...window.hass.states,
        "binary_sensor.health": {
          entity_id: "binary_sensor.health",
          state: "on",
          attributes: {
            bsm_role: "manager",
            bsm_key: "health",
            bsm_manager_url: "http://bsm",
            device_class: "problem",
            friendly_name: "Application health",
            lifecycle: "ready",
            checked_at: 1700000000,
            checks: {
              database: { healthy: false, message: "Database unavailable" },
              state: { healthy: true, message: "State loaded" },
            },
          },
        },
      },
      entities: {
        ...window.hass.entities,
        "binary_sensor.health": { device_id: "manager" },
      },
    };
    window.card.hass = window.hass;
  });
  await expect(
    page.getByText("Database unavailable", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("State loaded", { exact: true })).toBeVisible();
  await expect(page.getByText("Lifecycle: ready")).toBeVisible();
  await page.evaluate(() =>
    window.push(
      "binary_sensor.health",
      {
        checks: { database: { healthy: true, message: "Database recovered" } },
      },
      "off",
    ),
  );
  await expect(
    page.getByText("Database recovered", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Database unavailable", { exact: true }),
  ).toHaveCount(0);
});

for (const status of ["partial", "skipped"]) {
  test(`completed tasks display their ${status} outcome`, async ({ page }) => {
    await mount(page, "bsm-content-card", {
      entity: "sensor.server",
      content_source_sensor_entity: "sensor.worlds",
    });
    await page.evaluate(() => (window.acceptTask = true));
    await page.getByLabel("File", { exact: true }).selectOption("new.mcworld");
    await page.getByRole("button", { name: "Install world" }).click();
    await page.getByRole("button", { name: "Confirm", exact: true }).click();
    await expect(page.getByText(/Queued:/)).toBeVisible();
    await page.evaluate(
      (status) =>
        window.task({
          status: "completed",
          message: "Task finished",
          result: {
            status,
            message: "One item was not restored",
            details: {
              properties: { outcome: "skipped", reason: "Missing backup" },
            },
          },
        }),
      status,
    );
    await page.getByText("Completed outcome · task", { exact: true }).click();
    await expect(
      page.getByText(
        status === "partial"
          ? /Operation partially completed/
          : "Operation skipped.",
      ),
    ).toBeVisible();
    await expect(
      page.getByText("Missing backup", { exact: true }),
    ).toBeVisible();
  });
}

test("bounded entity attributes show a partial-data notice", async ({
  page,
}) => {
  await mount(page, "bsm-properties-card", { entity: "sensor.props" });
  await page.evaluate(() =>
    window.push("sensor.props", {
      bsm_truncated_attributes: ["server_properties"],
    }),
  );
  await expect(page.getByText(/Entity details are limited/)).toBeVisible();
});

test("diagnostics snapshots compare and report source availability", async ({
  page,
}) => {
  await mount(page, "bsm-diagnostics-card", { entity: "sensor.version" });
  await page.evaluate(() => {
    window.snapshotCount = 0;
    window.hass.callWS = async (request) => {
      window.requests.push(request);
      const result =
        request.service === "compare_diagnostic_snapshots"
          ? {
              same_instance: true,
              changes: [
                {
                  subsystem: "events",
                  field: "workers",
                  before: 1,
                  after: 2,
                  delta: 1,
                },
              ],
            }
          : {
              snapshot_id: String(++window.snapshotCount),
              instance_id: "instance",
              summary: { status: "ok", ready: true, findings: [] },
              sections: [
                {
                  name: "events",
                  owner: "application",
                  status: "ok",
                  age_seconds: 1,
                  data: { pending_workers: 1 },
                },
              ],
            };
      return { response: { results: [{ manager_url: "http://bsm", result }] } };
    };
  });
  await page.getByRole("button", { name: "Collect snapshot" }).click();
  await expect(page.getByText("No findings reported.")).toBeVisible();
  await page.getByRole("button", { name: "Capture baseline" }).click();
  await page.getByRole("button", { name: "Collect snapshot" }).click();
  await page.getByRole("button", { name: "Compare snapshots" }).click();
  await expect(page.getByRole("heading", { name: "Comparison" })).toBeVisible();
  expect(
    await page.evaluate(
      () =>
        window.requests.find(
          (r) => r.service === "compare_diagnostic_snapshots",
        ).service_data.before.snapshot_id,
    ),
  ).toBe("1");
  await page.evaluate(
    () =>
      (window.hass.callWS = async () => ({
        response: {
          results: [
            { error: { message: "Administrator required", status_code: 403 } },
          ],
        },
      })),
  );
  await page.getByRole("button", { name: "Collect snapshot" }).click();
  await expect(page.getByText(/Data: forbidden/)).toBeVisible();
  await expect(page.getByText("No findings reported.")).toBeVisible();
});

test("log rotation reloads the current file without replaying mutations", async ({
  page,
}) => {
  await mount(page, "bsm-logs-card", { entity: "sensor.server" });
  await page.evaluate(() => {
    window.logReads = 0;
    window.hass.callWS = async (request) => {
      window.requests.push(request);
      window.logReads++;
      return {
        response: {
          results: [
            window.logReads === 2
              ? { error: { message: "Log rotated", status_code: 409 } }
              : {
                  result: {
                    data: window.logReads === 1 ? "old file" : "new file",
                    start: 100,
                    file_id: String(window.logReads),
                    has_more: true,
                  },
                },
          ],
        },
      };
    };
  });
  await page.getByRole("button", { name: "Load latest" }).click();
  await expect(page.locator("pre")).toHaveText("old file");
  await page.getByRole("button", { name: "Load older" }).click();
  await expect(page.locator("pre")).toHaveText("new file");
  expect(
    await page.evaluate(() => window.requests.map((r) => r.service_data)),
  ).toEqual([{}, { before: 100, file_id: "1" }, {}]);
});

test("runtime shutdown needs confirmation and explains the expected disconnect", async ({
  page,
}) => {
  await mount(page, "bsm-runtime-card", { entity: "sensor.version" });
  await page.getByRole("button", { name: "Shut down web runtime" }).click();
  expect(
    await page.evaluate(
      () =>
        window.requests.filter((r) => r.service === "shutdown_web_runtime")
          .length,
    ),
  ).toBe(0);
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(
    page.getByText(
      "Shutdown accepted. API and WebSocket disconnection is expected.",
    ),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () =>
        window.requests.find((r) => r.service === "shutdown_web_runtime")
          .service_data,
    ),
  ).toEqual({ confirm: true });
});

test("diagnostics ignore a response after the selected target changes", async ({
  page,
}) => {
  await mount(page, "bsm-diagnostics-card", { entity: "sensor.version" });
  await page.evaluate(() => (window.delayResponse = true));
  await page.getByRole("button", { name: "Collect snapshot" }).click();
  await page.evaluate(() => {
    window.card.select("sensor.other_version");
    window.resolveResponse({
      response: {
        results: [
          {
            result: {
              snapshot_id: "late",
              summary: { ready: true, status: "ok", findings: [] },
              sections: [],
            },
          },
        ],
      },
    });
  });
  await expect(page.getByText("No findings reported.")).toHaveCount(0);
  expect(await page.evaluate(() => window.card.snapshot)).toBeNull();
});

test("declared event payload requirements stop invalid requests", async ({
  page,
}) => {
  await mount(page, "bsm-event-trigger-card", { entity: "sensor.version" });
  await page.evaluate(
    () =>
      (window.hass.callWS = async (request) => {
        window.requests.push(request);
        return {
          response: {
            results: [
              {
                result: {
                  events: [
                    {
                      name: "example",
                      phase: "custom",
                      public: true,
                      owner: "plugin",
                      description: "Example event",
                      payload_schema: { required: ["message"] },
                    },
                  ],
                },
              },
            ],
          },
        };
      }),
  );
  await page.getByRole("button", { name: "Load event catalog" }).click();
  await page.getByLabel("Declared custom event").selectOption("example");
  await page.getByRole("button", { name: "Trigger event" }).click();
  await expect(page.getByRole("alert")).toContainText("requires 'message'");
  expect(
    await page.evaluate(() =>
      window.requests.some((r) => r.service === "trigger_plugin_event"),
    ),
  ).toBe(false);
});

test("saved plugin settings show refresh warnings without sending the write again", async ({
  page,
}) => {
  await mount(page, "bsm-plugin-settings-card", { entity: "sensor.manager" });
  await page.getByRole("tab", { name: "Backup" }).click();
  await page.getByLabel("Interval", { exact: true }).fill("5");
  await page.evaluate(() => {
    const original = window.hass.callWS;
    window.hass.callWS = async (request) => {
      if (request.service !== "update_plugin_settings")
        return original(request);
      window.requests.push(request);
      return {
        response: {
          results: [
            {
              manager_url: "http://bsm",
              status: "success",
              result: { status: "success" },
              warnings: [
                {
                  code: "refresh_failed",
                  message:
                    "Settings were saved; refreshing them failed. Refresh before retrying.",
                },
              ],
            },
          ],
        },
      };
    };
  });
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(
    page.getByText(/Settings were saved; refreshing them failed/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Save settings" }),
  ).toBeDisabled();
  expect(
    await page.evaluate(
      () =>
        window.requests.filter((r) => r.service === "update_plugin_settings")
          .length,
    ),
  ).toBe(1);
});
