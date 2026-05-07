import src.services.dto.onboarding_dto as onboarding_dto
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import src.services.use_cases.whatsapp_onboarding_service as whatsapp_onboarding_service


class OnboardingStatusService:
    def __init__(
        self,
        whatsapp_onboarding_service: whatsapp_onboarding_service.WhatsappOnboardingService,
        google_calendar_onboarding_service: (
            google_calendar_onboarding_service.GoogleCalendarOnboardingService
        ),
    ) -> None:
        self._whatsapp_onboarding_service = whatsapp_onboarding_service
        self._google_calendar_onboarding_service = google_calendar_onboarding_service

    def get_status(self, tenant_id: str) -> onboarding_dto.OnboardingStatusResponseDTO:
        whatsapp_status = self._whatsapp_onboarding_service.get_connection_status(tenant_id)
        google_status = self._google_calendar_onboarding_service.get_connection_status(tenant_id)
        whatsapp_connected = whatsapp_status.status == "CONNECTED"
        google_connected = google_status.status == "CONNECTED"
        google_reauth_required = google_status.status == "REAUTH_REQUIRED"
        return onboarding_dto.OnboardingStatusResponseDTO(
            whatsapp_connected=whatsapp_connected,
            google_calendar_connected=google_connected,
            google_calendar_reauth_required=google_reauth_required,
            ready=whatsapp_connected and google_connected,
        )
