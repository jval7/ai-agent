import type * as backendApiPort from "@ports/backend_api_port";
import type * as patientModel from "@domain/models/patient";

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

  async createPatient(input: patientModel.CreatePatientInput) {
    return this.api.createPatient(input);
  }

  async updatePatient(whatsappUserId: string, input: patientModel.UpdatePatientInput) {
    return this.api.updatePatient(whatsappUserId, input);
  }
}
