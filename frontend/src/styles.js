import { css } from "lit";
export const styles = css`
  :host {
    display: block;
    height: 100%;
    color: var(--primary-text-color);
  }
  ha-card {
    height: 100%;
    box-sizing: border-box;
    overflow: hidden;
  }
  .body {
    padding: 16px;
    display: grid;
    gap: 12px;
  }
  h2 {
    font-size: 1.1rem;
    font-weight: 500;
    margin: 0;
  }
  h3 {
    font-size: 0.95rem;
    margin: 4px 0;
  }
  .row,
  .actions,
  .heading {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .heading {
    justify-content: space-between;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
  }
  .tile {
    border: 1px solid var(--divider-color);
    border-radius: var(--ha-card-border-radius, 12px);
    padding: 12px;
    min-width: 0;
  }
  .muted,
  small {
    color: var(--secondary-text-color);
  }
  .error {
    color: var(--error-color, #db4437);
  }
  .notice {
    padding: 10px;
    border-radius: 8px;
    background: var(--secondary-background-color);
  }
  .value {
    font-size: 1.25rem;
    font-weight: 500;
  }
  label {
    display: grid;
    gap: 5px;
    font-size: 0.9rem;
  }
  input,
  textarea,
  select,
  button {
    font: inherit;
    color: inherit;
    box-sizing: border-box;
  }
  input,
  textarea,
  select {
    width: 100%;
    background: var(--card-background-color);
    border: 1px solid var(--divider-color);
    border-radius: 6px;
    padding: 10px;
  }
  textarea {
    min-height: 85px;
    resize: vertical;
  }
  button {
    background: var(--secondary-background-color);
    border: 1px solid var(--divider-color);
    border-radius: 8px;
    min-height: 40px;
    padding: 8px 12px;
    cursor: pointer;
  }
  button.primary {
    background: var(--primary-color);
    color: var(--text-primary-color, #fff);
    border-color: transparent;
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  button:focus-visible,
  input:focus-visible,
  textarea:focus-visible,
  select:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
  .scroll {
    overflow-x: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    text-align: left;
  }
  th,
  td {
    padding: 8px;
    border-bottom: 1px solid var(--divider-color);
  }
  th {
    font-size: 0.85rem;
    color: var(--secondary-text-color);
  }
  fieldset {
    border: 1px solid var(--divider-color);
    border-radius: 8px;
    margin: 0;
    padding: 8px 12px;
  }
  legend {
    padding: 0 4px;
  }
  ha-selector {
    display: block;
  }
  .tabs button[aria-selected="true"] {
    border-color: var(--primary-color);
    color: var(--primary-color);
  }
  .confirm {
    border: 1px solid var(--error-color);
    padding: 12px;
    border-radius: 8px;
  }
  @media (max-width: 450px) {
    .body {
      padding: 12px;
    }
    .grid {
      grid-template-columns: 1fr;
    }
  }
`;
