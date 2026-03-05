export type SchedulingRequestKind = "INITIAL" | "RETRY";

export type SchedulingRequestStatus =
  | "AWAITING_CONSULTATION_REVIEW"
  | "AWAITING_CONSULTATION_DETAILS"
  | "COLLECTING_PREFERENCES"
  | "AWAITING_PROFESSIONAL_SLOTS"
  | "AWAITING_PATIENT_CHOICE"
  | "CONSULTATION_REJECTED"
  | "CANCELLED"
  | "BOOKED"
  | "HUMAN_HANDOFF";

export type SchedulingSlotStatus = "PROPOSED" | "SELECTED" | "BOOKED" | "REJECTED" | "UNAVAILABLE";

export interface SchedulingSlot {
  slotId: string;
  startAt: string;
  endAt: string;
  timezone: string;
  status: SchedulingSlotStatus;
}

export interface SchedulingRequestSummary {
  requestId: string;
  conversationId: string;
  whatsappUserId: string;
  requestKind: SchedulingRequestKind;
  status: SchedulingRequestStatus;
  roundNumber: number;
  patientPreferenceNote: string | null;
  rejectionSummary: string | null;
  professionalNote: string | null;
  patientFirstName: string | null;
  patientLastName: string | null;
  patientAge: number | null;
  consultationReason: string | null;
  consultationDetails: string | null;
  appointmentModality: "PRESENCIAL" | "VIRTUAL" | null;
  patientLocation: string | null;
  slotOptionsMap: Record<string, string>;
  selectedSlotId: string | null;
  calendarEventId: string | null;
  createdAt: string;
  updatedAt: string;
  slots: SchedulingSlot[];
}

export interface ProfessionalSlotInput {
  slotId: string;
  startAt: string;
  endAt: string;
  timezone: string;
}

export interface SubmitProfessionalSlotsInput {
  slots: ProfessionalSlotInput[];
  professionalNote: string | null;
}

export interface SubmitProfessionalSlotsResult {
  status: "AWAITING_PATIENT_CHOICE";
  slotBatchId: string;
  outboundMessageId: string;
  assistantText: string;
}

export interface ResolveConsultationReviewInput {
  decision: "APPROVE" | "REQUEST_MORE_INFO" | "REJECT";
  professionalNote: string | null;
}

export interface ResolveConsultationReviewResult {
  status: SchedulingRequestStatus;
  outboundMessageId: string;
  assistantText: string;
}

export interface RescheduleBookedSlotInput {
  startAt: string;
  endAt: string;
  timezone: string;
  eventSummary: string | null;
}

export interface CancelBookedSlotInput {
  reason: string | null;
}
