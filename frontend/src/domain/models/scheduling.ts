export type SchedulingRequestKind = "INITIAL" | "RETRY";

export type SchedulingRequestStatus =
  | "AWAITING_PROFESSIONAL_SLOTS"
  | "AWAITING_PATIENT_CHOICE"
  | "BOOKED"
  | "HUMAN_HANDOFF";

export type SchedulingSlotStatus = "PROPOSED" | "BOOKED" | "REJECTED" | "UNAVAILABLE";

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
  patientPreferenceNote: string;
  rejectionSummary: string | null;
  professionalNote: string | null;
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
