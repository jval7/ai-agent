import type * as agentModel from "@domain/models/agent";
import type * as authModel from "@domain/models/auth";
import type * as blacklistModel from "@domain/models/blacklist";
import type * as conversationModel from "@domain/models/conversation";
import type * as whatsappModel from "@domain/models/whatsapp";
import type * as backendApiPort from "@ports/backend_api_port";
import type * as tokenSessionPort from "@ports/token_session_port";
import * as apiErrorModule from "@shared/http/api_error";

import type * as httpTypes from "./http_types";

interface RequestOptions {
  method: "GET" | "POST" | "PUT" | "DELETE";
  authRequired: boolean;
  body?: string;
  retryOnUnauthorized?: boolean;
}

export class BackendApiAdapter implements backendApiPort.BackendApiPort {
  private readonly baseUrl: string;
  private readonly tokenSession: tokenSessionPort.TokenSessionPort;
  private refreshInFlight: Promise<string | null> | null;

  constructor(baseUrl: string, tokenSession: tokenSessionPort.TokenSessionPort) {
    this.baseUrl = baseUrl;
    this.tokenSession = tokenSession;
    this.refreshInFlight = null;
  }

  async register(input: authModel.RegisterInput): Promise<authModel.AuthTokens> {
    const payload = await this.request<httpTypes.AuthTokensApiResponse>("/v1/auth/register", {
      method: "POST",
      authRequired: false,
      body: JSON.stringify({
        tenant_name: input.tenantName,
        email: input.email,
        password: input.password
      })
    });
    return mapAuthTokens(payload);
  }

  async login(input: authModel.LoginInput): Promise<authModel.AuthTokens> {
    const payload = await this.request<httpTypes.AuthTokensApiResponse>("/v1/auth/login", {
      method: "POST",
      authRequired: false,
      body: JSON.stringify({
        email: input.email,
        password: input.password
      })
    });
    return mapAuthTokens(payload);
  }

  async refresh(refreshToken: string): Promise<authModel.AuthTokens> {
    const payload = await this.refreshTokens(refreshToken);
    return mapAuthTokens(payload);
  }

  async logout(refreshToken: string): Promise<void> {
    await this.request<void>("/v1/auth/logout", {
      method: "POST",
      authRequired: true,
      body: JSON.stringify({
        refresh_token: refreshToken
      })
    });
  }

  async getSystemPrompt(): Promise<agentModel.SystemPrompt> {
    const payload = await this.request<httpTypes.SystemPromptApiResponse>(
      "/v1/agent/system-prompt",
      {
        method: "GET",
        authRequired: true
      }
    );
    return {
      tenantId: payload.tenant_id,
      systemPrompt: payload.system_prompt
    };
  }

  async updateSystemPrompt(systemPrompt: string): Promise<agentModel.SystemPrompt> {
    const payload = await this.request<httpTypes.SystemPromptApiResponse>(
      "/v1/agent/system-prompt",
      {
        method: "PUT",
        authRequired: true,
        body: JSON.stringify({
          system_prompt: systemPrompt
        })
      }
    );
    return {
      tenantId: payload.tenant_id,
      systemPrompt: payload.system_prompt
    };
  }

  async createEmbeddedSignupSession(): Promise<whatsappModel.EmbeddedSignupSession> {
    const payload = await this.request<httpTypes.EmbeddedSignupSessionApiResponse>(
      "/v1/whatsapp/embedded-signup/session",
      {
        method: "POST",
        authRequired: true
      }
    );

    return {
      state: payload.state,
      connectUrl: payload.connect_url
    };
  }

  async getWhatsappConnection(): Promise<whatsappModel.WhatsappConnection> {
    const payload = await this.request<httpTypes.WhatsappConnectionApiResponse>(
      "/v1/whatsapp/connection",
      {
        method: "GET",
        authRequired: true
      }
    );

    return {
      tenantId: payload.tenant_id,
      status: payload.status,
      phoneNumberId: payload.phone_number_id,
      businessAccountId: payload.business_account_id
    };
  }

  async listConversations(): Promise<conversationModel.ConversationSummary[]> {
    const payload = await this.request<httpTypes.ConversationListApiResponse>("/v1/conversations", {
      method: "GET",
      authRequired: true
    });

    return payload.items.map((item) => ({
      conversationId: item.conversation_id,
      whatsappUserId: item.whatsapp_user_id,
      lastMessagePreview: item.last_message_preview,
      updatedAt: item.updated_at,
      controlMode: item.control_mode
    }));
  }

  async listConversationMessages(
    conversationId: string
  ): Promise<conversationModel.ConversationMessage[]> {
    const payload = await this.request<httpTypes.MessageListApiResponse>(
      `/v1/conversations/${conversationId}/messages`,
      {
        method: "GET",
        authRequired: true
      }
    );

    return payload.items.map((item) => ({
      messageId: item.message_id,
      conversationId: item.conversation_id,
      role: item.role,
      direction: item.direction,
      content: item.content,
      createdAt: item.created_at
    }));
  }

