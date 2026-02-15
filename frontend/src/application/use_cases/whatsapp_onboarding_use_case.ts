import type * as backendApiPort from "@ports/backend_api_port";

export class WhatsappOnboardingUseCase {
  private readonly api: backendApiPort.BackendApiPort;

  constructor(api: backendApiPort.BackendApiPort) {
    this.api = api;
  }

  async getConnectionStatus() {
    return this.api.getWhatsappConnection();
  }

  async createEmbeddedSignupSession() {
    return this.api.createEmbeddedSignupSession();
  }
}
