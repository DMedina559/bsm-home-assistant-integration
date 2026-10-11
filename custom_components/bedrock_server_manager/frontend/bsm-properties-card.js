import{b as s,g as r,j as d,k as h}from"./shared-EVDKEACZ.js";var l={gamemode:["survival","creative","adventure","spectator"],difficulty:["peaceful","easy","normal","hard"],"default-player-permission-level":["visitor","member","operator"]},a=class extends h{static title="Server properties";static key="level_name";syncState(){this.available&&(this.draft.update(this.state.attributes.server_properties||{}),this.requestUpdate())}selectedChanged(){this.syncState()}edit(t,e){this.draft.set(t,e),this.requestUpdate()}async save(){!this.draft.dirty||this.draft.conflicts.length||await this.action("update_properties",{properties:this.draft.changes},"Properties saved. Some changes require a restart.")&&(this.draft.reset(this.draft.live),this.requestUpdate())}render(){return this.frame(r`${this.editNotice()}
        <div class="grid">
          ${Object.entries(this.draft.value).map(([t,e])=>l[t]?this.selectInput(s(t),e,l[t],i=>this.edit(t,i)):["true","false"].includes(String(e))?this.selectInput(s(t),String(e),["true","false"],i=>this.edit(t,i)):this.input(s(t),e,i=>this.edit(t,i)))}
        </div>
        ${this.available&&!Object.keys(this.draft.value).length?r`<p>No properties are available.</p>`:""}<button
          class="primary"
          ?disabled=${!this.available||this.busy||!this.draft.dirty||this.draft.conflicts.length>0}
          @click=${this.save}
        >
          Save properties
        </button>`)}};d("bsm-properties-card",a,"BSM Properties","Edit server properties with external-change protection.");
