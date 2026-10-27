import{g as i,h as s,j as n,k as l}from"./shared-3LOQBGQY.js";var a=class extends l{static role="manager";static key="bsm_version";static title="API operations";static properties={operations:{state:!0},operation:{state:!0},parameters:{state:!0},body:{state:!0},result:{state:!0},loading:{state:!0}};constructor(){super(),this.operations=[],this.operation="",this.parameters="{}",this.body=""}reconnected(){super.reconnected(),this.loading=!1,this.available&&this.discover()}selectedChanged(){this.loading=!1,this.operations=[],this.operation="",this.result=null,this._loaded=""}syncState(){this.available&&this._loaded!==this.selection&&(this._loaded=this.selection,this.discover())}async discover(){let e=this._generation;this.loading=!0;try{let t=await this.responseService("discover_operations",{refresh:!0});if(e!==this._generation)return;this.operations=t.results?.[0]?.result?.operations||[],this.error=""}catch(t){e===this._generation&&(this.error=t.message||String(t))}finally{e===this._generation&&(this.loading=!1)}}async invoke(){if(this.busy||!this.available)return;let e=this._generation;try{let t=JSON.parse(this.parameters),r={operation_id:this.operation,path_params:t.path_params||{},query:t.query||{}};this.body.trim()&&(r.json_data=JSON.parse(this.body));let o=this.operations.find(d=>d.operation_id===this.operation);if(o?.method.toUpperCase()!=="GET"&&!window.confirm(`Run ${o?.method} ${this.operation}?`))return;let h=await this.action("call_operation",r,"Operation completed."),p=this._lastResponse;h&&e===this._generation&&(this.result=p,this.error="")}catch(t){e===this._generation&&(this.error=t.message||String(t))}}render(){let e=this.operations.find(t=>t.operation_id===this.operation);return this.frame(i`${this.selectInput("Operation",this.operation,[{value:"",label:"Select operation"},...this.operations.map(t=>({value:t.operation_id,label:`${t.plugin?`${t.plugin} \xB7 `:""}${t.method.toUpperCase()} ${t.summary||t.operation_id}`}))],t=>{this.operation=t,this.result=null})}${e?i`<small>${e.description||e.path}</small>
                <details>
                  <summary>Request contract</summary>
                  ${s({parameters:e.parameters,request_body:e.request_body})}
                </details>`:""}<label
          >Parameters (JSON)<textarea
            aria-label="Parameters"
            .value=${this.parameters}
            @input=${t=>this.parameters=t.target.value}
          ></textarea></label
        ><label
          >Request body (JSON)<textarea
            aria-label="Request body"
            .value=${this.body}
            @input=${t=>this.body=t.target.value}
          ></textarea>
        </label>
        <div class="actions">
          <button
            ?disabled=${this.loading||this.busy||!this.available}
            @click=${this.discover}
          >
            Refresh operations</button
          ><button
            ?disabled=${this.loading||this.busy||!this.available||!this.operation}
            @click=${this.invoke}
          >
            Run operation
          </button>
        </div>
        ${this.result?s(this.result):""}`)}};n("bsm-api-card",a,"BSM API Operations","Discover and invoke authenticated core and plugin operations with SDK validation.");
