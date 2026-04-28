export interface TenantProfile {
  tenantId: string;
  name: string;
  professionalName: string | null;
}

export interface UpdateTenantProfileInput {
  professionalName: string | null;
}
