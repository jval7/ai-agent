import * as vitestModule from "vitest";

import type * as backendApiPort from "@ports/backend_api_port";

import * as onboardingUseCaseModule from "./onboarding_use_case";

vitestModule.describe("OnboardingUseCase", () => {
  vitestModule.it("delegates whatsapp/google/status operations to api port", async () => {
    const apiMock = {
      getWhatsappConnection: vitestModule.vi.fn(async () => ({
        tenantId: "tenant-1",
        status: "CONNECTED",
        phoneNumberId: "phone-1",
        businessAccountId: "business-1"
      })),
      createEmbeddedSignupSession: vitestModule.vi.fn(async () => ({
        state: "meta-state",
        connectUrl: "https://meta.test/connect"
      })),
      getGoogleCalendarConnection: vitestModule.vi.fn(async () => ({
        tenantId: "tenant-1",
        status: "CONNECTED",
        calendarId: "primary",
        professionalTimezone: "America/Bogota",
        connectedAt: "2026-03-01T00:00:00Z"
      })),
      createGoogleOauthSession: vitestModule.vi.fn(async () => ({
        state: "google-state",
        connectUrl: "https://google.test/connect"
      })),
      getOnboardingStatus: vitestModule.vi.fn(async () => ({
        whatsappConnected: true,
        googleCalendarConnected: true,
        ready: true
      }))
    } as Partial<backendApiPort.BackendApiPort> as backendApiPort.BackendApiPort;

    const useCase = new onboardingUseCaseModule.OnboardingUseCase(apiMock);

    const whatsapp = await useCase.getWhatsappConnectionStatus();
    const whatsappSession = await useCase.createWhatsappSession();
    const google = await useCase.getGoogleCalendarConnectionStatus();
    const googleSession = await useCase.createGoogleSession();
    const onboardingStatus = await useCase.getOnboardingStatus();

    vitestModule.expect(whatsapp.status).toBe("CONNECTED");
    vitestModule.expect(whatsappSession.state).toBe("meta-state");
    vitestModule.expect(google.professionalTimezone).toBe("America/Bogota");
    vitestModule.expect(googleSession.state).toBe("google-state");
    vitestModule.expect(onboardingStatus.ready).toBe(true);
  });
});
