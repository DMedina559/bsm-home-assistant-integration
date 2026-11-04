import{b as u}from"./shared-7NSZLO6S.js";import{g as i,h as r,j as c}from"./shared-3LOQBGQY.js";var l=class extends u{static title="Scheduler";static role="manager";static key="bsm_version";static properties={scheduleId:{state:!0},configuration:{state:!0},options:{state:!0}};constructor(){super(),this.resetForm()}resetForm(){this.scheduleId="",this.options="{}",this.configuration={task:"backup",server_name:"",enabled:!1,time:"03:00",timezone:"",weekdays:[0,1,2,3,4,5,6],catch_up:!0,stagger_minutes:15},this._baseline=this.formSnapshot()}formSnapshot(){return JSON.stringify([this.scheduleId,this.configuration,this.options])}loadEntry(s){if(this.formSnapshot()!==this._baseline&&!window.confirm("Discard unsaved schedule changes?"))return;this.scheduleId=s.schedule_id;let{options:t,...n}=s.configuration;this.configuration={...n},this.options=JSON.stringify(t||{},null,2),this._baseline=this.formSnapshot()}selectedChanged(){super.selectedChanged(),this.resetForm()}change(s,t){this.configuration={...this.configuration,[s]:t}}async action(s,...t){let n=this._generation,e=await super.action(s,...t);return e&&n===this._generation&&["save_schedule","delete_schedule","control_schedule"].includes(s)&&await this.read("list_schedules"),e}async save(){try{let s=JSON.parse(this.options),{timezone:t,...n}=this.configuration;await this.action("save_schedule",{schedule_id:this.scheduleId,configuration:{...n,...t.trim()?{timezone:t.trim()}:{},options:s}},"Schedule saved.")&&(this._baseline=this.formSnapshot())}catch(s){this.error=s.message}}render(){let s=this.busy||this.loading||!this.available,t=this.configuration,n=this.result?.task_types?.length?this.result.task_types:["backup","verify"];return this.frame(i`${this.readNotice()}${this.readButton("Refresh schedules","list_schedules")}
        <p class="muted">
          Leave timezone blank for the application default. Leave timezone blank
          for the application default. Schedules run on the BSM host. Use an
          IANA timezone such as America/Los_Angeles; daylight saving changes
          apply automatically.
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
                        ${[["run_now","Run now"],[e.configuration.enabled?"pause":"resume",e.configuration.enabled?"Pause":"Resume"],...["failed","interrupted","deferred"].includes(e.last_status)?[["retry","Retry now"]]:[]].map(([a,o])=>i`<button ?disabled=${s||["run_now","retry"].includes(a)&&!e.available} @click=${()=>this.action("control_schedule",{schedule_id:e.schedule_id,action:a,...e.revision?{revision:e.revision}:{}},"Schedule action accepted.",{confirm:a==="run_now"||a==="retry"?`${o} for ${e.schedule_id}?`:null})}>${o}</button>`)}
                        <button
                          ?disabled=${s}
                          @click=${()=>this.loadEntry(e)}
                        >
                          Edit</button
                        ><button
                          ?disabled=${s}
                          @click=${()=>this.action("delete_schedule",{schedule_id:e.schedule_id},"Schedule deleted.",{confirm:`Delete ${e.schedule_id}?`})}
                        >
                          Delete
                        </button>
                      </div>
                      ${e.last_error?i`<p class="error">${e.last_error}</p>`:""}
                    </div>`)}`:""}
        <h3>Schedule configuration</h3>
        <fieldset ?disabled=${s}>
          <div class="grid">
            ${this.input("Schedule ID",this.scheduleId,e=>this.scheduleId=e)}${this.selectInput("Task",t.task,n,e=>this.change("task",e))}${this.input("Server name",t.server_name,e=>this.change("server_name",e))}${this.input("Time",t.time,e=>this.change("time",e),"time")}
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
            ${["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map((e,a)=>i`<label class="row"><input style="width:auto" type="checkbox" aria-label=${e} .checked=${t.weekdays.includes(a)} @change=${o=>this.change("weekdays",o.target.checked?[...t.weekdays,a].sort():t.weekdays.filter(h=>h!==a))} />${e}</label>`)}
          </div>
          <div class="row">
            ${[["enabled","Enabled"],["catch_up","Catch up after downtime"]].map(([e,a])=>i`<label class="row"
                  ><input
                    style="width:auto"
                    type="checkbox"
                    .checked=${t[e]}
                    @change=${o=>this.change(e,o.target.checked)}
                  />${a}</label
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
          ?disabled=${s||!this.scheduleId||!t.server_name||!t.weekdays.length}
          @click=${this.save}
        >
          Save schedule
        </button>
        <details>
          <summary>Run history and supported tasks</summary>
          ${r(this.result)}
        </details>`)}};c("bsm-scheduler-card",l,"BSM Scheduler","Manage backup, verification, and plugin task schedules with timezone and run history.");
