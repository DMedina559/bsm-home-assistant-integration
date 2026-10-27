import { html, register } from "./base.js";
import { InspectorCard, responseValue } from "./inspector.js";
import { outcomeValue } from "./task-outcome.js";

class RestoreCard extends InspectorCard {
  static title = "Server backups";
  static key = "world_backups_count";
  static properties = {
    filePath: { state: true },
    recoveryKey: { state: true },
    backups: { state: true },
    backupId: { state: true },
    mode: { state: true },
    components: { state: true },
    choices: { state: true },
    manifest: { state: true },
    plan: { state: true },
    selectedComponents: { state: true },
  };
  constructor() {
    super();
    this.resetBackupState();
  }
  resetBackupState() {
    this.filePath = "";
    this.recoveryKey = "";
    this.backups = null;
    this.backupId = "";
    this.mode = "default";
    this.components = [];
    this.choices = [];
    this.manifest = null;
    this.plan = null;
    this.selectedComponents = [];
    this._handled = new Set();
  }
  selectedChanged() {
    super.selectedChanged();
    this.resetBackupState();
  }
  reconnected() {
    super.reconnected();
    this.plan = null;
  }
  chooseBackup(value) {
    this.backupId = value;
    this.manifest = null;
    this.plan = null;
    this.selectedComponents = [];
  }
  async refresh() {
    const generation = this._generation;
    const value = await this.read("list_server_snapshots", {});
    if (!value || generation !== this._generation) return;
    this.backups = value.backups || [];
    if (!this.backups.some((b) => b.backup_id === this.backupId))
      this.chooseBackup("");
    try {
      const discovered = responseValue(
        await this.responseService("discover_operations", {}),
      );
      if (generation !== this._generation) return;
      const schema = discovered.operations.find(
        (o) => o.operation_id === "create_server_snapshot",
      )?.request_body?.content?.["application/json"]?.schema;
      const raw = schema?.properties?.components;
      const selection = raw?.anyOf?.find((s) => s.type === "array") || raw;
      this.choices = (selection?.items?.enum || []).map((value) => ({
        value,
        label: selection?.["x-bsm-choice-labels"]?.[value] || value,
      }));
      if (!this.components.length)
        this.components = selection?.["x-bsm-default-components"] || [];
    } catch (error) {
      if (generation === this._generation) this.error = error.message;
    }
  }
  _showTasks() {
    super._showTasks();
    for (const { task } of this._tasks.values()) {
      if (task.status !== "completed" || this._handled.has(task.id)) continue;
      this._handled.add(task.id);
      if (task.result?.backup?.backup_id) {
        const updated = task.result.backup;
        this.backups = [
          updated,
          ...(this.backups || []).filter(
            (b) => b.backup_id !== updated.backup_id,
          ),
        ];
      }
      if (task.result?.backup?.backup_id === this.backupId) {
        this.manifest = task.result.backup.manifest;
        this.selectedComponents = Object.entries(
          this.manifest?.components || {},
        )
          .filter(([, v]) => v === "included")
          .map(([k]) => k);
        this.plan = null;
      }
      if (task.result?.plan?.backup_id === this.backupId)
        this.plan = task.result.plan;
    }
  }
  selectionFields(options, selected, change) {
    return html`<fieldset ?disabled=${this.busy || this.loading}>
      <legend>Components</legend>
      ${options.map((option) => html`<label class="row"><input style="width:auto" type="checkbox" .checked=${selected.includes(option.value)} @change=${(e) => change(e.target.checked ? [...selected, option.value] : selected.filter((v) => v !== option.value))} />${option.label}</label>`)}
    </fieldset>`;
  }
  async action(service, ...args) {
    const generation = this._generation;
    const success = await super.action(service, ...args);
    if (
      success &&
      generation === this._generation &&
      service === "restore_server_snapshot"
    )
      this.plan = null;
    return success;
  }
  credential() {
    return this.recoveryKey ? { recovery_key: this.recoveryKey } : {};
  }
  requestData() {
    return {
      backup_id: this.backupId,
      components: this.selectedComponents,
      ...this.credential(),
    };
  }
  render() {
    const disabled = this.busy || this.loading || !this.available;
    const archived = Object.entries(this.manifest?.components || {})
      .filter(([, v]) => v === "included")
      .map(([value]) => ({ value, label: value }));
    return this.frame(
      html`${this.readNotice()}
        <div class="actions">
          <button ?disabled=${disabled} @click=${this.refresh}>
            Refresh backups</button
          >${this.readButton("Backup health", "get_backup_health")}${this.readButton("Recovery status", "get_restore_recovery")}
        </div>
        <h3>Create backup</h3>
        ${this.selectInput(
          "Backup contents",
          this.mode,
          [
            { value: "default", label: "Global defaults" },
            { value: "world", label: "World" },
            { value: "selected", label: "Selected components" },
            { value: "full", label: "Full server directory" },
          ],
          (v) => (this.mode = v),
        )}
        ${this.mode === "selected" ? this.selectionFields(this.choices, this.components, (v) => (this.components = v)) : ""}
        <button
          ?disabled=${disabled || (this.mode === "selected" && !this.components.length)}
          @click=${() => this.action("create_server_snapshot", this.mode === "default" ? {} : { mode: this.mode, ...(this.mode === "selected" ? { components: this.components } : {}) }, "Backup requested.")}
        >
          Create backup
        </button>
        <h3>Saved backups</h3>
        ${this.backups === null ? html`<p class="muted">Load backups to see available archives.</p>` : this.backups.length ? this.selectInput("Backup", this.backupId, [{ value: "", label: "Select backup" }, ...this.backups.map((b) => ({ value: b.backup_id, label: `${b.label || b.filename} · ${b.created_at ? new Date(b.created_at).toLocaleString() : "Unknown time"} · ${b.verification?.status || "unverified"}` }))], (v) => this.chooseBackup(v)) : html`<p>No backups available.</p>`}
        ${this.backupId ? html`<div class="actions"><button ?disabled=${disabled} @click=${() => this.action("inspect_server_snapshot", { backup_id: this.backupId, ...this.credential() }, "Inspection requested.")}>Inspect</button>${["verify", "pin", "unpin", "drill"].map((action) => html`<button ?disabled=${disabled} @click=${() => this.action("manage_server_snapshot", { backup_id: this.backupId, action, ...this.credential() }, "Request accepted.")}>${{ verify: "Verify", pin: "Pin", unpin: "Unpin", drill: "Recovery drill" }[action]}</button>`)}</div>` : ""}
        ${
          this.manifest
            ? html`<h3>Restore selection</h3>
                ${this.selectionFields(
                  archived,
                  this.selectedComponents,
                  (v) => {
                    this.selectedComponents = v;
                    this.plan = null;
                  },
                )}
                <div class="actions">
                  <button
                    ?disabled=${disabled || !this.selectedComponents.length}
                    @click=${() => {
                      this.plan = null;
                      this.action(
                        "plan_snapshot_restore",
                        this.requestData(),
                        "Review requested.",
                      );
                    }}
                  >
                    Review restore</button
                  ><button
                    ?disabled=${disabled || !this.selectedComponents.length}
                    @click=${() => this.action("dry_run_server_restore", this.requestData(), "Dry run requested.")}
                  >
                    Dry run
                  </button>
                </div>`
            : ""
        }
        ${
          this.plan
            ? html`<h3>Restore review</h3>
                ${outcomeValue({ ...this.plan, token: undefined })}<button
                  ?disabled=${disabled}
                  @click=${() => {
                    const plan = this.plan;
                    this.action(
                      "restore_server_snapshot",
                      {
                        backup_id: plan.backup_id,
                        components: plan.components,
                        token: plan.token,
                        ...this.credential(),
                      },
                      "Restore requested.",
                      {
                        confirm:
                          "Restore the reviewed components? Current data will be replaced and the server may stop and restart.",
                      },
                    );
                  }}
                >
                  Restore reviewed components
                </button>`
            : ""
        }
        <details>
          <summary>Files and recovery key</summary>
          <form @submit=${(e) => e.preventDefault()}>
            ${this.input("File path on Home Assistant", this.filePath, (v) => (this.filePath = v))}
            ${this.input(
              "Recovery key (optional)",
              this.recoveryKey,
              (v) => {
                this.recoveryKey = v;
                this.plan = null;
              },
              "password",
            )}
            <p class="muted">
              Use an allowed Home Assistant directory. Downloads need a new
              filename. A recovery key is only needed when the BSM host does not
              have the archive key.
            </p>
            <div class="actions">
              <button
                type="button"
                ?disabled=${disabled || !this.filePath}
                @click=${() => this.action("import_server_snapshot", { file_path: this.filePath, ...this.credential() }, "Import requested.")}
              >
                Import archive</button
              ><button
                type="button"
                ?disabled=${disabled || !this.filePath || !this.backupId}
                @click=${() => this.action("download_server_snapshot", { backup_id: this.backupId, file_path: this.filePath }, "Archive saved on Home Assistant.")}
              >
                Export archive
              </button>
            </div>
          </form>
        </details>
        <div class="actions">
          ${this.button("Prune backups", "prune_backups", {}, { confirm: "Prune unprotected backups using retention settings? Removed backups cannot be recovered." })}${this.button("Retry recovery", "recover_server_backup", {}, { confirm: "Retry restore journal recovery? Stop the server first; recovery can roll back server data." })}
        </div>
        <details>
          <summary>Health and recovery details</summary>
          ${outcomeValue(this.result)}
        </details>`,
    );
  }
}
register(
  "bsm-restore-card",
  RestoreCard,
  "BSM Backups and Restore",
  "Create component backups, inspect archives, verify, and review restores before applying.",
);
