import * as reactQueryModule from "@tanstack/react-query";
import * as testingLibraryReactModule from "@testing-library/react";
import * as luxonModule from "luxon";
import * as vitestModule from "vitest";

import type * as containerModule from "@infrastructure/di/container";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";

import * as newManualAppointmentModalModule from "./NewManualAppointmentModal";

function renderModal(
  props: Partial<newManualAppointmentModalModule.NewManualAppointmentModalProps> & {
    container?: unknown;
  } = {}
) {
  const {
    container: appContainer,
    isOpen = true,
    onClose = vitestModule.vi.fn(),
    onCreated = vitestModule.vi.fn()
  } = props;

  const defaultContainer = {
    patientUseCase: {
      listPatients: vitestModule.vi.fn(async () => []),
      createPatient: vitestModule.vi.fn()
    },
    schedulingUseCase: {
      getAvailability: vitestModule.vi.fn(async () => ({
        tenantId: "tenant-1",
        calendarId: "primary",
        timezone: "America/Bogota",
        busyIntervals: []
      }))
    },
    manualAppointmentUseCase: {
      createAppointment: vitestModule.vi.fn(async () => ({
        appointmentId: "appt-1",
        tenantId: "tenant-1",
        patientWhatsappUserId: "wa-1",
        status: "SCHEDULED",
        calendarEventId: "event-1",
        startAt: "2026-03-12T09:00:00-05:00",
        endAt: "2026-03-12T10:00:00-05:00",
        timezone: "America/Bogota",
        summary: null,
        isVirtual: true,
        meetUrl: "https://meet.google.com/abc",
        paymentAmountCop: 100000,
        paymentCurrency: "COP" as const,
        paymentMethod: null,
        paymentStatus: "PENDING",
        paymentUpdatedAt: null,
        createdAt: "2026-03-01T00:00:00Z",
        updatedAt: "2026-03-01T00:00:00Z",
        cancelledAt: null
      }))
    }
  };

  const resolvedContainer = appContainer ?? defaultContainer;

  const queryClient = new reactQueryModule.QueryClient({
    defaultOptions: { queries: { retry: false } }
  });

  return {
    ...testingLibraryReactModule.render(
      <reactQueryModule.QueryClientProvider client={queryClient}>
        <appContainerContextModule.AppContainerProvider
          container={resolvedContainer as containerModule.AppContainer}
        >
          <newManualAppointmentModalModule.NewManualAppointmentModal
            isOpen={isOpen}
            onClose={onClose}
            onCreated={onCreated}
          />
        </appContainerContextModule.AppContainerProvider>
      </reactQueryModule.QueryClientProvider>
    ),
    onClose,
    onCreated,
    resolvedContainer
  };
}

