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

export interface GoogleOauthSessionApiResponse {
  state: string;
  connect_url: string;
}

export interface WhatsappConnectionApiResponse {
  tenant_id: string;
  status: "DISCONNECTED" | "PENDING" | "CONNECTED";
  phone_number_id: string | null;
  business_account_id: string | null;
}

export interface GoogleCalendarConnectionApiResponse {
  tenant_id: string;
  status: "DISCONNECTED" | "PENDING" | "CONNECTED";
  calendar_id: string | null;
  professional_timezone: string | null;
  connected_at: string | null;
}

export interface OnboardingStatusApiResponse {
  whatsapp_connected: boolean;
  google_calendar_connected: boolean;
  ready: boolean;
}

export interface GoogleCalendarBusyIntervalApiResponse {
  start_at: string;
  end_at: string;
}

export interface GoogleCalendarAvailabilityApiResponse {
  tenant_id: string;
  calendar_id: string;
  timezone: string;
  busy_intervals: GoogleCalendarBusyIntervalApiResponse[];
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

export interface SchedulingSlotApiResponse {
  slot_id: string;
  start_at: string;
  end_at: string;
  timezone: string;
  status: "PROPOSED" | "BOOKED" | "REJECTED" | "UNAVAILABLE";
}

export interface SchedulingRequestSummaryApiResponse {
  request_id: string;
  conversation_id: string;
  whatsapp_user_id: string;
  request_kind: "INITIAL" | "RETRY";
  status: "AWAITING_PROFESSIONAL_SLOTS" | "AWAITING_PATIENT_CHOICE" | "BOOKED" | "HUMAN_HANDOFF";
  round_number: number;
  patient_preference_note: string;
  rejection_summary: string | null;
  professional_note: string | null;
  selected_slot_id: string | null;
  calendar_event_id: string | null;
  created_at: string;
  updated_at: string;
  slots: SchedulingSlotApiResponse[];
}

export interface SchedulingRequestListApiResponse {
  items: SchedulingRequestSummaryApiResponse[];
}

export interface SubmitProfessionalSlotsApiRequest {
  slots: {
    slot_id: string;
    start_at: string;
    end_at: string;
    timezone: string;
  }[];
  professional_note: string | null;
}

export interface SubmitProfessionalSlotsApiResponse {
  status: "AWAITING_PATIENT_CHOICE";
  slot_batch_id: string;
  outbound_message_id: string;
  assistant_text: string;
}

export interface ApiErrorResponse {
  detail: string;
  request_id?: string;
}
