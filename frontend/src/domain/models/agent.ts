export type Weekday = "MON" | "TUE" | "WED" | "THU" | "FRI" | "SAT" | "SUN";
export type Modality = "PRESENCIAL" | "VIRTUAL";

export interface AssistantIdentity {
  assistantName: string | null;
  professionalTitle: string | null;
  professionalName: string | null;
  professionalAddressTerm: string | null;
  mainCity: string | null;
  tone: string | null;
  languages: string[];
}

export interface TariffPrice {
  currency: string;
  amount: number;
}

export interface TariffOption {
  label: string;
  description: string | null;
  prices: TariffPrice[];
}

export type TargetPatient = "NEW" | "RETURNING";

export interface ServiceOffering {
  name: string | null;
  description: string | null;
  modalities: Modality[];
  targetPatients: TargetPatient[];
  tariffs: TariffOption[];
}

export interface PaymentMethod {
  currency: string;
  methodName: string;
  holder: string | null;
  instructions: string | null;
  appliesWhen: string | null;
}

export interface ProfessionalContext {
  approach: string | null;
  commonTopics: string[];
  servicesNotOffered: string[];
  coverageNotes: string | null;
}

export interface ProfessionalProfile {
  tenantId: string;
  identity: AssistantIdentity | null;
  professionalContext: ProfessionalContext | null;
  services: ServiceOffering[];
  paymentMethods: PaymentMethod[];
}

export interface UpdateProfessionalProfileInput {
  identity: AssistantIdentity | null;
  professionalContext: ProfessionalContext | null;
  services: ServiceOffering[];
  paymentMethods: PaymentMethod[];
}

export interface SystemPrompt {
  tenantId: string;
  systemPrompt: string;
}

export interface OfficeLocation {
  address: string;
  arrivalInstructions: string | null;
}

export type PaymentTiming = "BEFORE_SESSION" | "AFTER_SESSION";

export interface AgentSettings {
  tenantId: string;
  messageDebounceDelaySeconds: number;
  assistantEnabled: boolean;
  appointmentReminderEnabled: boolean;
  appointmentReminderDaysBefore: number | null;
  appointmentReminderAttendanceTemplateName: string | null;
  appointmentReminderPaymentTemplateName: string | null;
  paymentDetailsText: string | null;
  officeLocation: OfficeLocation | null;
  paymentTiming: PaymentTiming;
}

export interface UpdateAgentSettingsInput {
  messageDebounceDelaySeconds: number;
  assistantEnabled: boolean;
  appointmentReminderEnabled: boolean;
  appointmentReminderDaysBefore: number | null;
  appointmentReminderAttendanceTemplateName: string | null;
  appointmentReminderPaymentTemplateName: string | null;
  paymentDetailsText: string | null;
  officeLocation: OfficeLocation | null;
  paymentTiming: PaymentTiming;
}
