import type * as backendApiPort from "@ports/backend_api_port";

export class AgentUseCase {
  private readonly api: backendApiPort.BackendApiPort;

  constructor(api: backendApiPort.BackendApiPort) {
    this.api = api;
  }

  async getSystemPrompt() {
    return this.api.getSystemPrompt();
  }

  async updateSystemPrompt(systemPrompt: string) {
    return this.api.updateSystemPrompt(systemPrompt);
  }

  async getAgentSettings() {
    return this.api.getAgentSettings();
  }

  async updateAgentSettings(debounceDelay: number) {
    return this.api.updateAgentSettings(debounceDelay);
  }

  async getDevFeatures() {
    return this.api.getDevFeatures();
  }

  async getSandboxMode() {
    return this.api.getSandboxMode();
  }

  async updateSandboxMode(enabled: boolean) {
    return this.api.updateSandboxMode(enabled);
  }
}
