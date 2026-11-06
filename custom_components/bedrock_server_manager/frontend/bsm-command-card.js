import{h as s,k as n,l as e}from"./shared-C27S2ORL.js";var m=class extends e{static title="Server command";static properties={command:{state:!0}};constructor(){super(),this.command=""}selectedChanged(){this.command=""}async send(){let t=this.command.trim();t&&await this.action("send_command",{command:t},"Command sent.")&&(this.command="")}render(){return this.frame(s`${this.input("Command",this.command,t=>this.command=t)}<button
          class="primary"
          ?disabled=${!this.available||this.busy||this.actionDenied("send_command")||!this.command.trim()}
          @click=${this.send}
        >
          Send command
        </button>`)}};n("bsm-command-card",m,"BSM Command","Send commands to a selected server.");
