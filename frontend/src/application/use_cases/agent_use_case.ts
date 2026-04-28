import type * as agentModel from "@domain/models/agent";
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

  async updateAgentSettings(input: agentModel.UpdateAgentSettingsInput) {
    return this.api.updateAgentSettings(input);
  }

  async getProfessionalProfile() {
    return this.api.getProfessionalProfile();
  }

  async updateProfessionalProfile(input: agentModel.UpdateProfessionalProfileInput) {
    return this.api.updateProfessionalProfile(input);
  }

  async getDevFeatures() {
    return this.api.getDevFeatures();
  }

  async updateSandboxMode(enabled: boolean) {
    return this.api.updateSandboxMode(enabled);
  }
}
