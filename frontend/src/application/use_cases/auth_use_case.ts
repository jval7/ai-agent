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

  async bootstrapSession(): Promise<boolean> {
    if (this.tokenSession.getAccessToken() !== null) {
      return true;
    }

    const refreshToken = this.tokenSession.getRefreshToken();
    if (refreshToken === null) {
      return false;
    }

    try {
      const tokens = await this.api.refresh(refreshToken);
      this.persistTokens(tokens);
      return true;
    } catch (error: unknown) {
      if (error instanceof apiErrorModule.ApiError && error.statusCode === 401) {
        this.tokenSession.clearAll();
        return false;
      }
      if (error instanceof TypeError) {
        return false;
      }
      throw error;
    }
  }

  async login(input: authModel.LoginInput): Promise<void> {
    const tokens = await this.api.login(input);
    this.persistTokens(tokens);
  }

  async register(input: authModel.RegisterInput): Promise<void> {
    const tokens = await this.api.register(input);
    this.persistTokens(tokens);
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
