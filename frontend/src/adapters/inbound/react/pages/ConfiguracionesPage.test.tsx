import * as reactQueryModule from "@tanstack/react-query";
import * as testingLibraryReactModule from "@testing-library/react";
import * as reactRouterDomModule from "react-router-dom";
import * as vitestModule from "vitest";

import type * as containerModule from "@infrastructure/di/container";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";

import * as configuracionesPageModule from "./ConfiguracionesPage";

function renderConfiguracionesPage(container: unknown, path = "/configuraciones") {
  const queryClient = new reactQueryModule.QueryClient({
    defaultOptions: {
      queries: {
        retry: false
      }
    }
  });

  return testingLibraryReactModule.render(
    <reactQueryModule.QueryClientProvider client={queryClient}>
      <appContainerContextModule.AppContainerProvider
        container={container as containerModule.AppContainer}
      >
        <reactRouterDomModule.MemoryRouter initialEntries={[path]}>
          <reactRouterDomModule.Routes>
            <reactRouterDomModule.Route
              element={<configuracionesPageModule.ConfiguracionesPage />}
              path="/configuraciones"
            />
          </reactRouterDomModule.Routes>
        </reactRouterDomModule.MemoryRouter>
      </appContainerContextModule.AppContainerProvider>
    </reactQueryModule.QueryClientProvider>
  );
}

function buildContainer(overrides: Record<string, unknown> = {}) {
  return {
    onboardingUseCase: {
      getWhatsappConnectionStatus: vitestModule.vi.fn(async () => ({
        tenantId: "tenant-1",
        status: "CONNECTED",
        phoneNumberId: "phone-1",
        businessAccountId: "business-1"
      })),
      getGoogleCalendarConnectionStatus: vitestModule.vi.fn(async () => ({
        tenantId: "tenant-1",
        status: "DISCONNECTED",
        calendarId: null,
        professionalTimezone: null,
        connectedAt: null
      })),
      getOnboardingStatus: vitestModule.vi.fn(async () => ({
        whatsappConnected: true,
        googleCalendarConnected: false,
        ready: false
      })),
      createWhatsappSession: vitestModule.vi.fn(async () => ({
        state: "meta-state",
        connectUrl: "https://meta.test/oauth"
      })),
      createGoogleSession: vitestModule.vi.fn(async () => ({
        state: "google-state",
        connectUrl: "https://google.test/oauth"
      }))
    },
    agentUseCase: {
      getSystemPrompt: vitestModule.vi.fn(async () => ({
        systemPrompt: "You are a helpful assistant"
      })),
      updateSystemPrompt: vitestModule.vi.fn(async () => undefined),
      getAgentSettings: vitestModule.vi.fn(async () => ({
        tenantId: "tenant-1",
        messageDebounceDelaySeconds: 5,
        appointmentReminderEnabled: false,
        appointmentReminderDaysBefore: null,
        appointmentReminderAttendanceTemplateName: null,
        appointmentReminderPaymentTemplateName: null,
        paymentDetailsText: null
      })),
      updateAgentSettings: vitestModule.vi.fn(async () => undefined)
    },
    whatsappTemplateUseCase: {
      listOfficialTemplateStatus: vitestModule.vi.fn(async () => [
        {
          kind: "ATTENDANCE",
          name: "appointment_reminder_attendance",
          metaStatus: "NOT_CREATED",
          rejectionReason: null
        },
        {
          kind: "PAYMENT",
          name: "appointment_reminder_payment",
          metaStatus: "NOT_CREATED",
          rejectionReason: null
        }
      ]),
      activateOfficialTemplate: vitestModule.vi.fn(async () => undefined),
      deactivateOfficialTemplate: vitestModule.vi.fn(async () => undefined)
    },
    tenantUseCase: {
      getProfile: vitestModule.vi.fn(async () => ({
        tenantId: "tenant-1",
        name: "Ana Garcia",
        professionalName: "Dra. Ana Garcia"
      })),
      updateProfile: vitestModule.vi.fn(async () => ({
        tenantId: "tenant-1",
        name: "Ana Garcia",
        professionalName: "Dra. Ana M. Garcia"
      }))
    },
    ...overrides
  };
}