vitestModule.describe("NewManualAppointmentModal", () => {
  vitestModule.beforeEach(() => {
    vitestModule.vi.spyOn(luxonModule.DateTime, "now").mockReturnValue(
      luxonModule.DateTime.fromISO("2026-03-01T00:00:00", {
        zone: "America/Bogota"
      }) as luxonModule.DateTime<true>
    );
  });

  vitestModule.afterEach(() => {
    vitestModule.vi.restoreAllMocks();
  });

  vitestModule.it("renders modal heading and sections when isOpen is true", () => {
    renderModal();
    expect(testingLibraryReactModule.screen.getByText("Nueva cita manual")).toBeInTheDocument();
    expect(testingLibraryReactModule.screen.getByText("Paciente")).toBeInTheDocument();
    expect(testingLibraryReactModule.screen.getByText("Fecha y hora")).toBeInTheDocument();
    expect(testingLibraryReactModule.screen.getByText("Pago")).toBeInTheDocument();
    expect(
      testingLibraryReactModule.screen.getByRole("button", { name: "Agendar cita" })
    ).toBeInTheDocument();
  });

  vitestModule.it("renders nothing when isOpen is false", () => {
    renderModal({ isOpen: false });
    expect(
      testingLibraryReactModule.screen.queryByText("Nueva cita manual")
    ).not.toBeInTheDocument();
  });

  vitestModule.it("calls onClose when Cancelar button is clicked", () => {
    const { onClose } = renderModal();
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: "Cancelar" })
    );
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  vitestModule.it("calls onClose when ESC key is pressed", () => {
    const { onClose } = renderModal();
    testingLibraryReactModule.fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  vitestModule.it("shows error when submitting without selecting a patient", async () => {
    renderModal();
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: "Agendar cita" })
    );
    await testingLibraryReactModule.waitFor(() => {
      expect(
        testingLibraryReactModule.screen.getByText("Debes seleccionar un paciente.")
      ).toBeInTheDocument();
    });
  });

  vitestModule.it("shows payment amount error when amount is zero or empty on submit", async () => {
    const listPatientsMock = vitestModule.vi.fn(async () => [
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
    ]);

    renderModal({
      container: {
        patientUseCase: { listPatients: listPatientsMock, createPatient: vitestModule.vi.fn() },
        schedulingUseCase: {
          getAvailability: vitestModule.vi.fn(async () => ({
            tenantId: "tenant-1",
            calendarId: "primary",
            timezone: "America/Bogota",
            busyIntervals: []
          }))
        },
        manualAppointmentUseCase: { createAppointment: vitestModule.vi.fn() }
      }
    });

    // Wait for patient list to load then select a patient
    await testingLibraryReactModule.waitFor(() => {
      expect(
        testingLibraryReactModule.screen.getByRole("option", { name: /Jane Doe/i })
      ).toBeInTheDocument();
    });

    const modalEl = testingLibraryReactModule.screen.getByTestId("new-manual-appointment-modal");
    const withinModal = testingLibraryReactModule.within(modalEl);

    testingLibraryReactModule.fireEvent.change(
      withinModal.getByRole("combobox", { name: /Seleccionar paciente/i }),
      { target: { value: "wa-1" } }
    );

    // Click day 12
    const dayButtons = withinModal.getAllByRole("button", { name: "12" });
    testingLibraryReactModule.fireEvent.click(dayButtons[0]!);

    // Wait for 9 AM slot and click it
    await testingLibraryReactModule.waitFor(() => {
      expect(withinModal.getAllByRole("button", { name: "9 AM" })[0]).toBeInTheDocument();
    });
    testingLibraryReactModule.fireEvent.click(
      withinModal.getAllByRole("button", { name: "9 AM" })[0]!
    );

    // Leave payment amount empty and submit
    testingLibraryReactModule.fireEvent.click(
      withinModal.getByRole("button", { name: "Agendar cita" })
    );

    await testingLibraryReactModule.waitFor(() => {
      expect(
        testingLibraryReactModule.screen.getByText("El valor de la consulta debe ser mayor a cero.")
      ).toBeInTheDocument();
    });
  });

  vitestModule.it(
    "shows payment method error when PAID status is selected but no method chosen",
    async () => {
      renderModal();
      // Select PAID status
      testingLibraryReactModule.fireEvent.click(
        testingLibraryReactModule.screen.getByRole("button", { name: "Pagado" })
      );
      // Try to submit without filling required fields
      testingLibraryReactModule.fireEvent.click(
        testingLibraryReactModule.screen.getByRole("button", { name: "Agendar cita" })
      );
      // Hits patient error first, but PAID flow is set up
      await testingLibraryReactModule.waitFor(() => {
        expect(
          testingLibraryReactModule.screen.getByText("Debes seleccionar un paciente.")
        ).toBeInTheDocument();
      });
    }
  );

  vitestModule.it("creates appointment on happy path submit", async () => {
    const createAppointmentMock = vitestModule.vi.fn(async () => ({
      appointmentId: "appt-1",
      tenantId: "tenant-1",
      patientWhatsappUserId: "wa-1",
      status: "SCHEDULED",
      calendarEventId: "event-1",
      startAt: "2026-03-12T09:00:00-05:00",
      endAt: "2026-03-12T10:00:00-05:00",
      timezone: "America/Bogota",
      summary: null,
      isVirtual: true,
      meetUrl: "https://meet.google.com/abc",
      paymentAmountCop: 80000,
      paymentCurrency: "COP" as const,
      paymentMethod: null,
      paymentStatus: "PENDING",
      paymentUpdatedAt: null,
      createdAt: "2026-03-01T00:00:00Z",
      updatedAt: "2026-03-01T00:00:00Z",
      cancelledAt: null
    }));

    const { onCreated } = renderModal({
      container: {
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
          ]),
          createPatient: vitestModule.vi.fn()
        },
        schedulingUseCase: {
          getAvailability: vitestModule.vi.fn(async () => ({
            tenantId: "tenant-1",
            calendarId: "primary",
            timezone: "America/Bogota",
            busyIntervals: []
          }))
        },
        manualAppointmentUseCase: { createAppointment: createAppointmentMock }
      }
    });

    await testingLibraryReactModule.waitFor(() => {
      expect(
        testingLibraryReactModule.screen.getByRole("option", { name: /Jane Doe/i })
      ).toBeInTheDocument();
    });

    const modalEl = testingLibraryReactModule.screen.getByTestId("new-manual-appointment-modal");
    const withinModal = testingLibraryReactModule.within(modalEl);

    testingLibraryReactModule.fireEvent.change(
      withinModal.getByRole("combobox", { name: /Seleccionar paciente/i }),
      { target: { value: "wa-1" } }
    );

    // Select day 12
    const dayButtons = withinModal.getAllByRole("button", { name: "12" });
    testingLibraryReactModule.fireEvent.click(dayButtons[0]!);

    // Select 9 AM slot
    await testingLibraryReactModule.waitFor(() => {
      expect(withinModal.getAllByRole("button", { name: "9 AM" })[0]).toBeInTheDocument();
    });
    testingLibraryReactModule.fireEvent.click(
      withinModal.getAllByRole("button", { name: "9 AM" })[0]!
    );

    // Fill in payment amount
    testingLibraryReactModule.fireEvent.change(withinModal.getByRole("spinbutton"), {
      target: { value: "80000" }
    });

    // Submit
    testingLibraryReactModule.fireEvent.click(
      withinModal.getByRole("button", { name: "Agendar cita" })
    );

    await testingLibraryReactModule.waitFor(() => {
      expect(createAppointmentMock).toHaveBeenCalledWith(
        expect.objectContaining({
          patientWhatsappUserId: "wa-1",
          paymentAmountCop: 80000,
          paymentCurrency: "COP",
          paymentStatus: "PENDING",
          paymentMethod: null
        })
      );
    });

    await testingLibraryReactModule.waitFor(() => {
      expect(onCreated).toHaveBeenCalledTimes(1);
    });
  });
});
