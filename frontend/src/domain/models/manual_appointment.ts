export type ManualAppointmentStatus = "SCHEDULED" | "CANCELLED";
export type AppointmentPaymentMethod = "CASH" | "TRANSFER";
export type AppointmentPaymentStatus = "PENDING" | "PAID";
export type AppointmentPaymentCurrency = "COP" | "USD";

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
  isVirtual: boolean;
  meetUrl: string | null;
  paymentAmountCop: number | null;
  paymentCurrency: AppointmentPaymentCurrency;
  paymentMethod: AppointmentPaymentMethod | null;
  paymentStatus: AppointmentPaymentStatus;
  paymentUpdatedAt: string | null;
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
  isVirtual: boolean;
  paymentAmountCop: number;
  paymentCurrency: AppointmentPaymentCurrency;
  paymentStatus: AppointmentPaymentStatus;
  paymentMethod: AppointmentPaymentMethod | null;
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

export interface UpdateManualAppointmentPaymentInput {
  paymentAmountCop: number;
  paymentCurrency?: AppointmentPaymentCurrency;
  paymentMethod: AppointmentPaymentMethod;
  paymentStatus: AppointmentPaymentStatus;
}

export interface ChangeManualAppointmentModalityInput {
  newModality: "PRESENCIAL" | "VIRTUAL";
}
