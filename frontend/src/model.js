/** Pure state helpers shared by cards and their browser tests. */
export const DOMAIN = "bedrock_server_manager";
export const unavailable = (state) =>
  !state || ["unavailable", "unknown"].includes(state.state);
export const copy = (value) => structuredClone(value);
export const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
export const label = (key) =>
  key.replace(/[_-]/g, " ").replace(/^./, (c) => c.toUpperCase());

export class Draft {
  constructor() {
    this.reset({});
  }
  reset(value) {
    this.base = copy(value);
    this.live = copy(value);
    this.changes = {};
  }
  update(value) {
    this.live = copy(value);
    if (!this.dirty) this.base = copy(value);
  }
  set(key, value) {
    if (equal(value, this.base[key])) delete this.changes[key];
    else this.changes[key] = value;
  }
  get dirty() {
    return Object.keys(this.changes).length > 0;
  }
  get conflicts() {
    return Object.keys(this.changes).filter(
      (key) =>
        !equal(this.live[key], this.base[key]) &&
        !equal(this.live[key], this.changes[key]),
    );
  }
  get value() {
    return { ...this.live, ...this.changes };
  }
}

export function entityKey(hass, entityId) {
  const state = hass?.states?.[entityId];
  return state?.attributes?.bsm_key;
}
export function deviceId(hass, entityId) {
  return (
    hass?.entities?.[entityId]?.device_id ||
    hass?.states?.[entityId]?.attributes?.device_id
  );
}
export function entities(hass, role, key) {
  return Object.entries(hass?.states || {})
    .filter(
      ([id, s]) =>
        s.attributes?.bsm_role === role &&
        (!key || entityKey(hass, id) === key),
    )
    .sort(([a], [b]) => a.localeCompare(b));
}
export function related(hass, anchor, key) {
  const anchorDevice = deviceId(hass, anchor);
  return Object.entries(hass?.states || {}).find(
    ([id]) =>
      entityKey(hass, id) === key &&
      anchorDevice &&
      deviceId(hass, id) === anchorDevice,
  )?.[0];
}
export function taskError(task) {
  return (
    task.error?.message ||
    task.error?.detail ||
    task.message ||
    "The operation failed."
  );
}
export function filename(value) {
  return typeof value === "string" ? value : value.filename || value.name;
}

export function schemaValue(value, schema) {
  if (schema.enum)
    return schema.enum.find((item) => String(item) === String(value));
  if (["number", "integer"].includes(schema.type)) {
    if (
      value === "" ||
      value === null ||
      value === undefined ||
      !Number.isFinite(Number(value))
    )
      throw Error("Enter a valid number.");
    const number = Number(value);
    if (schema.type === "integer" && !Number.isInteger(number))
      throw Error("Enter a whole number.");
    if (schema.minimum != null && number < schema.minimum)
      throw Error(`Minimum is ${schema.minimum}.`);
    if (schema.maximum != null && number > schema.maximum)
      throw Error(`Maximum is ${schema.maximum}.`);
    if (schema.exclusiveMinimum != null && number <= schema.exclusiveMinimum)
      throw Error(`Must exceed ${schema.exclusiveMinimum}.`);
    if (schema.exclusiveMaximum != null && number >= schema.exclusiveMaximum)
      throw Error(`Must be less than ${schema.exclusiveMaximum}.`);
    return number;
  }
  if (["object", "array"].includes(schema.type) && typeof value === "string")
    return JSON.parse(value);
  return value;
}
