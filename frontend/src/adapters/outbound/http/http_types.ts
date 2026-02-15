export interface AuthTokensApiResponse {
  access_token: string;
  refresh_token: string;
  expires_in_seconds: number;
  token_type: string;
}

export interface SystemPromptApiResponse {
  tenant_id: string;
  system_prompt: string;
}

export interface EmbeddedSignupSessionApiResponse {
  state: string;
  connect_url: string;
}

export interface WhatsappConnectionApiResponse {
  tenant_id: string;
  status: "DISCONNECTED" | "PENDING" | "CONNECTED";
  phone_number_id: string | null;
  business_account_id: string | null;
}

export interface ConversationSummaryApiResponse {
  conversation_id: string;
  whatsapp_user_id: string;
  last_message_preview: string | null;
  updated_at: string;
  control_mode: "AI" | "HUMAN";
}

export interface ConversationListApiResponse {
  items: ConversationSummaryApiResponse[];
}

export interface MessageApiResponse {
  message_id: string;
  conversation_id: string;
  role: string;
  direction: string;
  content: string;
  created_at: string;
}

export interface MessageListApiResponse {
  items: MessageApiResponse[];
}

export interface ConversationControlModeApiResponse {
  conversation_id: string;
  tenant_id: string;
  control_mode: "AI" | "HUMAN";
  updated_at: string;
}

export interface BlacklistEntryApiResponse {
  tenant_id: string;
  whatsapp_user_id: string;
  created_at: string;
}

export interface BlacklistListApiResponse {
  items: BlacklistEntryApiResponse[];
}

export interface ApiErrorResponse {
  detail: string;
}
