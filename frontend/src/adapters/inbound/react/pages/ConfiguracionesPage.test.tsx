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
        reminderBillingTestPhoneNumber: null,
        paymentDetailsText: null,
        officeLocation: null,
        virtualSessionInstructions: null
      })),
      updateAgentSettings: vitestModule.vi.fn(async () => ({
        tenantId: "tenant-1",
        messageDebounceDelaySeconds: 5,
        appointmentReminderEnabled: false,
        appointmentReminderDaysBefore: null,
        appointmentReminderAttendanceTemplateName: null,
        appointmentReminderPaymentTemplateName: null,
        reminderBillingTestPhoneNumber: null,
        paymentDetailsText: null,
        officeLocation: null,
        virtualSessionInstructions: null
      }))
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
    whatsappBillingUseCase: {
      runPreflight: vitestModule.vi.fn(async (phone: string) => ({
        ok: true,
        recipientPhoneNumber: phone
      }))
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

  vitestModule.it("opens disclosure modal first and chains preflight + activate flow", async () => {
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
    vitestModule
      .expect(
        (container.whatsappBillingUseCase.runPreflight as vitestModule.Mock).mock.calls.length
      )
      .toBe(0);

    testingLibraryReactModule.fireEvent.click(continueButton);

    const phoneInput =
      await testingLibraryReactModule.screen.findByLabelText(/Tu número de WhatsApp/i);
    testingLibraryReactModule.fireEvent.change(phoneInput, {
      target: { value: "+573009998877" }
    });

    const verifyButton = testingLibraryReactModule.screen.getByRole("button", {
      name: /Verificar/i
    });
    testingLibraryReactModule.fireEvent.click(verifyButton);

    await testingLibraryReactModule.waitFor(() => {
      vitestModule
        .expect(container.whatsappBillingUseCase.runPreflight)
        .toHaveBeenCalledWith("+573009998877");
    });
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

    vitestModule.expect(container.whatsappBillingUseCase.runPreflight).not.toHaveBeenCalled();
    vitestModule
      .expect(container.whatsappTemplateUseCase.activateOfficialTemplate)
      .not.toHaveBeenCalled();
  });

  // --- Consultorio tab tests ---

  vitestModule.it(
    "renders Consultorio tab with initial office location data from backend",
    async () => {
      const container = buildContainer({
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
            reminderBillingTestPhoneNumber: null,
            paymentDetailsText: null,
            officeLocation: {
              address: "Calle 5 # 38-25, Cali",
              arrivalInstructions: "Llegar 20 minutos antes con cedula fisica",
              accessNotes: "Edificio azul, piso 3"
            },
            virtualSessionInstructions: "El link de Google Meet llega al correo 24h antes."
          })),
          updateAgentSettings: vitestModule.vi.fn(async () => undefined)
        }
      });

      renderConfiguracionesPage(container);

      const consultorioTab = await testingLibraryReactModule.screen.findByRole("button", {
        name: "Consultorio"
      });
      testingLibraryReactModule.fireEvent.click(consultorioTab);

      const addressInput = await testingLibraryReactModule.screen.findByLabelText(
        "Direccion del consultorio"
      );
      await testingLibraryReactModule.waitFor(() => {
        vitestModule.expect((addressInput as HTMLInputElement).value).toBe("Calle 5 # 38-25, Cali");
      });

      const arrivalInput =
        testingLibraryReactModule.screen.getByLabelText("Indicaciones de llegada");
      vitestModule
        .expect((arrivalInput as HTMLTextAreaElement).value)
        .toBe("Llegar 20 minutos antes con cedula fisica");

      const accessInput = testingLibraryReactModule.screen.getByLabelText("Notas de acceso");
      vitestModule.expect((accessInput as HTMLTextAreaElement).value).toBe("Edificio azul, piso 3");

      const virtualInput = testingLibraryReactModule.screen.getByLabelText(
        "Instrucciones para sesiones virtuales"
      );
      vitestModule
        .expect((virtualInput as HTMLTextAreaElement).value)
        .toBe("El link de Google Meet llega al correo 24h antes.");
    }
  );

  vitestModule.it(
    "submits office_location with all fields when address and sub-fields are filled",
    async () => {
      const updateAgentSettingsMock = vitestModule.vi.fn(async () => ({
        tenantId: "tenant-1",
        messageDebounceDelaySeconds: 5,
        appointmentReminderEnabled: false,
        appointmentReminderDaysBefore: null,
        appointmentReminderAttendanceTemplateName: null,
        appointmentReminderPaymentTemplateName: null,
        reminderBillingTestPhoneNumber: null,
        paymentDetailsText: null,
        officeLocation: {
          address: "Calle 5 # 38-25, Cali",
          arrivalInstructions: "Llegar 20 minutos antes",
          accessNotes: "Piso 3"
        },
        virtualSessionInstructions: null
      }));
      const container = buildContainer({
        agentUseCase: {
          getSystemPrompt: vitestModule.vi.fn(async () => ({
            systemPrompt: ""
          })),
          updateSystemPrompt: vitestModule.vi.fn(async () => undefined),
          getAgentSettings: vitestModule.vi.fn(async () => ({
            tenantId: "tenant-1",
            messageDebounceDelaySeconds: 5,
            appointmentReminderEnabled: false,
            appointmentReminderDaysBefore: null,
            appointmentReminderAttendanceTemplateName: null,
            appointmentReminderPaymentTemplateName: null,
            reminderBillingTestPhoneNumber: null,
            paymentDetailsText: null,
            officeLocation: null,
            virtualSessionInstructions: null
          })),
          updateAgentSettings: updateAgentSettingsMock
        }
      });

      renderConfiguracionesPage(container);

      const consultorioTab = await testingLibraryReactModule.screen.findByRole("button", {
        name: "Consultorio"
      });
      testingLibraryReactModule.fireEvent.click(consultorioTab);

      const addressInput = await testingLibraryReactModule.screen.findByLabelText(
        "Direccion del consultorio"
      );
      testingLibraryReactModule.fireEvent.change(addressInput, {
        target: { value: "Calle 5 # 38-25, Cali" }
      });

      const arrivalInput =
        testingLibraryReactModule.screen.getByLabelText("Indicaciones de llegada");
      testingLibraryReactModule.fireEvent.change(arrivalInput, {
        target: { value: "Llegar 20 minutos antes" }
      });

      const accessInput = testingLibraryReactModule.screen.getByLabelText("Notas de acceso");
      testingLibraryReactModule.fireEvent.change(accessInput, {
        target: { value: "Piso 3" }
      });

      const saveButton = testingLibraryReactModule.screen.getByRole("button", { name: "Guardar" });
      testingLibraryReactModule.fireEvent.click(saveButton);

      await testingLibraryReactModule.waitFor(() => {
        vitestModule.expect(updateAgentSettingsMock).toHaveBeenCalledWith(
          vitestModule.expect.objectContaining({
            officeLocation: {
              address: "Calle 5 # 38-25, Cali",
              arrivalInstructions: "Llegar 20 minutos antes",
              accessNotes: "Piso 3"
            }
          })
        );
      });
    }
  );

  vitestModule.it(
    "submits office_location with only address when arrival/access are empty",
    async () => {
      const updateAgentSettingsMock = vitestModule.vi.fn(async () => ({
        tenantId: "tenant-1",
        messageDebounceDelaySeconds: 5,
        appointmentReminderEnabled: false,
        appointmentReminderDaysBefore: null,
        appointmentReminderAttendanceTemplateName: null,
        appointmentReminderPaymentTemplateName: null,
        reminderBillingTestPhoneNumber: null,
        paymentDetailsText: null,
        officeLocation: {
          address: "Calle 5 # 38-25, Cali",
          arrivalInstructions: null,
          accessNotes: null
        },
        virtualSessionInstructions: null
      }));
      const container = buildContainer({
        agentUseCase: {
          getSystemPrompt: vitestModule.vi.fn(async () => ({ systemPrompt: "" })),
          updateSystemPrompt: vitestModule.vi.fn(async () => undefined),
          getAgentSettings: vitestModule.vi.fn(async () => ({
            tenantId: "tenant-1",
            messageDebounceDelaySeconds: 5,
            appointmentReminderEnabled: false,
            appointmentReminderDaysBefore: null,
            appointmentReminderAttendanceTemplateName: null,
            appointmentReminderPaymentTemplateName: null,
            reminderBillingTestPhoneNumber: null,
            paymentDetailsText: null,
            officeLocation: null,
            virtualSessionInstructions: null
          })),
          updateAgentSettings: updateAgentSettingsMock
        }
      });

      renderConfiguracionesPage(container);

      const consultorioTab = await testingLibraryReactModule.screen.findByRole("button", {
        name: "Consultorio"
      });
      testingLibraryReactModule.fireEvent.click(consultorioTab);

      const addressInput = await testingLibraryReactModule.screen.findByLabelText(
        "Direccion del consultorio"
      );
      testingLibraryReactModule.fireEvent.change(addressInput, {
        target: { value: "Calle 5 # 38-25, Cali" }
      });

      const saveButton = testingLibraryReactModule.screen.getByRole("button", { name: "Guardar" });
      testingLibraryReactModule.fireEvent.click(saveButton);

      await testingLibraryReactModule.waitFor(() => {
        vitestModule.expect(updateAgentSettingsMock).toHaveBeenCalledWith(
          vitestModule.expect.objectContaining({
            officeLocation: {
              address: "Calle 5 # 38-25, Cali",
              arrivalInstructions: null,
              accessNotes: null
            }
          })
        );
      });
    }
  );

  vitestModule.it(
    "sends office_location null when address is empty even if arrival_instructions is filled",
    async () => {
      // UX decision: address is mandatory for office_location. Leaving address
      // blank while filling arrival_instructions discards the sub-fields silently
      // (no orphaned data is stored). This avoids confusing the backend with an
      // office_location that has no address.
      const updateAgentSettingsMock = vitestModule.vi.fn(async () => ({
        tenantId: "tenant-1",
        messageDebounceDelaySeconds: 5,
        appointmentReminderEnabled: false,
        appointmentReminderDaysBefore: null,
        appointmentReminderAttendanceTemplateName: null,
        appointmentReminderPaymentTemplateName: null,
        reminderBillingTestPhoneNumber: null,
        paymentDetailsText: null,
        officeLocation: null,
        virtualSessionInstructions: null
      }));
      const container = buildContainer({
        agentUseCase: {
          getSystemPrompt: vitestModule.vi.fn(async () => ({ systemPrompt: "" })),
          updateSystemPrompt: vitestModule.vi.fn(async () => undefined),
          getAgentSettings: vitestModule.vi.fn(async () => ({
            tenantId: "tenant-1",
            messageDebounceDelaySeconds: 5,
            appointmentReminderEnabled: false,
            appointmentReminderDaysBefore: null,
            appointmentReminderAttendanceTemplateName: null,
            appointmentReminderPaymentTemplateName: null,
            reminderBillingTestPhoneNumber: null,
            paymentDetailsText: null,
            officeLocation: null,
            virtualSessionInstructions: null
          })),
          updateAgentSettings: updateAgentSettingsMock
        }
      });

      renderConfiguracionesPage(container);

      const consultorioTab = await testingLibraryReactModule.screen.findByRole("button", {
        name: "Consultorio"
      });
      testingLibraryReactModule.fireEvent.click(consultorioTab);

      // Leave address empty, fill arrival_instructions
      const arrivalInput =
        await testingLibraryReactModule.screen.findByLabelText("Indicaciones de llegada");
      testingLibraryReactModule.fireEvent.change(arrivalInput, {
        target: { value: "Llegar 20 minutos antes" }
      });

      const saveButton = testingLibraryReactModule.screen.getByRole("button", { name: "Guardar" });
      testingLibraryReactModule.fireEvent.click(saveButton);

      await testingLibraryReactModule.waitFor(() => {
        vitestModule.expect(updateAgentSettingsMock).toHaveBeenCalledWith(
          vitestModule.expect.objectContaining({
            officeLocation: null
          })
        );
      });
    }
  );

  vitestModule.it("sends virtual_session_instructions null when field is empty", async () => {
    const updateAgentSettingsMock = vitestModule.vi.fn(async () => ({
      tenantId: "tenant-1",
      messageDebounceDelaySeconds: 5,
      appointmentReminderEnabled: false,
      appointmentReminderDaysBefore: null,
      appointmentReminderAttendanceTemplateName: null,
      appointmentReminderPaymentTemplateName: null,
      reminderBillingTestPhoneNumber: null,
      paymentDetailsText: null,
      officeLocation: null,
      virtualSessionInstructions: null
    }));
    const container = buildContainer({
      agentUseCase: {
        getSystemPrompt: vitestModule.vi.fn(async () => ({ systemPrompt: "" })),
        updateSystemPrompt: vitestModule.vi.fn(async () => undefined),
        getAgentSettings: vitestModule.vi.fn(async () => ({
          tenantId: "tenant-1",
          messageDebounceDelaySeconds: 5,
          appointmentReminderEnabled: false,
          appointmentReminderDaysBefore: null,
          appointmentReminderAttendanceTemplateName: null,
          appointmentReminderPaymentTemplateName: null,
          reminderBillingTestPhoneNumber: null,
          paymentDetailsText: null,
          officeLocation: null,
          virtualSessionInstructions: null
        })),
        updateAgentSettings: updateAgentSettingsMock
      }
    });

    renderConfiguracionesPage(container);

    const consultorioTab = await testingLibraryReactModule.screen.findByRole("button", {
      name: "Consultorio"
    });
    testingLibraryReactModule.fireEvent.click(consultorioTab);

    // Verify virtual instructions field exists and is empty, then save
    const virtualInput = await testingLibraryReactModule.screen.findByLabelText(
      "Instrucciones para sesiones virtuales"
    );
    vitestModule.expect((virtualInput as HTMLTextAreaElement).value).toBe("");

    const saveButton = testingLibraryReactModule.screen.getByRole("button", { name: "Guardar" });
    testingLibraryReactModule.fireEvent.click(saveButton);

    await testingLibraryReactModule.waitFor(() => {
      vitestModule.expect(updateAgentSettingsMock).toHaveBeenCalledWith(
        vitestModule.expect.objectContaining({
          virtualSessionInstructions: null
        })
      );
    });
  });

  vitestModule.it("shows success banner after saving office data", async () => {
    const updateAgentSettingsMock = vitestModule.vi.fn(async () => ({
      tenantId: "tenant-1",
      messageDebounceDelaySeconds: 5,
      appointmentReminderEnabled: false,
      appointmentReminderDaysBefore: null,
      appointmentReminderAttendanceTemplateName: null,
      appointmentReminderPaymentTemplateName: null,
      reminderBillingTestPhoneNumber: null,
      paymentDetailsText: null,
      officeLocation: {
        address: "Calle 5 # 38-25, Cali",
        arrivalInstructions: null,
        accessNotes: null
      },
      virtualSessionInstructions: null
    }));
    const container = buildContainer({
      agentUseCase: {
        getSystemPrompt: vitestModule.vi.fn(async () => ({ systemPrompt: "" })),
        updateSystemPrompt: vitestModule.vi.fn(async () => undefined),
        getAgentSettings: vitestModule.vi.fn(async () => ({
          tenantId: "tenant-1",
          messageDebounceDelaySeconds: 5,
          appointmentReminderEnabled: false,
          appointmentReminderDaysBefore: null,
          appointmentReminderAttendanceTemplateName: null,
          appointmentReminderPaymentTemplateName: null,
          reminderBillingTestPhoneNumber: null,
          paymentDetailsText: null,
          officeLocation: null,
          virtualSessionInstructions: null
        })),
        updateAgentSettings: updateAgentSettingsMock
      }
    });

    renderConfiguracionesPage(container);

    const consultorioTab = await testingLibraryReactModule.screen.findByRole("button", {
      name: "Consultorio"
    });
    testingLibraryReactModule.fireEvent.click(consultorioTab);

    const addressInput = await testingLibraryReactModule.screen.findByLabelText(
      "Direccion del consultorio"
    );
    testingLibraryReactModule.fireEvent.change(addressInput, {
      target: { value: "Calle 5 # 38-25, Cali" }
    });

    const saveButton = testingLibraryReactModule.screen.getByRole("button", { name: "Guardar" });
    testingLibraryReactModule.fireEvent.click(saveButton);

    await testingLibraryReactModule.waitFor(() => {
      vitestModule
        .expect(testingLibraryReactModule.screen.getByText("Datos del consultorio guardados."))
        .toBeInTheDocument();
    });
  });
});
