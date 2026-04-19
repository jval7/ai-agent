import type * as tenantModel from "@domain/models/tenant";
import type * as backendApiPort from "@ports/backend_api_port";

export class TenantUseCase {
  private readonly api: backendApiPort.BackendApiPort;

  constructor(api: backendApiPort.BackendApiPort) {
    this.api = api;
  }

  async getProfile(): Promise<tenantModel.TenantProfile> {
    return this.api.getTenantProfile();
  }

  async updateProfile(
    input: tenantModel.UpdateTenantProfileInput
  ): Promise<tenantModel.TenantProfile> {
    return this.api.updateTenantProfile(input);
  }
}
