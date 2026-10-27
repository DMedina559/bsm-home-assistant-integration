import { html, register } from "./base.js";
import { InspectorCard } from "./inspector.js";
import { outcomeValue } from "./task-outcome.js";
class SchedulerCard extends InspectorCard {
  static title = "Scheduler";
  static role = "manager";
  static key = "bsm_version";
  static properties = {
    scheduleId: { state: true },
    configuration: { state: true },
    options: { state: true },
  };
  constructor() {
    super();
    this.resetForm();
  }
  resetForm() {
    this.scheduleId = "";
    this.options = "{}";
    this.configuration = {
      task: "backup",
      server_name: "",
      enabled: true,
      time: "03:00",
      timezone: "UTC",
      weekdays: [0, 1, 2, 3, 4, 5, 6],
      catch_up: true,
      stagger_minutes: 15,
    };
  }
  selectedChanged() {
    super.selectedChanged();
    this.resetForm();
  }
  change(key, value) {
    this.configuration = { ...this.configuration, [key]: value };
  }
  async action(service, ...args) {
    const generation = this._generation;
    const success = await super.action(service, ...args);
    if (
      success &&
      generation === this._generation &&
      ["save_schedule", "delete_schedule"].includes(service)
    )
      await this.read("list_schedules");
    return success;
  }
  async save() {
    try {
      const options = JSON.parse(this.options);
      await this.action(
        "save_schedule",
        {
          schedule_id: this.scheduleId,
          configuration: { ...this.configuration, options },
        },
        "Schedule saved.",
      );
    } catch (error) {
      this.error = error.message;
    }
  }
  render() {
    const disabled = this.busy || this.loading || !this.available,
      c = this.configuration;
    const tasks = this.result?.task_types?.length
      ? this.result.task_types
      : ["backup", "verify"];
    return this.frame(
      html`${this.readNotice()}${this.readButton("Refresh schedules", "list_schedules")}
        <p class="muted">
          Schedules run on the BSM host. Use an IANA timezone such as
          America/Los_Angeles; daylight saving changes apply automatically.
        </p>
        ${
          this.result
            ? html`<p>
                  Host: ${this.result.host_timezone || "Unknown"} · Server time:
                  ${this.result.server_time || "Unknown"}
                </p>
                ${this.result.timezone_database_available === false ? html`<p class="error">Timezone data is missing on the BSM host.</p>` : ""}${(
                  this.result.schedules || []
                ).map(
                  (entry) =>
                    html`<div class="tile">
                      <strong>${entry.schedule_id}</strong
                      ><span
                        >${entry.configuration.task} ·
                        ${entry.configuration.server_name} ·
                        ${entry.configuration.time}
                        ${entry.configuration.timezone}</span
                      ><small
                        >Next:
                        ${entry.next_run_at ? new Date(entry.next_run_at).toLocaleString() : "Not scheduled"}
                        · ${entry.last_status || "Not run"}</small
                      >
                      <div class="actions">
                        <button
                          ?disabled=${disabled}
                          @click=${() => {
                            this.scheduleId = entry.schedule_id;
                            const { options, ...configuration } =
                              entry.configuration;
                            this.configuration = { ...configuration };
                            this.options = JSON.stringify(
                              options || {},
                              null,
                              2,
                            );
                          }}
                        >
                          Edit</button
                        ><button
                          ?disabled=${disabled}
                          @click=${() => this.action("delete_schedule", { schedule_id: entry.schedule_id }, "Schedule deleted.", { confirm: `Delete ${entry.schedule_id}?` })}
                        >
                          Delete
                        </button>
                      </div>
                      ${entry.last_error ? html`<p class="error">${entry.last_error}</p>` : ""}
                    </div>`,
                )}`
            : ""
        }
        <h3>Schedule configuration</h3>
        <fieldset ?disabled=${disabled}>
          <div class="grid">
            ${this.input("Schedule ID", this.scheduleId, (v) => (this.scheduleId = v))}${this.selectInput("Task", c.task, tasks, (v) => this.change("task", v))}${this.input("Server name", c.server_name, (v) => this.change("server_name", v))}${this.input("Time", c.time, (v) => this.change("time", v), "time")}
            <label
              >Timezone<input
                aria-label="Timezone"
                list="schedule-timezones"
                .value=${c.timezone}
                @input=${(e) => this.change("timezone", e.target.value)}
              /><datalist id="schedule-timezones">
                ${(this.result?.timezones || ["UTC", "America/Los_Angeles"]).map((zone) => html`<option value=${zone}></option>`)}
              </datalist></label
            >
            ${this.input("Stagger (minutes)", c.stagger_minutes, (v) => this.change("stagger_minutes", Number(v)), "number")}
          </div>
          <div class="row">
            ${["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day, index) => html`<label class="row"><input style="width:auto" type="checkbox" aria-label=${day} .checked=${c.weekdays.includes(index)} @change=${(e) => this.change("weekdays", e.target.checked ? [...c.weekdays, index].sort() : c.weekdays.filter((v) => v !== index))} />${day}</label>`)}
          </div>
          <div class="row">
            ${[
              ["enabled", "Enabled"],
              ["catch_up", "Catch up after downtime"],
            ].map(
              ([key, title]) =>
                html`<label class="row"
                  ><input
                    style="width:auto"
                    type="checkbox"
                    .checked=${c[key]}
                    @change=${(e) => this.change(key, e.target.checked)}
                  />${title}</label
                >`,
            )}
          </div>
          <label
            >Task options (JSON)<textarea
              aria-label="Task options"
              .value=${this.options}
              @input=${(e) => (this.options = e.target.value)}
            ></textarea>
          </label>
        </fieldset>
        <button
          ?disabled=${disabled || !this.scheduleId || !c.server_name || !c.weekdays.length}
          @click=${this.save}
        >
          Save schedule
        </button>
        <details>
          <summary>Run history and supported tasks</summary>
          ${outcomeValue(this.result)}
        </details>`,
    );
  }
}
register(
  "bsm-scheduler-card",
  SchedulerCard,
  "BSM Scheduler",
  "Manage backup, verification, and plugin task schedules with timezone and run history.",
);
