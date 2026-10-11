import{a as i,c as n,i as c,j as o,k as d}from"./shared-5SVUCQ5X.js";var l=class extends d{static role="manager";static key="bsm_version";static title="Background tasks";static properties={loading:{state:!0},filter:{state:!0}};constructor(){super(),this.filter="all",this.loading=!1,this.items=new Map}selectedChanged(){this.items?.clear(),this._loaded="",this._managerUrl="",clearTimeout(this._refreshTimer)}disconnectedCallback(){clearTimeout(this._refreshTimer),super.disconnectedCallback()}syncState(){this.available&&this._loaded!==this.selection&&(this._loaded=this.selection,this.load())}managerUrl(){return this.state?.attributes.bsm_manager_url||this._managerUrl}_taskUpdate(t){super._taskUpdate(t),!(this._taskCache.get(`${t.manager_url}:${t.id}`)!==t||!this.managerUrl()||t.manager_url!==this.managerUrl())&&(this.items.set(t.id,t),this.requestUpdate())}async load(){if(this.loading||!this.available)return;let t=this._generation;this.loading=!0;try{let s=await this.responseService("list_tasks",{});if(t!==this._generation)return;for(let a of s.managers||[]){this._managerUrl=a.manager_url;for(let e of a.tasks||[]){let r=`${a.manager_url}:${e.id}`;this._taskUpdate({...e,manager_url:a.manager_url});let h=this._taskCache.get(r);this.items.set(e.id,h)}}this.error=""}catch(s){t===this._generation&&(this.error=s.message||String(s))}finally{t===this._generation&&(this.loading=!1,this.requestUpdate(),clearTimeout(this._refreshTimer),this.isConnected&&(this._refreshTimer=setTimeout(()=>this.load(),5e3)))}}render(){let t=[...this.items.values()].sort((e,r)=>Number(["completed","failed","cancelled"].includes(e.status))-Number(["completed","failed","cancelled"].includes(r.status))),s=t.filter(e=>!["completed","failed","cancelled"].includes(e.status)),a=t.filter(e=>this.filter==="all"||(this.filter==="active"?s.includes(e):e.status===this.filter));return this.frame(i`<div class="heading">
          <small>${s.length} active · ${t.length} known</small
          ><button
            ?disabled=${this.loading||!this.available}
            @click=${this.load}
          >
            Refresh tasks
          </button>
        </div>
        ${this.selectInput("Show tasks",this.filter,["all","active","completed","failed","cancelled"],e=>this.filter=e)}${a.map(e=>i`<details
              class="tile"
              ?open=${!["completed","failed","cancelled"].includes(e.status)}
            >
              <summary>
                ${n(e.status)} · ${e.message||e.id}
              </summary>
              <small>Task ${e.id}</small>${c(e)}
            </details>`)}${a.length?"":i`<p class="muted">${this.loading?"Loading tasks\u2026":"No tasks in this view."}</p>`}`)}};o("bsm-tasks-card",l,"BSM Tasks","Live task status, structured outcomes and failures with HTTP recovery.");
