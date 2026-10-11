import { BsmCard, html, register, unavailable } from "./base.js";
import { filename } from "./model.js";
class ContentCard extends BsmCard {
  static title = "Install server content";
  static properties = {
    source: { state: true },
    file: { state: true },
    uploadPath: { state: true },
    canUpload: { state: true },
  };
  static getConfigForm() {
    const form = super.getConfigForm();
    form.schema.push({
      name: "content_source_sensor_entity",
      selector: {
        entity: { integration: "bedrock_server_manager", domain: "sensor" },
      },
    });
    return form;
  }
  setConfig(config) {
    super.setConfig(config);
    this.source = config.content_source_sensor_entity || "";
  }
  selectedChanged() {
    this.file = "";
    this.canUpload = false;
    this._checked = "";
  }
  reconnected() {
    super.reconnected();
    this._checked = "";
    if (this.available) this.syncState();
  }
  syncState() {
    if (!this.available || this._checked === this.selection) return;
    this._checked = this.selection;
    const generation = this._generation;
    this.responseService("discover_operations", {})
      .then((response) => {
        if (generation === this._generation)
          this.canUpload = (
            response.results?.[0]?.result?.operations || []
          ).some((op) => op.operation_id === "upload_content");
      })
      .catch(() => {
        if (generation === this._generation) this._checked = "";
      });
  }
  render() {
    const manager = this.state?.attributes.bsm_manager_url;
    const sources = Object.entries(this.hass?.states || {}).filter(
      ([, s]) =>
        manager &&
        s.attributes.bsm_manager_url === manager &&
        (s.attributes.available_worlds_list ||
          s.attributes.available_addons_list),
    );
    const source = sources.find(([id]) => id === this.source)?.[1],
      type = source?.attributes.available_worlds_list ? "world" : "addon";
    const files = (
      source?.attributes.available_worlds_list ||
      source?.attributes.available_addons_list ||
      []
    ).map(filename);
    return this.frame(
      html`${this.selectInput(
          "Content source",
          this.source || "",
          [
            { value: "", label: "Select source" },
            ...sources.map(([id, s]) => ({
              value: id,
              label: s.attributes.friendly_name || id,
            })),
          ],
          (v) => {
            this.source = v;
            this.file = "";
          },
        )}${this.selectInput("File", this.file || "", [{ value: "", label: "Select file" }, ...files], (v) => (this.file = v))}${source && unavailable(source) ? html`<p class="error">The content source is unavailable.</p>` : ""}<button
          ?disabled=${!this.available || this.busy || !this.file || unavailable(source)}
          @click=${() => this.action(`install_${type}`, { filename: this.file }, "Request accepted.", { confirm: type === "world" ? "Installing a world replaces this server’s current world. Continue?" : null })}
        >
          Install ${type}
        </button>
        ${this.button("Export world", "export_world", {}, { message: "Export requested." })}
        ${
          this.canUpload
            ? html`<details>
                <summary>Upload from Home Assistant</summary>
                <small
                  >The file must be inside a Home Assistant allowed path.</small
                >${this.input("File path", this.uploadPath || "", (v) => (this.uploadPath = v))}<button
                  ?disabled=${!this.available || this.busy || !this.uploadPath}
                  @click=${() => this.action("upload_content", { file_path: this.uploadPath }, "Content uploaded.")}
                >
                  Upload content
                </button>
              </details>`
            : html`<small>Uploads require the content-uploader plugin.</small>`
        }`,
    );
  }
}
register(
  "bsm-content-card",
  ContentCard,
  "BSM Content",
  "Install available worlds or addons and follow task outcomes.",
);

// Preserve dashboards using the original content installer card tag.
if (!customElements.get("bsm-content-installer-card")) {
  customElements.define(
    "bsm-content-installer-card",
    class extends ContentCard {},
  );
}
