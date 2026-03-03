import * as reactQueryModule from "@tanstack/react-query";
import * as testingLibraryReactModule from "@testing-library/react";
import * as reactRouterDomModule from "react-router-dom";
import * as luxonModule from "luxon";
import * as vitestModule from "vitest";

import type * as containerModule from "@infrastructure/di/container";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";

import * as agendaPageModule from "./AgendaPage";

function renderAgendaPage(container: unknown) {
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
        <reactRouterDomModule.MemoryRouter initialEntries={["/agenda"]}>
          <reactRouterDomModule.Routes>
            <reactRouterDomModule.Route element={<agendaPageModule.AgendaPage />} path="/agenda" />
          </reactRouterDomModule.Routes>
        </reactRouterDomModule.MemoryRouter>
      </appContainerContextModule.AppContainerProvider>
    </reactQueryModule.QueryClientProvider>
  );
}

vitestModule.describe("AgendaPage", () => {
  vitestModule.beforeEach(() => {
    vitestModule.vi.spyOn(appShellModule, "AppShell").mockImplementation((props) => {
      return <div>{props.children}</div>;
    });
  });

  vitestModule.afterEach(() => {
    vitestModule.vi.restoreAllMocks();
  });

  vitestModule.it("marks slot as busy when it overlaps a busy interval", () => {
    const now = luxonModule.DateTime.fromISO("2026-03-01T00:00:00Z", { zone: "UTC" });
    const candidates = agendaPageModule.buildCalendarSlotCandidates({
      requestId: "req-1",
      timezone: "UTC",
      selectedDayIso: "2026-03-01",
      busyIntervals: [
        {
          start: luxonModule.DateTime.fromISO("2026-03-01T10:30:00Z", { zone: "UTC" }),
          end: luxonModule.DateTime.fromISO("2026-03-01T11:30:00Z", { zone: "UTC" })
        }
      ],
      now
    });

    const tenAmSlot = candidates.find((slot) => slot.startAt.startsWith("2026-03-01T10:00:00"));
    const elevenAmSlot = candidates.find((slot) => slot.startAt.startsWith("2026-03-01T11:00:00"));

    expect(tenAmSlot?.isBusy).toBe(true);
    expect(elevenAmSlot?.isBusy).toBe(true);
  });

  vitestModule.it("moves request to waiting-patient tab after successful submit", async () => {
    const listRequestsMock = vitestModule.vi.fn(async () => [
      {
        requestId: "req-1",
        conversationId: "conv-1",
        whatsappUserId: "wa-1",
        requestKind: "INITIAL",
        status: "AWAITING_PROFESSIONAL_SLOTS",
        roundNumber: 1,
        patientPreferenceNote: "prefiere tarde",
        rejectionSummary: null,
        professionalNote: null,
        patientFirstName: null,
        patientLastName: null,
        patientAge: null,
        consultationReason: null,
        consultationDetails: null,
        appointmentModality: null,
        patientLocation: null,
        slotOptionsMap: {},
        selectedSlotId: null,
        calendarEventId: null,
        createdAt: "2026-03-01T00:00:00Z",
        updatedAt: "2026-03-01T00:00:00Z",
        slots: []
      }
    ]);
    const getAvailabilityMock = vitestModule.vi.fn(async () => ({
      tenantId: "tenant-1",
      calendarId: "primary",
      timezone: "UTC",
      busyIntervals: []
    }));
    const submitProfessionalSlotsMock = vitestModule.vi.fn(async () => ({
      status: "AWAITING_PATIENT_CHOICE",
      slotBatchId: "req-1",
      outboundMessageId: "wamid-1",
      assistantText: "Listo, enviado al paciente."
    }));

    const container = {
      onboardingUseCase: {
        getGoogleCalendarConnectionStatus: vitestModule.vi.fn(async () => ({
          tenantId: "tenant-1",
          status: "CONNECTED",
          calendarId: "primary",
          professionalTimezone: "UTC",
          connectedAt: "2026-03-01T00:00:00Z"
        }))
      },
      schedulingUseCase: {
        listRequests: listRequestsMock,
        getAvailability: getAvailabilityMock,
        submitProfessionalSlots: submitProfessionalSlotsMock
      }
    };

    renderAgendaPage(container);

    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", {
        name: /Agendamiento en Curso/
      })
    );

    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", {
        name: /Pendiente Slots/
      })
    );

    await testingLibraryReactModule.waitFor(() => {
      expect(testingLibraryReactModule.screen.getByText("req-1")).toBeInTheDocument();
    });

    const nextMonthButton = testingLibraryReactModule.screen.getByRole("button", {
      name: "Siguiente"
    });
    testingLibraryReactModule.fireEvent.click(nextMonthButton);

    const firstSlotButton = await testingLibraryReactModule.screen.findByRole("button", {
      name: /06:00 - 07:00/
    });
    testingLibraryReactModule.fireEvent.click(firstSlotButton);

    const submitButton = testingLibraryReactModule.screen.getByRole("button", {
      name: "Enviar slots al chatbot"
    });
    testingLibraryReactModule.fireEvent.click(submitButton);

    await testingLibraryReactModule.waitFor(() => {
      expect(
        testingLibraryReactModule.screen.getByRole("button", {
          name: /Esperando Paciente \(1\)/
        })
      ).toBeInTheDocument();
      expect(
        testingLibraryReactModule.screen.getByText("Listo, enviado al paciente.")
      ).toBeInTheDocument();
    });
  });
});
