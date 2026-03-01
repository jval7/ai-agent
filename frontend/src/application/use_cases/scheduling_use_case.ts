import type * as schedulingModel from "@domain/models/scheduling";
import type * as backendApiPort from "@ports/backend_api_port";

export class SchedulingUseCase {
  private readonly api: backendApiPort.BackendApiPort;

  constructor(api: backendApiPort.BackendApiPort) {
    this.api = api;
  }

  async listRequests(status?: schedulingModel.SchedulingRequestStatus) {
    return this.api.listSchedulingRequests(status);
  }

  async listRequestsByConversation(conversationId: string) {
    return this.api.listConversationSchedulingRequests(conversationId);
  }

  async getAvailability(fromIso: string, toIso: string) {
    return this.api.getGoogleCalendarAvailability(fromIso, toIso);
  }

  async submitProfessionalSlots(
    conversationId: string,
    requestId: string,
    input: schedulingModel.SubmitProfessionalSlotsInput
  ) {
    return this.api.submitProfessionalSlots(conversationId, requestId, input);
  }
}
