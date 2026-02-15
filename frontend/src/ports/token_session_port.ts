export interface TokenSessionPort {
  getAccessToken(): string | null;
  setAccessToken(token: string): void;
  clearAccessToken(): void;
  getRefreshToken(): string | null;
  setRefreshToken(token: string): void;
  clearRefreshToken(): void;
  clearAll(): void;
}
