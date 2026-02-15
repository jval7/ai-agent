import type * as agentModel from "@domain/models/agent";
import type * as authModel from "@domain/models/auth";
import type * as blacklistModel from "@domain/models/blacklist";
import type * as conversationModel from "@domain/models/conversation";
import type * as whatsappModel from "@domain/models/whatsapp";

export interface BackendApiPort {
  register(input: authModel.RegisterInput): Promise<authModel.AuthTokens>;
  login(input: authModel.LoginInput): Promise<authModel.AuthTokens>;
  refresh(refreshToken: string): Promise<authModel.AuthTokens>;
  logout(refreshToken: string): Promise<void>;

  getSystemPrompt(): Promise<agentModel.SystemPrompt>;
  updateSystemPrompt(systemPrompt: string): Promise<agentModel.SystemPrompt>;

  createEmbeddedSignupSession(): Promise<whatsappModel.EmbeddedSignupSession>;
  getWhatsappConnection(): Promise<whatsappModel.WhatsappConnection>;

  listConversations(): Promise<conversationModel.ConversationSummary[]>;
  listConversationMessages(
    conversationId: string
  ): Promise<conversationModel.ConversationMessage[]>;
  updateConversationControlMode(
    conversationId: string,
    controlMode: conversationModel.ControlMode
  ): Promise<conversationModel.ControlMode>;

  listBlacklist(): Promise<blacklistModel.BlacklistEntry[]>;
  addBlacklist(whatsappUserId: string): Promise<blacklistModel.BlacklistEntry>;
  removeBlacklist(whatsappUserId: string): Promise<void>;
}
