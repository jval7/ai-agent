export type WhatsappConnectionStatus = "DISCONNECTED" | "PENDING" | "CONNECTED";

export interface EmbeddedSignupSession {
  state: string;
  connectUrl: string;
  appId: string;
  configId: string;
}

export interface EmbeddedSignupCompleteRequest {
  code?: string;
  state: string;
  registrationPin?: string;
  originUrl?: string;
  accessToken?: string;
  phoneNumberId?: string;
  wabaId?: string;
}

export interface WhatsappConnection {
  tenantId: string;
  status: WhatsappConnectionStatus;
  phoneNumberId: string | null;
  businessAccountId: string | null;
}