  async updateConversationControlMode(
    conversationId: string,
    controlMode: conversationModel.ControlMode
  ): Promise<conversationModel.ControlMode> {
    const payload = await this.request<httpTypes.ConversationControlModeApiResponse>(
      `/v1/conversations/${conversationId}/control-mode`,
      {
        method: "PUT",
        authRequired: true,
        body: JSON.stringify({
          control_mode: controlMode
        })
      }
    );

    return payload.control_mode;
  }

  async listBlacklist(): Promise<blacklistModel.BlacklistEntry[]> {
    const payload = await this.request<httpTypes.BlacklistListApiResponse>("/v1/blacklist", {
      method: "GET",
      authRequired: true
    });

    return payload.items.map((item) => ({
      tenantId: item.tenant_id,
      whatsappUserId: item.whatsapp_user_id,
      createdAt: item.created_at
    }));
  }

  async addBlacklist(whatsappUserId: string): Promise<blacklistModel.BlacklistEntry> {
    const payload = await this.request<httpTypes.BlacklistEntryApiResponse>("/v1/blacklist", {
      method: "POST",
      authRequired: true,
      body: JSON.stringify({
        whatsapp_user_id: whatsappUserId
      })
    });

    return {
      tenantId: payload.tenant_id,
      whatsappUserId: payload.whatsapp_user_id,
      createdAt: payload.created_at
    };
  }

  async removeBlacklist(whatsappUserId: string): Promise<void> {
    await this.request<void>(`/v1/blacklist/${whatsappUserId}`, {
      method: "DELETE",
      authRequired: true
    });
  }

  private async request<T>(path: string, options: RequestOptions): Promise<T> {
    const retryOnUnauthorized = options.retryOnUnauthorized ?? true;

    const headers = new Headers();
    headers.set("Content-Type", "application/json");

    if (options.authRequired) {
      const accessToken = this.tokenSession.getAccessToken();
      if (accessToken) {
        headers.set("Authorization", `Bearer ${accessToken}`);
      }
    }

    const requestInit: RequestInit = {
      method: options.method,
      headers
    };
    if (options.body !== undefined) {
      requestInit.body = options.body;
    }

    const response = await fetch(`${this.baseUrl}${path}`, requestInit);

    if (response.status === 401 && options.authRequired && retryOnUnauthorized) {
      const refreshedToken = await this.refreshAccessTokenWithLock();
      if (refreshedToken === null) {
        throw new apiErrorModule.ApiError(401, "token expired");
      }

      return this.request<T>(path, {
        ...options,
        retryOnUnauthorized: false
      });
    }

    if (!response.ok) {
      throw await this.parseError(response);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    const payload = (await response.json()) as T;
    return payload;
  }

  private async refreshAccessTokenWithLock(): Promise<string | null> {
    if (this.refreshInFlight !== null) {
      return this.refreshInFlight;
    }

    const refreshToken = this.tokenSession.getRefreshToken();
    if (refreshToken === null) {
      return null;
    }

    this.refreshInFlight = this.performRefresh(refreshToken);

    try {
      return await this.refreshInFlight;
    } finally {
      this.refreshInFlight = null;
    }
  }

  private async performRefresh(refreshToken: string): Promise<string | null> {
    try {
      const payload = await this.refreshTokens(refreshToken);
      const tokens = mapAuthTokens(payload);
      this.tokenSession.setAccessToken(tokens.accessToken);
      this.tokenSession.setRefreshToken(tokens.refreshToken);
      return tokens.accessToken;
    } catch (error: unknown) {
      if (!(error instanceof apiErrorModule.ApiError) && !(error instanceof TypeError)) {
        throw error;
      }
      this.tokenSession.clearAll();
      return null;
    }
  }

  private async refreshTokens(refreshToken: string): Promise<httpTypes.AuthTokensApiResponse> {
    const response = await fetch(`${this.baseUrl}/v1/auth/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        refresh_token: refreshToken
      })
    });

    if (!response.ok) {
      throw await this.parseError(response);
    }

    const payload = (await response.json()) as httpTypes.AuthTokensApiResponse;
    return payload;
  }

  private async parseError(response: Response): Promise<apiErrorModule.ApiError> {
    const fallbackMessage = `request failed with status ${response.status}`;
    const contentType = response.headers.get("content-type") ?? "";

    if (!contentType.includes("application/json")) {
      return new apiErrorModule.ApiError(response.status, fallbackMessage);
    }

    let payload: Partial<httpTypes.ApiErrorResponse>;
    try {
      payload = (await response.json()) as Partial<httpTypes.ApiErrorResponse>;
    } catch (error: unknown) {
      if (error instanceof SyntaxError) {
        return new apiErrorModule.ApiError(response.status, fallbackMessage);
      }
      throw error;
    }
    if (typeof payload.detail !== "string" || payload.detail.trim() === "") {
      return new apiErrorModule.ApiError(response.status, fallbackMessage);
    }

    return new apiErrorModule.ApiError(response.status, payload.detail);
  }
}

function mapAuthTokens(payload: httpTypes.AuthTokensApiResponse): authModel.AuthTokens {
  return {
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token,
    expiresInSeconds: payload.expires_in_seconds
  };
}
