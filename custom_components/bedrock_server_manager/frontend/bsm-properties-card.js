import{a as n}from"./shared-UXCKWJE4.js";import{b as s,g as i,j as l,k as o}from"./shared-66JIFLDQ.js";var h={gamemode:["survival","creative","adventure","spectator"],difficulty:["peaceful","easy","normal","hard"],"default-player-permission-level":["visitor","member","operator"]},a=class extends o{static title="Server properties";static key="level_name";static properties={raw:{state:!0}};async loadRaw(){let t=this._generation;try{let e=n(await this.responseService("get_raw_properties",{}));t===this._generation&&(this.raw=e.raw_content)}catch(e){t===this._generation&&(this.error=e.message)}}syncState(){this.available&&(this.draft.update(this.state.attributes.server_properties||{}),this.requestUpdate())}selectedChanged(){this.raw=null,this.syncState()}edit(t,e){this.draft.set(t,e),this.requestUpdate()}async save(){!this.draft.dirty||this.draft.conflicts.length||await this.action("update_properties",{properties:this.draft.changes},"Properties saved. Some changes require a restart.")&&(this.draft.reset(this.draft.live),this.requestUpdate())}render(){return this.frame(i`${this.editNotice()}
        <div class="grid">
          ${Object.entries(this.draft.value).map(([t,e])=>h[t]?this.selectInput(s(t),e,h[t],r=>this.edit(t,r)):["true","false"].includes(String(e))?this.selectInput(s(t),String(e),["true","false"],r=>this.edit(t,r)):this.input(s(t),e,r=>this.edit(t,r)))}
        </div>
        ${this.available&&!Object.keys(this.draft.value).length?i`<p>No properties are available.</p>`:""}<button
          class="primary"
          ?disabled=${!this.available||this.busy||!this.draft.dirty||this.draft.conflicts.length>0}
          @click=${this.save}
        >
          Save properties
        </button>
        <div class="actions">
          ${this.button("Validate server","validate_server",{},{message:"Server validation completed."})}<button
            ?disabled=${!this.available||this.busy}
            @click=${this.loadRaw}
          >
            View raw properties
          </button>
        </div>
        ${this.raw!=null?i`<details open>
                <summary>Raw server.properties (read only)</summary>
                <pre style="white-space:pre-wrap;overflow-wrap:anywhere">
${this.raw}</pre>
              </details>`:""}`)}};l("bsm-properties-card",a,"BSM Properties","Edit server properties with external-change protection.");
