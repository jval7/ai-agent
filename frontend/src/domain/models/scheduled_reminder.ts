export interface ScheduledReminder {
  reminderId: string;
  sourceType: "SCHEDULING_REQUEST" | "MANUAL_APPOINTMENT";
  sourceId: string;
  patientWhatsappUserId: string;
  patientName: string;
  appointmentStartAt: string;
  reminderScheduledFor: string;
  templateName: string;
  status: "PENDING" | "SENT" | "FAILED" | "CANCELLED";
  createdAt: string;
}

export interface ScheduledReminderList {
  items: ScheduledReminder[];
}
