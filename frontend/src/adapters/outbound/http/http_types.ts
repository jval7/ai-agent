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

export interface PatientApiResponse {
  tenant_id: string;
  whatsapp_user_id: string;
  first_name: string;
  last_name: string;
  email: string;
  age: number;
  consultation_reason: string;
  location: string;
  phone: string;
  created_at: string;
}

export interface PatientListApiResponse {
  items: PatientApiResponse[];
}

export interface CreatePatientApiRequest {
  whatsapp_user_id: string;
  first_name: string;
  last_name: string;
  email: string;
  age: number;
  consultation_reason: string;
  location: string;
  phone: string;
}

export interface UpdatePatientApiRequest {
  first_name: string;
  last_name: string;
  email: string;
  age: number;
  consultation_reason: string;
  location: string;
  phone: string;
}

export interface ManualAppointmentApiResponse {
  appointment_id: string;
  tenant_id: string;
  patient_whatsapp_user_id: string;
  status: "SCHEDULED" | "CANCELLED";
  calendar_event_id: string | null;
  start_at: string;
  end_at: string;
  timezone: string;
  summary: string;
  payment_amount_cop: number | null;
  payment_method: "CASH" | "TRANSFER" | null;
  payment_status: "PENDING" | "PAID";
  payment_updated_at: string | null;
  created_at: string;
  updated_at: string;
  cancelled_at: string | null;
}

export interface ManualAppointmentListApiResponse {
  items: ManualAppointmentApiResponse[];
}

export interface CreateManualAppointmentApiRequest {
  patient_whatsapp_user_id: string;
  start_at: string;
  end_at: string;
  timezone: string;
  summary: string | null;
}

export interface RescheduleManualAppointmentApiRequest {
  start_at: string;
  end_at: string;
  timezone: string;
  summary: string | null;
}

export interface CancelManualAppointmentApiRequest {
  reason: string | null;
}

export interface UpdateManualAppointmentPaymentApiRequest {
  payment_amount_cop: number;
  payment_method: "CASH" | "TRANSFER";
  payment_status: "PENDING" | "PAID";
}

export interface SchedulingSlotApiResponse {
  slot_id: string;
  start_at: string;
  end_at: string;
  timezone: string;
  status: "PROPOSED" | "SELECTED" | "BOOKED" | "REJECTED" | "UNAVAILABLE";
}

export interface SchedulingRequestSummaryApiResponse {
  request_id: string;
  conversation_id: string;
  whatsapp_user_id: string;
  request_kind: "INITIAL" | "RETRY";
  status:
    | "AWAITING_CONSULTATION_REVIEW"
    | "AWAITING_CONSULTATION_DETAILS"
    | "AWAITING_PATIENT_CHOICE"
    | "AWAITING_PAYMENT_CONFIRMATION"
    | "CONSULTATION_REJECTED"
    | "CANCELLED"
    | "BOOKED"
    | "HUMAN_HANDOFF";
  audience_type: "ADULTS" | "CHILDREN" | null;
  round_number: number;
  patient_preference_note: string | null;
  rejection_summary: string | null;
  professional_note: string | null;
  patient_first_name: string | null;
  patient_last_name: string | null;
  patient_age: number | null;
  consultation_reason: string | null;
  consultation_details: string | null;
  appointment_modality: "PRESENCIAL" | "VIRTUAL" | null;
  patient_location: string | null;
  slot_options_map: Record<string, string>;
  selected_slot_id: string | null;
  calendar_event_id: string | null;
  payment_amount_cop: number | null;
  payment_method: "CASH" | "TRANSFER" | null;
  payment_status: "PENDING" | "PAID";
  payment_updated_at: string | null;
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

export interface ResolveConsultationReviewApiRequest {
  decision: "REQUEST_MORE_INFO" | "REJECT";
  professional_note: string | null;
}

export interface ResolveConsultationReviewApiResponse {
  status:
    | "AWAITING_CONSULTATION_REVIEW"
    | "AWAITING_CONSULTATION_DETAILS"
    | "AWAITING_PATIENT_CHOICE"
    | "AWAITING_PAYMENT_CONFIRMATION"
    | "CONSULTATION_REJECTED"
    | "CANCELLED"
    | "BOOKED"
    | "HUMAN_HANDOFF";
  outbound_message_id: string;
  assistant_text: string;
}

export interface ResolvePaymentReviewApiRequest {
  decision: "APPROVE" | "SEND_REMINDER";
  professional_note: string | null;
}

export interface ResolvePaymentReviewApiResponse {
  status:
    | "AWAITING_CONSULTATION_REVIEW"
    | "AWAITING_CONSULTATION_DETAILS"
    | "AWAITING_PATIENT_CHOICE"
    | "AWAITING_PAYMENT_CONFIRMATION"
    | "CONSULTATION_REJECTED"
    | "CANCELLED"
    | "BOOKED"
    | "HUMAN_HANDOFF";
  outbound_message_id: string;
  assistant_text: string;
}

export interface RescheduleBookedSlotApiRequest {
  start_at: string;
  end_at: string;
  timezone: string;
  event_summary: string | null;
}

export interface CancelBookedSlotApiRequest {
  reason: string | null;
}

export interface UpdateBookedSlotPaymentApiRequest {
  payment_amount_cop: number;
  payment_method: "CASH" | "TRANSFER";
  payment_status: "PENDING" | "PAID";
}

export interface ApiErrorResponse {
  detail: string;
  request_id?: string;
}
