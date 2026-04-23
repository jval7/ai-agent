export interface BillingPreflightResult {
  ok: boolean;
  recipientPhoneNumber: string;
}

export type BillingPreflightErrorCode =
  | "WHATSAPP_BILLING_NOT_CONFIGURED"
  | "WHATSAPP_PREFLIGHT_FAILED";

export interface BillingPreflightErrorDetail {
  code: BillingPreflightErrorCode;
  metaErrorCode: number | null;
  message: string;
}
