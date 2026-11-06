import{b as d}from"./shared-MLQC27XJ.js";import{h as i,i as c,k as u}from"./shared-C27S2ORL.js";var h=class extends d{static title="Scheduler";static role="manager";static key="bsm_version";static properties={scheduleId:{state:!0},configuration:{state:!0},options:{state:!0}};constructor(){super(),this.resetForm()}resetForm(){this.scheduleId="",this.options="{}",this.configuration={task:"",server_name:"",enabled:!1,time:"03:00",timezone:"",weekdays:[0,1,2,3,4,5,6],catch_up:!0,stagger_minutes:15},this._baseline=this.formSnapshot()}formSnapshot(){return JSON.stringify([this.scheduleId,this.configuration,this.options])}loadEntry(s){if(this.formSnapshot()!==this._baseline&&!window.confirm("Discard unsaved schedule changes?"))return;this.scheduleId=s.schedule_id;let{options:t,...a}=s.configuration;this.configuration={...a},this.options=JSON.stringify(t||{},null,2),this._baseline=this.formSnapshot()}selectedChanged(){super.selectedChanged(),this.resetForm(),this._catalogRequested=!1,this.syncState()}reconnected(){super.reconnected(),this._catalogRequested=!1,this.syncState()}syncState(){this.available&&!this._catalogRequested&&(this._catalogRequested=!0,this.read("list_schedules"))}get taskTypes(){return[...new Set([...this.result?.task_types||[],...Object.keys(this.result?.task_definitions||{})])].sort()}async read(s,t={},a=!0){let n=await super.read(s,t,a);if(n&&a&&s==="list_schedules"&&!this.configuration.task){let r=this.formSnapshot()===this._baseline;this.change("task",this.taskTypes[0]||""),r&&(this._baseline=this.formSnapshot())}return n}change(s,t){this.configuration={...this.configuration,[s]:t}}async action(s,...t){let a=this._generation,n=await super.action(s,...t);return n&&a===this._generation&&["save_schedule","delete_schedule","control_schedule"].includes(s)&&await this.read("list_schedules"),n}async save(){try{let s=JSON.parse(this.options),{timezone:t,...a}=this.configuration;await this.action("save_schedule",{schedule_id:this.scheduleId,configuration:{...a,...t.trim()?{timezone:t.trim()}:{},options:s}},"Schedule saved.")&&(this._baseline=this.formSnapshot())}catch(s){this.error=s.message}}render(){let s=this.busy||this.loading||!this.available,t=this.configuration,a=this.taskTypes,n=this.result?.task_definitions?.[t.task],r=[{value:"",label:"Select task"},...t.task&&!a.includes(t.task)?[{value:t.task,label:`${t.task} (unavailable)`}]:[],...a];return this.frame(i`${this.readNotice()}${this.readButton("Refresh schedules","list_schedules")}
        <p class="muted">
          Leave timezone blank for the application default. Schedules run on the
          BSM host. Use an IANA timezone such as America/Los_Angeles; daylight
          saving changes apply automatically.
        </p>
        ${this.result?i`<p>
                  Host: ${this.result.host_timezone||"Unknown"} · Server time:
                  ${this.result.server_time||"Unknown"}
                </p>
                ${this.result.timezone_database_available===!1?i`<p class="error">Timezone data is missing on the BSM host.</p>`:""}${(this.result.schedules||[]).map(e=>i`<div class="tile">
                      <strong>${e.schedule_id}</strong
                      ><span
                        >${e.configuration.task} ·
                        ${e.configuration.server_name} ·
                        ${e.configuration.time}
                        ${e.configuration.timezone}</span
                      ><small
                        >Next:
                        ${e.next_run_at?new Date(e.next_run_at).toLocaleString():"Not scheduled"}
                        · ${e.last_status||"Not run"}</small
                      >
                      ${e.next_attempt_at?i`<small>Next attempt: ${new Date(e.next_attempt_at).toLocaleString()}</small>`:""}
                      ${e.blocked_reason?i`<small>${e.blocked_reason}</small>`:""}
                      ${e.retry_exhausted?i`<p class="error">Automatic retries exhausted.</p>`:""}
                      <div class="actions">
                        ${[["run_now","Run now"],[e.configuration.enabled?"pause":"resume",e.configuration.enabled?"Pause":"Resume"],...["failed","interrupted","deferred"].includes(e.last_status)?[["retry","Retry now"]]:[]].map(([o,l])=>i`<button ?disabled=${s||this.actionDenied("control_schedule")||["run_now","retry"].includes(o)&&!e.available} @click=${()=>this.action("control_schedule",{schedule_id:e.schedule_id,action:o,...e.revision?{revision:e.revision}:{}},"Schedule action accepted.",{confirm:o==="run_now"||o==="retry"?`${l} for ${e.schedule_id}?`:null})}>${l}</button>`)}
                        <button
                          ?disabled=${s}
                          @click=${()=>this.loadEntry(e)}
                        >
                          Edit</button
                        ><button
                          ?disabled=${s||this.actionDenied("delete_schedule")}
                          @click=${()=>this.action("delete_schedule",{schedule_id:e.schedule_id},"Schedule deleted.",{confirm:`Delete ${e.schedule_id}?`})}
                        >
                          Delete
                        </button>
                      </div>
                      ${e.last_error?i`<p class="error">${e.last_error}</p>`:""}
                    </div>`)}`:""}
        <h3>Schedule configuration</h3>
        ${this.result?a.length?"":i`<p>No scheduler tasks are currently available on this manager.</p>`:i`<p>Load the manager's registered tasks before creating a schedule.</p>`}
        ${t.task&&!a.includes(t.task)?i`<p class="error">This task is not currently registered. Select an available task before saving.</p>`:""}
        ${n?i`<p>
                  ${n.description||t.task}${n.owner?i`<small>Provided by: ${n.owner}</small>`:""}
                </p>
                ${n.options_schema?i`<details>
                        <summary>Task options schema</summary>
                        ${c(n.options_schema)}
                      </details>`:""}`:""}
        <fieldset ?disabled=${s}>
          <div class="grid">
            ${this.input("Schedule ID",this.scheduleId,e=>this.scheduleId=e)}${this.selectInput("Task",t.task,r,e=>this.change("task",e))}${this.input("Server name",t.server_name,e=>this.change("server_name",e))}${this.input("Time",t.time,e=>this.change("time",e),"time")}
            <label
              >Timezone<input
                aria-label="Timezone"
                list="schedule-timezones"
                .value=${t.timezone}
                @input=${e=>this.change("timezone",e.target.value)}
              /><datalist id="schedule-timezones">
                ${(this.result?.timezones||["UTC","America/Los_Angeles"]).map(e=>i`<option value=${e}></option>`)}
              </datalist></label
            >
            ${this.input("Stagger (minutes)",t.stagger_minutes,e=>this.change("stagger_minutes",Number(e)),"number")}
          </div>
          <div class="row">
            ${["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map((e,o)=>i`<label class="row"><input style="width:auto" type="checkbox" aria-label=${e} .checked=${t.weekdays.includes(o)} @change=${l=>this.change("weekdays",l.target.checked?[...t.weekdays,o].sort():t.weekdays.filter(m=>m!==o))} />${e}</label>`)}
          </div>
          <div class="row">
            ${[["enabled","Enabled"],["catch_up","Catch up after downtime"]].map(([e,o])=>i`<label class="row"
                  ><input
                    style="width:auto"
                    type="checkbox"
                    .checked=${t[e]}
                    @change=${l=>this.change(e,l.target.checked)}
                  />${o}</label
                >`)}
          </div>
          <label
            >Task options (JSON)<textarea
              aria-label="Task options"
              .value=${this.options}
              @input=${e=>this.options=e.target.value}
            ></textarea>
          </label>
        </fieldset>
        <button
          ?disabled=${s||this.actionDenied("save_schedule")||!a.includes(t.task)||!this.scheduleId||!t.server_name||!t.weekdays.length}
          @click=${this.save}
        >
          Save schedule
        </button>
        <details>
          <summary>Run history and supported tasks</summary>
          ${c(this.result)}
        </details>`)}};u("bsm-scheduler-card",h,"BSM Scheduler","Manage backup, verification, and plugin task schedules with timezone and run history.");
