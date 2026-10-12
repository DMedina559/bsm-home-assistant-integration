import{a as o,e as r,g as a,j as c,k as u}from"./shared-T5QDO26S.js";var l=class extends u{static title="Install server content";static properties={source:{state:!0},file:{state:!0},uploadPath:{state:!0},canUpload:{state:!0}};static getConfigForm(){let e=super.getConfigForm();return e.schema.push({name:"content_source_sensor_entity",selector:{entity:{integration:"bedrock_server_manager",domain:"sensor"}}}),e}setConfig(e){super.setConfig(e),this.source=e.content_source_sensor_entity||""}selectedChanged(){this.file="",this.canUpload=!1,this._checked=""}reconnected(){super.reconnected(),this._checked="",this.available&&this.syncState()}syncState(){if(!this.available||this._checked===this.selection)return;this._checked=this.selection;let e=this._generation;this.responseService("discover_operations",{}).then(i=>{e===this._generation&&(this.canUpload=(i.results?.[0]?.result?.operations||[]).some(s=>s.operation_id==="upload_content"))}).catch(()=>{e===this._generation&&(this._checked="")})}render(){let e=this.state?.attributes.bsm_manager_url,i=Object.entries(this.hass?.states||{}).filter(([,t])=>e&&t.attributes.bsm_manager_url===e&&(t.attributes.available_worlds_list||t.attributes.available_addons_list)),s=i.find(([t])=>t===this.source)?.[1],n=s?.attributes.available_worlds_list?"world":"addon",h=(s?.attributes.available_worlds_list||s?.attributes.available_addons_list||[]).map(r);return this.frame(a`${this.selectInput("Content source",this.source||"",[{value:"",label:"Select source"},...i.map(([t,d])=>({value:t,label:d.attributes.friendly_name||t}))],t=>{this.source=t,this.file=""})}${this.selectInput("File",this.file||"",[{value:"",label:"Select file"},...h],t=>this.file=t)}${s&&o(s)?a`<p class="error">The content source is unavailable.</p>`:""}<button
          ?disabled=${!this.available||this.busy||!this.file||o(s)}
          @click=${()=>this.action(`install_${n}`,{filename:this.file},"Request accepted.",{confirm:n==="world"?"Installing a world replaces this server\u2019s current world. Continue?":null})}
        >
          Install ${n}
        </button>
        ${this.button("Export world","export_world",{},{message:"Export requested."})}
        ${this.canUpload?a`<details>
                <summary>Upload from Home Assistant</summary>
                <small
                  >The file must be inside a Home Assistant allowed path.</small
                >${this.input("File path",this.uploadPath||"",t=>this.uploadPath=t)}<button
                  ?disabled=${!this.available||this.busy||!this.uploadPath}
                  @click=${()=>this.action("upload_content",{file_path:this.uploadPath},"Content uploaded.")}
                >
                  Upload content
                </button>
              </details>`:a`<small>Uploads require the content-uploader plugin.</small>`}`)}};c("bsm-content-card",l,"BSM Content","Install available worlds or addons and follow task outcomes.");customElements.get("bsm-content-installer-card")||customElements.define("bsm-content-installer-card",class extends l{});
