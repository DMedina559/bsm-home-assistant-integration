import { BsmCard, html, register } from "./base.js";
import { outcomeValue } from "./task-outcome.js";
class ApiCard extends BsmCard {
  static role = "manager";
  static key = "bsm_version";
  static title = "API operations";
  static properties = {
    operations: { state: true },
    operation: { state: true },
    parameters: { state: true },
    body: { state: true },
    result: { state: true },
    loading: { state: true },
  };
  constructor() {
    super();
    this.operations = [];
    this.operation = "";
    this.parameters = "{}";
    this.body = "";
  }
  reconnected() {
    super.reconnected();
    this.loading = false;
    if (this.available) this.discover();
  }
  selectedChanged() {
    this.loading = false;
    this.operations = [];
    this.operation = "";
    this.result = null;
    this._loaded = "";
  }
  syncState() {
    if (this.available && this._loaded !== this.selection) {
      this._loaded = this.selection;
      this.discover();
    }
  }
  async discover() {
    const generation = this._generation;
    this.loading = true;
    try {
      const response = await this.responseService("discover_operations", {
        refresh: true,
      });
      if (generation !== this._generation) return;
      this.operations = response.results?.[0]?.result?.operations || [];
      this.error = "";
    } catch (error) {
      if (generation === this._generation)
        this.error = error.message || String(error);
    } finally {
      if (generation === this._generation) this.loading = false;
    }
  }
  async invoke() {
    if (this.busy || !this.available) return;
    const generation = this._generation;
    try {
      const parameters = JSON.parse(this.parameters);
      const data = {
        operation_id: this.operation,
        path_params: parameters.path_params || {},
        query: parameters.query || {},
      };
      if (this.body.trim()) data.json_data = JSON.parse(this.body);
      const operation = this.operations.find(
        (o) => o.operation_id === this.operation,
      );
      if (
        operation?.method.toUpperCase() !== "GET" &&
        !window.confirm(`Run ${operation?.method} ${this.operation}?`)
      )
        return;
      const success = await this.action(
        "call_operation",
        data,
        "Operation completed.",
      );
      const response = this._lastResponse;
      if (success && generation === this._generation) {
        this.result = response;
        this.error = "";
      }
    } catch (error) {
      if (generation === this._generation)
        this.error = error.message || String(error);
    }
  }
  render() {
    const operation = this.operations.find(
      (o) => o.operation_id === this.operation,
    );
    return this.frame(
      html`${this.selectInput(
          "Operation",
          this.operation,
          [
            { value: "", label: "Select operation" },
            ...this.operations.map((o) => ({
              value: o.operation_id,
              label: `${o.plugin ? `${o.plugin} · ` : ""}${o.method.toUpperCase()} ${o.summary || o.operation_id}`,
            })),
          ],
          (v) => {
            this.operation = v;
            this.result = null;
          },
        )}${
          operation
            ? html`<small>${operation.description || operation.path}</small>
                <details>
                  <summary>Request contract</summary>
                  ${outcomeValue({ parameters: operation.parameters, request_body: operation.request_body })}
                </details>`
            : ""
        }<label
          >Parameters (JSON)<textarea
            aria-label="Parameters"
            .value=${this.parameters}
            @input=${(e) => (this.parameters = e.target.value)}
          ></textarea></label
        ><label
          >Request body (JSON)<textarea
            aria-label="Request body"
            .value=${this.body}
            @input=${(e) => (this.body = e.target.value)}
          ></textarea>
        </label>
        <div class="actions">
          <button
            ?disabled=${this.loading || this.busy || !this.available}
            @click=${this.discover}
          >
            Refresh operations</button
          ><button
            ?disabled=${this.loading || this.busy || !this.available || !this.operation}
            @click=${this.invoke}
          >
            Run operation
          </button>
        </div>
        ${this.result ? outcomeValue(this.result) : ""}`,
    );
  }
}
register(
  "bsm-api-card",
  ApiCard,
  "BSM API Operations",
  "Discover and invoke authenticated core and plugin operations with SDK validation.",
);
