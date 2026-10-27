/** On-demand reads retain prior data visibly and reject late target responses. */
import { BsmCard, html } from "./base.js";
export function responseValue(response) {
  const item = response.results?.[0];
  if (!item) throw Error("No response was returned for this target.");
  if (item.error) {
    const error = Error(item.error.message);
    error.code = item.error.code;
    error.status = item.error.status_code;
    throw error;
  }
  return item.result;
}
export class InspectorCard extends BsmCard {
  static properties = {
    loading: { state: true },
    result: { state: true },
    resourceState: { state: true },
    loadedAt: { state: true },
  };
  constructor() {
    super();
    this.loading = false;
    this.resourceState = "not loaded";
  }
  selectedChanged() {
    this.loading = false;
    this.result = null;
    this.loadedAt = null;
    this.resourceState = "not loaded";
    this._request = (this._request || 0) + 1;
  }
  reconnected() {
    super.reconnected();
    this.loading = false;
    this._request = (this._request || 0) + 1;
    if (this.result) this.resourceState = "stale";
  }
  async read(service, data = {}, apply = true) {
    if (this.loading || !this.available) return null;
    const generation = this._generation,
      request = (this._request = (this._request || 0) + 1);
    this.loading = true;
    this.error = "";
    try {
      const result = responseValue(await this.responseService(service, data));
      if (generation !== this._generation || request !== this._request)
        return null;
      if (apply) this.result = result;
      this.resourceState = "current";
      this.loadedAt = new Date();
      return result;
    } catch (error) {
      if (generation === this._generation && request === this._request) {
        this.resourceState =
          error.code === "unsupported_operation"
            ? "unsupported"
            : error.status === 403
              ? "forbidden"
              : this.result
                ? "stale"
                : "unavailable";
        this.error = error.message || String(error);
        this.lastError = error;
      }
      return null;
    } finally {
      if (generation === this._generation && request === this._request)
        this.loading = false;
    }
  }
  readButton(title, service, data = {}) {
    return html`<button
      ?disabled=${this.loading || this.busy || !this.available}
      @click=${() => this.read(service, data)}
    >
      ${title}
    </button>`;
  }
  readNotice() {
    return html`<p class="muted" role="status">
      ${this.loading ? "Loading…" : `Data: ${this.resourceState}`}${this.loadedAt ? ` · Last loaded ${this.loadedAt.toLocaleTimeString()}` : ""}.
      Details load on demand.
    </p>`;
  }
}
