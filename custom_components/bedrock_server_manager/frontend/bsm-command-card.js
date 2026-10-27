import{g as s,j as a,k as e}from"./shared-3LOQBGQY.js";var m=class extends e{static title="Server command";static properties={command:{state:!0}};constructor(){super(),this.command=""}selectedChanged(){this.command=""}async send(){let t=this.command.trim();t&&await this.action("send_command",{command:t},"Command sent.")&&(this.command="")}render(){return this.frame(s`${this.input("Command",this.command,t=>this.command=t)}<button
          class="primary"
          ?disabled=${!this.available||this.busy||!this.command.trim()}
          @click=${this.send}
        >
          Send command
        </button>`)}};a("bsm-command-card",m,"BSM Command","Send commands to a selected server.");
