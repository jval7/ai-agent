import * as vitestModule from "vitest";

import type * as agentModel from "@domain/models/agent";
import type * as authModel from "@domain/models/auth";
import type * as blacklistModel from "@domain/models/blacklist";
import type * as conversationModel from "@domain/models/conversation";
import type * as backendApiPort from "@ports/backend_api_port";
import type * as whatsappModel from "@domain/models/whatsapp";

import * as authUseCaseModule from "./auth_use_case";

class InMemoryTokenSession {
  private accessToken: string | null;
  private refreshToken: string | null;

  constructor(accessToken: string | null, refreshToken: string | null) {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
  }

  getAccessToken(): string | null {
    return this.accessToken;
  }

  setAccessToken(token: string): void {
    this.accessToken = token;
  }

  clearAccessToken(): void {
    this.accessToken = null;
  }

  getRefreshToken(): string | null {
    return this.refreshToken;
  }

  setRefreshToken(token: string): void {
    this.refreshToken = token;
  }

  clearRefreshToken(): void {
    this.refreshToken = null;
  }

  clearAll(): void {
    this.clearAccessToken();
    this.clearRefreshToken();
  }
}

class FakeBackendApi implements backendApiPort.BackendApiPort {
  refreshCalls = 0;

  async register(_input: authModel.RegisterInput): Promise<authModel.AuthTokens> {
    throw new Error("not used");
  }

  async login(_input: authModel.LoginInput): Promise<authModel.AuthTokens> {
    throw new Error("not used");
  }

  async refresh(_refreshToken: string): Promise<authModel.AuthTokens> {
    this.refreshCalls += 1;
    return {
      accessToken: "access-new",
      refreshToken: "refresh-new",
      expiresInSeconds: 1800
    };
  }

  async logout(_refreshToken: string): Promise<void> {
    return;
  }

  async getSystemPrompt(): Promise<agentModel.SystemPrompt> {
    throw new Error("not used");
  }

  async updateSystemPrompt(_systemPrompt: string): Promise<agentModel.SystemPrompt> {
    throw new Error("not used");
  }

  async createEmbeddedSignupSession(): Promise<whatsappModel.EmbeddedSignupSession> {
    throw new Error("not used");
  }

  async getWhatsappConnection(): Promise<whatsappModel.WhatsappConnection> {
    throw new Error("not used");
  }

  async listConversations(): Promise<conversationModel.ConversationSummary[]> {
    throw new Error("not used");
  }

  async listConversationMessages(
    _conversationId: string
  ): Promise<conversationModel.ConversationMessage[]> {
    throw new Error("not used");
  }

  async updateConversationControlMode(
    _conversationId: string,
    _controlMode: "AI" | "HUMAN"
  ): Promise<conversationModel.ControlMode> {
    throw new Error("not used");
  }

  async listBlacklist(): Promise<blacklistModel.BlacklistEntry[]> {
    throw new Error("not used");
  }

  async addBlacklist(_whatsappUserId: string): Promise<blacklistModel.BlacklistEntry> {
    throw new Error("not used");
  }

  async removeBlacklist(_whatsappUserId: string): Promise<void> {
    return;
  }
}

vitestModule.describe("AuthUseCase", () => {
  vitestModule.it("bootstraps session from refresh token", async () => {
    const api = new FakeBackendApi();
    const tokenSession = new InMemoryTokenSession(null, "refresh-old");
    const authUseCase = new authUseCaseModule.AuthUseCase(api, tokenSession);

    const hasSession = await authUseCase.bootstrapSession();

    vitestModule.expect(hasSession).toBe(true);
    vitestModule.expect(api.refreshCalls).toBe(1);
    vitestModule.expect(tokenSession.getAccessToken()).toBe("access-new");
    vitestModule.expect(tokenSession.getRefreshToken()).toBe("refresh-new");
  });
});
