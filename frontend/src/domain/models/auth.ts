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

export interface AcceptInvitationInput {
  token: string;
  password: string;
}

export interface RequestPasswordResetInput {
  email: string;
}

export interface ConfirmPasswordResetInput {
  token: string;
  password: string;
}
