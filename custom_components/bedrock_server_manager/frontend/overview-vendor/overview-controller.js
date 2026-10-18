import { createApiClient } from "./api-client/operations.js";
import { createSessionRuntimeModule } from "./runtime/sessionRuntime.js";
import { createPreferenceStore } from "./storage/index.js";

export function createOverviewController({ storage, onChange }) {
  const { sessionRuntime } = createSessionRuntimeModule();
  const preferences = createPreferenceStore(storage, {
    runningOnly: {
      version: 1,
      validate: (value) => typeof value === "boolean",
    },
  });
  let hass,
    entryId,
    identity,
    active = false,
    busy = false;
  let state = {
    servers: [],
    loading: false,
    error: null,
    updated: null,
    runningOnly: false,
  };
  const publish = (patch) => {
    state = { ...state, ...patch };
    onChange(state);
  };
  const client = createApiClient({
    request: async (path, options) => {
      const signal = options.signal;
      signal?.throwIfAborted();
      let operation, server;
      if (path === "/api/servers" && options.method === "GET")
        operation = "list_servers";
      else {
        const match = /^\/api\/server\/([^/]+)\/process_info$/.exec(path);
        if (!match || options.method !== "GET")
          throw Error("Unsupported card operation");
        operation = "get_server_process_info";
        server = decodeURIComponent(match[1]);
      }
      let timer, abort;
      try {
        return await Promise.race([
          hass.callWS({
            type: "bedrock_server_manager/card_read",
            entry_id: entryId,
            operation,
            ...(server === undefined ? {} : { server_name: server }),
          }),
          new Promise((_, reject) => {
            timer = setTimeout(
              () => reject(Error("Home Assistant request timed out")),
              15000,
            );
            abort = () => reject(signal.reason);
            signal?.addEventListener("abort", abort, { once: true });
          }),
        ]);
      } finally {
        clearTimeout(timer);
        signal?.removeEventListener("abort", abort);
      }
    },
  });
  return {
    configure(nextHass, nextEntry) {
      const nextIdentity = JSON.stringify([nextHass.user?.id ?? "", nextEntry]);
      if (
        nextIdentity !== identity ||
        hass?.connection !== nextHass.connection
      ) {
        sessionRuntime.reset();
        busy = false;
        identity = nextIdentity;
        publish({
          servers: [],
          loading: false,
          error: null,
          updated: null,
          runningOnly: preferences.read(identity, "runningOnly", false),
        });
      }
      hass = nextHass;
      entryId = nextEntry;
    },
    start() {
      active = true;
    },
    stop() {
      active = false;
      sessionRuntime.reset();
      busy = false;
    },
    setRunningOnly(value) {
      preferences.write(identity, "runningOnly", value);
      publish({ runningOnly: value });
    },
    async refresh() {
      if (!active || busy || !hass || !entryId) return;
      busy = true;
      const session = sessionRuntime.capture();
      publish({ loading: true, error: null });
      try {
        const fleet = await client.callOperation("list_servers", {
          signal: session.signal,
        });
        session.signal.throwIfAborted();
        if (!Array.isArray(fleet.servers)) throw Error("Invalid server list");
        const servers = await Promise.all(
          fleet.servers.map(async ({ name }) => {
            try {
              const result = await client.callOperation(
                "get_server_process_info",
                { path: { server_name: name }, signal: session.signal },
              );
              return { name, process: result.process_info ?? null };
            } catch {
              return { name, unavailable: true };
            }
          }),
        );
        if (sessionRuntime.isCurrent(session) && active)
          publish({ servers, updated: new Date(), error: null });
      } catch (error) {
        if (sessionRuntime.isCurrent(session) && active)
          publish({ error: error.message ?? "Unable to load servers" });
      } finally {
        if (sessionRuntime.isCurrent(session)) {
          busy = false;
          publish({ loading: false });
        }
      }
    },
  };
}
