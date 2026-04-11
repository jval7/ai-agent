import type * as backendApiPort from "@ports/backend_api_port";
import type * as whatsappTemplateModel from "@domain/models/whatsapp_template";

export class WhatsappTemplateUseCase {
  private readonly api: backendApiPort.BackendApiPort;

  constructor(api: backendApiPort.BackendApiPort) {
    this.api = api;
  }

  async listTemplates() {
    return this.api.listWhatsappTemplates();
  }

  async createTemplate(request: whatsappTemplateModel.CreateTemplateRequest) {
    return this.api.createWhatsappTemplate(request);
  }

  async deleteTemplate(name: string) {
    return this.api.deleteWhatsappTemplate(name);
  }
}
