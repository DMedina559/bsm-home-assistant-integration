import{g as o,k as u}from"./shared-3LOQBGQY.js";function d(n){let t=n.results?.[0];if(!t)throw Error("No response was returned for this target.");if(t.error){let r=Error(t.error.message);throw r.code=t.error.code,r.status=t.error.status_code,r}return t.result}var l=class extends u{static properties={loading:{state:!0},result:{state:!0},resourceState:{state:!0},loadedAt:{state:!0}};constructor(){super(),this.loading=!1,this.resourceState="not loaded"}selectedChanged(){this.loading=!1,this.result=null,this.loadedAt=null,this.resourceState="not loaded",this._request=(this._request||0)+1}reconnected(){super.reconnected(),this.loading=!1,this._request=(this._request||0)+1,this.result&&(this.resourceState="stale")}async read(t,r={},s=!0){if(this.loading||!this.available)return null;let i=this._generation,a=this._request=(this._request||0)+1;this.loading=!0,this.error="";try{let e=d(await this.responseService(t,r));return i!==this._generation||a!==this._request?null:(s&&(this.result=e),this.resourceState="current",this.loadedAt=new Date,e)}catch(e){return i===this._generation&&a===this._request&&(this.resourceState=e.code==="unsupported_operation"?"unsupported":e.status===403?"forbidden":this.result?"stale":"unavailable",this.error=e.message||String(e),this.lastError=e),null}finally{i===this._generation&&a===this._request&&(this.loading=!1)}}readButton(t,r,s={}){return o`<button
      ?disabled=${this.loading||this.busy||!this.available}
      @click=${()=>this.read(r,s)}
    >
      ${t}
    </button>`}readNotice(){return o`<p class="muted" role="status">
      ${this.loading?"Loading\u2026":`Data: ${this.resourceState}`}${this.loadedAt?` \xB7 Last loaded ${this.loadedAt.toLocaleTimeString()}`:""}.
      Details load on demand.
    </p>`}};export{d as a,l as b};
