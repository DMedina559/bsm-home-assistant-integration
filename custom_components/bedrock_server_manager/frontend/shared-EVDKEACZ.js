var E="bedrock_server_manager",y=r=>!r||["unavailable","unknown"].includes(r.state),k=r=>structuredClone(r),V=(r,t)=>JSON.stringify(r)===JSON.stringify(t),g=r=>r.replace(/[_-]/g," ").replace(/^./,t=>t.toUpperCase()),z=class{constructor(){this.reset({})}reset(t){this.base=k(t),this.live=k(t),this.changes={}}update(t){this.live=k(t),this.dirty||(this.base=k(t))}set(t,e){V(e,this.base[t])?delete this.changes[t]:this.changes[t]=e}get dirty(){return Object.keys(this.changes).length>0}get conflicts(){return Object.keys(this.changes).filter(t=>!V(this.live[t],this.base[t])&&!V(this.live[t],this.changes[t]))}get value(){return{...this.live,...this.changes}}};function ct(r,t){return r?.states?.[t]?.attributes?.bsm_key}function ht(r,t){return r?.entities?.[t]?.device_id||r?.states?.[t]?.attributes?.device_id}function O(r,t,e){return Object.entries(r?.states||{}).filter(([s,i])=>i.attributes?.bsm_role===t&&(!e||ct(r,s)===e)).sort(([s],[i])=>s.localeCompare(i))}function M(r,t,e){let s=ht(r,t);return Object.entries(r?.states||{}).find(([i])=>ct(r,i)===e&&s&&ht(r,i)===s)?.[0]}function dt(r){return r.error?.message||r.error?.detail||r.message||"The operation failed."}function Gt(r){return typeof r=="string"?r:r.filename||r.name}function Kt(r,t){if(t.enum)return t.enum.find(e=>String(e)===String(r));if(["number","integer"].includes(t.type)){if(r===""||r===null||r===void 0||!Number.isFinite(Number(r)))throw Error("Enter a valid number.");let e=Number(r);if(t.type==="integer"&&!Number.isInteger(e))throw Error("Enter a whole number.");if(t.minimum!=null&&e<t.minimum)throw Error(`Minimum is ${t.minimum}.`);if(t.maximum!=null&&e>t.maximum)throw Error(`Maximum is ${t.maximum}.`);if(t.exclusiveMinimum!=null&&e<=t.exclusiveMinimum)throw Error(`Must exceed ${t.exclusiveMinimum}.`);if(t.exclusiveMaximum!=null&&e>=t.exclusiveMaximum)throw Error(`Must be less than ${t.exclusiveMaximum}.`);return e}return["object","array"].includes(t.type)&&typeof r=="string"?JSON.parse(r):r}var X=globalThis,ut=r=>r,L=X.trustedTypes,pt=L?L.createPolicy("lit-html",{createHTML:r=>r}):void 0,$t="$lit$",b=`lit$${Math.random().toFixed(9).slice(2)}$`,yt="?"+b,Rt=`<${yt}>`,A=document,N=()=>A.createComment(""),P=r=>r===null||typeof r!="object"&&typeof r!="function",Y=Array.isArray,Ht=r=>Y(r)||typeof r?.[Symbol.iterator]=="function",F=`[ 	
\f\r]`,U=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,ft=/-->/g,mt=/>/g,v=RegExp(`>|${F}(?:([^\\s"'>=/]+)(${F}*=${F}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),gt=/'/g,_t=/"/g,vt=/^(?:script|style|textarea|title)$/i,tt=r=>(t,...e)=>({_$litType$:r,strings:t,values:e}),c=tt(1),Qt=tt(2),Xt=tt(3),x=Symbol.for("lit-noChange"),h=Symbol.for("lit-nothing"),bt=new WeakMap,w=A.createTreeWalker(A,129);function wt(r,t){if(!Y(r)||!r.hasOwnProperty("raw"))throw Error("invalid template strings array");return pt!==void 0?pt.createHTML(t):t}var jt=(r,t)=>{let e=r.length-1,s=[],i,n=t===2?"<svg>":t===3?"<math>":"",o=U;for(let l=0;l<e;l++){let a=r[l],u,p,d=-1,m=0;for(;m<a.length&&(o.lastIndex=m,p=o.exec(a),p!==null);)m=o.lastIndex,o===U?p[1]==="!--"?o=ft:p[1]!==void 0?o=mt:p[2]!==void 0?(vt.test(p[2])&&(i=RegExp("</"+p[2],"g")),o=v):p[3]!==void 0&&(o=v):o===v?p[0]===">"?(o=i??U,d=-1):p[1]===void 0?d=-2:(d=o.lastIndex-p[2].length,u=p[1],o=p[3]===void 0?v:p[3]==='"'?_t:gt):o===_t||o===gt?o=v:o===ft||o===mt?o=U:(o=v,i=void 0);let f=o===v&&r[l+1].startsWith("/>")?" ":"";n+=o===U?a+Rt:d>=0?(s.push(u),a.slice(0,d)+$t+a.slice(d)+b+f):a+b+(d===-2?l:f)}return[wt(r,n+(r[e]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),s]},R=class r{constructor({strings:t,_$litType$:e},s){let i;this.parts=[];let n=0,o=0,l=t.length-1,a=this.parts,[u,p]=jt(t,e);if(this.el=r.createElement(u,s),w.currentNode=this.el.content,e===2||e===3){let d=this.el.content.firstChild;d.replaceWith(...d.childNodes)}for(;(i=w.nextNode())!==null&&a.length<l;){if(i.nodeType===1){if(i.hasAttributes())for(let d of i.getAttributeNames())if(d.endsWith($t)){let m=p[o++],f=i.getAttribute(d).split(b),S=/([.?@])?(.*)/.exec(m);a.push({type:1,index:n,name:S[2],strings:f,ctor:S[1]==="."?G:S[1]==="?"?K:S[1]==="@"?Z:T}),i.removeAttribute(d)}else d.startsWith(b)&&(a.push({type:6,index:n}),i.removeAttribute(d));if(vt.test(i.tagName)){let d=i.textContent.split(b),m=d.length-1;if(m>0){i.textContent=L?L.emptyScript:"";for(let f=0;f<m;f++)i.append(d[f],N()),w.nextNode(),a.push({type:2,index:++n});i.append(d[m],N())}}}else if(i.nodeType===8)if(i.data===yt)a.push({type:2,index:n});else{let d=-1;for(;(d=i.data.indexOf(b,d+1))!==-1;)a.push({type:7,index:n}),d+=b.length-1}n++}}static createElement(t,e){let s=A.createElement("template");return s.innerHTML=t,s}};function C(r,t,e=r,s){if(t===x)return t;let i=s!==void 0?e._$Co?.[s]:e._$Cl,n=P(t)?void 0:t._$litDirective$;return i?.constructor!==n&&(i?._$AO?.(!1),n===void 0?i=void 0:(i=new n(r),i._$AT(r,e,s)),s!==void 0?(e._$Co??=[])[s]=i:e._$Cl=i),i!==void 0&&(t=C(r,i._$AS(r,t.values),i,s)),t}var J=class{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){let{el:{content:e},parts:s}=this._$AD,i=(t?.creationScope??A).importNode(e,!0);w.currentNode=i;let n=w.nextNode(),o=0,l=0,a=s[0];for(;a!==void 0;){if(o===a.index){let u;a.type===2?u=new H(n,n.nextSibling,this,t):a.type===1?u=new a.ctor(n,a.name,a.strings,this,t):a.type===6&&(u=new Q(n,this,t)),this._$AV.push(u),a=s[++l]}o!==a?.index&&(n=w.nextNode(),o++)}return w.currentNode=A,i}p(t){let e=0;for(let s of this._$AV)s!==void 0&&(s.strings!==void 0?(s._$AI(t,s,e),e+=s.strings.length-2):s._$AI(t[e])),e++}},H=class r{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,s,i){this.type=2,this._$AH=h,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=s,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode,e=this._$AM;return e!==void 0&&t?.nodeType===11&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=C(this,t,e),P(t)?t===h||t==null||t===""?(this._$AH!==h&&this._$AR(),this._$AH=h):t!==this._$AH&&t!==x&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):Ht(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==h&&P(this._$AH)?this._$AA.nextSibling.data=t:this.T(A.createTextNode(t)),this._$AH=t}$(t){let{values:e,_$litType$:s}=t,i=typeof s=="number"?this._$AC(t):(s.el===void 0&&(s.el=R.createElement(wt(s.h,s.h[0]),this.options)),s);if(this._$AH?._$AD===i)this._$AH.p(e);else{let n=new J(i,this),o=n.u(this.options);n.p(e),this.T(o),this._$AH=n}}_$AC(t){let e=bt.get(t.strings);return e===void 0&&bt.set(t.strings,e=new R(t)),e}k(t){Y(this._$AH)||(this._$AH=[],this._$AR());let e=this._$AH,s,i=0;for(let n of t)i===e.length?e.push(s=new r(this.O(N()),this.O(N()),this,this.options)):s=e[i],s._$AI(n),i++;i<e.length&&(this._$AR(s&&s._$AB.nextSibling,i),e.length=i)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){let s=ut(t).nextSibling;ut(t).remove(),t=s}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},T=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,s,i,n){this.type=1,this._$AH=h,this._$AN=void 0,this.element=t,this.name=e,this._$AM=i,this.options=n,s.length>2||s[0]!==""||s[1]!==""?(this._$AH=Array(s.length-1).fill(new String),this.strings=s):this._$AH=h}_$AI(t,e=this,s,i){let n=this.strings,o=!1;if(n===void 0)t=C(this,t,e,0),o=!P(t)||t!==this._$AH&&t!==x,o&&(this._$AH=t);else{let l=t,a,u;for(t=n[0],a=0;a<n.length-1;a++)u=C(this,l[s+a],e,a),u===x&&(u=this._$AH[a]),o||=!P(u)||u!==this._$AH[a],u===h?t=h:t!==h&&(t+=(u??"")+n[a+1]),this._$AH[a]=u}o&&!i&&this.j(t)}j(t){t===h?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},G=class extends T{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===h?void 0:t}},K=class extends T{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==h)}},Z=class extends T{constructor(t,e,s,i,n){super(t,e,s,i,n),this.type=5}_$AI(t,e=this){if((t=C(this,t,e,0)??h)===x)return;let s=this._$AH,i=t===h&&s!==h||t.capture!==s.capture||t.once!==s.once||t.passive!==s.passive,n=t!==h&&(s===h||i);i&&this.element.removeEventListener(this.name,this,s),n&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},Q=class{constructor(t,e,s){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=s}get _$AU(){return this._$AM._$AU}_$AI(t){C(this,t)}};var qt=X.litHtmlPolyfillSupport;qt?.(R,H),(X.litHtmlVersions??=[]).push("3.3.3");var At=(r,t,e)=>{let s=e?.renderBefore??t,i=s._$litPart$;if(i===void 0){let n=e?.renderBefore??null;s._$litPart$=i=new H(t.insertBefore(N(),n),n,void 0,e??{})}return i._$AI(r),i};var D=globalThis,W=D.ShadowRoot&&(D.ShadyCSS===void 0||D.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,et=Symbol(),xt=new WeakMap,j=class{constructor(t,e,s){if(this._$cssResult$=!0,s!==et)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o,e=this.t;if(W&&t===void 0){let s=e!==void 0&&e.length===1;s&&(t=xt.get(e)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),s&&xt.set(e,t))}return t}toString(){return this.cssText}},St=r=>new j(typeof r=="string"?r:r+"",void 0,et),st=(r,...t)=>{let e=r.length===1?r[0]:t.reduce((s,i,n)=>s+(o=>{if(o._$cssResult$===!0)return o.cssText;if(typeof o=="number")return o;throw Error("Value passed to 'css' function must be a 'css' function result: "+o+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+r[n+1],r[0]);return new j(e,r,et)},kt=(r,t)=>{if(W)r.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let e of t){let s=document.createElement("style"),i=D.litNonce;i!==void 0&&s.setAttribute("nonce",i),s.textContent=e.cssText,r.appendChild(s)}},it=W?r=>r:r=>r instanceof CSSStyleSheet?(t=>{let e="";for(let s of t.cssRules)e+=s.cssText;return St(e)})(r):r;var{is:zt,defineProperty:Lt,getOwnPropertyDescriptor:Dt,getOwnPropertyNames:Wt,getOwnPropertySymbols:It,getPrototypeOf:Bt}=Object,I=globalThis,Et=I.trustedTypes,Vt=Et?Et.emptyScript:"",Ft=I.reactiveElementPolyfillSupport,q=(r,t)=>r,rt={toAttribute(r,t){switch(t){case Boolean:r=r?Vt:null;break;case Object:case Array:r=r==null?r:JSON.stringify(r)}return r},fromAttribute(r,t){let e=r;switch(t){case Boolean:e=r!==null;break;case Number:e=r===null?null:Number(r);break;case Object:case Array:try{e=JSON.parse(r)}catch{e=null}}return e}},Tt=(r,t)=>!zt(r,t),Ct={attribute:!0,type:String,converter:rt,reflect:!1,useDefault:!1,hasChanged:Tt};Symbol.metadata??=Symbol("metadata"),I.litPropertyMetadata??=new WeakMap;var _=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=Ct){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){let s=Symbol(),i=this.getPropertyDescriptor(t,s,e);i!==void 0&&Lt(this.prototype,t,i)}}static getPropertyDescriptor(t,e,s){let{get:i,set:n}=Dt(this.prototype,t)??{get(){return this[e]},set(o){this[e]=o}};return{get:i,set(o){let l=i?.call(this);n?.call(this,o),this.requestUpdate(t,l,s)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??Ct}static _$Ei(){if(this.hasOwnProperty(q("elementProperties")))return;let t=Bt(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(q("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(q("properties"))){let e=this.properties,s=[...Wt(e),...It(e)];for(let i of s)this.createProperty(i,e[i])}let t=this[Symbol.metadata];if(t!==null){let e=litPropertyMetadata.get(t);if(e!==void 0)for(let[s,i]of e)this.elementProperties.set(s,i)}this._$Eh=new Map;for(let[e,s]of this.elementProperties){let i=this._$Eu(e,s);i!==void 0&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){let e=[];if(Array.isArray(t)){let s=new Set(t.flat(1/0).reverse());for(let i of s)e.unshift(it(i))}else t!==void 0&&e.push(it(t));return e}static _$Eu(t,e){let s=e.attribute;return s===!1?void 0:typeof s=="string"?s:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){let t=new Map,e=this.constructor.elementProperties;for(let s of e.keys())this.hasOwnProperty(s)&&(t.set(s,this[s]),delete this[s]);t.size>0&&(this._$Ep=t)}createRenderRoot(){let t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return kt(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,s){this._$AK(t,s)}_$ET(t,e){let s=this.constructor.elementProperties.get(t),i=this.constructor._$Eu(t,s);if(i!==void 0&&s.reflect===!0){let n=(s.converter?.toAttribute!==void 0?s.converter:rt).toAttribute(e,s.type);this._$Em=t,n==null?this.removeAttribute(i):this.setAttribute(i,n),this._$Em=null}}_$AK(t,e){let s=this.constructor,i=s._$Eh.get(t);if(i!==void 0&&this._$Em!==i){let n=s.getPropertyOptions(i),o=typeof n.converter=="function"?{fromAttribute:n.converter}:n.converter?.fromAttribute!==void 0?n.converter:rt;this._$Em=i;let l=o.fromAttribute(e,n.type);this[i]=l??this._$Ej?.get(i)??l,this._$Em=null}}requestUpdate(t,e,s,i=!1,n){if(t!==void 0){let o=this.constructor;if(i===!1&&(n=this[t]),s??=o.getPropertyOptions(t),!((s.hasChanged??Tt)(n,e)||s.useDefault&&s.reflect&&n===this._$Ej?.get(t)&&!this.hasAttribute(o._$Eu(t,s))))return;this.C(t,e,s)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,e,{useDefault:s,reflect:i,wrapped:n},o){s&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,o??e??this[t]),n!==!0||o!==void 0)||(this._$AL.has(t)||(this.hasUpdated||s||(e=void 0),this._$AL.set(t,e)),i===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[i,n]of this._$Ep)this[i]=n;this._$Ep=void 0}let s=this.constructor.elementProperties;if(s.size>0)for(let[i,n]of s){let{wrapped:o}=n,l=this[i];o!==!0||this._$AL.has(i)||l===void 0||this.C(i,void 0,n,l)}}let t=!1,e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(s=>s.hostUpdate?.()),this.update(e)):this._$EM()}catch(s){throw t=!1,this._$EM(),s}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(t){}firstUpdated(t){}};_.elementStyles=[],_.shadowRootOptions={mode:"open"},_[q("elementProperties")]=new Map,_[q("finalized")]=new Map,Ft?.({ReactiveElement:_}),(I.reactiveElementVersions??=[]).push("2.1.2");var nt=globalThis,$=class extends _{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){let e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=At(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return x}};$._$litElement$=!0,$.finalized=!0,nt.litElementHydrateSupport?.({LitElement:$});var Jt=nt.litElementPolyfillSupport;Jt?.({LitElement:$});(nt.litElementVersions??=[]).push("4.2.2");function B(r){return r==null?c`<span class="muted">None</span>`:Array.isArray(r)?c`<ul>
      ${r.map(t=>c`<li>${B(t)}</li>`)}
    </ul>`:typeof r=="object"?c`<dl>
      ${Object.entries(r).map(([t,e])=>c`<dt>${g(t)}</dt>
            <dd style="margin:0 0 8px;overflow-wrap:anywhere">
              ${B(e)}
            </dd>`)}
    </dl>`:c`<span style="overflow-wrap:anywhere">${String(r)}</span>`}function Ot(r){return c`${r.error?c`<div class="error" role="alert">${B(r.error)}</div>`:h}${r.result!=null?c`<h4>Outcome</h4>
            ${B(r.result)}`:h}
    <details>
      <summary>Raw response</summary>
      <pre style="white-space:pre-wrap;overflow-wrap:anywhere">
${JSON.stringify(r,null,2)}</pre>
    </details>`}var ot=new WeakMap,at=r=>["completed","failed","cancelled"].includes(r.status),Mt=r=>JSON.stringify(r,(t,e)=>e&&typeof e=="object"&&!Array.isArray(e)?Object.fromEntries(Object.entries(e).sort(([s],[i])=>s.localeCompare(i))):e);function Ut(r){let t=r.connection;return ot.has(t)||ot.set(t,new lt(t)),ot.get(t)}var lt=class{constructor(t){this.connection=t,this.owners=new Set,this.tasks=new Map,this.retired=new Map,this.inflight=new Map,this.groups=new Map,this.generation=0,this.requestGeneration=0,this.ready=()=>{this.requestGeneration++,this.inflight.clear(),this.emit("reconnect",{});for(let e of this.groups.values())this.poll(e)},this.visible=()=>{for(let e of this.groups.values())clearTimeout(e.timer),document.hidden||this.poll(e)}}acquire(t){return this.owners.add(t),this.owners.size===1&&this.start(),()=>{this.owners.delete(t),this.owners.size||this.stop()}}start(){let t=++this.generation;this.unsubscribers=[];for(let[e,s]of[["task",`${E}_task_update`],["event",`${E}_event`]])this.connection.subscribeEvents(i=>{t===this.generation&&(e==="task"?this.accept(i.data):this.emit(e,i.data))},s).then(i=>{t!==this.generation?i():this.unsubscribers.push(i)}).catch(()=>{t===this.generation&&this.emit("subscription_error",{})});this.connection.addEventListener?.("ready",this.ready),document.addEventListener("visibilitychange",this.visible)}stop(){this.generation++,this.requestGeneration++;for(let t of this.unsubscribers||[])t();this.unsubscribers=[],this.connection.removeEventListener?.("ready",this.ready),document.removeEventListener("visibilitychange",this.visible);for(let t of this.groups.values())clearTimeout(t.timer);this.groups.clear(),this.inflight.clear()}emit(t,e){for(let s of this.owners)s(t,e)}accept(t){if(!t||typeof t.id!="string"||typeof t.manager_url!="string"||!["queued","running","cancelling","completed","failed","cancelled"].includes(t.status))return;let e=`${t.manager_url}:${t.id}`,s=this.tasks.get(e),i=t.epoch!=null||t.revision!=null;if(i&&(typeof t.epoch!="string"||!t.epoch.trim()||!Number.isSafeInteger(t.revision)||t.revision<1)||s?.epoch&&!i)return;let n=this.retired.get(e)||new Set;if(!(n.has(t.epoch)||s?.epoch===t.epoch&&s?.revision>=t.revision)&&(s?.epoch&&t.epoch&&s.epoch!==t.epoch&&n.add(s.epoch),!(!i&&s&&at(s)&&!at(t)))){if(this.retired.set(e,n),this.tasks.set(e,t),this.tasks.size>500){let o=this.tasks.keys().next().value;this.tasks.delete(o),this.retired.delete(o)}this.emit("task",t)}}async request(t,e,s,i){let n=e.startsWith("get_")||e==="list_tasks"||e==="discover_operations",o=new Set(["get_application_settings","get_plugin_settings","get_task","list_tasks","discover_operations"]),l=typeof i.entity_id=="string"?t.states?.[i.entity_id]?.attributes?.bsm_manager_url:null,a=Mt([e,s,o.has(e)&&l?l:i]);if(n&&this.inflight.has(a))return this.inflight.get(a);let u=this.requestGeneration,p=t.callWS({type:"call_service",domain:E,service:e,service_data:s,target:i,return_response:!0}).then(d=>{if(u!==this.requestGeneration)throw Error("Connection changed; current data is being reloaded.");let m=d.response||{};if(e==="list_tasks"||e==="get_task")for(let f of m.managers||[])for(let S of f.task?[f.task]:f.tasks||[])this.accept({...S,manager_url:f.manager_url});return m});n&&this.inflight.set(a,p);try{return await p}finally{this.inflight.get(a)===p&&this.inflight.delete(a)}}watch(t,e,{managerUrl:s,taskId:i,all:n=!1}={}){let o=s||Mt(e),l=this.groups.get(o);l||(l={key:o,hass:t,target:e,watches:new Set,loading:!1},this.groups.set(o,l));let a={taskId:i,all:n};return l.watches.add(a),l.hass=t,!l.timer&&!l.loading&&(l.timer=setTimeout(()=>this.poll(l),1e3)),()=>{l.watches.delete(a)&&(l.watches.size||(clearTimeout(l.timer),this.groups.get(o)===l&&this.groups.delete(o)))}}async poll(t){if(!(t.loading||document.hidden||this.groups.get(t.key)!==t)){clearTimeout(t.timer),t.loading=!0;try{[...t.watches].some(s=>s.all)&&await this.request(t.hass,"list_tasks",{},t.target);let e=new Set([...t.watches].map(s=>s.taskId).filter(Boolean));for(let s of e){let i=this.tasks.get(`${t.key}:${s}`);(!i||!at(i))&&await this.request(t.hass,"get_task",{task_id:s},t.target)}this.emit("poll_ok",{manager_url:t.key})}catch(e){this.emit("poll_error",{manager_url:t.key,message:e.message||String(e)})}finally{t.loading=!1,this.groups.get(t.key)===t&&!document.hidden&&(t.timer=setTimeout(()=>this.poll(t),5e3))}}}};var Nt=st`
  :host {
    display: block;
    min-width: 0;
    color: var(--primary-text-color);
  }
  ha-card {
    min-width: 0;
    box-sizing: border-box;
    overflow: hidden;
  }
  .body {
    padding: 16px;
    display: grid;
    gap: 12px;
    min-width: 0;
    grid-template-columns: minmax(0, 1fr);
  }
  h2 {
    font-size: 1.1rem;
    font-weight: 500;
    margin: 0;
  }
  h3 {
    font-size: 0.95rem;
    margin: 4px 0;
  }
  .row,
  .actions,
  .heading {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .heading {
    justify-content: space-between;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(160px, 100%), 1fr));
    gap: 12px;
  }
  .tile {
    border: 1px solid var(--divider-color);
    border-radius: var(--ha-card-border-radius, 12px);
    padding: 12px;
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .muted,
  small {
    color: var(--secondary-text-color);
  }
  .error {
    color: var(--error-color, #db4437);
  }
  .notice {
    padding: 10px;
    border-radius: 8px;
    background: var(--secondary-background-color);
  }
  .value {
    font-size: 1.25rem;
    font-weight: 500;
  }
  label {
    display: grid;
    gap: 5px;
    font-size: 0.9rem;
  }
  input,
  textarea,
  select,
  button {
    font: inherit;
    color: inherit;
    box-sizing: border-box;
  }
  input,
  textarea,
  select {
    width: 100%;
    min-width: 0;
    max-width: 100%;
    background: var(--card-background-color);
    border: 1px solid var(--divider-color);
    border-radius: 6px;
    padding: 10px;
  }
  textarea {
    min-height: 85px;
    resize: vertical;
  }
  button {
    background: var(--secondary-background-color);
    border: 1px solid var(--divider-color);
    border-radius: 8px;
    min-height: 40px;
    padding: 8px 12px;
    cursor: pointer;
  }
  button.primary {
    background: var(--primary-color);
    color: var(--text-primary-color, #fff);
    border-color: transparent;
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  button:focus-visible,
  input:focus-visible,
  textarea:focus-visible,
  select:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
  .scroll {
    overflow-x: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    text-align: left;
  }
  th,
  td {
    padding: 8px;
    border-bottom: 1px solid var(--divider-color);
  }
  th {
    font-size: 0.85rem;
    color: var(--secondary-text-color);
  }
  fieldset {
    border: 1px solid var(--divider-color);
    border-radius: 8px;
    margin: 0;
    padding: 8px 12px;
  }
  legend {
    padding: 0 4px;
  }
  ha-selector {
    display: block;
  }
  .tabs button[aria-selected="true"] {
    border-color: var(--primary-color);
    color: var(--primary-color);
  }
  .confirm {
    border: 1px solid var(--error-color);
    padding: 12px;
    border-radius: 8px;
  }
  @media (max-width: 450px) {
    .body {
      padding: 12px;
    }
    .grid {
      grid-template-columns: 1fr;
    }
  }
`;function Ee(r,t,e,s){customElements.get(r)||customElements.define(r,t),window.customCards||=[],window.customCards.some(i=>i.type===r)||window.customCards.push({type:r,name:e,description:s,preview:!0})}var Pt=class extends ${static properties={hass:{attribute:!1},config:{state:!0},selection:{state:!0},busy:{state:!0},error:{state:!0},feedback:{state:!0},confirmation:{state:!0},revision:{state:!0}};static styles=Nt;static role="server";static key="status";static title="Bedrock Server Manager";static getConfigForm(){return{schema:[{name:"title",selector:{text:{}}},{name:"entity",selector:{entity:{integration:E}}},{name:"debug",selector:{boolean:{}}}],computeLabel:t=>t.name==="entity"?`Default ${this.role}`:g(t.name)}}static getStubConfig(t){return{entity:O(t,this.role,this.key)[0]?.[0]}}constructor(){super(),this.draft=new z,this.selection="",this.busy=!1,this.error="",this.feedback="",this.revision=0,this._generation=0,this._taskCache=new Map,this._tasks=new Map}setConfig(t){if(!t||typeof t!="object")throw Error("A card configuration is required.");if(t.history_hours!=null&&(!Number.isInteger(t.history_hours)||t.history_hours<1||t.history_hours>168))throw Error("History hours must be a whole number from 1 to 168.");this.config={...t};let e=t.entity||t.manager_entity||t.target_server_sensor_entity||t.target_device||"";e!==this.selection&&this.select(e)}getCardSize(){return 4}getGridOptions(){return{columns:12,min_columns:6,rows:"auto"}}get state(){return this.hass?.states?.[this.selection]}get available(){return this.hass?.connected!==!1&&!y(this.state)}get target(){return this.selection.includes(".")?{entity_id:this.selection}:{device_id:this.selection}}stateFor(t){let e=M(this.hass,this.selection,t);return this.hass?.states?.[e]}select(t){this._generation++,this.selection=t||"",this.error="",this.feedback="",this.busy=!1,this.confirmation=null,this.draft.reset({}),this._tasks.clear(),this._releaseTaskWatchers(),this.selectedChanged()}selectedChanged(){}connectedCallback(){super.connectedCallback(),this._subscribeTasks()}disconnectedCallback(){super.disconnectedCallback(),this._generation++,this._releaseRuntime?.(),this._releaseRuntime=null,this._connection=null,this._releaseTaskWatchers(),this._tasks.clear()}updated(t){t.has("hass")&&(this.normalizeSelection(),this._subscribeTasks(),this.syncState())}normalizeSelection(){if(!this.selection)return;let t;if(this.selection.includes(".")){if(this.state?.attributes.bsm_key===this.constructor.key)return;t=M(this.hass,this.selection,this.constructor.key)}else t=O(this.hass,this.constructor.role,this.constructor.key).find(([e])=>this.hass.entities?.[e]?.device_id===this.selection)?.[0];t&&t!==this.selection&&this.select(t)}knownPlayers(){let t=this.hass?.entities?.[this.selection]?.device_id,e=this.hass?.devices?.[t]?.via_device_id,s=this.config.global_players_entity||this.config.global_players_sensor_entity||this.config.global_player_sensor_entity;return s?this.hass.states[s]?.attributes.global_players_list||[]:O(this.hass,"manager","global_players_count").find(([n])=>this.hass.entities?.[n]?.device_id===e)?.[1].attributes.global_players_list||[]}taskOutcomes(){return c`${[...this._tasks.values()].filter(({task:t})=>["completed","failed","cancelled"].includes(t.status)&&(t.result!=null||t.error)).map(({task:t})=>c`<details class="tile">
            <summary>${g(t.status)} outcome · ${t.id}</summary>
            ${Ot(t)}
          </details>`)}`}syncState(){}_releaseTaskWatchers(){for(let t of this._taskWatchers||[])t();this._taskWatchers=[]}_subscribeTasks(){let t=this.hass?.connection;if(!(!this.isConnected||!t||this._connection===t)){if(this._connection&&this._connection!==t){this._generation++;for(let e of this._tasks.values())e.generation=this._generation}this._releaseRuntime?.(),this._releaseTaskWatchers(),this._connection=t,this.runtime=Ut(this.hass),this._taskCache=this.runtime.tasks,this._releaseRuntime=this.runtime.acquire((e,s)=>{if(e==="task")this._taskUpdate(s);else if(e==="event")this._eventUpdate(s);else if(e==="reconnect"){this._generation++,this._releaseTaskWatchers();for(let i of this._tasks.values())i.generation=this._generation;this.reconnected()}else e==="poll_error"?this.pollFailed(s):e==="poll_ok"&&this.pollRecovered(s)}),this.reconnected()}}_eventUpdate(){}reconnected(){for(let t of this._tasks.values())["completed","failed","cancelled"].includes(t.task.status)||this._watchTask(t)}pollFailed(){}pollRecovered(){}_watchTask(t){this._taskWatchers||=[],this._taskWatchers.push(this.runtime.watch(this.hass,t.target,{managerUrl:t.task.manager_url,taskId:t.task.id}))}_taskUpdate(t){let e=this._tasks.get(`${t.manager_url}:${t.id}`);!e||e.generation!==this._generation||(e.task=t,this._showTasks())}_showTasks(){let t=[...this._tasks.values()].map(s=>s.task),e=t.find(s=>["failed","cancelled"].includes(s.status));this.error=e?dt(e):"",this.busy=t.some(s=>!["completed","failed","cancelled"].includes(s.status)),this.feedback=t.map(s=>`${g(s.status)}: ${s.message||s.id}`).join(" \xB7 "),this.busy||this._releaseTaskWatchers(),this.requestUpdate()}async responseService(t,e,s=this.target){return this._subscribeTasks(),this.runtime.request(this.hass,t,e,s)}async action(t,e={},s="Changes saved.",i={}){if(this.busy||!i.allowUnavailable&&!this.available)return!1;if(i.confirm&&!i.confirmed)return this.confirmation={service:t,data:k(e),message:s,options:i,target:this.selection},!1;let n=this._generation,o={...this.target};this.busy=!0,this.error="",this.feedback="Sending request\u2026",this._tasks.clear(),this._releaseTaskWatchers();try{let l=await this.responseService(t,e,o);if(n!==this._generation)return!1;this._lastResponse=l;for(let a of l.results||[]){let u=a.result?.task_id;if(!u)continue;let p=`${a.manager_url}:${u}`;this._tasks.set(p,{generation:n,target:o,task:this._taskCache.get(p)||{id:u,manager_url:a.manager_url,status:"queued",message:"Waiting for task outcome"}})}if(this._tasks.size){if(this._showTasks(),this.busy)for(let a of this._tasks.values())this._watchTask(a)}else this.busy=!1,this.feedback=(l.results||[]).map(({result:a})=>a?.status==="skipped"?`Skipped: ${a.message||"No change required."}`:a?.message).filter(Boolean).join(" \xB7 ")||s;return this.config.debug&&console.debug("BSM action",t,"acknowledged"),!0}catch(l){return n!==this._generation||(this.error=l.message||String(l),this.feedback="",this.busy=!1),!1}}moreInfo(t){this.dispatchEvent(new CustomEvent("hass-more-info",{detail:{entityId:t},bubbles:!0,composed:!0}))}async nativeAction(t,e,s,i={}){if(this.busy||y(this.hass?.states?.[s]))return!1;let n=this._generation;this.busy=!0,this.error="";try{return await this.hass.callService(t,e,i,{entity_id:s}),n!==this._generation?!1:(this.feedback="Request sent. State updates when confirmed by the server.",!0)}catch(o){return n===this._generation&&(this.error=o.message||String(o)),!1}finally{n===this._generation&&(this.busy=!1)}}resourceNotice(t=this.state){let e=t?.attributes.bsm_resource_state;return e==="unsupported"?c`<small class="muted"
        >This backend does not support this resource.</small
      >`:e==="stale"?c`<small class="muted"
        >Retained data may be
        stale${t.attributes.bsm_updated_at?` \xB7 last received ${new Date(t.attributes.bsm_updated_at*1e3).toLocaleString()}`:""}.</small
      >`:h}metric(t){if(!t)return h;let e=t.entity_id,s=t.attributes.friendly_name||e,i=t.state;return t.attributes.device_class==="connectivity"&&(i=t.state==="on"?"Connected":"Unavailable"),t.attributes.device_class==="problem"&&(i=t.state==="on"?"Problem":"Healthy"),t.attributes.bsm_key==="websocket"&&(i=t.state==="on"?"Live":"Offline"),c`<button
      class="tile"
      style="text-align:left"
      @click=${()=>this.moreInfo(e)}
    >
      <small>${s}</small>
      <div class="value">
        ${y(t)?"Unavailable":i}
        ${t.attributes.unit_of_measurement||""}
      </div>
      ${this.resourceNotice(t)}
      ${t.attributes.message?c`<small>${t.attributes.message}</small>`:h}
    </button>`}entityControl(t){let e=M(this.hass,this.selection,t),s=this.hass?.states?.[e];return s?e.startsWith("switch.")?c`<div class="heading">
        <span>${s.attributes.friendly_name}</span
        ><button
          ?disabled=${this.busy||y(s)}
          @click=${()=>this.nativeAction("switch",s.state==="on"?"turn_off":"turn_on",e)}
        >
          ${s.state==="on"?"Disable":"Enable"}
        </button>
      </div>`:c`<label
      >${s.attributes.friendly_name}<input
        aria-label=${s.attributes.friendly_name}
        .value=${y(s)?"":s.state}
        ?disabled=${this.busy||y(s)}
        @change=${i=>this.nativeAction("text","set_value",e,{value:i.target.value})}
    /></label>`:h}history(t){let e=t.map(i=>M(this.hass,this.selection,i)).filter(Boolean),s=JSON.stringify([e,this.config.history_hours||6]);s!==this._historySignature&&(this._historySignature=s,this._graphs=[],this._createHistory(e,s));for(let i of this._graphs||[])i.hass=this.hass;return c`${this._graphs||[]}`}async _createHistory(t,e){if(!(!t.length||!window.loadCardHelpers))try{let s=await window.loadCardHelpers();if(e!==this._historySignature||!this.isConnected)return;this._graphs=t.map(i=>s.createCardElement({type:"history-graph",entities:[i],hours_to_show:this.config.history_hours||6})),this.requestUpdate()}catch{this.error="History cards could not load. Live metrics remain available."}}pick(){let t=O(this.hass,this.constructor.role,this.constructor.key);return c`<label
      >${g(this.constructor.role)}<select
        aria-label=${g(this.constructor.role)}
        .value=${this.selection}
        ?disabled=${this.busy}
        @change=${e=>this.select(e.target.value)}
      >
        <option value="">Select ${this.constructor.role}</option>
        ${t.map(([e,s])=>c`<option value=${e} .selected=${e===this.selection}>${s.attributes.friendly_name||e}</option>`)}
      </select></label
    >`}button(t,e,s={},i={}){return c`<button
      ?disabled=${this.busy||!this.available&&!i.allowUnavailable}
      @click=${()=>this.action(e,s,i.message||"Changes saved.",i)}
    >
      ${t}
    </button>`}input(t,e,s,i="text"){return c`<label
      >${t}<input
        aria-label=${t}
        type=${i}
        .value=${String(e??"")}
        ?disabled=${this.busy}
        @input=${n=>s(n.target.value)}
    /></label>`}selectInput(t,e,s,i){return c`<label
      >${t}<select
        aria-label=${t}
        .value=${String(e??"")}
        ?disabled=${this.busy}
        @change=${n=>i(n.target.value)}
      >
        ${s.map(n=>c`<option value=${n.value??n} .selected=${String(n.value??n)===String(e??"")}>${n.label??n}</option>`)}
      </select></label
    >`}editNotice(){return this.draft.dirty?c`<div class="notice" role="status">
          Unsaved
          changes.${this.draft.conflicts.length?c`<span class="error"> Changed elsewhere: ${this.draft.conflicts.map(g).join(", ")}. Reload before saving.</span>`:h}<button
            @click=${()=>{this.draft.reset(this.draft.live),this.requestUpdate()}}
          >
            Discard edits and reload
          </button>
        </div>`:h}frame(t,{picker:e=!0,confirmationControls:s=!0}={}){return c`<ha-card
      ><div class="body">
        <h2>${this.config?.title||this.constructor.title}</h2>
        ${e?this.pick():h}
        ${this.selection&&!this.available?c`<p class="notice" role="status">${this.state?"This resource is unavailable. Controls are disabled until it recovers.":"The configured entity is missing. Choose another resource."}</p>`:h}
        ${this.resourceNotice()} ${t}
        <div aria-live="polite" role="status" ?hidden=${!this.feedback}>
          ${this.feedback}
        </div>
        ${this.taskOutcomes()}
        ${this.error?c`<div class="error" role="alert">${this.error}</div>`:h}
        ${s&&this.confirmation?c`<section class="confirm" aria-label="Confirm action">
                <p>${this.confirmation.options.confirm}</p>
                <div class="actions">
                  <button
                    @click=${()=>{let i=this.confirmation;this.confirmation=null,i.target===this.selection&&this.action(i.service,i.data,i.message,{...i.options,confirmed:!0})}}
                  >
                    Confirm</button
                  ><button
                    @click=${()=>{this.confirmation=null}}
                  >
                    Cancel
                  </button>
                </div>
              </section>`:h}
      </div></ha-card
    >`}};export{y as a,g as b,O as c,M as d,Gt as e,Kt as f,c as g,B as h,Ot as i,Ee as j,Pt as k};
/*! For license information please see shared-EVDKEACZ.js.LEGAL.txt */
