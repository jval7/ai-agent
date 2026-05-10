export interface ScheduledReminder {
  reminderId: string;
  sourceType: "SCHEDULING_REQUEST" | "MANUAL_APPOINTMENT";
  sourceId: string;
  patientWhatsappUserId: string;
  patientName: string;
  appointmentStartAt: string;
  reminderScheduledFor: string;
  templateName: string;
  status: "PENDING" | "SENT" | "DELIVERED" | "READ" | "FAILED" | "CANCELLED";
  failureReason: string | null;
  createdAt: string;
}

export interface ScheduledReminderList {
  items: ScheduledReminder[];
}
