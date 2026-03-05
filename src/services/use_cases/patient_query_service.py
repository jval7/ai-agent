import src.domain.entities.patient as patient_entity
import src.infra.logs as app_logs
import src.ports.clock_port as clock_port
import src.ports.patient_repository_port as patient_repository_port
import src.ports.scheduling_repository_port as scheduling_repository_port
import src.services.constants as service_constants
import src.services.dto.auth_dto as auth_dto
import src.services.dto.patient_dto as patient_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service

logger = app_logs.get_logger(__name__)


class PatientQueryService:
    def __init__(
        self,
        patient_repository: patient_repository_port.PatientRepositoryPort,
        scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
        google_calendar_onboarding_service: (
            google_calendar_onboarding_service.GoogleCalendarOnboardingService
        ),
        clock: clock_port.ClockPort,
    ) -> None:
        self._patient_repository = patient_repository
        self._scheduling_repository = scheduling_repository
        self._google_calendar_onboarding_service = google_calendar_onboarding_service
        self._clock = clock

    def list_patients(self, claims: auth_dto.TokenClaimsDTO) -> patient_dto.PatientListResponseDTO:
        self._ensure_owner(claims)
        patients = self._patient_repository.list_by_tenant(claims.tenant_id)
        sorted_patients = sorted(patients, key=lambda item: item.created_at, reverse=True)
        return patient_dto.PatientListResponseDTO(
            items=[self._to_patient_dto(item) for item in sorted_patients]
        )

    def get_patient(
        self,
        claims: auth_dto.TokenClaimsDTO,
        whatsapp_user_id: str,
    ) -> patient_dto.PatientDTO:
        self._ensure_owner(claims)
        patient = self._patient_repository.get_by_whatsapp_user(claims.tenant_id, whatsapp_user_id)
        if patient is None:
            raise service_exceptions.EntityNotFoundError("patient not found")
        return self._to_patient_dto(patient)

    def delete_patient(
        self,
        claims: auth_dto.TokenClaimsDTO,
        whatsapp_user_id: str,
    ) -> None:
        self._ensure_owner(claims)
        requests = self._scheduling_repository.list_requests_by_tenant(claims.tenant_id)
        deleted_event_ids: set[str] = set()
        deleted_scheduling_requests_count = 0
        for request in requests:
            if request.whatsapp_user_id != whatsapp_user_id:
                continue
            calendar_event_id = request.calendar_event_id
            if calendar_event_id is not None and calendar_event_id not in deleted_event_ids:
                self._google_calendar_onboarding_service.delete_event(
                    tenant_id=claims.tenant_id,
                    event_id=calendar_event_id,
                )
                deleted_event_ids.add(calendar_event_id)
            self._scheduling_repository.delete_request(claims.tenant_id, request.id)
            deleted_scheduling_requests_count += 1

        self._patient_repository.delete(claims.tenant_id, whatsapp_user_id)
        logger.info(
            "patient.deleted",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="patient.deleted",
                    message="patient record deleted by owner",
                    data={
                        "tenant_id": claims.tenant_id,
                        "whatsapp_user_id": whatsapp_user_id,
                        "deleted_calendar_events_count": len(deleted_event_ids),
                        "deleted_scheduling_requests_count": deleted_scheduling_requests_count,
                    },
                )
            },
        )

    def _ensure_owner(self, claims: auth_dto.TokenClaimsDTO) -> None:
        if claims.role != service_constants.DEFAULT_OWNER_ROLE:
            raise service_exceptions.AuthorizationError("owner role required")

    def _to_patient_dto(
        self,
        patient: patient_entity.Patient,
    ) -> patient_dto.PatientDTO:
        return patient_dto.PatientDTO(
            tenant_id=patient.tenant_id,
            whatsapp_user_id=patient.whatsapp_user_id,
            first_name=patient.first_name,
            last_name=patient.last_name,
            email=patient.email,
            age=patient.age,
            consultation_reason=patient.consultation_reason,
            location=patient.location,
            phone=patient.phone,
            created_at=patient.created_at,
        )
