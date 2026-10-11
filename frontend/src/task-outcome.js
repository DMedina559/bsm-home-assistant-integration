import { html, nothing } from "lit";
import { label } from "./model.js";
export function outcomeValue(value) {
  if (value === null || value === undefined)
    return html`<span class="muted">None</span>`;
  if (Array.isArray(value))
    return html`<ul>
      ${value.map((item) => html`<li>${outcomeValue(item)}</li>`)}
    </ul>`;
  if (typeof value === "object")
    return html`<dl>
      ${Object.entries(value).map(
        ([key, item]) =>
          html`<dt>${label(key)}</dt>
            <dd style="margin:0 0 8px;overflow-wrap:anywhere">
              ${outcomeValue(item)}
            </dd>`,
      )}
    </dl>`;
  return html`<span style="overflow-wrap:anywhere">${String(value)}</span>`;
}
export function taskOutcome(task) {
  return html`${task.error ? html`<div class="error" role="alert">${outcomeValue(task.error)}</div>` : nothing}${
      task.result != null
        ? html`<h4>Outcome</h4>
            ${outcomeValue(task.result)}`
        : nothing
    }
    <details>
      <summary>Raw response</summary>
      <pre style="white-space:pre-wrap;overflow-wrap:anywhere">
${JSON.stringify(task, null, 2)}</pre>
    </details>`;
}
