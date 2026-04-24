export interface SystemPrompt {
  tenantId: string;
  systemPrompt: string;
}

export interface OfficeLocation {
  address: string;
  arrivalInstructions: string | null;
  accessNotes: string | null;
}

export interface AgentSettings {
  tenantId: string;
  messageDebounceDelaySeconds: number;
  appointmentReminderEnabled: boolean;
  appointmentReminderDaysBefore: number | null;
  appointmentReminderAttendanceTemplateName: string | null;
  appointmentReminderPaymentTemplateName: string | null;
  reminderBillingTestPhoneNumber: string | null;
  paymentDetailsText: string | null;
  officeLocation: OfficeLocation | null;
  virtualSessionInstructions: string | null;
}

export interface UpdateAgentSettingsInput {
  messageDebounceDelaySeconds: number;
  appointmentReminderEnabled: boolean;
  appointmentReminderDaysBefore: number | null;
  appointmentReminderAttendanceTemplateName: string | null;
  appointmentReminderPaymentTemplateName: string | null;
  paymentDetailsText: string | null;
  officeLocation: OfficeLocation | null;
  virtualSessionInstructions: string | null;
}
