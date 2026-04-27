import * as reactQueryModule from "@tanstack/react-query";
import * as testingLibraryReactModule from "@testing-library/react";
import * as reactRouterDomModule from "react-router-dom";
import * as luxonModule from "luxon";
import * as vitestModule from "vitest";

import type * as containerModule from "@infrastructure/di/container";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";

import * as calendarUtilsModule from "@shared/utils/calendar";
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
    const candidates = calendarUtilsModule.buildCalendarSlotCandidates({
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
          consultationReason: "Ansiedad",
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
          consultationReason: "Ansiedad",
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
        testingLibraryReactModule.screen.getAllByRole("button", {
          name: /^Agenda$/
        })[0]!
      );

      await testingLibraryReactModule.waitFor(() => {
        expect(
          testingLibraryReactModule.screen.getByText("Calendario de citas agendadas")
        ).toBeInTheDocument();
        expect(testingLibraryReactModule.screen.getByText("+1 más")).toBeInTheDocument();
        expect(testingLibraryReactModule.screen.getAllByText("Ana Lopez").length).toBeGreaterThan(
          0
        );
      });

      // Click on the day "12" in the mobile calendar to go to dayList step
      const dayButtons = testingLibraryReactModule.screen.getAllByRole("button", { name: "12" });
      testingLibraryReactModule.fireEvent.click(dayButtons[0]!);

      // In dayList step, click the 11:00 - 12:00 appointment to go to detail step
      // getAllByRole because the desktop calendar also renders the same time chips in jsdom
      const timeButtons = await testingLibraryReactModule.screen.findAllByRole("button", {
        name: /11:00 - 12:00/
      });
      testingLibraryReactModule.fireEvent.click(timeButtons[0]!);

      // Detail step shows AppointmentDetailCard with patient name
      await testingLibraryReactModule.waitFor(() => {
        expect(testingLibraryReactModule.screen.getAllByText("Juan Perez").length).toBeGreaterThan(
          0
        );
        // AppointmentDetailCard shows the origin kicker
        expect(testingLibraryReactModule.screen.getByText("Cita chatbot")).toBeInTheDocument();
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
            location: "Bogota",
            phonePrefix: null,
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
            isVirtual: false,
            meetUrl: null,
            paymentAmountCop: null,
            paymentCurrency: "COP" as const,
            paymentMethod: null,
            paymentStatus: "PENDING",
            paymentUpdatedAt: null,
            createdAt: "2026-03-01T00:00:00Z",
            updatedAt: "2026-03-01T00:00:00Z",
            cancelledAt: null
          }
        ])
      }
    };

    renderAgendaPage(container);

    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getAllByRole("button", {
        name: /^Agenda$/
      })[0]!
    );

    await testingLibraryReactModule.waitFor(() => {
      expect(
        testingLibraryReactModule.screen.getByRole("button", { name: /15:00 - 16:00/ })
      ).toBeInTheDocument();
    });

    // Click on day "12" in the mobile calendar to go to dayList
    const dayButtons = testingLibraryReactModule.screen.getAllByRole("button", { name: "12" });
    testingLibraryReactModule.fireEvent.click(dayButtons[0]!);

    // In dayList, click on the 15:00 - 16:00 appointment chip
    // getAllByRole because the desktop calendar also renders the same time chips in jsdom
    const timeButtons = await testingLibraryReactModule.screen.findAllByRole("button", {
      name: /15:00 - 16:00/
    });
    testingLibraryReactModule.fireEvent.click(timeButtons[0]!);

    // Detail step shows AppointmentDetailCard with patient name and summary
    await testingLibraryReactModule.waitFor(() => {
      expect(testingLibraryReactModule.screen.getAllByText("Maria Manual").length).toBeGreaterThan(
        0
      );
      expect(testingLibraryReactModule.screen.getAllByText("Cita control").length).toBeGreaterThan(
        0
      );
      // AppointmentDetailCard shows origin kicker
      expect(testingLibraryReactModule.screen.getByText("Cita manual")).toBeInTheDocument();
    });
  });

  vitestModule.it("creates patient from agenda panel", async () => {
    const createPatientMock = vitestModule.vi.fn(async () => ({
      tenantId: "tenant-1",
      whatsappUserId: "573001112233",
      firstName: "Jane",
      lastName: "Doe",
      email: "jane@example.com",
      age: 29,
      location: "Bogota",
      phonePrefix: "+57",
      phone: "300 111 2233",
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

    // Open new manual appointment modal via "+ Nueva cita manual" button
    const nuevaCitaButtons = await testingLibraryReactModule.screen.findAllByRole("button", {
      name: /Nueva cita manual/i
    });
    testingLibraryReactModule.fireEvent.click(nuevaCitaButtons[0]!);

    await testingLibraryReactModule.waitFor(() => {
      expect(testingLibraryReactModule.screen.getByText("Nueva cita manual")).toBeInTheDocument();
    });

    // Open new patient modal via the "+ Nuevo paciente" link inside the appointment modal
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", {
        name: /\+ Nuevo paciente/i
      })
    );

    await testingLibraryReactModule.waitFor(() => {
      expect(testingLibraryReactModule.screen.getByText("Nuevo paciente")).toBeInTheDocument();
    });

    // Fill in modal fields (no WhatsApp ID field — derived from prefix+phone)
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
      testingLibraryReactModule.screen.getByLabelText(/^Prefijo$/i),
      {
        target: { value: "+57" }
      }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText(/^Teléfono$/i),
      {
        target: { value: "300 111 2233" }
      }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText(/Edad/i),
      {
        target: { value: "29" }
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
        whatsappUserId: "573001112233",
        firstName: "Jane",
        lastName: "Doe",
        email: "jane@example.com",
        age: 29,
        location: "Bogota",
        phonePrefix: "+57",
        phone: "300 111 2233"
      });
    });
  });

  vitestModule.it("blocks modal submit when Prefijo is empty", async () => {
    const createPatientMock = vitestModule.vi.fn();
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

    // Open new manual appointment modal via "+ Nueva cita manual" button
    const nuevaCitaButtons = await testingLibraryReactModule.screen.findAllByRole("button", {
      name: /Nueva cita manual/i
    });
    testingLibraryReactModule.fireEvent.click(nuevaCitaButtons[0]!);

    await testingLibraryReactModule.waitFor(() => {
      expect(testingLibraryReactModule.screen.getByText("Nueva cita manual")).toBeInTheDocument();
    });

    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", {
        name: /\+ Nuevo paciente/i
      })
    );

    await testingLibraryReactModule.waitFor(() => {
      expect(testingLibraryReactModule.screen.getByText("Nuevo paciente")).toBeInTheDocument();
    });

    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText(/^Nombre$/i),
      { target: { value: "Jane" } }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText(/Apellido/i),
      { target: { value: "Doe" } }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText(/Email/i),
      { target: { value: "jane@example.com" } }
    );
    // Leave Prefijo empty intentionally
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText(/^Teléfono$/i),
      { target: { value: "300 111 2233" } }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText(/Edad/i),
      { target: { value: "29" } }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText(/Ubicación/i),
      { target: { value: "Bogota" } }
    );

    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: "Crear paciente" })
    );

    await testingLibraryReactModule.waitFor(() => {
      expect(
        testingLibraryReactModule.screen.getByText(/Especifica el prefijo telefónico/)
      ).toBeInTheDocument();
    });
    expect(createPatientMock).not.toHaveBeenCalled();
  });

  vitestModule.it("creates manual appointment from agenda panel", async () => {
    vitestModule.vi.spyOn(luxonModule.DateTime, "now").mockReturnValue(
      luxonModule.DateTime.fromISO("2026-03-01T00:00:00", {
        zone: "America/Bogota"
      }) as luxonModule.DateTime<true>
    );

    const createManualAppointmentMock = vitestModule.vi.fn(async () => ({
      appointmentId: "manual-1",
      tenantId: "tenant-1",
      patientWhatsappUserId: "wa-1",
      status: "SCHEDULED",
      calendarEventId: "event-1",
      startAt: "2026-03-12T09:00:00-05:00",
      endAt: "2026-03-12T10:00:00-05:00",
      timezone: "America/Bogota",
      isVirtual: false,
      meetUrl: null,
      paymentAmountCop: 120000,
      paymentCurrency: "COP" as const,
      paymentMethod: null,
      paymentStatus: "PENDING",
      paymentUpdatedAt: null,
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
          professionalTimezone: "America/Bogota",
          connectedAt: "2026-03-01T00:00:00Z"
        }))
      },
      schedulingUseCase: {
        listRequests: vitestModule.vi.fn(async () => []),
        getAvailability: vitestModule.vi.fn(async () => ({
          tenantId: "tenant-1",
          calendarId: "primary",
          timezone: "America/Bogota",
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
            location: "Bogota",
            phonePrefix: null,
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

    // Open the new manual appointment modal via "+ Nueva cita manual" button
    const nuevaCitaButtons = await testingLibraryReactModule.screen.findAllByRole("button", {
      name: /Nueva cita manual/i
    });
    testingLibraryReactModule.fireEvent.click(nuevaCitaButtons[0]!);

    await testingLibraryReactModule.waitFor(() => {
      expect(testingLibraryReactModule.screen.getByText("Nueva cita manual")).toBeInTheDocument();
    });

    await testingLibraryReactModule.waitFor(() => {
      expect(
        testingLibraryReactModule.screen.getByRole("option", {
          name: /Jane Doe · 573001112233/
        })
      ).toBeInTheDocument();
    });

    // Scope to the modal to avoid colliding with the page calendar
    const modalEl = testingLibraryReactModule.screen.getByTestId("new-manual-appointment-modal");
    const withinModal = testingLibraryReactModule.within(modalEl);

    // Select patient
    const patientSelect = withinModal.getByRole("combobox", {
      name: /Seleccionar paciente/i
    });
    testingLibraryReactModule.fireEvent.change(patientSelect, {
      target: { value: "wa-1" }
    });
    expect(patientSelect).toHaveValue("wa-1");

    // Click day 12 in the SlotPicker calendar (March 12 is future from mock now=March 1)
    const dayButtons = withinModal.getAllByRole("button", { name: "12" });
    testingLibraryReactModule.fireEvent.click(dayButtons[0]!);

    // Click the 9 AM slot chip
    await testingLibraryReactModule.waitFor(() => {
      expect(withinModal.getAllByRole("button", { name: "9 AM" })[0]).toBeInTheDocument();
    });
    testingLibraryReactModule.fireEvent.click(
      withinModal.getAllByRole("button", { name: "9 AM" })[0]!
    );

    // Fill in the summary
    testingLibraryReactModule.fireEvent.change(
      withinModal.getByLabelText(/^Motivo de consulta$/i),
      {
        target: { value: "Cita manual" }
      }
    );

    // Fill in the payment amount (required by the modal)
    testingLibraryReactModule.fireEvent.change(withinModal.getByRole("spinbutton"), {
      target: { value: "120000" }
    });

    // Submit
    testingLibraryReactModule.fireEvent.click(
      withinModal.getByRole("button", {
        name: "Agendar cita"
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
    vitestModule.vi
      .spyOn(luxonModule.DateTime, "now")
      .mockReturnValue(luxonModule.DateTime.utc(2026, 3, 1, 0, 0, 0) as luxonModule.DateTime<true>);

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
      testingLibraryReactModule.screen.getAllByRole("button", {
        name: /^Agenda$/
      })[0]!
    );

    // Wait for data to load, then navigate to detail via mobile wizard
    await testingLibraryReactModule.waitFor(() => {
      expect(
        testingLibraryReactModule.screen.getByText("Calendario de citas agendadas")
      ).toBeInTheDocument();
    });

    // Click day "12" in the mobile calendar to go to dayList step
    const dayButtons = testingLibraryReactModule.screen.getAllByRole("button", { name: "12" });
    testingLibraryReactModule.fireEvent.click(dayButtons[0]!);

    // Click the 09:00 - 10:00 appointment in dayList to go to detail step
    const timeButtons = await testingLibraryReactModule.screen.findAllByRole("button", {
      name: /09:00 - 10:00/
    });
    testingLibraryReactModule.fireEvent.click(timeButtons[0]!);

    // AppointmentDetailCard is now shown; click "Cancelar cita" in ACCIONES
    // (new behavior: single click triggers window.confirm() and cancels immediately)
    const cancelAccionesButtons = await testingLibraryReactModule.screen.findAllByRole("button", {
      name: "Cancelar cita"
    });
    testingLibraryReactModule.fireEvent.click(cancelAccionesButtons[0]!);

    await testingLibraryReactModule.waitFor(() => {
      expect(cancelBookedSlotMock).toHaveBeenCalledWith("req-booked-1", {
        reason: null
      });
    });
    expect(confirmSpy).toHaveBeenCalledTimes(1);
  });

  vitestModule.it("updates manual appointment payment from booked detail", async () => {
    vitestModule.vi
      .spyOn(luxonModule.DateTime, "now")
      .mockReturnValue(luxonModule.DateTime.utc(2026, 3, 1, 0, 0, 0) as luxonModule.DateTime<true>);

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
      isVirtual: false,
      meetUrl: null,
      paymentAmountCop: 120000,
      paymentCurrency: "COP" as const,
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
            location: "Bogota",
            phonePrefix: null,
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
            isVirtual: false,
            meetUrl: null,
            paymentAmountCop: null,
            paymentCurrency: "COP" as const,
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
      testingLibraryReactModule.screen.getAllByRole("button", { name: /^Agenda$/ })[0]!
    );

    // Wait for calendar to load, then navigate to detail via mobile wizard
    await testingLibraryReactModule.waitFor(() => {
      expect(
        testingLibraryReactModule.screen.getByText("Calendario de citas agendadas")
      ).toBeInTheDocument();
    });

    // Click day "12" in mobile calendar to go to dayList step
    const dayButtons = testingLibraryReactModule.screen.getAllByRole("button", { name: "12" });
    testingLibraryReactModule.fireEvent.click(dayButtons[0]!);

    // Click the 15:00 - 16:00 appointment in dayList to go to detail step
    const timeButtons = await testingLibraryReactModule.screen.findAllByRole("button", {
      name: /15:00 - 16:00/
    });
    testingLibraryReactModule.fireEvent.click(timeButtons[0]!);

    // AppointmentDetailCard is shown with payment form (PENDING status)
    await testingLibraryReactModule.waitFor(() => {
      expect(
        testingLibraryReactModule.screen.getByRole("spinbutton", { name: /Valor \(COP\)/i })
      ).toBeInTheDocument();
    });

    // Fill in payment amount
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByRole("spinbutton", {
        name: /Valor \(COP\)/i
      }),
      {
        target: { value: "120000" }
      }
    );

    // Change payment category
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByRole("combobox", { name: /Categoría de pago/i }),
      {
        target: { value: "TRANSFER" }
      }
    );

    // Submit payment — AppointmentDetailCard always sets paymentStatus to "PAID"
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: "Registrar pago" })
    );

    await testingLibraryReactModule.waitFor(() => {
      expect(updateManualPaymentMock).toHaveBeenCalledWith("manual-1", {
        paymentAmountCop: 120000,
        paymentCurrency: "COP",
        paymentMethod: "TRANSFER",
        paymentStatus: "PAID"
      });
    });
  });

  vitestModule.it("updates chatbot appointment payment from booked detail", async () => {
    vitestModule.vi
      .spyOn(luxonModule.DateTime, "now")
      .mockReturnValue(luxonModule.DateTime.utc(2026, 3, 1, 0, 0, 0) as luxonModule.DateTime<true>);

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
      paymentCurrency: "COP" as const,
      paymentMethod: "CASH",
      paymentStatus: "PAID",
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
            paymentCurrency: "COP" as const,
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
      testingLibraryReactModule.screen.getAllByRole("button", { name: /^Agenda$/ })[0]!
    );

    // Wait for calendar to load, then navigate to detail via mobile wizard
    await testingLibraryReactModule.waitFor(() => {
      expect(
        testingLibraryReactModule.screen.getByText("Calendario de citas agendadas")
      ).toBeInTheDocument();
    });

    // Click day "12" in mobile calendar to go to dayList step
    const dayButtons = testingLibraryReactModule.screen.getAllByRole("button", { name: "12" });
    testingLibraryReactModule.fireEvent.click(dayButtons[0]!);

    // Click the 09:00 - 10:00 appointment in dayList to go to detail step
    const timeButtons = await testingLibraryReactModule.screen.findAllByRole("button", {
      name: /09:00 - 10:00/
    });
    testingLibraryReactModule.fireEvent.click(timeButtons[0]!);

    // AppointmentDetailCard is shown with payment form (PENDING status)
    await testingLibraryReactModule.waitFor(() => {
      expect(
        testingLibraryReactModule.screen.getByRole("spinbutton", { name: /Valor \(COP\)/i })
      ).toBeInTheDocument();
    });

    // Fill in payment amount (default category is CASH)
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByRole("spinbutton", {
        name: /Valor \(COP\)/i
      }),
      {
        target: { value: "80000" }
      }
    );

    // Submit payment — AppointmentDetailCard always sets paymentStatus to "PAID"
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: "Registrar pago" })
    );

    await testingLibraryReactModule.waitFor(() => {
      expect(updateBookedPaymentMock).toHaveBeenCalledWith("req-booked-1", {
        paymentAmountCop: 80000,
        paymentCurrency: "COP",
        paymentMethod: "CASH",
        paymentStatus: "PAID"
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
            paymentCurrency: "COP" as const,
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
            paymentCurrency: "COP" as const,
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

    const finanzasButtons = testingLibraryReactModule.screen.getAllByRole("button", {
      name: /Finanzas/
    });
    testingLibraryReactModule.fireEvent.click(finanzasButtons[0]!);

    await testingLibraryReactModule.waitFor(() => {
      expect(testingLibraryReactModule.screen.getByText("Paciente Bot")).toBeInTheDocument();
      expect(testingLibraryReactModule.screen.getByText("Paciente Manual")).toBeInTheDocument();
    });

    const filtersToggle = testingLibraryReactModule.screen.getByRole("button", {
      name: /Filtros/i
    });
    testingLibraryReactModule.fireEvent.click(filtersToggle);

    const paidChip = await testingLibraryReactModule.screen.findByRole("button", {
      name: /^Pagadas$/i
    });
    testingLibraryReactModule.fireEvent.click(paidChip);

    await testingLibraryReactModule.waitFor(() => {
      expect(testingLibraryReactModule.screen.getByText("Paciente Bot")).toBeInTheDocument();
      expect(testingLibraryReactModule.screen.queryByText("Paciente Manual")).toBeNull();
    });
  });

  vitestModule.it(
    "shows SlotPicker when Reprogramar cita is clicked for a booked manual appointment",
    async () => {
      vitestModule.vi
        .spyOn(luxonModule.DateTime, "now")
        .mockReturnValue(
          luxonModule.DateTime.utc(2026, 3, 1, 0, 0, 0) as luxonModule.DateTime<true>
        );

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
              location: "Bogota",
              phonePrefix: null,
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
              isVirtual: false,
              meetUrl: null,
              paymentAmountCop: null,
              paymentCurrency: "COP" as const,
              paymentMethod: null,
              paymentStatus: "PENDING",
              paymentUpdatedAt: null,
              createdAt: "2026-03-01T00:00:00Z",
              updatedAt: "2026-03-01T00:00:00Z",
              cancelledAt: null
            }
          ]),
          rescheduleAppointment: vitestModule.vi.fn(),
          cancelAppointment: vitestModule.vi.fn(),
          updatePayment: vitestModule.vi.fn()
        }
      };

      renderAgendaPage(container);

      testingLibraryReactModule.fireEvent.click(
        testingLibraryReactModule.screen.getAllByRole("button", { name: /^Agenda$/ })[0]!
      );

      // Wait for calendar to load
      await testingLibraryReactModule.waitFor(() => {
        expect(
          testingLibraryReactModule.screen.getByText("Calendario de citas agendadas")
        ).toBeInTheDocument();
      });

      // Click day "12" in the calendar
      const dayButtons = testingLibraryReactModule.screen.getAllByRole("button", { name: "12" });
      testingLibraryReactModule.fireEvent.click(dayButtons[0]!);

      // Click the appointment in dayList to go to detail step
      const timeButtons = await testingLibraryReactModule.screen.findAllByRole("button", {
        name: /15:00 - 16:00/
      });
      testingLibraryReactModule.fireEvent.click(timeButtons[0]!);

      // Click "Reprogramar cita" button in AppointmentDetailCard
      const rescheduleButton = await testingLibraryReactModule.screen.findByRole("button", {
        name: "Reprogramar cita"
      });
      testingLibraryReactModule.fireEvent.click(rescheduleButton);

      // SlotPicker panel should be visible
      await testingLibraryReactModule.waitFor(() => {
        expect(
          testingLibraryReactModule.screen.getByTestId("reschedule-slotpicker-panel")
        ).toBeInTheDocument();
      });

      // Helper text should be shown (unique to the SlotPicker panel)
      expect(
        testingLibraryReactModule.screen.getByText("Selecciona un nuevo horario disponible.")
      ).toBeInTheDocument();
    }
  );

  vitestModule.it(
    "pre-selects current appointment slot in SlotPicker when reschedule opens",
    async () => {
      vitestModule.vi
        .spyOn(luxonModule.DateTime, "now")
        .mockReturnValue(
          luxonModule.DateTime.utc(2026, 3, 1, 0, 0, 0) as luxonModule.DateTime<true>
        );

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
              location: "Bogota",
              phonePrefix: null,
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
              isVirtual: false,
              meetUrl: null,
              paymentAmountCop: null,
              paymentCurrency: "COP" as const,
              paymentMethod: null,
              paymentStatus: "PENDING",
              paymentUpdatedAt: null,
              createdAt: "2026-03-01T00:00:00Z",
              updatedAt: "2026-03-01T00:00:00Z",
              cancelledAt: null
            }
          ]),
          rescheduleAppointment: vitestModule.vi.fn(),
          cancelAppointment: vitestModule.vi.fn(),
          updatePayment: vitestModule.vi.fn()
        }
      };

      renderAgendaPage(container);

      testingLibraryReactModule.fireEvent.click(
        testingLibraryReactModule.screen.getAllByRole("button", { name: /^Agenda$/ })[0]!
      );

      await testingLibraryReactModule.waitFor(() => {
        expect(
          testingLibraryReactModule.screen.getByText("Calendario de citas agendadas")
        ).toBeInTheDocument();
      });

      // Navigate to detail
      const dayButtons = testingLibraryReactModule.screen.getAllByRole("button", { name: "12" });
      testingLibraryReactModule.fireEvent.click(dayButtons[0]!);

      const timeButtons = await testingLibraryReactModule.screen.findAllByRole("button", {
        name: /15:00 - 16:00/
      });
      testingLibraryReactModule.fireEvent.click(timeButtons[0]!);

      // Open reschedule
      const rescheduleButton = await testingLibraryReactModule.screen.findByRole("button", {
        name: "Reprogramar cita"
      });
      testingLibraryReactModule.fireEvent.click(rescheduleButton);

      // SlotPicker should show "Horarios seleccionados" pill for the current slot
      await testingLibraryReactModule.waitFor(() => {
        expect(
          testingLibraryReactModule.screen.getByText("Horarios seleccionados")
        ).toBeInTheDocument();
      });

      // The pill should show the current appointment time (mar. 12, 3:00 PM in Bogota = UTC-5, so 15:00 UTC = 10:00 AM Bogota)
      // SlotPicker renders as LLL dd, h:mm a in locale es
      // UTC 15:00 = America/Bogota 10:00 (UTC-5)
      expect(
        testingLibraryReactModule.screen.getByText(/mar\. 12.*10:00|10:00 a/i)
      ).toBeInTheDocument();
    }
  );
});
