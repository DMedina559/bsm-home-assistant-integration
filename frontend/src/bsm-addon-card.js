import { BsmCard, html, register } from "./base.js";
class AddonCard extends BsmCard {
  static title = "Installed addons";
  static key = "server_addons_count";
  static properties = { type: { state: true } };
  constructor() {
    super();
    this.type = "behavior";
  }
  syncState() {
    if (this.available) {
      const packs = this.state.attributes.server_addons_list || {};
      this.draft.update(
        Object.fromEntries(
          Object.entries(packs).map(([key, items]) => [
            key,
            items.map((pack) => pack.uuid),
          ]),
        ),
      );
      this.requestUpdate();
    }
  }
  selectedChanged() {
    this.syncState();
  }
  get packs() {
    const key = `${this.type}_packs`;
    const items = this.state?.attributes.server_addons_list?.[key] || [];
    const order = this.draft.value[key] || [];
    const position = (pack) => {
      const index = order.indexOf(pack.uuid);
      return index < 0 ? order.length : index;
    };
    return [...items].sort((a, b) => position(a) - position(b));
  }
  move(index, direction) {
    const key = `${this.type}_packs`,
      items = [...this.packs];
    [items[index], items[index + direction]] = [
      items[index + direction],
      items[index],
    ];
    this.draft.set(
      key,
      items.map((pack) => pack.uuid),
    );
    this.requestUpdate();
  }
  async save() {
    if (this.draft.conflicts.length) return;
    const saved = await this.action(
      "reorder_addons",
      {
        pack_type: this.type,
        uuids: this.packs
          .filter((p) => p.status === "ACTIVE")
          .map((p) => p.uuid),
      },
      "Addon order saved.",
    );
    if (saved) {
      const key = `${this.type}_packs`;
      const submitted = this.draft.value[key];
      delete this.draft.changes[key];
      this.draft.base[key] = structuredClone(submitted);
      this.draft.live[key] = structuredClone(submitted);
      this.requestUpdate();
    }
  }
  render() {
    return this.frame(
      html`${this.selectInput("Pack type", this.type, ["behavior", "resource"], (v) => (this.type = v))}${this.editNotice()}${this.packs.map(
          (pack, index) =>
            html`<section class="tile">
              <div class="heading">
                <strong>${pack.name || pack.uuid}</strong
                ><small>${pack.status}</small>
              </div>
              <div class="actions">
                ${this.button(pack.status === "ACTIVE" ? "Disable" : "Enable", pack.status === "ACTIVE" ? "disable_addon" : "enable_addon", { pack_uuid: pack.uuid, pack_type: this.type })}${this.button("Uninstall", "uninstall_addon", { pack_uuid: pack.uuid, pack_type: this.type }, { confirm: `Uninstall ${pack.name || pack.uuid}?` })}<button
                  aria-label=${`Move ${pack.name} up`}
                  ?disabled=${this.busy || !this.available || index === 0}
                  @click=${() => this.move(index, -1)}
                >
                  ↑</button
                ><button
                  aria-label=${`Move ${pack.name} down`}
                  ?disabled=${this.busy || !this.available || index === this.packs.length - 1}
                  @click=${() => this.move(index, 1)}
                >
                  ↓
                </button>
              </div>
              ${pack.subpacks?.length ? this.selectInput(`Subpack for ${pack.name}`, pack.active_subpack || "", [{ value: "", label: "Default" }, ...pack.subpacks.map((s) => ({ value: s.folder_name, label: s.name || s.folder_name }))], (v) => this.action("update_addon_subpack", { pack_uuid: pack.uuid, pack_type: this.type, subpack_name: v })) : ""}
            </section>`,
        )}${this.available && !this.packs.length ? html`<p class="muted">No ${this.type} packs installed.</p>` : ""}<button
          ?disabled=${this.busy || !this.available || !this.draft.dirty || this.draft.conflicts.length > 0}
          @click=${this.save}
        >
          Save addon order
        </button>`,
    );
  }
}
register(
  "bsm-addon-card",
  AddonCard,
  "BSM Addons",
  "Enable, configure and reorder installed addons.",
);
