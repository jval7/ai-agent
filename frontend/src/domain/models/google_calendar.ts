export type GoogleCalendarConnectionStatus = "DISCONNECTED" | "PENDING" | "CONNECTED";

export interface GoogleOauthSession {
  state: string;
  connectUrl: string;
}

export interface GoogleCalendarConnection {
  tenantId: string;
  status: GoogleCalendarConnectionStatus;
  calendarId: string | null;
  professionalTimezone: string | null;
  connectedAt: string | null;
}

export interface GoogleCalendarBusyInterval {
  startAt: string;
  endAt: string;
}

export interface GoogleCalendarAvailability {
  tenantId: string;
  calendarId: string;
  timezone: string;
  busyIntervals: GoogleCalendarBusyInterval[];
}
