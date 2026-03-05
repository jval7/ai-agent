export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresInSeconds: number;
}

export interface LoginInput {
  email: string;
  password: string;
}

export type AuthStatus = "loading" | "authenticated" | "anonymous";
