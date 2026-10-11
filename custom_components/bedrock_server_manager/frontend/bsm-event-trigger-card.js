import{g as a,j as i,k as r}from"./shared-7UTSRN4G.js";var t=class extends r{static title="Trigger plugin event";static role="manager";static key="bsm_version";static properties={eventName:{state:!0},payload:{state:!0}};constructor(){super(),this.eventName="",this.payload="{}"}selectedChanged(){this.eventName="",this.payload="{}"}async send(){try{let e=JSON.parse(this.payload||"{}");if(!e||Array.isArray(e)||typeof e!="object")throw Error("Event payload must be a JSON object.");await this.action("trigger_plugin_event",{event_name:this.eventName.trim(),event_payload:e},"Plugin event delivered.")}catch(e){this.error=e.message}}render(){return this.frame(a`${this.input("Event name",this.eventName,e=>this.eventName=e)}<label
          >Event payload (JSON)<textarea
            aria-label="Event payload"
            .value=${this.payload}
            ?disabled=${this.busy}
            @input=${e=>this.payload=e.target.value}
          ></textarea></label
        ><button
          ?disabled=${this.busy||!this.available||!this.eventName.trim()}
          @click=${this.send}
        >
          Trigger event
        </button>`)}};i("bsm-event-trigger-card",t,"BSM Plugin Event","Trigger plugin events using a validated object payload.");
