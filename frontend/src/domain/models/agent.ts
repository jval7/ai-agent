export interface SystemPrompt {
  tenantId: string;
  systemPrompt: string;
}

export interface AgentSettings {
  tenantId: string;
  messageDebounceDelaySeconds: number;
  appointmentReminderEnabled: boolean;
  appointmentReminderDaysBefore: number | null;
  appointmentReminderTemplateName: string | null;
  appointmentReminderTemplateLanguage: string;
}

export interface UpdateAgentSettingsInput {
  messageDebounceDelaySeconds: number;
  appointmentReminderEnabled: boolean;
  appointmentReminderDaysBefore: number | null;
  appointmentReminderTemplateName: string | null;
  appointmentReminderTemplateLanguage: string;
}
