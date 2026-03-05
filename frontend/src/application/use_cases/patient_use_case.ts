import type * as backendApiPort from "@ports/backend_api_port";

export class PatientUseCase {
  private readonly api: backendApiPort.BackendApiPort;

  constructor(api: backendApiPort.BackendApiPort) {
    this.api = api;
  }

  async listPatients() {
    return this.api.listPatients();
  }

  async getPatient(whatsappUserId: string) {
    return this.api.getPatient(whatsappUserId);
  }

  async removePatient(whatsappUserId: string) {
    return this.api.removePatient(whatsappUserId);
  }
}
