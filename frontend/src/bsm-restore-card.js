import { BsmCard, html, register, unavailable } from "./base.js";
import { filename } from "./model.js";
class RestoreCard extends BsmCard {
  static title = "Restore server backup";
  static key = "world_backups_count";
  static properties = { type: { state: true }, file: { state: true } };
  constructor() {
    super();
    this.type = "world";
    this.file = "";
  }
  selectedChanged() {
    this.file = "";
  }
  render() {
    const source =
        this.stateFor(`${this.type}_backups_count`) ||
        (this.type === "world" ? this.state : null),
      files = (source?.attributes[`${this.type}_backups_list`] || []).map(
        filename,
      );
    return this.frame(
      html`${this.selectInput(
          "Backup type",
          this.type,
          ["world", "allowlist", "properties", "permissions"],
          (v) => {
            this.type = v;
            this.file = "";
          },
        )}${this.selectInput("Backup file", this.file, [{ value: "", label: "Select backup" }, ...files], (v) => (this.file = v))}${unavailable(source) ? html`<p class="muted">This backup list is unavailable.</p>` : !files.length ? html`<p class="muted">No backups of this type.</p>` : ""}
        <div class="actions">
          <button
            ?disabled=${this.busy || !this.available || unavailable(source) || !this.file}
            @click=${() => this.action("restore_backup", { restore_type: this.type, backup_file: this.file }, "Request accepted.", { confirm: "Restoring replaces current server data. Continue?" })}
          >
            Restore selected backup</button
          >${this.button("Restore latest backups", "restore_latest_all", {}, { message: "Request accepted.", confirm: "Restore the latest world and configuration backups, replacing current data?" })}
          ${this.button("Prune old backups", "prune_backups", {}, { message: "Backup pruning accepted.", confirm: "Prune backups using the server retention settings? Removed backups cannot be recovered." })}
        </div>`,
    );
  }
}
register(
  "bsm-restore-card",
  RestoreCard,
  "BSM Restore",
  "Restore selected or latest backups with task feedback.",
);
