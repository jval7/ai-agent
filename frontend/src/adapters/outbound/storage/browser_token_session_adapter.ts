import type * as tokenSessionPort from "@ports/token_session_port";

const REFRESH_TOKEN_STORAGE_KEY = "AI_AGENT_REFRESH_TOKEN";

export class BrowserTokenSessionAdapter implements tokenSessionPort.TokenSessionPort {
  private accessToken: string | null;

  constructor() {
    this.accessToken = null;
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
    return window.localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
  }

  setRefreshToken(token: string): void {
    window.localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, token);
  }

  clearRefreshToken(): void {
    window.localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
  }

  clearAll(): void {
    this.clearAccessToken();
    this.clearRefreshToken();
  }
}
