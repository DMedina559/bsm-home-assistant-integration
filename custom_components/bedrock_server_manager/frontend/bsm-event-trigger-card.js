import{b as r}from"./shared-7NSZLO6S.js";import{g as i,h as s,j as n}from"./shared-3LOQBGQY.js";var l=class extends r{static title="Plugin events";static role="manager";static key="bsm_version";static properties={eventName:{state:!0},payload:{state:!0},catalog:{state:!0},activity:{state:!0}};constructor(){super(),this.eventName="",this.payload="{}",this.catalog=[]}selectedChanged(){super.selectedChanged(),this.eventName="",this.payload="{}",this.catalog=[],this.activity=null}async loadCatalog(){let t=await this.read("list_application_events",{},!1);t&&(this.catalog=t.events||[])}async loadActivity(){let t=await this.read("get_event_activity",{limit:25,...this.eventName?{name:this.eventName}:{}},!1);t&&(this.activity=t)}async send(){try{let t=JSON.parse(this.payload||"{}");if(!t||Array.isArray(t)||typeof t!="object")throw Error("Event payload must be a JSON object.");let e=this.catalog.find(a=>a.name===this.eventName);for(let a of e?.payload_schema?.required||[])if(!(a in t))throw Error(`Event payload requires '${a}'.`);await this.action("trigger_plugin_event",{event_name:this.eventName.trim(),event_payload:t},"Plugin event delivered.")}catch(t){this.error=t.message}}render(){let t=this.catalog.find(e=>e.name===this.eventName);return this.frame(i`${this.readNotice()}
        <div class="actions">
          <button
            ?disabled=${this.loading||!this.available}
            @click=${this.loadCatalog}
          >
            Load event catalog</button
          ><button
            ?disabled=${this.loading||!this.available}
            @click=${this.loadActivity}
          >
            Load event activity
          </button>
        </div>
        ${this.catalog.length?this.selectInput("Declared custom event",this.eventName,[{value:"",label:"Choose event"},...this.catalog.filter(e=>e.phase==="custom"&&e.public).map(e=>({value:e.name,label:`${e.name} \xB7 ${e.owner}`}))],e=>this.eventName=e):""}${this.input("Event name",this.eventName,e=>this.eventName=e)}${t?i`<p>${t.description}</p>
                <details>
                  <summary>Declared payload contract</summary>
                  ${s(t.payload_schema)}
                </details>`:""}<label
          >Event payload (JSON)<textarea
            aria-label="Event payload"
            .value=${this.payload}
            ?disabled=${this.busy}
            @input=${e=>this.payload=e.target.value}
          ></textarea></label
        ><button
          ?disabled=${this.busy||this.loading||!this.available||!this.eventName.trim()}
          @click=${this.send}
        >
          Trigger event
        </button>
        <p class="muted">
          The backend validates the full event contract. Catalog and activity
          reads require administrator access.
        </p>
        ${this.activity?i`<h3>Delivery activity</h3>
                ${s(this.activity)}`:""}`)}};n("bsm-event-trigger-card",l,"BSM Plugin Event","Discover declared event contracts, trigger plugin events and inspect delivery activity.");
