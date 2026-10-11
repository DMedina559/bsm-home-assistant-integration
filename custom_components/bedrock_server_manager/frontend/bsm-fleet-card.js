import{a as r,b as i,d as c,e as a,h,i as u}from"./shared-26346ZH3.js";var l=class extends u{static title="Bedrock servers";static getConfigForm(){let t=super.getConfigForm();return t.schema=t.schema.filter(e=>e.name!=="entity"),t.schema.push({name:"entities",selector:{entity:{integration:"bedrock_server_manager",domain:"sensor",multiple:!0}}}),t}render(){let t=c(this.hass,"server","status").filter(([e])=>!this.config.entities?.length||this.config.entities.includes(e));return this.frame(r`<div class="grid">
          ${t.map(([e,s])=>{let o=this.hass.states[a(this.hass,e,"online_players_count")],m=this.hass.states[a(this.hass,e,"cpu_percent")],n=this.hass.states[a(this.hass,e,"memory_mb")];return r`<section class="tile">
              <button
                style="width:100%;text-align:left"
                @click=${()=>this.moreInfo(e)}
              >
                ${s.attributes.bsm_server_name||s.attributes.friendly_name}
              </button>
              <p>
                ${i(s)?"Unavailable":s.state} ·
                ${s.attributes.installed_version||"Version unknown"}
              </p>
              <small
                >Players ${i(o)?"\u2014":o.state} · CPU
                ${i(m)?"\u2014":`${m.state}%`} · RAM
                ${i(n)?"\u2014":`${n.state} ${n.attributes.unit_of_measurement}`}</small
              >
            </section>`})}
        </div>
        ${t.length?"":r`<p class="muted">No server status entities are available. Add servers in integration options.</p>`}`,{picker:!1})}};h("bsm-fleet-card",l,"BSM Fleet","A compact overview of selected servers with native entity details.");
