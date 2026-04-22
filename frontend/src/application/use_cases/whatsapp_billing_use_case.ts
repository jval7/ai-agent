import type * as backendApiPort from "@ports/backend_api_port";
import type * as whatsappBillingModel from "@domain/models/whatsapp_billing";

export class WhatsappBillingUseCase {
  private readonly api: backendApiPort.BackendApiPort;

  constructor(api: backendApiPort.BackendApiPort) {
    this.api = api;
  }

  async runPreflight(phoneNumber: string): Promise<whatsappBillingModel.BillingPreflightResult> {
    return this.api.sendBillingPreflight(phoneNumber);
  }
}
