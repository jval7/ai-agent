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
        submitProfessionalSlots: submitProfessionalSlotsMock,
        resolveConsultationReview: vitestModule.vi.fn(),
        rescheduleBookedSlot: vitestModule.vi.fn(),
        cancelBookedSlot: vitestModule.vi.fn()
      },
      patientUseCase: {
        listPatients: vitestModule.vi.fn(async () => [])
      },
      manualAppointmentUseCase: {
        listAppointments: vitestModule.vi.fn(async () => [])
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
          submitProfessionalSlots: vitestModule.vi.fn(),
          resolveConsultationReview: vitestModule.vi.fn(),
          rescheduleBookedSlot: vitestModule.vi.fn(),
          cancelBookedSlot: vitestModule.vi.fn()
        },
        patientUseCase: {
          listPatients: vitestModule.vi.fn(async () => [])
        },
        manualAppointmentUseCase: {
          listAppointments: vitestModule.vi.fn(async () => [])
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
        name: /11:00 - 12:00/
      });
      if (secondAppointmentButton === undefined) {
        throw new Error("No se encontró la cita de 11:00 - 12:00.");
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

  vitestModule.it("renders manual scheduled appointments in booked calendar", async () => {
    vitestModule.vi
      .spyOn(luxonModule.DateTime, "now")
      .mockReturnValue(luxonModule.DateTime.utc(2026, 3, 1, 0, 0, 0) as luxonModule.DateTime<true>);

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
        listRequests: vitestModule.vi.fn(async () => [
          {
            requestId: "req-booked-1",
            conversationId: "conv-booked-1",
            whatsappUserId: "wa-booked-1",
            requestKind: "INITIAL",
            status: "BOOKED",
            roundNumber: 1,
            patientPreferenceNote: null,
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
          }
        ]),
        getAvailability: vitestModule.vi.fn(async () => ({
          tenantId: "tenant-1",
          calendarId: "primary",
          timezone: "UTC",
          busyIntervals: []
        })),
        submitProfessionalSlots: vitestModule.vi.fn(),
        resolveConsultationReview: vitestModule.vi.fn(),
        rescheduleBookedSlot: vitestModule.vi.fn(),
        cancelBookedSlot: vitestModule.vi.fn()
      },
      patientUseCase: {
        listPatients: vitestModule.vi.fn(async () => [
          {
            tenantId: "tenant-1",
            whatsappUserId: "wa-manual-1",
            firstName: "Maria",
            lastName: "Manual",
            email: "maria@example.com",
            age: 30,
            consultationReason: "Control",
            location: "Bogota",
            phone: "573001001001",
            createdAt: "2026-03-01T00:00:00Z"
          }
        ])
      },
      manualAppointmentUseCase: {
        listAppointments: vitestModule.vi.fn(async () => [
          {
            appointmentId: "manual-1",
            tenantId: "tenant-1",
            patientWhatsappUserId: "wa-manual-1",
            status: "SCHEDULED",
            calendarEventId: "event-manual-1",
            startAt: "2026-03-12T15:00:00Z",
            endAt: "2026-03-12T16:00:00Z",
            timezone: "America/Bogota",
            summary: "Cita control",
            createdAt: "2026-03-01T00:00:00Z",
            updatedAt: "2026-03-01T00:00:00Z",
            cancelledAt: null
          }
        ])
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
        testingLibraryReactModule.screen.getByRole("button", { name: /15:00 - 16:00/ })
      ).toBeInTheDocument();
    });

    const manualAppointmentButton = testingLibraryReactModule.screen
      .getAllByRole("button", { name: /15:00 - 16:00/ })
      .find((button) => button.getAttribute("title")?.includes("Manual") === true);
    if (manualAppointmentButton === undefined) {
      throw new Error("No se encontró la cita manual en la previsualización del calendario.");
    }
    testingLibraryReactModule.fireEvent.click(manualAppointmentButton);

    await testingLibraryReactModule.waitFor(() => {
      expect(testingLibraryReactModule.screen.getByText("Detalle cita manual")).toBeInTheDocument();
      expect(testingLibraryReactModule.screen.getByText("Cita control")).toBeInTheDocument();
    });
  });

  vitestModule.it("creates patient from agenda panel", async () => {
    const createPatientMock = vitestModule.vi.fn(async () => ({
      tenantId: "tenant-1",
      whatsappUserId: "wa-1",
      firstName: "Jane",
      lastName: "Doe",
      email: "jane@example.com",
      age: 29,
      consultationReason: "Ansiedad",
      location: "Bogota",
      phone: "573001112233",
      createdAt: "2026-03-01T00:00:00Z"
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
        listRequests: vitestModule.vi.fn(async () => []),
        getAvailability: vitestModule.vi.fn(async () => ({
          tenantId: "tenant-1",
          calendarId: "primary",
          timezone: "UTC",
          busyIntervals: []
        })),
        submitProfessionalSlots: vitestModule.vi.fn(),
        resolveConsultationReview: vitestModule.vi.fn(),
        rescheduleBookedSlot: vitestModule.vi.fn(),
        cancelBookedSlot: vitestModule.vi.fn()
      },
      patientUseCase: {
        listPatients: vitestModule.vi.fn(async () => []),
        createPatient: createPatientMock
      },
      manualAppointmentUseCase: {
        listAppointments: vitestModule.vi.fn(async () => [])
      }
    };

    renderAgendaPage(container);

    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", {
        name: /Agendamiento manual/
      })
    );

    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText(/WhatsApp ID/i),
      {
        target: { value: "wa-1" }
      }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText(/^Nombre$/i),
      {
        target: { value: "Jane" }
      }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText(/Apellido/i),
      {
        target: { value: "Doe" }
      }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText(/Email/i),
      {
        target: { value: "jane@example.com" }
      }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByRole("spinbutton", { name: /Edad/i }),
      {
        target: { value: "29" }
      }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText(/Teléfono/i),
      {
        target: { value: "573001112233" }
      }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText(/Motivo de consulta/i),
      {
        target: { value: "Ansiedad" }
      }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText(/Ubicación/i),
      {
        target: { value: "Bogota" }
      }
    );

    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", {
        name: "Crear paciente"
      })
    );

    await testingLibraryReactModule.waitFor(() => {
      expect(createPatientMock).toHaveBeenCalledWith({
        whatsappUserId: "wa-1",
        firstName: "Jane",
        lastName: "Doe",
        email: "jane@example.com",
        age: 29,
        consultationReason: "Ansiedad",
        location: "Bogota",
        phone: "573001112233"
      });
    });
  });

  vitestModule.it("creates manual appointment from agenda panel", async () => {
    const createManualAppointmentMock = vitestModule.vi.fn(async () => ({
      appointmentId: "manual-1",
      tenantId: "tenant-1",
      patientWhatsappUserId: "wa-1",
      status: "SCHEDULED",
      calendarEventId: "event-1",
      startAt: "2026-03-12T09:00:00Z",
      endAt: "2026-03-12T10:00:00Z",
      timezone: "UTC",
      summary: "Cita manual",
      createdAt: "2026-03-01T00:00:00Z",
      updatedAt: "2026-03-01T00:00:00Z",
      cancelledAt: null
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
        listRequests: vitestModule.vi.fn(async () => []),
        getAvailability: vitestModule.vi.fn(async () => ({
          tenantId: "tenant-1",
          calendarId: "primary",
          timezone: "UTC",
          busyIntervals: []
        })),
        submitProfessionalSlots: vitestModule.vi.fn(),
        resolveConsultationReview: vitestModule.vi.fn(),
        rescheduleBookedSlot: vitestModule.vi.fn(),
        cancelBookedSlot: vitestModule.vi.fn()
      },
      patientUseCase: {
        listPatients: vitestModule.vi.fn(async () => [
          {
            tenantId: "tenant-1",
            whatsappUserId: "wa-1",
            firstName: "Jane",
            lastName: "Doe",
            email: "jane@example.com",
            age: 29,
            consultationReason: "Ansiedad",
            location: "Bogota",
            phone: "573001112233",
            createdAt: "2026-03-01T00:00:00Z"
          }
        ])
      },
      manualAppointmentUseCase: {
        listAppointments: vitestModule.vi.fn(async () => []),
        createAppointment: createManualAppointmentMock
      }
    };

    renderAgendaPage(container);

    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", {
        name: /Agendamiento manual/
      })
    );

    await testingLibraryReactModule.waitFor(() => {
      expect(
        testingLibraryReactModule.screen.getByRole("option", {
          name: /Jane Doe \(wa-1\)/
        })
      ).toBeInTheDocument();
    });

    const patientSelect = testingLibraryReactModule.screen.getByRole("combobox", {
      name: /Paciente/i
    });

    testingLibraryReactModule.fireEvent.change(patientSelect, {
      target: { value: "wa-1" }
    });
    expect(patientSelect).toHaveValue("wa-1");
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText(/^Fecha$/i),
      {
        target: { value: "2026-03-12" }
      }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText(/^Hora$/i),
      {
        target: { value: "09" }
      }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText(/^Minuto$/i),
      {
        target: { value: "00" }
      }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText(/^Duración$/i),
      {
        target: { value: "60" }
      }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText(/^Resumen$/i),
      {
        target: { value: "Cita manual" }
      }
    );

    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", {
        name: "Crear cita manual"
      })
    );

    await testingLibraryReactModule.waitFor(() => {
      expect(createManualAppointmentMock).toHaveBeenCalledWith(
        expect.objectContaining({
          patientWhatsappUserId: "wa-1",
          timezone: "America/Bogota",
          summary: "Cita manual",
          startAt: expect.stringContaining("2026-03-12T09:00"),
          endAt: expect.stringContaining("2026-03-12T10:00")
        })
      );
    });
  });

  vitestModule.it("cancels booked chatbot appointment from agenda", async () => {
    const confirmSpy = vitestModule.vi.spyOn(window, "confirm").mockReturnValue(true);
    const cancelBookedSlotMock = vitestModule.vi.fn(async () => ({
      requestId: "req-booked-1",
      conversationId: "conv-booked-1",
      whatsappUserId: "wa-booked-1",
      requestKind: "INITIAL",
      status: "CANCELLED",
      roundNumber: 1,
      patientPreferenceNote: null,
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
      selectedSlotId: null,
      calendarEventId: null,
      createdAt: "2026-03-01T00:00:00Z",
      updatedAt: "2026-03-01T00:00:00Z",
      slots: []
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
        listRequests: vitestModule.vi.fn(async () => [
          {
            requestId: "req-booked-1",
            conversationId: "conv-booked-1",
            whatsappUserId: "wa-booked-1",
            requestKind: "INITIAL",
            status: "BOOKED",
            roundNumber: 1,
            patientPreferenceNote: null,
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
            selectedSlotId: "slot-1",
            calendarEventId: "event-1",
            createdAt: "2026-03-01T00:00:00Z",
            updatedAt: "2026-03-01T00:00:00Z",
            slots: [
              {
                slotId: "slot-1",
                startAt: "2026-03-12T09:00:00Z",
                endAt: "2026-03-12T10:00:00Z",
                timezone: "UTC",
                status: "BOOKED"
              }
            ]
          }
        ]),
        getAvailability: vitestModule.vi.fn(async () => ({
          tenantId: "tenant-1",
          calendarId: "primary",
          timezone: "UTC",
          busyIntervals: []
        })),
        submitProfessionalSlots: vitestModule.vi.fn(),
        resolveConsultationReview: vitestModule.vi.fn(),
        rescheduleBookedSlot: vitestModule.vi.fn(),
        cancelBookedSlot: cancelBookedSlotMock
      },
      patientUseCase: {
        listPatients: vitestModule.vi.fn(async () => [])
      },
      manualAppointmentUseCase: {
        listAppointments: vitestModule.vi.fn(async () => [])
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

    const cancelButton = await testingLibraryReactModule.screen.findByRole("button", {
      name: "Cancelar cita bot"
    });
    testingLibraryReactModule.fireEvent.click(cancelButton);

    await testingLibraryReactModule.waitFor(() => {
      expect(cancelBookedSlotMock).toHaveBeenCalledWith("req-booked-1", {
        reason: null
      });
    });
    expect(confirmSpy).toHaveBeenCalledTimes(1);
  });

  vitestModule.it("updates manual appointment payment from booked detail", async () => {
    const updateManualPaymentMock = vitestModule.vi.fn(async () => ({
      appointmentId: "manual-1",
      tenantId: "tenant-1",
      patientWhatsappUserId: "wa-manual-1",
      status: "SCHEDULED",
      calendarEventId: "event-manual-1",
      startAt: "2026-03-12T15:00:00Z",
      endAt: "2026-03-12T16:00:00Z",
      timezone: "UTC",
      summary: "Cita control",
      paymentAmountCop: 120000,
      paymentMethod: "TRANSFER",
      paymentStatus: "PAID",
      paymentUpdatedAt: "2026-03-10T10:00:00Z",
      createdAt: "2026-03-01T00:00:00Z",
      updatedAt: "2026-03-10T10:00:00Z",
      cancelledAt: null
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
        listRequests: vitestModule.vi.fn(async () => []),
        getAvailability: vitestModule.vi.fn(async () => ({
          tenantId: "tenant-1",
          calendarId: "primary",
          timezone: "UTC",
          busyIntervals: []
        })),
        submitProfessionalSlots: vitestModule.vi.fn(),
        resolveConsultationReview: vitestModule.vi.fn(),
        rescheduleBookedSlot: vitestModule.vi.fn(),
        cancelBookedSlot: vitestModule.vi.fn(),
        updateBookedPayment: vitestModule.vi.fn()
      },
      patientUseCase: {
        listPatients: vitestModule.vi.fn(async () => [
          {
            tenantId: "tenant-1",
            whatsappUserId: "wa-manual-1",
            firstName: "Maria",
            lastName: "Manual",
            email: "maria@example.com",
            age: 30,
            consultationReason: "Control",
            location: "Bogota",
            phone: "573001001001",
            createdAt: "2026-03-01T00:00:00Z"
          }
        ])
      },
      manualAppointmentUseCase: {
        listAppointments: vitestModule.vi.fn(async () => [
          {
            appointmentId: "manual-1",
            tenantId: "tenant-1",
            patientWhatsappUserId: "wa-manual-1",
            status: "SCHEDULED",
            calendarEventId: "event-manual-1",
            startAt: "2026-03-12T15:00:00Z",
            endAt: "2026-03-12T16:00:00Z",
            timezone: "UTC",
            summary: "Cita control",
            paymentAmountCop: null,
            paymentMethod: null,
            paymentStatus: "PENDING",
            paymentUpdatedAt: null,
            createdAt: "2026-03-01T00:00:00Z",
            updatedAt: "2026-03-01T00:00:00Z",
            cancelledAt: null
          }
        ]),
        updatePayment: updateManualPaymentMock
      }
    };

    renderAgendaPage(container);

    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: /Agenda e Historial/ })
    );
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: /Agendadas/ })
    );

    await testingLibraryReactModule.waitFor(() => {
      expect(testingLibraryReactModule.screen.getByText("Detalle cita manual")).toBeInTheDocument();
    });

    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByRole("spinbutton", {
        name: /Valor \(COP\)/i
      }),
      {
        target: { value: "120000" }
      }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByRole("combobox", { name: /^Categoría$/i }),
      {
        target: { value: "TRANSFER" }
      }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByRole("combobox", { name: /^Estado$/i }),
      {
        target: { value: "PAID" }
      }
    );
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: "Guardar pago manual" })
    );

    await testingLibraryReactModule.waitFor(() => {
      expect(updateManualPaymentMock).toHaveBeenCalledWith("manual-1", {
        paymentAmountCop: 120000,
        paymentMethod: "TRANSFER",
        paymentStatus: "PAID"
      });
    });
  });

  vitestModule.it("updates chatbot appointment payment from booked detail", async () => {
    const updateBookedPaymentMock = vitestModule.vi.fn(async () => ({
      requestId: "req-booked-1",
      conversationId: "conv-booked-1",
      whatsappUserId: "wa-booked-1",
      requestKind: "INITIAL",
      status: "BOOKED",
      roundNumber: 1,
      patientPreferenceNote: null,
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
      selectedSlotId: "slot-1",
      calendarEventId: "event-1",
      paymentAmountCop: 80000,
      paymentMethod: "CASH",
      paymentStatus: "PENDING",
      paymentUpdatedAt: "2026-03-12T08:00:00Z",
      createdAt: "2026-03-01T00:00:00Z",
      updatedAt: "2026-03-12T08:00:00Z",
      slots: [
        {
          slotId: "slot-1",
          startAt: "2026-03-12T09:00:00Z",
          endAt: "2026-03-12T10:00:00Z",
          timezone: "UTC",
          status: "BOOKED"
        }
      ]
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
        listRequests: vitestModule.vi.fn(async () => [
          {
            requestId: "req-booked-1",
            conversationId: "conv-booked-1",
            whatsappUserId: "wa-booked-1",
            requestKind: "INITIAL",
            status: "BOOKED",
            roundNumber: 1,
            patientPreferenceNote: null,
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
            selectedSlotId: "slot-1",
            calendarEventId: "event-1",
            paymentAmountCop: null,
            paymentMethod: null,
            paymentStatus: "PENDING",
            paymentUpdatedAt: null,
            createdAt: "2026-03-01T00:00:00Z",
            updatedAt: "2026-03-01T00:00:00Z",
            slots: [
              {
                slotId: "slot-1",
                startAt: "2026-03-12T09:00:00Z",
                endAt: "2026-03-12T10:00:00Z",
                timezone: "UTC",
                status: "BOOKED"
              }
            ]
          }
        ]),
        getAvailability: vitestModule.vi.fn(async () => ({
          tenantId: "tenant-1",
          calendarId: "primary",
          timezone: "UTC",
          busyIntervals: []
        })),
        submitProfessionalSlots: vitestModule.vi.fn(),
        resolveConsultationReview: vitestModule.vi.fn(),
        rescheduleBookedSlot: vitestModule.vi.fn(),
        cancelBookedSlot: vitestModule.vi.fn(),
        updateBookedPayment: updateBookedPaymentMock
      },
      patientUseCase: {
        listPatients: vitestModule.vi.fn(async () => [])
      },
      manualAppointmentUseCase: {
        listAppointments: vitestModule.vi.fn(async () => []),
        updatePayment: vitestModule.vi.fn()
      }
    };

    renderAgendaPage(container);

    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: /Agenda e Historial/ })
    );
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: /Agendadas/ })
    );

    await testingLibraryReactModule.waitFor(() => {
      expect(
        testingLibraryReactModule.screen.getByRole("button", { name: "Guardar pago chatbot" })
      ).toBeInTheDocument();
    });

    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByRole("spinbutton", {
        name: /Valor \(COP\)/i
      }),
      {
        target: { value: "80000" }
      }
    );
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: "Guardar pago chatbot" })
    );

    await testingLibraryReactModule.waitFor(() => {
      expect(updateBookedPaymentMock).toHaveBeenCalledWith("req-booked-1", {
        paymentAmountCop: 80000,
        paymentMethod: "CASH",
        paymentStatus: "PENDING"
      });
    });
  });

  vitestModule.it("filters finance tab by payment status", async () => {
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
        listRequests: vitestModule.vi.fn(async () => [
          {
            requestId: "req-booked-1",
            conversationId: "conv-booked-1",
            whatsappUserId: "wa-bot-1",
            requestKind: "INITIAL",
            status: "BOOKED",
            roundNumber: 1,
            patientPreferenceNote: null,
            rejectionSummary: null,
            professionalNote: null,
            patientFirstName: "Paciente",
            patientLastName: "Bot",
            patientAge: 29,
            consultationReason: "Ansiedad",
            consultationDetails: null,
            appointmentModality: "PRESENCIAL",
            patientLocation: "Cali",
            slotOptionsMap: {},
            selectedSlotId: "slot-1",
            calendarEventId: "event-1",
            paymentAmountCop: 100000,
            paymentMethod: "TRANSFER",
            paymentStatus: "PAID",
            paymentUpdatedAt: "2026-03-12T08:00:00Z",
            createdAt: "2026-03-01T00:00:00Z",
            updatedAt: "2026-03-01T00:00:00Z",
            slots: [
              {
                slotId: "slot-1",
                startAt: "2026-03-12T09:00:00Z",
                endAt: "2026-03-12T10:00:00Z",
                timezone: "UTC",
                status: "BOOKED"
              }
            ]
          }
        ]),
        getAvailability: vitestModule.vi.fn(async () => ({
          tenantId: "tenant-1",
          calendarId: "primary",
          timezone: "UTC",
          busyIntervals: []
        })),
        submitProfessionalSlots: vitestModule.vi.fn(),
        resolveConsultationReview: vitestModule.vi.fn(),
        rescheduleBookedSlot: vitestModule.vi.fn(),
        cancelBookedSlot: vitestModule.vi.fn(),
        updateBookedPayment: vitestModule.vi.fn()
      },
      patientUseCase: {
        listPatients: vitestModule.vi.fn(async () => [
          {
            tenantId: "tenant-1",
            whatsappUserId: "wa-manual-1",
            firstName: "Paciente",
            lastName: "Manual",
            email: "manual@example.com",
            age: 33,
            consultationReason: "Control",
            location: "Bogota",
            phone: "573000000000",
            createdAt: "2026-03-01T00:00:00Z"
          }
        ])
      },
      manualAppointmentUseCase: {
        listAppointments: vitestModule.vi.fn(async () => [
          {
            appointmentId: "manual-1",
            tenantId: "tenant-1",
            patientWhatsappUserId: "wa-manual-1",
            status: "SCHEDULED",
            calendarEventId: "event-manual-1",
            startAt: "2026-03-11T15:00:00Z",
            endAt: "2026-03-11T16:00:00Z",
            timezone: "UTC",
            summary: "Cita manual",
            paymentAmountCop: null,
            paymentMethod: null,
            paymentStatus: "PENDING",
            paymentUpdatedAt: null,
            createdAt: "2026-03-01T00:00:00Z",
            updatedAt: "2026-03-01T00:00:00Z",
            cancelledAt: null
          }
        ]),
        updatePayment: vitestModule.vi.fn()
      }
    };

    renderAgendaPage(container);

    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: /Finanzas/ })
    );

    await testingLibraryReactModule.waitFor(() => {
      expect(testingLibraryReactModule.screen.getByText("Paciente Bot")).toBeInTheDocument();
      expect(testingLibraryReactModule.screen.getByText("Paciente Manual")).toBeInTheDocument();
    });

    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByRole("combobox", {
        name: /Estado de pago/i
      }),
      {
        target: { value: "PAID" }
      }
    );

    await testingLibraryReactModule.waitFor(() => {
      expect(testingLibraryReactModule.screen.getByText("Paciente Bot")).toBeInTheDocument();
      expect(testingLibraryReactModule.screen.queryByText("Paciente Manual")).toBeNull();
    });
  });
});
