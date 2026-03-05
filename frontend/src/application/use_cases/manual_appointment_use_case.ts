import type * as manualAppointmentModel from "@domain/models/manual_appointment";
import type * as backendApiPort from "@ports/backend_api_port";

export class ManualAppointmentUseCase {
  private readonly api: backendApiPort.BackendApiPort;

  constructor(api: backendApiPort.BackendApiPort) {
    this.api = api;
  }

  async listAppointments(status?: manualAppointmentModel.ManualAppointmentStatus) {
    return this.api.listManualAppointments(status);
  }

  async createAppointment(input: manualAppointmentModel.CreateManualAppointmentInput) {
    return this.api.createManualAppointment(input);
  }

  async rescheduleAppointment(
    appointmentId: string,
    input: manualAppointmentModel.RescheduleManualAppointmentInput
  ) {
    return this.api.rescheduleManualAppointment(appointmentId, input);
  }

  async cancelAppointment(
    appointmentId: string,
    input: manualAppointmentModel.CancelManualAppointmentInput
  ) {
    return this.api.cancelManualAppointment(appointmentId, input);
  }

  async updatePayment(
    appointmentId: string,
    input: manualAppointmentModel.UpdateManualAppointmentPaymentInput
  ) {
    return this.api.updateManualAppointmentPayment(appointmentId, input);
  }
}
