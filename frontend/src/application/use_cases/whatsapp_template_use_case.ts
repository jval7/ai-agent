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

  async listOfficialTemplateStatus(): Promise<whatsappTemplateModel.OfficialTemplateStatus[]> {
    return this.api.listOfficialTemplateStatus();
  }

  async activateOfficialTemplate(
    kind: whatsappTemplateModel.OfficialReminderKind
  ): Promise<whatsappTemplateModel.OfficialTemplateStatus> {
    return this.api.activateOfficialTemplate(kind);
  }

  async deactivateOfficialTemplate(
    kind: whatsappTemplateModel.OfficialReminderKind
  ): Promise<void> {
    return this.api.deactivateOfficialTemplate(kind);
  }
}
