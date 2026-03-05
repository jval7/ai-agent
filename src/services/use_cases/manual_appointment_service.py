import src.domain.entities.manual_appointment as manual_appointment_entity
import src.domain.entities.patient as patient_entity
import src.infra.logs as app_logs
import src.ports.clock_port as clock_port
import src.ports.id_generator_port as id_generator_port
import src.ports.manual_appointment_repository_port as manual_appointment_repository_port
import src.ports.patient_repository_port as patient_repository_port
import src.services.constants as service_constants
import src.services.dto.auth_dto as auth_dto
import src.services.dto.manual_appointment_dto as manual_appointment_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service

logger = app_logs.get_logger(__name__)


class ManualAppointmentService:
    def __init__(
        self,
        manual_appointment_repository: (
            manual_appointment_repository_port.ManualAppointmentRepositoryPort
        ),
        patient_repository: patient_repository_port.PatientRepositoryPort,
        google_calendar_onboarding_service: (
            google_calendar_onboarding_service.GoogleCalendarOnboardingService
        ),
        id_generator: id_generator_port.IdGeneratorPort,
        clock: clock_port.ClockPort,
    ) -> None:
        self._manual_appointment_repository = manual_appointment_repository
        self._patient_repository = patient_repository
        self._google_calendar_onboarding_service = google_calendar_onboarding_service
        self._id_generator = id_generator
        self._clock = clock

    def list_appointments(
        self,
        claims: auth_dto.TokenClaimsDTO,
        status: str | None = None,
    ) -> manual_appointment_dto.ManualAppointmentListResponseDTO:
        self._ensure_owner(claims)
        appointments = self._manual_appointment_repository.list_by_tenant(claims.tenant_id, status)
        sorted_appointments = sorted(appointments, key=lambda item: item.start_at)
        return manual_appointment_dto.ManualAppointmentListResponseDTO(
            items=[self._to_dto(item) for item in sorted_appointments]
        )

    def create_appointment(
        self,
        claims: auth_dto.TokenClaimsDTO,
        create_dto: manual_appointment_dto.CreateManualAppointmentDTO,
    ) -> manual_appointment_dto.ManualAppointmentDTO:
        self._ensure_owner(claims)

        patient = self._patient_repository.get_by_whatsapp_user(
            claims.tenant_id,
            create_dto.patient_whatsapp_user_id,
        )
        if patient is None:
            raise service_exceptions.EntityNotFoundError("patient not found")

        summary = self._resolve_summary(create_dto.summary, patient)
        event = self._google_calendar_onboarding_service.create_event(
            tenant_id=claims.tenant_id,
            start_at=create_dto.start_at,
            end_at=create_dto.end_at,
            summary=summary,
        )
        now_value = self._clock.now()
        appointment = manual_appointment_entity.ManualAppointment(
            id=self._id_generator.new_id(),
            tenant_id=claims.tenant_id,
            patient_whatsapp_user_id=patient.whatsapp_user_id,
            status="SCHEDULED",
            calendar_event_id=event.event_id,
            start_at=create_dto.start_at,
            end_at=create_dto.end_at,
            timezone=create_dto.timezone,
            summary=summary,
            created_at=now_value,
            updated_at=now_value,
            cancelled_at=None,
        )
        self._manual_appointment_repository.save(appointment)
        logger.info(
            "manual_appointment.created",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="manual_appointment.created",
                    message="manual appointment created",
                    data={
                        "tenant_id": claims.tenant_id,
                        "appointment_id": appointment.id,
                        "patient_whatsapp_user_id": appointment.patient_whatsapp_user_id,
                        "calendar_event_id": appointment.calendar_event_id,
                    },
                )
            },
        )
        return self._to_dto(appointment)

    def reschedule_appointment(
        self,
        claims: auth_dto.TokenClaimsDTO,
        appointment_id: str,
        input_dto: manual_appointment_dto.RescheduleManualAppointmentDTO,
    ) -> manual_appointment_dto.ManualAppointmentDTO:
        self._ensure_owner(claims)
        appointment = self._manual_appointment_repository.get_by_id(
            claims.tenant_id, appointment_id
        )
        if appointment is None:
            raise service_exceptions.EntityNotFoundError("manual appointment not found")
        if appointment.status != "SCHEDULED":
            raise service_exceptions.InvalidStateError("manual appointment is not scheduled")
        if appointment.calendar_event_id is None:
            raise service_exceptions.InvalidStateError("manual appointment has no calendar event")

        summary = self._normalize_text(input_dto.summary)
        resolved_summary = summary if summary is not None else appointment.summary
        updated_event = self._google_calendar_onboarding_service.update_event(
            tenant_id=claims.tenant_id,
            event_id=appointment.calendar_event_id,
            start_at=input_dto.start_at,
            end_at=input_dto.end_at,
            timezone=input_dto.timezone,
            summary=resolved_summary,
        )
        now_value = self._clock.now()
        appointment.start_at = input_dto.start_at
        appointment.end_at = input_dto.end_at
        appointment.timezone = input_dto.timezone
        appointment.summary = resolved_summary
        appointment.calendar_event_id = updated_event.event_id
        appointment.updated_at = now_value
        self._manual_appointment_repository.save(appointment)
        logger.info(
            "manual_appointment.rescheduled",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="manual_appointment.rescheduled",
                    message="manual appointment rescheduled",
                    data={
                        "tenant_id": claims.tenant_id,
                        "appointment_id": appointment.id,
                        "calendar_event_id": appointment.calendar_event_id,
                    },
                )
            },
        )
        return self._to_dto(appointment)

    def cancel_appointment(
        self,
        claims: auth_dto.TokenClaimsDTO,
        appointment_id: str,
        input_dto: manual_appointment_dto.CancelManualAppointmentDTO,
    ) -> manual_appointment_dto.ManualAppointmentDTO:
        del input_dto
        self._ensure_owner(claims)
        appointment = self._manual_appointment_repository.get_by_id(
            claims.tenant_id, appointment_id
        )
        if appointment is None:
            raise service_exceptions.EntityNotFoundError("manual appointment not found")
        if appointment.status == "CANCELLED":
            return self._to_dto(appointment)

        calendar_event_id = appointment.calendar_event_id
        if calendar_event_id is not None:
            try:
                self._google_calendar_onboarding_service.delete_event(
                    tenant_id=claims.tenant_id,
                    event_id=calendar_event_id,
                )
            except service_exceptions.ExternalProviderError as error:
                if not self._is_google_not_found_error(str(error)):
                    raise

        now_value = self._clock.now()
        appointment.status = "CANCELLED"
        appointment.calendar_event_id = None
        appointment.cancelled_at = now_value
        appointment.updated_at = now_value
        self._manual_appointment_repository.save(appointment)
        logger.info(
            "manual_appointment.cancelled",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="manual_appointment.cancelled",
                    message="manual appointment cancelled",
                    data={
                        "tenant_id": claims.tenant_id,
                        "appointment_id": appointment.id,
                    },
                )
            },
        )
        return self._to_dto(appointment)

    def _resolve_summary(
        self,
        requested_summary: str | None,
        patient: patient_entity.Patient,
    ) -> str:
        normalized_summary = self._normalize_text(requested_summary)
        if normalized_summary is not None:
            return normalized_summary
        return f"Cita - {patient.first_name} {patient.last_name}"

    def _normalize_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        if normalized_value == "":
            return None
        return normalized_value

    def _is_google_not_found_error(self, error_message: str) -> bool:
        normalized_message = error_message.lower()
        return "status=404" in normalized_message or "not found" in normalized_message

    def _ensure_owner(self, claims: auth_dto.TokenClaimsDTO) -> None:
        if claims.role != service_constants.DEFAULT_OWNER_ROLE:
            raise service_exceptions.AuthorizationError("owner role required")

    def _to_dto(
        self,
        appointment: manual_appointment_entity.ManualAppointment,
    ) -> manual_appointment_dto.ManualAppointmentDTO:
        return manual_appointment_dto.ManualAppointmentDTO(
            appointment_id=appointment.id,
            tenant_id=appointment.tenant_id,
            patient_whatsapp_user_id=appointment.patient_whatsapp_user_id,
            status=appointment.status,
            calendar_event_id=appointment.calendar_event_id,
            start_at=appointment.start_at,
            end_at=appointment.end_at,
            timezone=appointment.timezone,
            summary=appointment.summary,
            created_at=appointment.created_at,
            updated_at=appointment.updated_at,
            cancelled_at=appointment.cancelled_at,
        )
