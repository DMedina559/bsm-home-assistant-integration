import{b as o}from"./shared-UXCKWJE4.js";import{g as i,j as l}from"./shared-66JIFLDQ.js";var s=class extends o{static title="Server and application logs";static key="status";static properties={application:{state:!0},text:{state:!0},limited:{state:!0}};constructor(){super(),this.application=!1,this.text=""}selectedChanged(){super.selectedChanged(),this.text="",this.limited=!1}async load(t=!1){let e=await this.read(this.application?"get_application_log_history":"get_log_history",t&&this.result?{before:this.result.start,file_id:this.result.file_id}:{});if(!e){t&&this.lastError?.status===409&&(this.result=null,this.text="",this.feedback="Log rotated; loaded the current file.",await this.load());return}let a=t?`${e.data}${this.text}`:e.data;this.limited=a.length>131072,this.text=a.slice(-131072)}render(){return this.frame(i`${this.readNotice()}${this.selectInput("Log source",this.application?"application":"server",["server","application"],t=>{this.application=t==="application",this.selectedChanged()})}
        <div class="actions">
          <button
            ?disabled=${this.loading||!this.available}
            @click=${()=>this.load()}
          >
            Load latest</button
          ><button
            ?disabled=${this.loading||!this.available||!this.result?.has_more||this.limited}
            @click=${()=>this.load(!0)}
          >
            Load older
          </button>
        </div>
        <p class="muted">
          Application logs require administrator access. Log contents are loaded
          only when requested.
        </p>
        ${this.limited?i`<p class="notice">Display limited to the latest 128 KiB of text. Reload latest to start over.</p>`:""}
        <pre
          style="white-space:pre-wrap;overflow-wrap:anywhere;max-height:32rem;overflow:auto"
        >
${this.text||"No log page loaded."}</pre>`)}};l("bsm-logs-card",s,"BSM Logs","Read bounded log pages and recover after log rotation.");
