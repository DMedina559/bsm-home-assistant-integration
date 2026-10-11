var Q=globalThis,ot=r=>r,z=Q.trustedTypes,at=z?z.createPolicy("lit-html",{createHTML:r=>r}):void 0,pt="$lit$",b=`lit$${Math.random().toFixed(9).slice(2)}$`,ft="?"+b,Tt=`<${ft}>`,A=document,O=()=>A.createComment(""),T=r=>r===null||typeof r!="object"&&typeof r!="function",X=Array.isArray,Ut=r=>X(r)||typeof r?.[Symbol.iterator]=="function",W=`[ 	
\f\r]`,k=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,lt=/-->/g,ht=/>/g,y=RegExp(`>|${W}(?:([^\\s"'>=/]+)(${W}*=${W}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),ct=/'/g,dt=/"/g,mt=/^(?:script|style|textarea|title)$/i,Y=r=>(t,...e)=>({_$litType$:r,strings:t,values:e}),h=Y(1),Bt=Y(2),Vt=Y(3),x=Symbol.for("lit-noChange"),l=Symbol.for("lit-nothing"),ut=new WeakMap,v=A.createTreeWalker(A,129);function _t(r,t){if(!X(r)||!r.hasOwnProperty("raw"))throw Error("invalid template strings array");return at!==void 0?at.createHTML(t):t}var Pt=(r,t)=>{let e=r.length-1,s=[],i,n=t===2?"<svg>":t===3?"<math>":"",o=k;for(let c=0;c<e;c++){let a=r[c],u,p,d=-1,f=0;for(;f<a.length&&(o.lastIndex=f,p=o.exec(a),p!==null);)f=o.lastIndex,o===k?p[1]==="!--"?o=lt:p[1]!==void 0?o=ht:p[2]!==void 0?(mt.test(p[2])&&(i=RegExp("</"+p[2],"g")),o=y):p[3]!==void 0&&(o=y):o===y?p[0]===">"?(o=i??k,d=-1):p[1]===void 0?d=-2:(d=o.lastIndex-p[2].length,u=p[1],o=p[3]===void 0?y:p[3]==='"'?dt:ct):o===dt||o===ct?o=y:o===lt||o===ht?o=k:(o=y,i=void 0);let g=o===y&&r[c+1].startsWith("/>")?" ":"";n+=o===k?a+Tt:d>=0?(s.push(u),a.slice(0,d)+pt+a.slice(d)+b+g):a+b+(d===-2?c:g)}return[_t(r,n+(r[e]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),s]},U=class r{constructor({strings:t,_$litType$:e},s){let i;this.parts=[];let n=0,o=0,c=t.length-1,a=this.parts,[u,p]=Pt(t,e);if(this.el=r.createElement(u,s),v.currentNode=this.el.content,e===2||e===3){let d=this.el.content.firstChild;d.replaceWith(...d.childNodes)}for(;(i=v.nextNode())!==null&&a.length<c;){if(i.nodeType===1){if(i.hasAttributes())for(let d of i.getAttributeNames())if(d.endsWith(pt)){let f=p[o++],g=i.getAttribute(d).split(b),j=/([.?@])?(.*)/.exec(f);a.push({type:1,index:n,name:j[2],strings:g,ctor:j[1]==="."?K:j[1]==="?"?F:j[1]==="@"?G:E}),i.removeAttribute(d)}else d.startsWith(b)&&(a.push({type:6,index:n}),i.removeAttribute(d));if(mt.test(i.tagName)){let d=i.textContent.split(b),f=d.length-1;if(f>0){i.textContent=z?z.emptyScript:"";for(let g=0;g<f;g++)i.append(d[g],O()),v.nextNode(),a.push({type:2,index:++n});i.append(d[f],O())}}}else if(i.nodeType===8)if(i.data===ft)a.push({type:2,index:n});else{let d=-1;for(;(d=i.data.indexOf(b,d+1))!==-1;)a.push({type:7,index:n}),d+=b.length-1}n++}}static createElement(t,e){let s=A.createElement("template");return s.innerHTML=t,s}};function S(r,t,e=r,s){if(t===x)return t;let i=s!==void 0?e._$Co?.[s]:e._$Cl,n=T(t)?void 0:t._$litDirective$;return i?.constructor!==n&&(i?._$AO?.(!1),n===void 0?i=void 0:(i=new n(r),i._$AT(r,e,s)),s!==void 0?(e._$Co??=[])[s]=i:e._$Cl=i),i!==void 0&&(t=S(r,i._$AS(r,t.values),i,s)),t}var J=class{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){let{el:{content:e},parts:s}=this._$AD,i=(t?.creationScope??A).importNode(e,!0);v.currentNode=i;let n=v.nextNode(),o=0,c=0,a=s[0];for(;a!==void 0;){if(o===a.index){let u;a.type===2?u=new P(n,n.nextSibling,this,t):a.type===1?u=new a.ctor(n,a.name,a.strings,this,t):a.type===6&&(u=new Z(n,this,t)),this._$AV.push(u),a=s[++c]}o!==a?.index&&(n=v.nextNode(),o++)}return v.currentNode=A,i}p(t){let e=0;for(let s of this._$AV)s!==void 0&&(s.strings!==void 0?(s._$AI(t,s,e),e+=s.strings.length-2):s._$AI(t[e])),e++}},P=class r{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,s,i){this.type=2,this._$AH=l,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=s,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode,e=this._$AM;return e!==void 0&&t?.nodeType===11&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=S(this,t,e),T(t)?t===l||t==null||t===""?(this._$AH!==l&&this._$AR(),this._$AH=l):t!==this._$AH&&t!==x&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):Ut(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==l&&T(this._$AH)?this._$AA.nextSibling.data=t:this.T(A.createTextNode(t)),this._$AH=t}$(t){let{values:e,_$litType$:s}=t,i=typeof s=="number"?this._$AC(t):(s.el===void 0&&(s.el=U.createElement(_t(s.h,s.h[0]),this.options)),s);if(this._$AH?._$AD===i)this._$AH.p(e);else{let n=new J(i,this),o=n.u(this.options);n.p(e),this.T(o),this._$AH=n}}_$AC(t){let e=ut.get(t.strings);return e===void 0&&ut.set(t.strings,e=new U(t)),e}k(t){X(this._$AH)||(this._$AH=[],this._$AR());let e=this._$AH,s,i=0;for(let n of t)i===e.length?e.push(s=new r(this.O(O()),this.O(O()),this,this.options)):s=e[i],s._$AI(n),i++;i<e.length&&(this._$AR(s&&s._$AB.nextSibling,i),e.length=i)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){let s=ot(t).nextSibling;ot(t).remove(),t=s}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},E=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,s,i,n){this.type=1,this._$AH=l,this._$AN=void 0,this.element=t,this.name=e,this._$AM=i,this.options=n,s.length>2||s[0]!==""||s[1]!==""?(this._$AH=Array(s.length-1).fill(new String),this.strings=s):this._$AH=l}_$AI(t,e=this,s,i){let n=this.strings,o=!1;if(n===void 0)t=S(this,t,e,0),o=!T(t)||t!==this._$AH&&t!==x,o&&(this._$AH=t);else{let c=t,a,u;for(t=n[0],a=0;a<n.length-1;a++)u=S(this,c[s+a],e,a),u===x&&(u=this._$AH[a]),o||=!T(u)||u!==this._$AH[a],u===l?t=l:t!==l&&(t+=(u??"")+n[a+1]),this._$AH[a]=u}o&&!i&&this.j(t)}j(t){t===l?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},K=class extends E{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===l?void 0:t}},F=class extends E{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==l)}},G=class extends E{constructor(t,e,s,i,n){super(t,e,s,i,n),this.type=5}_$AI(t,e=this){if((t=S(this,t,e,0)??l)===x)return;let s=this._$AH,i=t===l&&s!==l||t.capture!==s.capture||t.once!==s.once||t.passive!==s.passive,n=t!==l&&(s===l||i);i&&this.element.removeEventListener(this.name,this,s),n&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},Z=class{constructor(t,e,s){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=s}get _$AU(){return this._$AM._$AU}_$AI(t){S(this,t)}};var Mt=Q.litHtmlPolyfillSupport;Mt?.(U,P),(Q.litHtmlVersions??=[]).push("3.3.3");var gt=(r,t,e)=>{let s=e?.renderBefore??t,i=s._$litPart$;if(i===void 0){let n=e?.renderBefore??null;s._$litPart$=i=new P(t.insertBefore(O(),n),n,void 0,e??{})}return i._$AI(r),i};var L="bedrock_server_manager",w=r=>!r||["unavailable","unknown"].includes(r.state),C=r=>structuredClone(r),tt=(r,t)=>JSON.stringify(r)===JSON.stringify(t),m=r=>r.replace(/[_-]/g," ").replace(/^./,t=>t.toUpperCase()),D=class{constructor(){this.reset({})}reset(t){this.base=C(t),this.live=C(t),this.changes={}}update(t){this.live=C(t),this.dirty||(this.base=C(t))}set(t,e){tt(e,this.base[t])?delete this.changes[t]:this.changes[t]=e}get dirty(){return Object.keys(this.changes).length>0}get conflicts(){return Object.keys(this.changes).filter(t=>!tt(this.live[t],this.base[t])&&!tt(this.live[t],this.changes[t]))}get value(){return{...this.live,...this.changes}}};function $t(r,t){return r?.states?.[t]?.attributes?.bsm_key}function bt(r,t){return r?.entities?.[t]?.device_id||r?.states?.[t]?.attributes?.device_id}function M(r,t,e){return Object.entries(r?.states||{}).filter(([s,i])=>i.attributes?.bsm_role===t&&(!e||$t(r,s)===e)).sort(([s],[i])=>s.localeCompare(i))}function N(r,t,e){let s=bt(r,t);return Object.entries(r?.states||{}).find(([i])=>$t(r,i)===e&&s&&bt(r,i)===s)?.[0]}function yt(r){return r.error?.message||r.error?.detail||r.message||"The operation failed."}function Jt(r){return typeof r=="string"?r:r.filename||r.name}function Kt(r,t){if(t.enum)return t.enum.find(e=>String(e)===String(r));if(["number","integer"].includes(t.type)){if(r===""||r===null||r===void 0||!Number.isFinite(Number(r)))throw Error("Enter a valid number.");let e=Number(r);if(t.type==="integer"&&!Number.isInteger(e))throw Error("Enter a whole number.");if(t.minimum!=null&&e<t.minimum)throw Error(`Minimum is ${t.minimum}.`);if(t.maximum!=null&&e>t.maximum)throw Error(`Maximum is ${t.maximum}.`);if(t.exclusiveMinimum!=null&&e<=t.exclusiveMinimum)throw Error(`Must exceed ${t.exclusiveMinimum}.`);if(t.exclusiveMaximum!=null&&e>=t.exclusiveMaximum)throw Error(`Must be less than ${t.exclusiveMaximum}.`);return e}return["object","array"].includes(t.type)&&typeof r=="string"?JSON.parse(r):r}var I=globalThis,q=I.ShadowRoot&&(I.ShadyCSS===void 0||I.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,et=Symbol(),vt=new WeakMap,H=class{constructor(t,e,s){if(this._$cssResult$=!0,s!==et)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o,e=this.t;if(q&&t===void 0){let s=e!==void 0&&e.length===1;s&&(t=vt.get(e)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),s&&vt.set(e,t))}return t}toString(){return this.cssText}},At=r=>new H(typeof r=="string"?r:r+"",void 0,et),st=(r,...t)=>{let e=r.length===1?r[0]:t.reduce((s,i,n)=>s+(o=>{if(o._$cssResult$===!0)return o.cssText;if(typeof o=="number")return o;throw Error("Value passed to 'css' function must be a 'css' function result: "+o+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+r[n+1],r[0]);return new H(e,r,et)},xt=(r,t)=>{if(q)r.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let e of t){let s=document.createElement("style"),i=I.litNonce;i!==void 0&&s.setAttribute("nonce",i),s.textContent=e.cssText,r.appendChild(s)}},it=q?r=>r:r=>r instanceof CSSStyleSheet?(t=>{let e="";for(let s of t.cssRules)e+=s.cssText;return At(e)})(r):r;var{is:Nt,defineProperty:Ht,getOwnPropertyDescriptor:Rt,getOwnPropertyNames:jt,getOwnPropertySymbols:zt,getPrototypeOf:Dt}=Object,B=globalThis,wt=B.trustedTypes,Lt=wt?wt.emptyScript:"",It=B.reactiveElementPolyfillSupport,R=(r,t)=>r,rt={toAttribute(r,t){switch(t){case Boolean:r=r?Lt:null;break;case Object:case Array:r=r==null?r:JSON.stringify(r)}return r},fromAttribute(r,t){let e=r;switch(t){case Boolean:e=r!==null;break;case Number:e=r===null?null:Number(r);break;case Object:case Array:try{e=JSON.parse(r)}catch{e=null}}return e}},Et=(r,t)=>!Nt(r,t),St={attribute:!0,type:String,converter:rt,reflect:!1,useDefault:!1,hasChanged:Et};Symbol.metadata??=Symbol("metadata"),B.litPropertyMetadata??=new WeakMap;var _=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=St){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){let s=Symbol(),i=this.getPropertyDescriptor(t,s,e);i!==void 0&&Ht(this.prototype,t,i)}}static getPropertyDescriptor(t,e,s){let{get:i,set:n}=Rt(this.prototype,t)??{get(){return this[e]},set(o){this[e]=o}};return{get:i,set(o){let c=i?.call(this);n?.call(this,o),this.requestUpdate(t,c,s)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??St}static _$Ei(){if(this.hasOwnProperty(R("elementProperties")))return;let t=Dt(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(R("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(R("properties"))){let e=this.properties,s=[...jt(e),...zt(e)];for(let i of s)this.createProperty(i,e[i])}let t=this[Symbol.metadata];if(t!==null){let e=litPropertyMetadata.get(t);if(e!==void 0)for(let[s,i]of e)this.elementProperties.set(s,i)}this._$Eh=new Map;for(let[e,s]of this.elementProperties){let i=this._$Eu(e,s);i!==void 0&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){let e=[];if(Array.isArray(t)){let s=new Set(t.flat(1/0).reverse());for(let i of s)e.unshift(it(i))}else t!==void 0&&e.push(it(t));return e}static _$Eu(t,e){let s=e.attribute;return s===!1?void 0:typeof s=="string"?s:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){let t=new Map,e=this.constructor.elementProperties;for(let s of e.keys())this.hasOwnProperty(s)&&(t.set(s,this[s]),delete this[s]);t.size>0&&(this._$Ep=t)}createRenderRoot(){let t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return xt(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,s){this._$AK(t,s)}_$ET(t,e){let s=this.constructor.elementProperties.get(t),i=this.constructor._$Eu(t,s);if(i!==void 0&&s.reflect===!0){let n=(s.converter?.toAttribute!==void 0?s.converter:rt).toAttribute(e,s.type);this._$Em=t,n==null?this.removeAttribute(i):this.setAttribute(i,n),this._$Em=null}}_$AK(t,e){let s=this.constructor,i=s._$Eh.get(t);if(i!==void 0&&this._$Em!==i){let n=s.getPropertyOptions(i),o=typeof n.converter=="function"?{fromAttribute:n.converter}:n.converter?.fromAttribute!==void 0?n.converter:rt;this._$Em=i;let c=o.fromAttribute(e,n.type);this[i]=c??this._$Ej?.get(i)??c,this._$Em=null}}requestUpdate(t,e,s,i=!1,n){if(t!==void 0){let o=this.constructor;if(i===!1&&(n=this[t]),s??=o.getPropertyOptions(t),!((s.hasChanged??Et)(n,e)||s.useDefault&&s.reflect&&n===this._$Ej?.get(t)&&!this.hasAttribute(o._$Eu(t,s))))return;this.C(t,e,s)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,e,{useDefault:s,reflect:i,wrapped:n},o){s&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,o??e??this[t]),n!==!0||o!==void 0)||(this._$AL.has(t)||(this.hasUpdated||s||(e=void 0),this._$AL.set(t,e)),i===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[i,n]of this._$Ep)this[i]=n;this._$Ep=void 0}let s=this.constructor.elementProperties;if(s.size>0)for(let[i,n]of s){let{wrapped:o}=n,c=this[i];o!==!0||this._$AL.has(i)||c===void 0||this.C(i,void 0,n,c)}}let t=!1,e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(s=>s.hostUpdate?.()),this.update(e)):this._$EM()}catch(s){throw t=!1,this._$EM(),s}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(t){}firstUpdated(t){}};_.elementStyles=[],_.shadowRootOptions={mode:"open"},_[R("elementProperties")]=new Map,_[R("finalized")]=new Map,It?.({ReactiveElement:_}),(B.reactiveElementVersions??=[]).push("2.1.2");var nt=globalThis,$=class extends _{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){let e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=gt(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return x}};$._$litElement$=!0,$.finalized=!0,nt.litElementHydrateSupport?.({LitElement:$});var qt=nt.litElementPolyfillSupport;qt?.({LitElement:$});(nt.litElementVersions??=[]).push("4.2.2");function V(r){return r==null?h`<span class="muted">None</span>`:Array.isArray(r)?h`<ul>
      ${r.map(t=>h`<li>${V(t)}</li>`)}
    </ul>`:typeof r=="object"?h`<dl>
      ${Object.entries(r).map(([t,e])=>h`<dt>${m(t)}</dt>
            <dd style="margin:0 0 8px;overflow-wrap:anywhere">
              ${V(e)}
            </dd>`)}
    </dl>`:h`<span style="overflow-wrap:anywhere">${String(r)}</span>`}function Ct(r){return h`${r.error?h`<div class="error" role="alert">${V(r.error)}</div>`:l}${r.result!=null?h`<h4>Outcome</h4>
            ${V(r.result)}`:l}
    <details>
      <summary>Raw response</summary>
      <pre style="white-space:pre-wrap;overflow-wrap:anywhere">
${JSON.stringify(r,null,2)}</pre>
    </details>`}var kt=st`
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
`;function $e(r,t,e,s){customElements.get(r)||customElements.define(r,t),window.customCards||=[],window.customCards.some(i=>i.type===r)||window.customCards.push({type:r,name:e,description:s,preview:!0})}var Ot=class extends ${static properties={hass:{attribute:!1},config:{state:!0},selection:{state:!0},busy:{state:!0},error:{state:!0},feedback:{state:!0},confirmation:{state:!0},revision:{state:!0}};static styles=kt;static role="server";static key="status";static title="Bedrock Server Manager";static getConfigForm(){return{schema:[{name:"title",selector:{text:{}}},{name:"entity",selector:{entity:{integration:L}}},{name:"debug",selector:{boolean:{}}}],computeLabel:t=>t.name==="entity"?`Default ${this.role}`:m(t.name)}}static getStubConfig(t){return{entity:M(t,this.role,this.key)[0]?.[0]}}constructor(){super(),this.draft=new D,this.selection="",this.busy=!1,this.error="",this.feedback="",this.revision=0,this._generation=0,this._taskCache=new Map,this._retiredTaskEpochs=new Map,this._tasks=new Map}setConfig(t){if(!t||typeof t!="object")throw Error("A card configuration is required.");if(t.history_hours!=null&&(!Number.isInteger(t.history_hours)||t.history_hours<1||t.history_hours>168))throw Error("History hours must be a whole number from 1 to 168.");this.config={...t};let e=t.entity||t.manager_entity||t.target_server_sensor_entity||t.target_device||"";e!==this.selection&&this.select(e)}getCardSize(){return 4}getGridOptions(){return{columns:12,min_columns:6,rows:"auto"}}get state(){return this.hass?.states?.[this.selection]}get available(){return!w(this.state)}get target(){return this.selection.includes(".")?{entity_id:this.selection}:{device_id:this.selection}}stateFor(t){let e=N(this.hass,this.selection,t);return this.hass?.states?.[e]}select(t){this._generation++,this.selection=t||"",this.error="",this.feedback="",this.busy=!1,this.confirmation=null,this.draft.reset({}),this._tasks.clear(),this.selectedChanged()}selectedChanged(){}connectedCallback(){super.connectedCallback(),this._subscribeTasks()}disconnectedCallback(){super.disconnectedCallback(),this._generation++,this._unsubscribe?.(),this._unsubscribe=null,this._connection=null,clearTimeout(this._pollTimer),this._tasks.clear()}updated(t){t.has("hass")&&(this.normalizeSelection(),this._subscribeTasks(),this.syncState())}normalizeSelection(){if(!this.selection)return;let t;if(this.selection.includes(".")){if(this.state?.attributes.bsm_key===this.constructor.key)return;t=N(this.hass,this.selection,this.constructor.key)}else t=M(this.hass,this.constructor.role,this.constructor.key).find(([e])=>this.hass.entities?.[e]?.device_id===this.selection)?.[0];t&&t!==this.selection&&this.select(t)}knownPlayers(){let t=this.hass?.entities?.[this.selection]?.device_id,e=this.hass?.devices?.[t]?.via_device_id,s=this.config.global_players_entity||this.config.global_players_sensor_entity||this.config.global_player_sensor_entity;return s?this.hass.states[s]?.attributes.global_players_list||[]:M(this.hass,"manager","global_players_count").find(([n])=>this.hass.entities?.[n]?.device_id===e)?.[1].attributes.global_players_list||[]}taskOutcomes(){return h`${[...this._tasks.values()].filter(({task:t})=>["completed","failed","cancelled"].includes(t.status)&&(t.result!=null||t.error)).map(({task:t})=>h`<details class="tile">
            <summary>${m(t.status)} outcome · ${t.id}</summary>
            ${Ct(t)}
          </details>`)}`}syncState(){}async _subscribeTasks(){let t=this.hass?.connection;if(!(!this.isConnected||!t||this._connection===t)){this._connection=t,this._unsubscribe?.(),this._unsubscribe=null;try{let e=await t.subscribeEvents(s=>this._taskUpdate(s.data),`${L}_task_update`);!this.isConnected||this._connection!==t?e():this._unsubscribe=e}catch{this._connection===t&&(this._connection=null)}}}_taskUpdate(t){let e=`${t.manager_url}:${t.id}`,s=this._taskCache.get(e);if(!["queued","running","cancelling","completed","failed","cancelled"].includes(t.status))return;let i=t.epoch!=null||t.revision!=null;if(i&&(typeof t.epoch!="string"||!t.epoch.trim()||!Number.isSafeInteger(t.revision)||t.revision<1)||s?.epoch&&!i)return;let n=this._retiredTaskEpochs.get(e)||new Set;if(n.has(t.epoch)||s?.epoch===t.epoch&&s.revision>=t.revision)return;if(s?.epoch&&t.epoch&&s.epoch!==t.epoch&&n.add(s.epoch),this._retiredTaskEpochs.set(e,n),this._taskCache.set(e,t),this._taskCache.size>100){let c=this._taskCache.keys().next().value;this._taskCache.delete(c),this._retiredTaskEpochs.delete(c)}let o=this._tasks.get(e);!o||o.generation!==this._generation||(o.task=t,this._showTasks())}_showTasks(){let t=[...this._tasks.values()].map(s=>s.task),e=t.find(s=>["failed","cancelled"].includes(s.status));this.error=e?yt(e):"",this.busy=t.some(s=>!["completed","failed","cancelled"].includes(s.status)),this.feedback=t.map(s=>`${m(s.status)}: ${s.message||s.id}`).join(" \xB7 "),this.requestUpdate()}async _pollTasks(t){if(!(!this.isConnected||t!==this._generation||!this.busy)){for(let e of this._tasks.values())if(!["completed","failed","cancelled"].includes(e.task.status))try{let s=await this.responseService("get_task",{task_id:e.task.id},e.target);if(t!==this._generation)return;for(let i of s.managers||[])this._taskUpdate({manager_url:i.manager_url,...i.task})}catch{}t===this._generation&&this.busy&&(this._pollTimer=setTimeout(()=>this._pollTasks(t),3e3))}}async responseService(t,e,s=this.target){return(await this.hass.callWS({type:"call_service",domain:L,service:t,service_data:e,target:s,return_response:!0})).response||{}}async action(t,e={},s="Changes saved.",i={}){if(this.busy||!i.allowUnavailable&&!this.available)return!1;if(i.confirm&&!i.confirmed)return this.confirmation={service:t,data:C(e),message:s,options:i,target:this.selection},!1;let n=this._generation,o={...this.target};this.busy=!0,this.error="",this.feedback="Sending request\u2026",this._tasks.clear();try{let c=await this.responseService(t,e,o);if(n!==this._generation)return!1;this._lastResponse=c;for(let a of c.results||[]){let u=a.result?.task_id;if(!u)continue;let p=`${a.manager_url}:${u}`;this._tasks.set(p,{generation:n,target:o,task:this._taskCache.get(p)||{id:u,status:"queued",message:"Waiting for task outcome"}})}return this._tasks.size?(this._showTasks(),this._pollTimer=setTimeout(()=>this._pollTasks(n),1e3)):(this.busy=!1,this.feedback=(c.results||[]).map(({result:a})=>a?.status==="skipped"?`Skipped: ${a.message||"No change required."}`:a?.message).filter(Boolean).join(" \xB7 ")||s),this.config.debug&&console.debug("BSM action",t,"acknowledged"),!0}catch(c){return n!==this._generation||(this.error=c.message||String(c),this.feedback="",this.busy=!1),!1}}moreInfo(t){this.dispatchEvent(new CustomEvent("hass-more-info",{detail:{entityId:t},bubbles:!0,composed:!0}))}async nativeAction(t,e,s,i={}){if(this.busy||w(this.hass?.states?.[s]))return!1;let n=this._generation;this.busy=!0,this.error="";try{return await this.hass.callService(t,e,i,{entity_id:s}),n!==this._generation?!1:(this.feedback="Request sent. State updates when confirmed by the server.",!0)}catch(o){return n===this._generation&&(this.error=o.message||String(o)),!1}finally{n===this._generation&&(this.busy=!1)}}metric(t){if(!t)return l;let e=t.entity_id,s=t.attributes.friendly_name||e,i=t.state;return t.attributes.device_class==="connectivity"&&(i=t.state==="on"?"Connected":"Unavailable"),t.attributes.device_class==="problem"&&(i=t.state==="on"?"Problem":"Healthy"),t.attributes.bsm_key==="websocket"&&(i=t.state==="on"?"Live":"Offline"),h`<button
      class="tile"
      style="text-align:left"
      @click=${()=>this.moreInfo(e)}
    >
      <small>${s}</small>
      <div class="value">
        ${w(t)?"Unavailable":i}
        ${t.attributes.unit_of_measurement||""}
      </div>
      ${t.attributes.message?h`<small>${t.attributes.message}</small>`:l}
    </button>`}entityControl(t){let e=N(this.hass,this.selection,t),s=this.hass?.states?.[e];return s?e.startsWith("switch.")?h`<div class="heading">
        <span>${s.attributes.friendly_name}</span
        ><button
          ?disabled=${this.busy||w(s)}
          @click=${()=>this.nativeAction("switch",s.state==="on"?"turn_off":"turn_on",e)}
        >
          ${s.state==="on"?"Disable":"Enable"}
        </button>
      </div>`:h`<label
      >${s.attributes.friendly_name}<input
        aria-label=${s.attributes.friendly_name}
        .value=${w(s)?"":s.state}
        ?disabled=${this.busy||w(s)}
        @change=${i=>this.nativeAction("text","set_value",e,{value:i.target.value})}
    /></label>`:l}history(t){let e=t.map(i=>N(this.hass,this.selection,i)).filter(Boolean),s=JSON.stringify([e,this.config.history_hours||6]);s!==this._historySignature&&(this._historySignature=s,this._graphs=[],this._createHistory(e,s));for(let i of this._graphs||[])i.hass=this.hass;return h`${this._graphs||[]}`}async _createHistory(t,e){if(!(!t.length||!window.loadCardHelpers))try{let s=await window.loadCardHelpers();if(e!==this._historySignature||!this.isConnected)return;this._graphs=t.map(i=>s.createCardElement({type:"history-graph",entities:[i],hours_to_show:this.config.history_hours||6})),this.requestUpdate()}catch{this.error="History cards could not load. Live metrics remain available."}}pick(){let t=M(this.hass,this.constructor.role,this.constructor.key);return h`<label
      >${m(this.constructor.role)}<select
        aria-label=${m(this.constructor.role)}
        .value=${this.selection}
        ?disabled=${this.busy}
        @change=${e=>this.select(e.target.value)}
      >
        <option value="">Select ${this.constructor.role}</option>
        ${t.map(([e,s])=>h`<option value=${e} .selected=${e===this.selection}>${s.attributes.friendly_name||e}</option>`)}
      </select></label
    >`}button(t,e,s={},i={}){return h`<button
      ?disabled=${this.busy||!this.available&&!i.allowUnavailable}
      @click=${()=>this.action(e,s,i.message||"Changes saved.",i)}
    >
      ${t}
    </button>`}input(t,e,s,i="text"){return h`<label
      >${t}<input
        aria-label=${t}
        type=${i}
        .value=${String(e??"")}
        ?disabled=${this.busy}
        @input=${n=>s(n.target.value)}
    /></label>`}selectInput(t,e,s,i){return h`<label
      >${t}<select
        aria-label=${t}
        .value=${String(e??"")}
        ?disabled=${this.busy}
        @change=${n=>i(n.target.value)}
      >
        ${s.map(n=>h`<option value=${n.value??n} .selected=${String(n.value??n)===String(e??"")}>${n.label??n}</option>`)}
      </select></label
    >`}editNotice(){return this.draft.dirty?h`<div class="notice" role="status">
          Unsaved
          changes.${this.draft.conflicts.length?h`<span class="error"> Changed elsewhere: ${this.draft.conflicts.map(m).join(", ")}. Reload before saving.</span>`:l}<button
            @click=${()=>{this.draft.reset(this.draft.live),this.requestUpdate()}}
          >
            Discard edits and reload
          </button>
        </div>`:l}frame(t,{picker:e=!0}={}){return h`<ha-card
      ><div class="body">
        <h2>${this.config?.title||this.constructor.title}</h2>
        ${e?this.pick():l}
        ${this.selection&&!this.available?h`<p class="notice" role="status">${this.state?"This resource is unavailable. Controls are disabled until it recovers.":"The configured entity is missing. Choose another resource."}</p>`:l}
        ${t}
        <div aria-live="polite" role="status" ?hidden=${!this.feedback}>
          ${this.feedback}
        </div>
        ${this.taskOutcomes()}
        ${this.error?h`<div class="error" role="alert">${this.error}</div>`:l}
        ${this.confirmation?h`<section class="confirm" aria-label="Confirm action">
                <p>${this.confirmation.options.confirm}</p>
                <div class="actions">
                  <button
                    @click=${()=>{let s=this.confirmation;this.confirmation=null,s.target===this.selection&&this.action(s.service,s.data,s.message,{...s.options,confirmed:!0})}}
                  >
                    Confirm</button
                  ><button
                    @click=${()=>{this.confirmation=null}}
                  >
                    Cancel
                  </button>
                </div>
              </section>`:l}
      </div></ha-card
    >`}};export{h as a,w as b,m as c,M as d,N as e,Jt as f,Kt as g,V as h,Ct as i,$e as j,Ot as k};
/*! For license information please see shared-5SVUCQ5X.js.LEGAL.txt */
