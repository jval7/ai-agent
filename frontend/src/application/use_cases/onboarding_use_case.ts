import type * as backendApiPort from "@ports/backend_api_port";

export class OnboardingUseCase {
  private readonly api: backendApiPort.BackendApiPort;

  constructor(api: backendApiPort.BackendApiPort) {
    this.api = api;
  }

  async getWhatsappConnectionStatus() {
    return this.api.getWhatsappConnection();
  }

  async createWhatsappSession() {
    return this.api.createEmbeddedSignupSession();
  }

  async getGoogleCalendarConnectionStatus() {
    return this.api.getGoogleCalendarConnection();
  }

  async createGoogleSession() {
    return this.api.createGoogleOauthSession();
  }

  async getOnboardingStatus() {
    return this.api.getOnboardingStatus();
  }
}
