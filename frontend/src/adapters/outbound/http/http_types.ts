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

export interface AgentSettingsApiResponse {
  tenant_id: string;
  message_debounce_delay_seconds: number;
}

export interface EmbeddedSignupSessionApiResponse {
  state: string;
  connect_url: string;
  app_id: string;
  config_id: string;
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

export interface ConversationTagApiResponse {
  id: string;
  name: string;
  slug: string;
  color: string;
  tag_type: "SYSTEM" | "CUSTOM";
}

export interface ConversationSummaryApiResponse {
  conversation_id: string;
  whatsapp_user_id: string;
  contact_name?: string | null;
  last_message_preview: string | null;
  updated_at: string;
  control_mode: "AI" | "HUMAN";
  tags?: ConversationTagApiResponse[];
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
  location: string;
  phone_prefix: string | null;
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
  location: string;
  phone_prefix: string | null;
  phone: string;
}

export interface UpdatePatientApiRequest {
  first_name: string;
  last_name: string;
  email: string;
  age: number;
  location: string;
  phone_prefix: string | null;
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
  is_virtual: boolean;
  meet_url: string | null;
  payment_amount_cop: number | null;
  payment_currency: "COP" | "USD" | null;
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
  is_virtual: boolean;
  payment_amount_cop: number;
  payment_currency: "COP" | "USD";
  payment_status: "PENDING" | "PAID";
  payment_method: "CASH" | "TRANSFER" | null;
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
  payment_currency: "COP" | "USD";
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
    | "SESSION_CLOSED"
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
  payment_currency: "COP" | "USD";
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
  payment_amount_cop: number | null;
  payment_currency: "COP" | "USD";
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
  payment_currency: "COP" | "USD";
  payment_method: "CASH" | "TRANSFER";
  payment_status: "PENDING" | "PAID";
}

export interface SendMessageApiRequest {
  message_text: string;
}

export interface MessageSentApiResponse {
  message_id: string;
  conversation_id: string;
  role: string;
  content: string;
  created_at: string;
}

export interface ApiErrorResponse {
  detail: string;
  request_id?: string;
}

export interface TemplateComponentApiResponse {
  type: string;
  text: string;
  example_values?: string[];
}

export interface WhatsappTemplateApiResponse {
  id: string;
  name: string;
  category: string;
  language: string;
  status: string;
  components: TemplateComponentApiResponse[];
}

export interface TemplateListApiResponse {
  templates: WhatsappTemplateApiResponse[];
}

export interface CreateTemplateApiRequest {
  name: string;
  category: string;
  language: string;
  components: TemplateComponentApiResponse[];
}

export interface TenantProfileResponse {
  tenant_id: string;
  name: string;
  professional_name: string | null;
}

export interface UpdateTenantProfileRequest {
  professional_name: string | null;
}

// --- Professional Profile wire types ---

export interface AssistantIdentityApiResponse {
  assistant_name: string | null;
  professional_title: string | null;
  professional_address_term: string | null;
  main_city: string | null;
  tone: string | null;
  languages: string[];
}

export interface ScheduleBlockApiResponse {
  weekday_from: string;
  weekday_to: string | null;
  start_time: string;
  end_time: string;
}

export interface TariffOptionApiResponse {
  label: string;
  amount: number;
  currency: string;
  discount_percent: number | null;
}

export interface ServiceOfferingApiResponse {
  name: string | null;
  description: string | null;
  audience: string | null;
  modalities: string[];
  tariffs_local: TariffOptionApiResponse[];
  tariffs_foreign: TariffOptionApiResponse[];
}

export interface PaymentMethodApiResponse {
  currency: string;
  method_name: string;
  holder: string | null;
  instructions: string | null;
  applies_when: string | null;
}

export interface ProfessionalContextApiResponse {
  approach: string | null;
  common_topics: string[];
  services_not_offered: string[];
  coverage_notes: string | null;
}

export interface ProfessionalProfileApiResponse {
  tenant_id: string;
  identity: AssistantIdentityApiResponse | null;
  professional_context: ProfessionalContextApiResponse | null;
  services: ServiceOfferingApiResponse[];
  presencial_schedule: ScheduleBlockApiResponse[];
  virtual_schedule: ScheduleBlockApiResponse[];
  payment_methods: PaymentMethodApiResponse[];
}

export interface UpdateProfessionalProfileApiRequest {
  identity: AssistantIdentityApiResponse | null;
  professional_context: ProfessionalContextApiResponse | null;
  services: ServiceOfferingApiResponse[];
  presencial_schedule: ScheduleBlockApiResponse[];
  virtual_schedule: ScheduleBlockApiResponse[];
  payment_methods: PaymentMethodApiResponse[];
}
