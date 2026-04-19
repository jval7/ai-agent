import re
import typing

import pydantic

import src.domain.entities.patient as patient_entity
import src.infra.logs as app_logs
import src.ports.clock_port as clock_port
import src.ports.patient_repository_port as patient_repository_port
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.scheduling_service as scheduling_service

logger = app_logs.get_logger(__name__)


class ResolvedPatientProfile(pydantic.BaseModel):
    full_name: str
    email: str
    age: int
    location: str
    phone_prefix: str | None
    phone: str


class ResolvedConfirmSelection(pydantic.BaseModel):
    confirm_input_dto: scheduling_dto.ConfirmSelectedSlotInputDTO
    patient_profile: ResolvedPatientProfile
    patient_exists: bool
    whatsapp_user_id: str


class PatientProfileResolver:
    def __init__(
        self,
        scheduling_svc: scheduling_service.SchedulingService,
        patient_repository: patient_repository_port.PatientRepositoryPort,
        clock: clock_port.ClockPort,
        professional_signature: str,
        sleep_seconds: typing.Callable[[float], None],
        google_network_retry_backoff_seconds: list[float] | None = None,
    ) -> None:
        self._scheduling_service = scheduling_svc
        self._patient_repository = patient_repository
        self._clock = clock
        self._professional_signature = professional_signature
        self._sleep_seconds = sleep_seconds
        self._google_network_retry_backoff_seconds = (
            google_network_retry_backoff_seconds
            if google_network_retry_backoff_seconds is not None
            else [1.0, 2.0, 4.0]
        )
        self._email_pattern = re.compile(
            r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
        )

    def resolve_confirm_selected_slot_input(
        self,
        tenant_id: str,
        conversation_id: str,
        tool_input_dto: scheduling_dto.ConfirmSelectedSlotToolInputDTO,
    ) -> ResolvedConfirmSelection:
        request_list = self._scheduling_service.list_requests_by_conversation(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
        )
        active_requests: list[scheduling_dto.SchedulingRequestSummaryDTO] = []
        for request in request_list.items:
            if request.status == "AWAITING_PATIENT_CHOICE":
                active_requests.append(request)

        if not active_requests:
            raise service_exceptions.InvalidStateError(
                "no scheduling request awaiting patient choice"
            )

        candidate_requests = active_requests
        if tool_input_dto.request_id is not None:
            candidate_requests = []
            for request in active_requests:
                if request.request_id == tool_input_dto.request_id:
                    candidate_requests.append(request)
            if not candidate_requests:
                raise service_exceptions.InvalidStateError(
                    "provided request_id is not awaiting patient choice"
                )

        target_request = self._select_target_request_for_confirmation(
            candidate_requests=candidate_requests,
            requested_slot_id=tool_input_dto.slot_id,
        )
        resolved_slot_id = tool_input_dto.slot_id
        if resolved_slot_id is None:
            resolved_slot_id = self._resolve_slot_id_for_confirmation(target_request)
        resolved_patient_profile, patient_exists = self._resolve_patient_profile_for_confirmation(
            tenant_id=tenant_id,
            whatsapp_user_id=target_request.whatsapp_user_id,
            request=target_request,
            tool_input_dto=tool_input_dto,
            default_patient_phone=target_request.whatsapp_user_id,
        )
        event_summary = self._build_event_summary_for_confirmation(
            resolved_patient_profile=resolved_patient_profile
        )

        return ResolvedConfirmSelection(
            confirm_input_dto=scheduling_dto.ConfirmSelectedSlotInputDTO(
                request_id=target_request.request_id,
                slot_id=resolved_slot_id,
                event_summary=event_summary,
                attendee_emails=[resolved_patient_profile.email],
            ),
            patient_profile=resolved_patient_profile,
            patient_exists=patient_exists,
            whatsapp_user_id=target_request.whatsapp_user_id,
        )

    def confirm_selected_slot_with_retry(
        self,
        tenant_id: str,
        conversation_id: str,
        confirm_input_dto: scheduling_dto.ConfirmSelectedSlotInputDTO,
    ) -> dict[str, object]:
        max_attempts = len(self._google_network_retry_backoff_seconds) + 1
        for attempt in range(max_attempts):
            try:
                result = self._scheduling_service.confirm_selected_slot_and_create_event(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    input_dto=confirm_input_dto,
                )
                return result.model_dump(mode="json")
            except service_exceptions.ExternalProviderError as error:
                error_message = str(error)
                if self._is_google_network_error(error_message):
                    if attempt < len(self._google_network_retry_backoff_seconds):
                        delay_seconds = self._google_network_retry_backoff_seconds[attempt]
                        logger.warning(
                            "webhook.scheduling.retry_google_network_error",
                            extra={
                                "event_data": app_logs.build_log_event(
                                    event_name="webhook.scheduling.retry_google_network_error",
                                    message="retrying google calendar error while confirming slot",
                                    data={
                                        "tenant_id": tenant_id,
                                        "conversation_id": conversation_id,
                                        "request_id": confirm_input_dto.request_id,
                                        "slot_id": confirm_input_dto.slot_id,
                                        "attempt": attempt + 1,
                                        "delay_seconds": delay_seconds,
                                    },
                                )
                            },
                        )
                        self._sleep_seconds(delay_seconds)
                        continue
                    return self._handoff_due_to_google_error(
                        tenant_id=tenant_id,
                        conversation_id=conversation_id,
                        request_id=confirm_input_dto.request_id,
                        slot_id=confirm_input_dto.slot_id,
                        reason="google_network_error",
                        error_message=error_message,
                    )

                return self._handoff_due_to_google_error(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    request_id=confirm_input_dto.request_id,
                    slot_id=confirm_input_dto.slot_id,
                    reason="google_unknown_error",
                    error_message=error_message,
                )

        return self._handoff_due_to_google_error(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            request_id=confirm_input_dto.request_id,
            slot_id=confirm_input_dto.slot_id,
            reason="google_network_error",
            error_message="retry loop exhausted",
        )

    def create_patient_after_successful_booking(
        self,
        tenant_id: str,
        whatsapp_user_id: str,
        patient_profile: ResolvedPatientProfile,
        patient_exists: bool,
    ) -> None:
        if patient_exists:
            return

        existing_patient = self._patient_repository.get_by_whatsapp_user(
            tenant_id=tenant_id,
            whatsapp_user_id=whatsapp_user_id,
        )
        if existing_patient is not None:
            return

        patient = patient_entity.Patient(
            tenant_id=tenant_id,
            whatsapp_user_id=whatsapp_user_id,
            first_name=self._extract_first_name(patient_profile.full_name),
            last_name=self._extract_last_name(patient_profile.full_name),
            email=patient_profile.email,
            age=patient_profile.age,
            location=patient_profile.location,
            phone_prefix=patient_profile.phone_prefix,
            phone=patient_profile.phone,
            created_at=self._clock.now(),
        )
        self._patient_repository.save(patient)
        logger.info(
            "webhook.patient.created",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="webhook.patient.created",
                    message="patient record created after booking confirmation",
                    data={
                        "tenant_id": tenant_id,
                        "whatsapp_user_id": whatsapp_user_id,
                    },
                )
            },
        )

    def _select_target_request_for_confirmation(
        self,
        candidate_requests: list[scheduling_dto.SchedulingRequestSummaryDTO],
        requested_slot_id: str | None,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        if requested_slot_id is None:
            if len(candidate_requests) == 1:
                return candidate_requests[0]
            raise service_exceptions.InvalidStateError(
                "multiple scheduling requests are waiting for confirmation"
            )

        matching_requests: list[scheduling_dto.SchedulingRequestSummaryDTO] = []
        for request in candidate_requests:
            if self._request_contains_proposed_slot(request, requested_slot_id):
                matching_requests.append(request)

        if len(matching_requests) == 1:
            return matching_requests[0]
        if len(matching_requests) > 1:
            raise service_exceptions.InvalidStateError(
                "slot_id matches multiple scheduling requests"
            )
        if len(candidate_requests) == 1:
            return candidate_requests[0]

        raise service_exceptions.InvalidStateError(
            "provided slot_id does not match active scheduling requests"
        )

    def _resolve_slot_id_for_confirmation(
        self,
        request: scheduling_dto.SchedulingRequestSummaryDTO,
    ) -> str:
        if request.selected_slot_id is not None and self._request_contains_proposed_slot(
            request=request,
            slot_id=request.selected_slot_id,
        ):
            return request.selected_slot_id

        raise service_exceptions.InvalidStateError(
            "slot selection is required; ask patient to choose a slot option number"
        )

    def _resolve_patient_profile_for_confirmation(
        self,
        tenant_id: str,
        whatsapp_user_id: str,
        request: scheduling_dto.SchedulingRequestSummaryDTO,
        tool_input_dto: scheduling_dto.ConfirmSelectedSlotToolInputDTO,
        default_patient_phone: str | None,
    ) -> tuple[ResolvedPatientProfile, bool]:
        existing_patient = self._patient_repository.get_by_whatsapp_user(
            tenant_id=tenant_id,
            whatsapp_user_id=whatsapp_user_id,
        )
        if existing_patient is not None:
            self._log_existing_patient_mismatch(
                tenant_id=tenant_id,
                whatsapp_user_id=whatsapp_user_id,
                existing_patient=existing_patient,
                tool_input_dto=tool_input_dto,
            )
            return (
                ResolvedPatientProfile(
                    full_name=self._build_patient_full_name(
                        first_name=existing_patient.first_name,
                        last_name=existing_patient.last_name,
                    )
                    or existing_patient.first_name,
                    email=existing_patient.email,
                    age=existing_patient.age,
                    location=existing_patient.location,
                    phone_prefix=existing_patient.phone_prefix,
                    phone=existing_patient.phone,
                ),
                True,
            )

        patient_full_name = self._coalesce_patient_text(
            primary=tool_input_dto.patient_full_name,
            fallback=self._build_patient_full_name(
                first_name=self._coalesce_patient_text(
                    primary=request.patient_first_name,
                    fallback=tool_input_dto.patient_first_name,
                ),
                last_name=self._coalesce_patient_text(
                    primary=request.patient_last_name,
                    fallback=tool_input_dto.patient_last_name,
                ),
            ),
        )
        if patient_full_name is None:
            raise service_exceptions.InvalidStateError(
                "missing required patient data: patient_full_name; ask only for the patient's full name now"
            )

        patient_email = self._normalize_patient_text(tool_input_dto.patient_email)
        if patient_email is None:
            raise service_exceptions.InvalidStateError(
                "missing required patient data: patient_email; ask only for the patient's email now"
            )
        if not self._email_pattern.fullmatch(patient_email):
            raise service_exceptions.InvalidStateError(
                "patient_email is invalid; ask only for a valid email now"
            )

        patient_phone = self._resolve_patient_phone(
            provided_patient_phone=tool_input_dto.patient_phone,
            fallback_patient_phone=default_patient_phone,
        )
        if patient_phone is None:
            raise service_exceptions.InvalidStateError(
                "missing required patient data: patient_phone; ask only for the patient's phone number now"
            )

        patient_age = self._coalesce_patient_age(
            primary=request.patient_age,
            fallback=tool_input_dto.patient_age,
        )
        if patient_age is None:
            raise service_exceptions.InvalidStateError(
                "missing required patient data: patient_age; ask only for the patient's age now"
            )
        if patient_age < 1 or patient_age > 120:
            raise service_exceptions.InvalidStateError(
                "patient_age is invalid; ask only for age as a whole number between 1 and 120"
            )

        patient_location = self._coalesce_patient_text(
            primary=request.patient_location,
            fallback=tool_input_dto.patient_location,
        )
        if patient_location is None:
            raise service_exceptions.InvalidStateError(
                "missing required patient data: patient_location; ask only for the patient's location now"
            )

        return (
            ResolvedPatientProfile(
                full_name=patient_full_name,
                email=patient_email,
                age=patient_age,
                location=patient_location,
                phone_prefix=None,
                phone=patient_phone,
            ),
            False,
        )

    def _build_event_summary_for_confirmation(
        self,
        resolved_patient_profile: ResolvedPatientProfile,
    ) -> str:
        return f"{resolved_patient_profile.full_name}/ {self._professional_signature}"

    def _log_existing_patient_mismatch(
        self,
        tenant_id: str,
        whatsapp_user_id: str,
        existing_patient: patient_entity.Patient,
        tool_input_dto: scheduling_dto.ConfirmSelectedSlotToolInputDTO,
    ) -> None:
        mismatched_fields: list[str] = []
        existing_full_name = self._build_patient_full_name(
            first_name=existing_patient.first_name,
            last_name=existing_patient.last_name,
        )

        normalized_full_name = self._normalize_patient_text(tool_input_dto.patient_full_name)
        if normalized_full_name is not None and normalized_full_name != existing_full_name:
            mismatched_fields.append("patient_full_name")

        normalized_first_name = self._normalize_patient_text(tool_input_dto.patient_first_name)
        if (
            normalized_first_name is not None
            and normalized_first_name != existing_patient.first_name
        ):
            mismatched_fields.append("patient_first_name")

        normalized_last_name = self._normalize_patient_text(tool_input_dto.patient_last_name)
        if normalized_last_name is not None and normalized_last_name != existing_patient.last_name:
            mismatched_fields.append("patient_last_name")

        normalized_email = self._normalize_patient_text(tool_input_dto.patient_email)
        if normalized_email is not None and normalized_email != existing_patient.email:
            mismatched_fields.append("patient_email")

        normalized_phone = self._normalize_patient_text(tool_input_dto.patient_phone)
        if normalized_phone is not None and normalized_phone != existing_patient.phone:
            mismatched_fields.append("patient_phone")

        normalized_age = self._normalize_patient_age(tool_input_dto.patient_age)
        if normalized_age is not None and normalized_age != existing_patient.age:
            mismatched_fields.append("patient_age")

        normalized_location = self._normalize_patient_text(tool_input_dto.patient_location)
        if normalized_location is not None and normalized_location != existing_patient.location:
            mismatched_fields.append("patient_location")

        if not mismatched_fields:
            return

        logger.info(
            "webhook.patient.mismatch_ignored",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="webhook.patient.mismatch_ignored",
                    message="incoming patient data differs from stored profile; stored profile is kept",
                    data={
                        "tenant_id": tenant_id,
                        "whatsapp_user_id": whatsapp_user_id,
                        "mismatched_fields": sorted(set(mismatched_fields)),
                    },
                )
            },
        )

    def _handoff_due_to_google_error(
        self,
        tenant_id: str,
        conversation_id: str,
        request_id: str,
        slot_id: str,
        reason: str,
        error_message: str,
    ) -> dict[str, object]:
        summary_for_professional = (
            "No se pudo confirmar el horario con Google Calendar. "
            f"request_id={request_id} slot_id={slot_id} error={error_message}"
        )
        handoff_result = self._scheduling_service.handoff_to_human(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            input_dto=scheduling_dto.HandoffToHumanInputDTO(
                reason=reason,
                summary_for_professional=summary_for_professional,
            ),
        )
        return {
            "status": handoff_result["status"],
            "control_mode": handoff_result["control_mode"],
            "reason": reason,
        }

    def _coalesce_patient_text(self, primary: str | None, fallback: str | None) -> str | None:
        normalized_primary = self._normalize_patient_text(primary)
        if normalized_primary is not None:
            return normalized_primary
        return self._normalize_patient_text(fallback)

    def _coalesce_patient_age(
        self,
        primary: int | None,
        fallback: int | str | None,
    ) -> int | None:
        if primary is not None:
            return primary
        return self._normalize_patient_age(fallback)

    def _normalize_patient_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        if normalized_value == "":
            return None
        return normalized_value

    def _build_patient_full_name(
        self,
        first_name: str | None,
        last_name: str | None,
    ) -> str | None:
        normalized_first_name = self._normalize_patient_text(first_name)
        normalized_last_name = self._normalize_patient_text(last_name)
        if normalized_first_name is None and normalized_last_name is None:
            return None
        if normalized_first_name is None:
            return normalized_last_name
        if normalized_last_name is None:
            return normalized_first_name
        return f"{normalized_first_name} {normalized_last_name}"

    def _extract_first_name(self, full_name: str) -> str:
        normalized_full_name = full_name.strip()
        parts = normalized_full_name.split()
        if not parts:
            return normalized_full_name
        return parts[0]

    def _extract_last_name(self, full_name: str) -> str:
        normalized_full_name = full_name.strip()
        parts = normalized_full_name.split()
        if len(parts) <= 1:
            return normalized_full_name
        return " ".join(parts[1:])

    def _normalize_patient_age(self, value: int | str | None) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        normalized_value = value.strip()
        if normalized_value == "":
            return None
        if not normalized_value.isdigit():
            return None
        return int(normalized_value)

    def _resolve_patient_phone(
        self,
        provided_patient_phone: str | None,
        fallback_patient_phone: str | None,
    ) -> str | None:
        normalized_provided_phone = self._normalize_patient_text(provided_patient_phone)
        if normalized_provided_phone is not None:
            return normalized_provided_phone
        return self._normalize_patient_text(fallback_patient_phone)

    def _request_contains_proposed_slot(
        self,
        request: scheduling_dto.SchedulingRequestSummaryDTO,
        slot_id: str,
    ) -> bool:
        return any(
            slot.slot_id == slot_id and slot.status in ("PROPOSED", "SELECTED")
            for slot in request.slots
        )

    def _is_google_network_error(self, error_message: str) -> bool:
        normalized_message = error_message.lower()
        return "network error" in normalized_message or "timeout" in normalized_message
