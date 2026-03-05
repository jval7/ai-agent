export type ManualAppointmentStatus = "SCHEDULED" | "CANCELLED";

export interface ManualAppointment {
  appointmentId: string;
  tenantId: string;
  patientWhatsappUserId: string;
  status: ManualAppointmentStatus;
  calendarEventId: string | null;
  startAt: string;
  endAt: string;
  timezone: string;
  summary: string;
  createdAt: string;
  updatedAt: string;
  cancelledAt: string | null;
}

export interface CreateManualAppointmentInput {
  patientWhatsappUserId: string;
  startAt: string;
  endAt: string;
  timezone: string;
  summary: string | null;
}

export interface RescheduleManualAppointmentInput {
  startAt: string;
  endAt: string;
  timezone: string;
  summary: string | null;
}

export interface CancelManualAppointmentInput {
  reason: string | null;
}
