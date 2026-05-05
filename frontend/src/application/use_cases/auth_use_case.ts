import type * as authModel from "@domain/models/auth";
import type * as backendApiPort from "@ports/backend_api_port";
import type * as tokenSessionPort from "@ports/token_session_port";
import * as apiErrorModule from "@shared/http/api_error";

export class AuthUseCase {
  private readonly api: backendApiPort.BackendApiPort;
  private readonly tokenSession: tokenSessionPort.TokenSessionPort;

  constructor(api: backendApiPort.BackendApiPort, tokenSession: tokenSessionPort.TokenSessionPort) {
    this.api = api;
    this.tokenSession = tokenSession;
  }

  async bootstrapSession(): Promise<authModel.UserProfile | null> {
    if (this.tokenSession.getAccessToken() !== null) {
      return this.getProfile();
    }

    const refreshToken = this.tokenSession.getRefreshToken();
    if (refreshToken === null) {
      return null;
    }

    try {
      const tokens = await this.api.refresh(refreshToken);
      this.persistTokens(tokens);
      return this.getProfile();
    } catch (error: unknown) {
      if (error instanceof apiErrorModule.ApiError && error.statusCode === 401) {
        this.tokenSession.clearAll();
        return null;
      }
      if (error instanceof TypeError) {
        return null;
      }
      throw error;
    }
  }

  async login(input: authModel.LoginInput): Promise<authModel.UserProfile> {
    const tokens = await this.api.login(input);
    this.persistTokens(tokens);
    const profile = await this.getProfile();
    if (profile === null) {
      throw new Error("Failed to fetch user profile after login");
    }
    return profile;
  }

  async acceptInvitation(input: authModel.AcceptInvitationInput): Promise<authModel.UserProfile> {
    const tokens = await this.api.acceptInvitation(input);
    this.persistTokens(tokens);
    const profile = await this.getProfile();
    if (profile === null) {
      throw new Error("Failed to fetch user profile after accepting invitation");
    }
    return profile;
  }

  async requestPasswordReset(input: authModel.RequestPasswordResetInput): Promise<void> {
    await this.api.requestPasswordReset(input);
  }

  async confirmPasswordReset(input: authModel.ConfirmPasswordResetInput): Promise<void> {
    await this.api.confirmPasswordReset(input);
  }

  async logout(): Promise<void> {
    const refreshToken = this.tokenSession.getRefreshToken();
    if (refreshToken !== null) {
      try {
        await this.api.logout(refreshToken);
      } catch (error: unknown) {
        if (!(error instanceof apiErrorModule.ApiError) && !(error instanceof TypeError)) {
          throw error;
        }
      }
    }

    this.tokenSession.clearAll();
  }

  async getProfile(): Promise<authModel.UserProfile | null> {
    try {
      return await this.api.getMe();
    } catch (error: unknown) {
      if (error instanceof apiErrorModule.ApiError || error instanceof TypeError) {
        return null;
      }
      throw error;
    }
  }

  hasActiveSession(): boolean {
    return (
      this.tokenSession.getAccessToken() !== null || this.tokenSession.getRefreshToken() !== null
    );
  }

  private persistTokens(tokens: authModel.AuthTokens): void {
    this.tokenSession.setAccessToken(tokens.accessToken);
    this.tokenSession.setRefreshToken(tokens.refreshToken);
  }
}
