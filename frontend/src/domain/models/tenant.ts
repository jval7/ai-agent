export interface TenantProfile {
  tenantId: string;
  name: string;
  professionalName: string | null;
  sessionDurationMinutes: number;
}

export interface UpdateTenantProfileInput {
  professionalName: string | null;
  sessionDurationMinutes?: number;
}
