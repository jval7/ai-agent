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

  vitestModule.it(
    "renders booked appointments in calendar and opens details on click",
    async () => {
      vitestModule.vi
        .spyOn(luxonModule.DateTime, "now")
        .mockReturnValue(
          luxonModule.DateTime.utc(2026, 3, 1, 0, 0, 0) as luxonModule.DateTime<true>
        );

      const listRequestsMock = vitestModule.vi.fn(async () => [
        {
          requestId: "req-booked-1",
          conversationId: "conv-booked-1",
          whatsappUserId: "wa-booked-1",
          requestKind: "INITIAL",
          status: "BOOKED",
          roundNumber: 1,
          patientPreferenceNote: "prefiere mañana",
          rejectionSummary: null,
          professionalNote: null,
          patientFirstName: "Ana",
          patientLastName: "Lopez",
          patientAge: 29,
          consultationReason: "Ansiedad",
          consultationDetails: null,
          appointmentModality: "PRESENCIAL",
          patientLocation: "Cali",
          slotOptionsMap: {},
          selectedSlotId: "slot-booked-1",
          calendarEventId: "event-booked-1",
          createdAt: "2026-03-01T00:00:00Z",
          updatedAt: "2026-03-01T00:00:00Z",
          slots: [
            {
              slotId: "slot-booked-1",
              startAt: "2026-03-12T09:00:00Z",
              endAt: "2026-03-12T10:00:00Z",
              timezone: "UTC",
              status: "BOOKED"
            }
          ]
        },
        {
          requestId: "req-booked-2",
          conversationId: "conv-booked-2",
          whatsappUserId: "wa-booked-2",
          requestKind: "INITIAL",
          status: "BOOKED",
          roundNumber: 1,
          patientPreferenceNote: "prefiere tarde",
          rejectionSummary: null,
          professionalNote: null,
          patientFirstName: "Juan",
          patientLastName: "Perez",
          patientAge: 35,
          consultationReason: "Estrés",
          consultationDetails: null,
          appointmentModality: "VIRTUAL",
          patientLocation: "Bogotá",
          slotOptionsMap: {},
          selectedSlotId: "slot-booked-2",
          calendarEventId: "event-booked-2",
          createdAt: "2026-03-01T00:00:00Z",
          updatedAt: "2026-03-01T00:00:00Z",
          slots: [
            {
              slotId: "slot-booked-2",
              startAt: "2026-03-12T11:00:00Z",
              endAt: "2026-03-12T12:00:00Z",
              timezone: "UTC",
              status: "BOOKED"
            }
          ]
        },
        {
          requestId: "req-booked-3",
          conversationId: "conv-booked-3",
          whatsappUserId: "wa-booked-3",
          requestKind: "INITIAL",
          status: "BOOKED",
          roundNumber: 1,
          patientPreferenceNote: "prefiere mediodía",
          rejectionSummary: null,
          professionalNote: null,
          patientFirstName: "Camila",
          patientLastName: "Diaz",
          patientAge: 31,
          consultationReason: "Insomnio",
          consultationDetails: null,
          appointmentModality: "PRESENCIAL",
          patientLocation: "Medellín",
          slotOptionsMap: {},
          selectedSlotId: "slot-booked-3",
          calendarEventId: "event-booked-3",
          createdAt: "2026-03-01T00:00:00Z",
          updatedAt: "2026-03-01T00:00:00Z",
          slots: [
            {
              slotId: "slot-booked-3",
              startAt: "2026-03-12T13:00:00Z",
              endAt: "2026-03-12T14:00:00Z",
              timezone: "UTC",
              status: "BOOKED"
            }
          ]
        }
      ]);

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
          getAvailability: vitestModule.vi.fn(async () => ({
            tenantId: "tenant-1",
            calendarId: "primary",
            timezone: "UTC",
            busyIntervals: []
          })),
          submitProfessionalSlots: vitestModule.vi.fn()
        }
      };

      renderAgendaPage(container);

      testingLibraryReactModule.fireEvent.click(
        testingLibraryReactModule.screen.getByRole("button", {
          name: /Agenda e Historial/
        })
      );

      testingLibraryReactModule.fireEvent.click(
        testingLibraryReactModule.screen.getByRole("button", {
          name: /Agendadas/
        })
      );

      await testingLibraryReactModule.waitFor(() => {
        expect(
          testingLibraryReactModule.screen.getByText("Calendario de citas agendadas")
        ).toBeInTheDocument();
        expect(testingLibraryReactModule.screen.getByText("+1 más")).toBeInTheDocument();
        expect(testingLibraryReactModule.screen.getByText("req-booked-1")).toBeInTheDocument();
      });

      const [secondAppointmentButton] = testingLibraryReactModule.screen.getAllByRole("button", {
        name: /11:00 - 12:00\s+Juan Perez/
      });
      if (secondAppointmentButton === undefined) {
        throw new Error("No se encontró la cita de Juan Perez.");
      }
      testingLibraryReactModule.fireEvent.click(secondAppointmentButton);

      await testingLibraryReactModule.waitFor(() => {
        expect(testingLibraryReactModule.screen.getByText("req-booked-2")).toBeInTheDocument();
        expect(
          testingLibraryReactModule.screen.getByText(/12 Mar 2026 11:00 - 12:00/)
        ).toBeInTheDocument();
      });
    }
  );
});
