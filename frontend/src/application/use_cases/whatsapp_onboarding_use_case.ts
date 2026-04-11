import type * as backendApiPort from "@ports/backend_api_port";
import type * as whatsappModel from "@domain/models/whatsapp";

export class WhatsappOnboardingUseCase {
  private readonly api: backendApiPort.BackendApiPort;

  constructor(api: backendApiPort.BackendApiPort) {
    this.api = api;
  }

  async getConnectionStatus() {
    return this.api.getWhatsappConnection();
  }

  async createEmbeddedSignupSession(registrationPin?: string) {
    return this.api.createEmbeddedSignupSession(registrationPin);
  }

  async completeEmbeddedSignup(request: whatsappModel.EmbeddedSignupCompleteRequest) {
    return this.api.completeEmbeddedSignup(request);
  }
}
