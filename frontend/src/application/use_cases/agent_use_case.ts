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
}
