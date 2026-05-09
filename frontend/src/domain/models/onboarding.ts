export interface OnboardingStatus {
  whatsappConnected: boolean;
  googleCalendarConnected: boolean;
  // True when Google rejected our refresh_token with invalid_grant — the
  // dashboard shows a reconnect banner so the user does not get silent
  // 502s on every Calendar call.
  googleCalendarReauthRequired: boolean;
  ready: boolean;
}
