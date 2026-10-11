import{a as i,b as o,f as n,j as r,k as c}from"./shared-5SVUCQ5X.js";var l=class extends c{static title="Install server content";static properties={source:{state:!0},file:{state:!0},uploadPath:{state:!0},canUpload:{state:!0}};static getConfigForm(){let e=super.getConfigForm();return e.schema.push({name:"content_source_sensor_entity",selector:{entity:{integration:"bedrock_server_manager",domain:"sensor"}}}),e}setConfig(e){super.setConfig(e),this.source=e.content_source_sensor_entity||""}selectedChanged(){this.file="",this.canUpload=!1,this._checked=""}syncState(){if(!this.available||this._checked===this.selection)return;this._checked=this.selection;let e=this._generation;this.responseService("discover_operations",{}).then(s=>{e===this._generation&&(this.canUpload=(s.results?.[0]?.result?.operations||[]).some(a=>a.operation_id==="upload_content"))}).catch(()=>{e===this._generation&&(this._checked="")})}render(){let e=Object.entries(this.hass?.states||{}).filter(([,t])=>t.attributes.available_worlds_list||t.attributes.available_addons_list),s=this.hass?.states[this.source],a=s?.attributes.available_worlds_list?"world":"addon",u=(s?.attributes.available_worlds_list||s?.attributes.available_addons_list||[]).map(n);return this.frame(i`${this.selectInput("Content source",this.source||"",[{value:"",label:"Select source"},...e.map(([t,h])=>({value:t,label:h.attributes.friendly_name||t}))],t=>{this.source=t,this.file=""})}${this.selectInput("File",this.file||"",[{value:"",label:"Select file"},...u],t=>this.file=t)}${s&&o(s)?i`<p class="error">The content source is unavailable.</p>`:""}<button
          ?disabled=${!this.available||this.busy||!this.file||o(s)}
          @click=${()=>this.action(`install_${a}`,{filename:this.file},"Request accepted.",{confirm:a==="world"?"Installing a world replaces this server\u2019s current world. Continue?":null})}
        >
          Install ${a}
        </button>
        ${this.button("Export world","export_world",{},{message:"Export requested."})}
        ${this.canUpload?i`<details>
                <summary>Upload from Home Assistant</summary>
                <small
                  >The file must be inside a Home Assistant allowed path.</small
                >${this.input("File path",this.uploadPath||"",t=>this.uploadPath=t)}<button
                  ?disabled=${!this.available||this.busy||!this.uploadPath}
                  @click=${()=>this.action("upload_content",{file_path:this.uploadPath},"Content uploaded.")}
                >
                  Upload content
                </button>
              </details>`:i`<small>Uploads require the content-uploader plugin.</small>`}`)}};r("bsm-content-card",l,"BSM Content","Install available worlds or addons and follow task outcomes.");customElements.get("bsm-content-installer-card")||customElements.define("bsm-content-installer-card",class extends l{});
