export interface TenantSummary {
  tenantId: string;
  tenantName: string;
  professionalName: string;
  patientCount: number;
  conversationCount: number;
  activeConversationsToday: number;
  manualAppointmentCountUpcoming: number;
  pendingReminderCount: number;
  totalRevenueCopThisMonth: number;
  lastActivityAt: string | null;
  ownerEmail: string;
  ownerIsActive: boolean;
}

export interface GlobalMetrics {
  tenantsCount: number;
  tenantsActive: number;
  totalPatients: number;
  totalConversations: number;
  activeConversationsToday: number;
  totalReminders: number;
  pendingReminders: number;
  totalRevenueCopThisMonth: number;
  controlModeDistribution: { ai: number; human: number };
  topTenantsByConversations: TenantSummary[];
}