vitestModule.describe("ConfiguracionesPage", () => {
  vitestModule.beforeEach(() => {
    vitestModule.vi.spyOn(appShellModule, "AppShell").mockImplementation((props) => {
      return <div>{props.children}</div>;
    });
  });

  vitestModule.afterEach(() => {
    vitestModule.vi.restoreAllMocks();
    vitestModule.vi.unstubAllGlobals();
  });

  vitestModule.it("redirects to google connect URL when connect button is clicked", async () => {
    const assignSpy = vitestModule.vi.fn();
    vitestModule.vi.stubGlobal("location", {
      assign: assignSpy
    });
    const container = buildContainer();

    renderConfiguracionesPage(container);

    const conexionesTab = await testingLibraryReactModule.screen.findByRole("button", {
      name: "Conexiones"
    });
    testingLibraryReactModule.fireEvent.click(conexionesTab);

    const googleButton = await testingLibraryReactModule.screen.findByRole("button", {
      name: "Conectar Google Calendar"
    });
    testingLibraryReactModule.fireEvent.click(googleButton);

    await testingLibraryReactModule.waitFor(() => {
      expect(assignSpy).toHaveBeenCalledWith("https://google.test/oauth");
    });
  });

  vitestModule.it("renders Perfil tab by default and shows professional name input", async () => {
    const container = buildContainer();

    renderConfiguracionesPage(container);

    const input = await testingLibraryReactModule.screen.findByLabelText("Nombre del profesional");
    vitestModule.expect(input).toBeInTheDocument();
    await testingLibraryReactModule.waitFor(() => {
      vitestModule.expect((input as HTMLInputElement).value).toBe("Dra. Ana Garcia");
    });
  });

  vitestModule.it("shows empty input when professionalName is null", async () => {
    const container = buildContainer({
      tenantUseCase: {
        getProfile: vitestModule.vi.fn(async () => ({
          tenantId: "tenant-1",
          name: "Ana Garcia",
          professionalName: null
        })),
        updateProfile: vitestModule.vi.fn(async () => ({
          tenantId: "tenant-1",
          name: "Ana Garcia",
          professionalName: null
        }))
      }
    });

    renderConfiguracionesPage(container);

    const input = await testingLibraryReactModule.screen.findByLabelText("Nombre del profesional");
    vitestModule.expect((input as HTMLInputElement).value).toBe("");
  });

  vitestModule.it("submits updated professional name and shows success banner", async () => {
    const updateProfileMock = vitestModule.vi.fn(async () => ({
      tenantId: "tenant-1",
      name: "Ana Garcia",
      professionalName: "Dra. Ana M. Garcia"
    }));
    const container = buildContainer({
      tenantUseCase: {
        getProfile: vitestModule.vi.fn(async () => ({
          tenantId: "tenant-1",
          name: "Ana Garcia",
          professionalName: "Dra. Ana Garcia"
        })),
        updateProfile: updateProfileMock
      }
    });

    renderConfiguracionesPage(container);

    const input = await testingLibraryReactModule.screen.findByLabelText("Nombre del profesional");
    await testingLibraryReactModule.waitFor(() => {
      vitestModule.expect((input as HTMLInputElement).value).toBe("Dra. Ana Garcia");
    });
    testingLibraryReactModule.fireEvent.change(input, {
      target: { value: "Dra. Ana M. Garcia" }
    });

    const saveButton = testingLibraryReactModule.screen.getByRole("button", { name: "Guardar" });
    testingLibraryReactModule.fireEvent.click(saveButton);

    await testingLibraryReactModule.waitFor(() => {
      vitestModule.expect(updateProfileMock).toHaveBeenCalledWith({
        professionalName: "Dra. Ana M. Garcia"
      });
    });

    await testingLibraryReactModule.waitFor(() => {
      vitestModule
        .expect(testingLibraryReactModule.screen.getByText("Perfil actualizado."))
        .toBeInTheDocument();
    });
  });

  vitestModule.it("shows oauth callback error banner from query params", async () => {
    const container = buildContainer();

    renderConfiguracionesPage(
      container,
      "/configuraciones?google_oauth=error&status=502&reason=boom"
    );

    await testingLibraryReactModule.waitFor(() => {
      expect(
        testingLibraryReactModule.screen.getByText(/Error en callback OAuth/)
      ).toBeInTheDocument();
      expect(testingLibraryReactModule.screen.getByText(/status=502/)).toBeInTheDocument();
    });
  });

  vitestModule.it("opens disclosure modal first and activates on confirm", async () => {
    const container = buildContainer();

    renderConfiguracionesPage(container);

    const ajustesTab = await testingLibraryReactModule.screen.findByRole("button", {
      name: /Ajustes del agente/i
    });
    testingLibraryReactModule.fireEvent.click(ajustesTab);

    const activateButton = await testingLibraryReactModule.screen.findByRole("button", {
      name: /Activar recordatorios/i
    });
    testingLibraryReactModule.fireEvent.click(activateButton);

    const continueButton = await testingLibraryReactModule.screen.findByRole("button", {
      name: /Ya configuré el método de pago/i
    });
    vitestModule
      .expect(
        (container.whatsappTemplateUseCase.activateOfficialTemplate as vitestModule.Mock).mock.calls
          .length
      )
      .toBe(0);

    testingLibraryReactModule.fireEvent.click(continueButton);

    await testingLibraryReactModule.waitFor(() => {
      vitestModule
        .expect(container.whatsappTemplateUseCase.activateOfficialTemplate)
        .toHaveBeenCalledWith("ATTENDANCE");
    });
  });

  vitestModule.it("blocks activation when disclosure modal is cancelled", async () => {
    const container = buildContainer();

    renderConfiguracionesPage(container);

    const ajustesTab = await testingLibraryReactModule.screen.findByRole("button", {
      name: /Ajustes del agente/i
    });
    testingLibraryReactModule.fireEvent.click(ajustesTab);

    const activateButton = await testingLibraryReactModule.screen.findByRole("button", {
      name: /Activar recordatorios/i
    });
    testingLibraryReactModule.fireEvent.click(activateButton);

    const cancelButton = await testingLibraryReactModule.screen.findByRole("button", {
      name: /^Cancelar$/i
    });
    testingLibraryReactModule.fireEvent.click(cancelButton);

    vitestModule
      .expect(container.whatsappTemplateUseCase.activateOfficialTemplate)
      .not.toHaveBeenCalled();
  });
});
