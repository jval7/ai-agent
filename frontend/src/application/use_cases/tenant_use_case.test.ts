import * as vitestModule from "vitest";

import type * as backendApiPort from "@ports/backend_api_port";

import * as tenantUseCaseModule from "./tenant_use_case";

vitestModule.describe("TenantUseCase", () => {
  vitestModule.it("delegates tenant profile operations to api port", async () => {
    const profile = {
      tenantId: "tenant-1",
      name: "Dr. Ana Garcia",
      professionalName: "Dra. Ana Garcia",
      sessionDurationMinutes: 60
    };

    const getProfileMock = vitestModule.vi.fn(async () => profile);
    const updateProfileMock = vitestModule.vi.fn(async () => ({
      ...profile,
      professionalName: "Dra. Ana M. Garcia"
    }));

    const apiMock = {
      getTenantProfile: getProfileMock,
      updateTenantProfile: updateProfileMock
    } as Partial<backendApiPort.BackendApiPort> as backendApiPort.BackendApiPort;

    const useCase = new tenantUseCaseModule.TenantUseCase(apiMock);

    const result = await useCase.getProfile();
    vitestModule.expect(result.tenantId).toBe("tenant-1");
    vitestModule.expect(result.professionalName).toBe("Dra. Ana Garcia");
    vitestModule.expect(getProfileMock).toHaveBeenCalledTimes(1);

    const updated = await useCase.updateProfile({ professionalName: "Dra. Ana M. Garcia" });
    vitestModule.expect(updated.professionalName).toBe("Dra. Ana M. Garcia");
    vitestModule.expect(updateProfileMock).toHaveBeenCalledWith({
      professionalName: "Dra. Ana M. Garcia"
    });
  });
});
