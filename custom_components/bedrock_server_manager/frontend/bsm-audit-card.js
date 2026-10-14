import{b as r}from"./shared-UXCKWJE4.js";import{g as t,h as e,j as s}from"./shared-66JIFLDQ.js";var i=class extends r{static title="Audit history";static role="manager";static key="bsm_version";static properties={actionFilter:{state:!0}};constructor(){super(),this.actionFilter=""}selectedChanged(){super.selectedChanged(),this.actionFilter=""}render(){return this.frame(t`${this.readNotice()}${this.input("Action filter (exact match)",this.actionFilter,a=>this.actionFilter=a)}${this.readButton("Load audit history","list_audit_logs",{limit:50,...this.actionFilter?{action:this.actionFilter}:{}})}
        <p class="muted">
          Administrator access required. The backend returns its full history;
          this view filters it and displays up to 50 records.
        </p>
        ${this.result?.truncated?t`<p class="notice">Showing a limited selection of ${this.result.total_matches} matching records.</p>`:""}${this.result?e(this.result.records):""}`)}};s("bsm-audit-card",i,"BSM Audit History","Inspect administrator audit records on demand.");
