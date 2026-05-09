import src.domain.entities.patient as patient_entity
import src.infra.logs as app_logs
import src.ports.clock_port as clock_port
import src.ports.manual_appointment_repository_port as manual_appointment_repository_port
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
        manual_appointment_repository: (
            manual_appointment_repository_port.ManualAppointmentRepositoryPort
        ),
        google_calendar_onboarding_service: (
            google_calendar_onboarding_service.GoogleCalendarOnboardingService
        ),
        clock: clock_port.ClockPort,
    ) -> None:
        self._patient_repository = patient_repository
        self._scheduling_repository = scheduling_repository
        self._manual_appointment_repository = manual_appointment_repository
        self._google_calendar_onboarding_service = google_calendar_onboarding_service
        self._clock = clock

    def list_patients(
        self,
        claims: auth_dto.TokenClaimsDTO,
        search: str | None = None,
    ) -> patient_dto.PatientListResponseDTO:
        self._ensure_professional(claims)
        return self._list_patients_by_tenant(claims.tenant_id, search=search)

    def list_patients_for_tenant(
        self,
        tenant_id: str,
        search: str | None = None,
    ) -> patient_dto.PatientListResponseDTO:
        return self._list_patients_by_tenant(tenant_id, search=search)

    def _list_patients_by_tenant(
        self,
        tenant_id: str,
        search: str | None = None,
    ) -> patient_dto.PatientListResponseDTO:
        patients = self._patient_repository.list_by_tenant(tenant_id)
        if search is not None:
            needle = search.casefold()
            patients = [
                p
                for p in patients
                if needle in (p.first_name or "").casefold()
                or needle in (p.last_name or "").casefold()
                or needle in (p.phone or "").casefold()
                or needle in (p.whatsapp_user_id or "").casefold()
            ]
        sorted_patients = sorted(patients, key=lambda item: item.created_at, reverse=True)
        return patient_dto.PatientListResponseDTO(
            items=[self._to_patient_dto(item) for item in sorted_patients]
        )

    def get_patient(
        self,
        claims: auth_dto.TokenClaimsDTO,
        whatsapp_user_id: str,
    ) -> patient_dto.PatientDTO:
        self._ensure_professional(claims)
        return self._get_patient_by_tenant(claims.tenant_id, whatsapp_user_id)

    def get_patient_for_tenant(
        self,
        tenant_id: str,
        whatsapp_user_id: str,
    ) -> patient_dto.PatientDTO:
        return self._get_patient_by_tenant(tenant_id, whatsapp_user_id)

    def _get_patient_by_tenant(
        self,
        tenant_id: str,
        whatsapp_user_id: str,
    ) -> patient_dto.PatientDTO:
        patient = self._patient_repository.get_by_whatsapp_user(tenant_id, whatsapp_user_id)
        if patient is None:
            raise service_exceptions.EntityNotFoundError("patient not found")
        return self._to_patient_dto(patient)

    def create_patient(
        self,
        claims: auth_dto.TokenClaimsDTO,
        create_dto: patient_dto.CreatePatientDTO,
    ) -> patient_dto.PatientDTO:
        self._ensure_professional(claims)
        return self._create_patient_for_tenant(claims.tenant_id, create_dto)

    def create_patient_for_tenant(
        self,
        tenant_id: str,
        create_dto: patient_dto.CreatePatientDTO,
    ) -> patient_dto.PatientDTO:
        return self._create_patient_for_tenant(tenant_id, create_dto)

    def _create_patient_for_tenant(
        self,
        tenant_id: str,
        create_dto: patient_dto.CreatePatientDTO,
    ) -> patient_dto.PatientDTO:
        existing_patient = self._patient_repository.get_by_whatsapp_user(
            tenant_id,
            create_dto.whatsapp_user_id,
        )
        if existing_patient is not None:
            raise service_exceptions.InvalidStateError("patient already exists")

        patient = patient_entity.Patient(
            tenant_id=tenant_id,
            whatsapp_user_id=create_dto.whatsapp_user_id,
            first_name=create_dto.first_name,
            last_name=create_dto.last_name,
            email=create_dto.email,
            age=create_dto.age,
            location=create_dto.location,
            phone_prefix=create_dto.phone_prefix,
            phone=create_dto.phone,
            created_at=self._clock.now(),
        )
        self._patient_repository.save(patient)
        logger.info(
            "patient.created",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="patient.created",
                    message="patient record created",
                    data={
                        "tenant_id": tenant_id,
                        "whatsapp_user_id": patient.whatsapp_user_id,
                    },
                )
            },
        )
        return self._to_patient_dto(patient)

    def update_patient(
        self,
        claims: auth_dto.TokenClaimsDTO,
        whatsapp_user_id: str,
        update_dto: patient_dto.UpdatePatientDTO,
    ) -> patient_dto.PatientDTO:
        self._ensure_professional(claims)
        return self._update_patient_for_tenant(claims.tenant_id, whatsapp_user_id, update_dto)

    def update_patient_for_tenant(
        self,
        tenant_id: str,
        whatsapp_user_id: str,
        update_dto: patient_dto.UpdatePatientDTO,
    ) -> patient_dto.PatientDTO:
        return self._update_patient_for_tenant(tenant_id, whatsapp_user_id, update_dto)

    def _update_patient_for_tenant(
        self,
        tenant_id: str,
        whatsapp_user_id: str,
        update_dto: patient_dto.UpdatePatientDTO,
    ) -> patient_dto.PatientDTO:
        existing_patient = self._patient_repository.get_by_whatsapp_user(
            tenant_id, whatsapp_user_id
        )
        if existing_patient is None:
            raise service_exceptions.EntityNotFoundError("patient not found")

        updated_patient = patient_entity.Patient(
            tenant_id=existing_patient.tenant_id,
            whatsapp_user_id=existing_patient.whatsapp_user_id,
            first_name=update_dto.first_name,
            last_name=update_dto.last_name,
            email=update_dto.email,
            age=update_dto.age,
            location=update_dto.location,
            phone_prefix=update_dto.phone_prefix,
            phone=update_dto.phone,
            created_at=existing_patient.created_at,
        )
        self._patient_repository.save(updated_patient)
        logger.info(
            "patient.updated",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="patient.updated",
                    message="patient record updated",
                    data={
                        "tenant_id": tenant_id,
                        "whatsapp_user_id": updated_patient.whatsapp_user_id,
                    },
                )
            },
        )
        return self._to_patient_dto(updated_patient)

    def delete_patient(
        self,
        claims: auth_dto.TokenClaimsDTO,
        whatsapp_user_id: str,
    ) -> None:
        self._ensure_professional(claims)
        self._delete_patient_for_tenant(claims.tenant_id, whatsapp_user_id)

    def delete_patient_for_tenant(
        self,
        tenant_id: str,
        whatsapp_user_id: str,
    ) -> None:
        self._delete_patient_for_tenant(tenant_id, whatsapp_user_id)

    def _delete_patient_for_tenant(
        self,
        tenant_id: str,
        whatsapp_user_id: str,
    ) -> None:
        requests = self._scheduling_repository.list_requests_by_tenant(tenant_id)
        deleted_event_ids: set[str] = set()
        deleted_scheduling_requests_count = 0
        for request in requests:
            if request.whatsapp_user_id != whatsapp_user_id:
                continue
            calendar_event_id = request.calendar_event_id
            if calendar_event_id is not None and calendar_event_id not in deleted_event_ids:
                self._google_calendar_onboarding_service.delete_event(
                    tenant_id=tenant_id,
                    event_id=calendar_event_id,
                )
                deleted_event_ids.add(calendar_event_id)
            self._scheduling_repository.delete_request(tenant_id, request.id)
            deleted_scheduling_requests_count += 1

        manual_appointments = self._manual_appointment_repository.list_by_patient(
            tenant_id=tenant_id,
            patient_whatsapp_user_id=whatsapp_user_id,
            status="SCHEDULED",
        )
        cancelled_manual_appointments_count = 0
        now_value = self._clock.now()
        for manual_appointment in manual_appointments:
            calendar_event_id = manual_appointment.calendar_event_id
            if calendar_event_id is not None and calendar_event_id not in deleted_event_ids:
                self._google_calendar_onboarding_service.delete_event(
                    tenant_id=tenant_id,
                    event_id=calendar_event_id,
                )
                deleted_event_ids.add(calendar_event_id)
            manual_appointment.status = "CANCELLED"
            manual_appointment.calendar_event_id = None
            manual_appointment.cancelled_at = now_value
            manual_appointment.updated_at = now_value
            self._manual_appointment_repository.save(manual_appointment)
            cancelled_manual_appointments_count += 1

        self._patient_repository.delete(tenant_id, whatsapp_user_id)
        logger.info(
            "patient.deleted",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="patient.deleted",
                    message="patient record deleted",
                    data={
                        "tenant_id": tenant_id,
                        "whatsapp_user_id": whatsapp_user_id,
                        "deleted_calendar_events_count": len(deleted_event_ids),
                        "deleted_scheduling_requests_count": deleted_scheduling_requests_count,
                        "cancelled_manual_appointments_count": cancelled_manual_appointments_count,
                    },
                )
            },
        )

    def _ensure_professional(self, claims: auth_dto.TokenClaimsDTO) -> None:
        if claims.role != service_constants.DEFAULT_PROFESSIONAL_ROLE:
            raise service_exceptions.AuthorizationError("professional role required")

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
            location=patient.location,
            phone_prefix=patient.phone_prefix,
            phone=patient.phone,
            created_at=patient.created_at,
        )
