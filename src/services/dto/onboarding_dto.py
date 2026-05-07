import pydantic


class OnboardingStatusResponseDTO(pydantic.BaseModel):
    whatsapp_connected: bool
    google_calendar_connected: bool
    # The user has a Google Calendar connection saved but it is no longer
    # usable: Google rejected the latest refresh with invalid_grant. The
    # UI uses this to show a reconnect banner instead of letting Calendar
    # endpoints fail with a 502 every poll.
    google_calendar_reauth_required: bool
    ready: bool
