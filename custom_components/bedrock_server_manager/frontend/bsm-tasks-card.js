import{b as h,g as a,i as o,j as d,k as m}from"./shared-KAYT4IEW.js";var l=class extends m{static role="manager";static key="bsm_version";static title="Background tasks";static properties={loading:{state:!0},filter:{state:!0}};constructor(){super(),this.filter="all",this.loading=!1,this.items=new Map}selectedChanged(){this.items?.clear(),this.loading=!1,this._releaseListing?.(),this._releaseListing=null,this._loaded="",this._managerUrl=""}disconnectedCallback(){this._releaseListing?.(),this._releaseListing=null,super.disconnectedCallback()}reconnected(){if(super.reconnected(),this._releaseListing?.(),this._releaseListing=null,this._loaded="",this.loading=!1,this.runtime&&this.managerUrl())for(let e of this.runtime.tasks.values())e.manager_url===this.managerUrl()&&this.items.set(e.id,e);this.available&&this.load()}pollFailed(e){e.manager_url===this.managerUrl()&&(this.error=`Live updates interrupted: ${e.message}. Retained task data may be stale.`)}pollRecovered(e){e.manager_url===this.managerUrl()&&this.error?.startsWith("Live updates interrupted:")&&(this.error="")}syncState(){this.available&&this._loaded!==this.selection&&(this._loaded=this.selection,this.load())}managerUrl(){return this.state?.attributes.bsm_manager_url||this._managerUrl}pruneItems(){for(let e of this.items.keys())this.runtime.tasks.has(`${this.managerUrl()}:${e}`)||this.items.delete(e)}_taskUpdate(e){super._taskUpdate(e),!(!this.managerUrl()||e.manager_url!==this.managerUrl())&&(this.items.delete(e.id),this.items.set(e.id,e),this.pruneItems(),this.requestUpdate())}async load(){if(this.loading||!this.available)return;let e=this._generation;this.loading=!0;try{let s=await this.responseService("list_tasks",{});if(e!==this._generation)return;for(let i of s.managers||[])if(!(this.state?.attributes.bsm_manager_url&&i.manager_url!==this.state.attributes.bsm_manager_url)){this._managerUrl=i.manager_url;for(let t of i.tasks||[]){let r=`${i.manager_url}:${t.id}`,n=this._taskCache.get(r);n&&this.items.set(t.id,n)}}!this._releaseListing&&this.runtime&&(this._releaseListing=this.runtime.watch(this.hass,this.target,{managerUrl:this.managerUrl(),all:!0})),this.pruneItems(),this.error=""}catch(s){e===this._generation&&(this.error=s.message||String(s))}finally{e===this._generation&&(this.loading=!1,this.requestUpdate())}}render(){let e=[...this.items.values()].sort((t,r)=>Number(["completed","failed","cancelled"].includes(t.status))-Number(["completed","failed","cancelled"].includes(r.status))),s=e.filter(t=>!["completed","failed","cancelled"].includes(t.status)),i=e.filter(t=>this.filter==="all"||(this.filter==="active"?s.includes(t):t.status===this.filter));return this.frame(a`<div class="heading">
          <small>${s.length} active · ${e.length} known</small
          ><button
            ?disabled=${this.loading||!this.available}
            @click=${this.load}
          >
            Refresh tasks
          </button>
        </div>
        ${this.selectInput("Show tasks",this.filter,["all","active","completed","failed","cancelled"],t=>this.filter=t)}${i.map(t=>a`<details
              class="tile"
              ?open=${!["completed","failed","cancelled"].includes(t.status)}
            >
              <summary>
                ${h(t.status)} · ${t.message||t.id}
              </summary>
              <small>Task ${t.id}</small>${o(t)}
            </details>`)}${i.length?"":a`<p class="muted">${this.loading?"Loading tasks\u2026":"No tasks in this view."}</p>`}`)}};d("bsm-tasks-card",l,"BSM Tasks","Live task status, structured outcomes and failures with HTTP recovery.");
