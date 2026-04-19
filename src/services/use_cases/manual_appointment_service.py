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
import src.services.use_cases.reminder_service as reminder_service_module

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
        reminder_service: reminder_service_module.ReminderService | None = None,
    ) -> None:
        self._manual_appointment_repository = manual_appointment_repository
        self._patient_repository = patient_repository
        self._google_calendar_onboarding_service = google_calendar_onboarding_service
        self._id_generator = id_generator
        self._clock = clock
        self._reminder_service = reminder_service

    def list_appointments(
        self,
        claims: auth_dto.TokenClaimsDTO,
        status: str | None = None,
    ) -> manual_appointment_dto.ManualAppointmentListResponseDTO:
        self._ensure_professional(claims)
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
        self._ensure_professional(claims)

        patient = self._patient_repository.get_by_whatsapp_user(
            claims.tenant_id,
            create_dto.patient_whatsapp_user_id,
        )
        if patient is None:
            raise service_exceptions.EntityNotFoundError("patient not found")

        motivo = self._normalize_text(create_dto.summary)
        summary = self._resolve_summary(create_dto.summary, patient)
        event_title = self._build_event_title(
            tenant_id=claims.tenant_id,
            patient=patient,
        )
        event = self._google_calendar_onboarding_service.create_event(
            tenant_id=claims.tenant_id,
            start_at=create_dto.start_at,
            end_at=create_dto.end_at,
            summary=event_title,
            attendee_emails=[patient.email],
            with_meet=create_dto.is_virtual,
            description=motivo,
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
            is_virtual=create_dto.is_virtual,
            meet_url=event.meet_url,
            created_at=now_value,
            updated_at=now_value,
            cancelled_at=None,
        )
        self._manual_appointment_repository.save(appointment)
        if self._reminder_service is not None:
            self._reminder_service.maybe_schedule_reminder(
                tenant_id=claims.tenant_id,
                source_type="MANUAL_APPOINTMENT",
                source_id=appointment.id,
                patient_whatsapp_user_id=appointment.patient_whatsapp_user_id,
                patient_name=patient.first_name,
                appointment_start_at=appointment.start_at,
            )
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
        self._ensure_professional(claims)
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
        reschedule_patient = self._patient_repository.get_by_whatsapp_user(
            claims.tenant_id, appointment.patient_whatsapp_user_id
        )
        reschedule_attendee_emails = (
            [reschedule_patient.email] if reschedule_patient is not None else []
        )
        reschedule_event_title = self._build_event_title(
            tenant_id=claims.tenant_id,
            patient=reschedule_patient,
        )
        updated_event = self._google_calendar_onboarding_service.update_event(
            tenant_id=claims.tenant_id,
            event_id=appointment.calendar_event_id,
            start_at=input_dto.start_at,
            end_at=input_dto.end_at,
            timezone=input_dto.timezone,
            summary=reschedule_event_title,
            attendee_emails=reschedule_attendee_emails,
            description=resolved_summary,
        )
        if self._reminder_service is not None:
            self._reminder_service.cancel_reminders_for_source(
                tenant_id=claims.tenant_id,
                source_type="MANUAL_APPOINTMENT",
                source_id=appointment.id,
            )
        now_value = self._clock.now()
        appointment.start_at = input_dto.start_at
        appointment.end_at = input_dto.end_at
        appointment.timezone = input_dto.timezone
        appointment.summary = resolved_summary
        appointment.calendar_event_id = updated_event.event_id
        appointment.updated_at = now_value
        self._manual_appointment_repository.save(appointment)
        if self._reminder_service is not None:
            patient = self._patient_repository.get_by_whatsapp_user(
                claims.tenant_id, appointment.patient_whatsapp_user_id
            )
            patient_name = patient.first_name if patient is not None else "Paciente"
            self._reminder_service.maybe_schedule_reminder(
                tenant_id=claims.tenant_id,
                source_type="MANUAL_APPOINTMENT",
                source_id=appointment.id,
                patient_whatsapp_user_id=appointment.patient_whatsapp_user_id,
                patient_name=patient_name,
                appointment_start_at=appointment.start_at,
            )
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
        self._ensure_professional(claims)
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

        if self._reminder_service is not None:
            self._reminder_service.cancel_reminders_for_source(
                tenant_id=claims.tenant_id,
                source_type="MANUAL_APPOINTMENT",
                source_id=appointment.id,
            )
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

    def update_payment(
        self,
        claims: auth_dto.TokenClaimsDTO,
        appointment_id: str,
        input_dto: manual_appointment_dto.UpdateManualAppointmentPaymentDTO,
    ) -> manual_appointment_dto.ManualAppointmentDTO:
        self._ensure_professional(claims)
        appointment = self._manual_appointment_repository.get_by_id(
            claims.tenant_id, appointment_id
        )
        if appointment is None:
            raise service_exceptions.EntityNotFoundError("manual appointment not found")
        if appointment.status != "SCHEDULED":
            raise service_exceptions.InvalidStateError("manual appointment is not scheduled")

        now_value = self._clock.now()
        appointment.payment_amount_cop = input_dto.payment_amount_cop
        appointment.payment_method = input_dto.payment_method
        appointment.payment_status = input_dto.payment_status
        appointment.payment_updated_at = now_value
        appointment.updated_at = now_value
        self._manual_appointment_repository.save(appointment)
        logger.info(
            "manual_appointment.payment_updated",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="manual_appointment.payment_updated",
                    message="manual appointment payment updated",
                    data={
                        "tenant_id": claims.tenant_id,
                        "appointment_id": appointment.id,
                        "payment_status": appointment.payment_status,
                        "payment_method": appointment.payment_method,
                        "payment_amount_cop": appointment.payment_amount_cop,
                    },
                )
            },
        )
        return self._to_dto(appointment)

    def _build_event_title(
        self,
        tenant_id: str,
        patient: patient_entity.Patient | None,
    ) -> str:
        professional_name = self._google_calendar_onboarding_service.get_professional_name(
            tenant_id
        )
        if not professional_name:
            professional_name = "Profesional"
        if patient is not None:
            patient_full_name = f"{patient.first_name} {patient.last_name}"
        else:
            patient_full_name = "Paciente"
        return f"{professional_name}/{patient_full_name}"

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

    def _ensure_professional(self, claims: auth_dto.TokenClaimsDTO) -> None:
        if claims.role != service_constants.DEFAULT_PROFESSIONAL_ROLE:
            raise service_exceptions.AuthorizationError("professional role required")

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
            is_virtual=appointment.is_virtual,
            meet_url=appointment.meet_url,
            payment_amount_cop=appointment.payment_amount_cop,
            payment_method=appointment.payment_method,
            payment_status=appointment.payment_status,
            payment_updated_at=appointment.payment_updated_at,
            created_at=appointment.created_at,
            updated_at=appointment.updated_at,
            cancelled_at=appointment.cancelled_at,
        )
