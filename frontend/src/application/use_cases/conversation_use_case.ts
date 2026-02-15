import type * as conversationModel from "@domain/models/conversation";
import type * as backendApiPort from "@ports/backend_api_port";

export class ConversationUseCase {
  private readonly api: backendApiPort.BackendApiPort;

  constructor(api: backendApiPort.BackendApiPort) {
    this.api = api;
  }

  async listConversations() {
    return this.api.listConversations();
  }

  async listMessages(conversationId: string) {
    return this.api.listConversationMessages(conversationId);
  }

  async updateControlMode(conversationId: string, controlMode: conversationModel.ControlMode) {
    return this.api.updateConversationControlMode(conversationId, controlMode);
  }
}
