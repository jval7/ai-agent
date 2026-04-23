export interface SystemPrompt {
  tenantId: string;
  systemPrompt: string;
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
}

export interface UpdateAgentSettingsInput {
  messageDebounceDelaySeconds: number;
  appointmentReminderEnabled: boolean;
  appointmentReminderDaysBefore: number | null;
  appointmentReminderAttendanceTemplateName: string | null;
  appointmentReminderPaymentTemplateName: string | null;
  paymentDetailsText: string | null;
}
