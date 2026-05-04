import * as vitestModule from "vitest";

import type * as backendApiPort from "@ports/backend_api_port";

import * as manualAppointmentUseCaseModule from "./manual_appointment_use_case";

vitestModule.describe("ManualAppointmentUseCase", () => {
  vitestModule.it("delegates manual appointment operations to api port", async () => {
    const listManualAppointmentsMock = vitestModule.vi.fn(async () => []);
    const createManualAppointmentMock = vitestModule.vi.fn(async () => ({
      appointmentId: "appt-1",
      tenantId: "tenant-1",
      patientWhatsappUserId: "wa-1",
      status: "SCHEDULED",
      calendarEventId: "event-1",
      startAt: "2026-03-10T10:00:00Z",
      endAt: "2026-03-10T11:00:00Z",
      timezone: "America/Bogota",
      summary: "Cita - Jane Doe",
      isVirtual: true,
      meetUrl: "https://meet.google.com/abc-defg-hij",
      paymentAmountCop: 120000,
      paymentCurrency: "COP" as const,
      paymentMethod: null,
      paymentStatus: "PENDING",
      paymentUpdatedAt: null,
      createdAt: "2026-03-01T10:00:00Z",
      updatedAt: "2026-03-01T10:00:00Z",
      cancelledAt: null
    }));
    const rescheduleManualAppointmentMock = vitestModule.vi.fn(async () => ({
      appointmentId: "appt-1",
      tenantId: "tenant-1",
      patientWhatsappUserId: "wa-1",
      status: "SCHEDULED",
      calendarEventId: "event-1",
      startAt: "2026-03-11T10:00:00Z",
      endAt: "2026-03-11T11:00:00Z",
      timezone: "America/Bogota",
      summary: "Cita - Jane Doe",
      isVirtual: true,
      meetUrl: "https://meet.google.com/abc-defg-hij",
      paymentAmountCop: null,
      paymentCurrency: "COP" as const,
      paymentMethod: null,
      paymentStatus: "PENDING",
      paymentUpdatedAt: null,
      createdAt: "2026-03-01T10:00:00Z",
      updatedAt: "2026-03-02T10:00:00Z",
      cancelledAt: null
    }));
    const cancelManualAppointmentMock = vitestModule.vi.fn(async () => ({
      appointmentId: "appt-1",
      tenantId: "tenant-1",
      patientWhatsappUserId: "wa-1",
      status: "CANCELLED",
      calendarEventId: null,
      startAt: "2026-03-11T10:00:00Z",
      endAt: "2026-03-11T11:00:00Z",
      timezone: "America/Bogota",
      summary: "Cita - Jane Doe",
      isVirtual: false,
      meetUrl: null,
      paymentAmountCop: 100000,
      paymentCurrency: "COP" as const,
      paymentMethod: "CASH",
      paymentStatus: "PENDING",
      paymentUpdatedAt: "2026-03-03T09:00:00Z",
      createdAt: "2026-03-01T10:00:00Z",
      updatedAt: "2026-03-03T10:00:00Z",
      cancelledAt: "2026-03-03T10:00:00Z"
    }));
    const updateManualAppointmentPaymentMock = vitestModule.vi.fn(async () => ({
      appointmentId: "appt-1",
      tenantId: "tenant-1",
      patientWhatsappUserId: "wa-1",
      status: "SCHEDULED",
      calendarEventId: "event-1",
      startAt: "2026-03-11T10:00:00Z",
      endAt: "2026-03-11T11:00:00Z",
      timezone: "America/Bogota",
      summary: "Cita - Jane Doe",
      isVirtual: true,
      meetUrl: null,
      paymentAmountCop: 100000,
      paymentCurrency: "COP" as const,
      paymentMethod: "TRANSFER",
      paymentStatus: "PAID",
      paymentUpdatedAt: "2026-03-03T11:00:00Z",
      createdAt: "2026-03-01T10:00:00Z",
      updatedAt: "2026-03-03T11:00:00Z",
      cancelledAt: null
    }));
    const changeManualAppointmentModalityMock = vitestModule.vi.fn(async () => ({
      appointmentId: "appt-1",
      tenantId: "tenant-1",
      patientWhatsappUserId: "wa-1",
      status: "SCHEDULED" as const,
      calendarEventId: "event-1",
      startAt: "2026-03-11T10:00:00Z",
      endAt: "2026-03-11T11:00:00Z",
      timezone: "America/Bogota",
      summary: "Cita - Jane Doe",
      isVirtual: false,
      meetUrl: null,
      paymentAmountCop: null,
      paymentCurrency: "COP" as const,
      paymentMethod: null,
      paymentStatus: "PENDING" as const,
      paymentUpdatedAt: null,
      createdAt: "2026-03-01T10:00:00Z",
      updatedAt: "2026-03-11T10:00:00Z",
      cancelledAt: null
    }));
    const apiMock = {
      listManualAppointments: listManualAppointmentsMock,
      createManualAppointment: createManualAppointmentMock,
      rescheduleManualAppointment: rescheduleManualAppointmentMock,
      cancelManualAppointment: cancelManualAppointmentMock,
      updateManualAppointmentPayment: updateManualAppointmentPaymentMock,
      changeManualAppointmentModality: changeManualAppointmentModalityMock
    } as Partial<backendApiPort.BackendApiPort> as backendApiPort.BackendApiPort;

    const useCase = new manualAppointmentUseCaseModule.ManualAppointmentUseCase(apiMock);

    await useCase.listAppointments();
    await useCase.createAppointment({
      patientWhatsappUserId: "wa-1",
      startAt: "2026-03-10T10:00:00Z",
      endAt: "2026-03-10T11:00:00Z",
      timezone: "America/Bogota",
      summary: null,
      isVirtual: true,
      paymentAmountCop: 120000,
      paymentCurrency: "COP",
      paymentStatus: "PENDING",
      paymentMethod: null
    });
    await useCase.rescheduleAppointment("appt-1", {
      startAt: "2026-03-11T10:00:00Z",
      endAt: "2026-03-11T11:00:00Z",
      timezone: "America/Bogota",
      summary: "Cita - Jane Doe"
    });
    await useCase.cancelAppointment("appt-1", { reason: "Paciente reagenda" });
    await useCase.updatePayment("appt-1", {
      paymentAmountCop: 100000,
      paymentMethod: "TRANSFER",
      paymentStatus: "PAID"
    });
    const changeResult = await useCase.changeModality("appt-1", { newModality: "PRESENCIAL" });

    vitestModule.expect(listManualAppointmentsMock).toHaveBeenCalledTimes(1);
    vitestModule.expect(createManualAppointmentMock).toHaveBeenCalledTimes(1);
    vitestModule.expect(rescheduleManualAppointmentMock).toHaveBeenCalledTimes(1);
    vitestModule.expect(cancelManualAppointmentMock).toHaveBeenCalledTimes(1);
    vitestModule.expect(updateManualAppointmentPaymentMock).toHaveBeenCalledTimes(1);
    vitestModule.expect(changeManualAppointmentModalityMock).toHaveBeenCalledWith("appt-1", {
      newModality: "PRESENCIAL"
    });
    vitestModule.expect(changeResult.isVirtual).toBe(false);
  });
});
