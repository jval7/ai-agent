import pydantic


class OnboardingStatusResponseDTO(pydantic.BaseModel):
    whatsapp_connected: bool
    google_calendar_connected: bool
    ready: bool
