import { BsmCard, html, register } from "./base.js";
class CommandCard extends BsmCard {
  static title = "Server command";
  static properties = { command: { state: true } };
  constructor() {
    super();
    this.command = "";
  }
  selectedChanged() {
    this.command = "";
  }
  async send() {
    const command = this.command.trim();
    if (!command) return;
    if (await this.action("send_command", { command }, "Command sent."))
      this.command = "";
  }
  render() {
    return this.frame(
      html`${this.input("Command", this.command, (value) => (this.command = value))}<button
          class="primary"
          ?disabled=${!this.available || this.busy || !this.command.trim()}
          @click=${this.send}
        >
          Send command
        </button>`,
    );
  }
}
register(
  "bsm-command-card",
  CommandCard,
  "BSM Command",
  "Send commands to a selected server.",
);
