export type WhatsappConnectionStatus = "DISCONNECTED" | "PENDING" | "CONNECTED";

export interface EmbeddedSignupSession {
  state: string;
  connectUrl: string;
}

export interface WhatsappConnection {
  tenantId: string;
  status: WhatsappConnectionStatus;
  phoneNumberId: string | null;
  businessAccountId: string | null;
}
