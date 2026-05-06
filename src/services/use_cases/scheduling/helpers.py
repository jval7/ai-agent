"""Shared helpers for the scheduling sub-modules.

What lives here:
  - Pure utility functions (normalisers, coercers, finders) that are
    stateless and require no I/O.
  - DTO conversion (_to_summary_dto).
  - Small predicate helpers (_is_google_conflict_error, etc.).

What does NOT live here:
  - Any I/O or repository calls.
  - Business-state transitions.
  - Side-effect coordination.

All functions are module-level (no class) so they can be imported and
called without a `self` context.
"""

import src.domain.entities.scheduling_request as scheduling_request_entity
import src.domain.entities.scheduling_slot as scheduling_slot_entity
import src.services.dto.scheduling_dto as scheduling_dto


def to_summary_dto(
    request: scheduling_request_entity.SchedulingRequest,
) -> scheduling_dto.SchedulingRequestSummaryDTO:
    slots = []
    for slot in request.slots:
        slots.append(
            scheduling_dto.SchedulingSlotDTO(
                slot_id=slot.id,
                start_at=slot.start_at,
                end_at=slot.end_at,
                timezone=slot.timezone,
                status=slot.status,
            )
        )

    return scheduling_dto.SchedulingRequestSummaryDTO(
        request_id=request.id,
        conversation_id=request.conversation_id,
        whatsapp_user_id=request.whatsapp_user_id,
        request_kind=request.request_kind,
        status=request.status,
        audience_type=request.audience_type,
        round_number=request.round_number,
        patient_preference_note=request.patient_preference_note,
        rejection_summary=request.rejection_summary,
        professional_note=request.professional_note,
        patient_first_name=request.patient_first_name,
        patient_last_name=request.patient_last_name,
        patient_age=request.patient_age,
        consultation_reason=request.consultation_reason,
        consultation_details=request.consultation_details,
        appointment_modality=request.appointment_modality,
        patient_location=request.patient_location,
        slot_options_map=request.slot_options_map,
        selected_slot_id=request.selected_slot_id,
        calendar_event_id=request.calendar_event_id,
        payment_amount_cop=request.payment_amount_cop,
        payment_currency=request.payment_currency,
        payment_method=request.payment_method,
        payment_status=request.payment_status,
        payment_updated_at=request.payment_updated_at,
        created_at=request.created_at,
        updated_at=request.updated_at,
        slots=slots,
    )


def normalize_patient_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized_value = value.strip()
    if normalized_value == "":
        return None
    return normalized_value


def normalize_patient_age(value: int | str | None) -> int | None:
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


def coalesce_patient_text(
    primary: str | None,
    fallback: str | None,
) -> str | None:
    normalized_primary = normalize_patient_text(primary)
    if normalized_primary is not None:
        return normalized_primary
    return normalize_patient_text(fallback)


def coalesce_patient_age(
    primary: int | str | None,
    fallback: int | None,
) -> int | None:
    normalized_primary = normalize_patient_age(primary)
    if normalized_primary is not None:
        return normalized_primary
    return fallback


def find_latest_request_by_statuses(
    requests: list[scheduling_request_entity.SchedulingRequest],
    statuses: tuple[str, ...],
) -> scheduling_request_entity.SchedulingRequest | None:
    filtered_requests: list[scheduling_request_entity.SchedulingRequest] = []
    for request in requests:
        if request.status in statuses:
            filtered_requests.append(request)

    if not filtered_requests:
        return None
    sorted_requests = sorted(filtered_requests, key=lambda item: item.updated_at, reverse=True)
    return sorted_requests[0]


def find_selectable_slot(
    request: scheduling_request_entity.SchedulingRequest,
    slot_id: str,
) -> scheduling_slot_entity.SchedulingSlot | None:
    for slot in request.slots:
        if slot.id == slot_id and slot.status in ("PROPOSED", "SELECTED"):
            return slot
    return None


def find_booked_slot(
    request: scheduling_request_entity.SchedulingRequest,
) -> scheduling_slot_entity.SchedulingSlot | None:
    if request.selected_slot_id is not None:
        for slot in request.slots:
            if slot.id == request.selected_slot_id:
                return slot
    for slot in request.slots:
        if slot.status == "BOOKED":
            return slot
    return None


def list_remaining_slot_ids(
    request: scheduling_request_entity.SchedulingRequest,
) -> list[str]:
    remaining_slot_ids: list[str] = []
    for slot in request.slots:
        if slot.status == "PROPOSED":
            remaining_slot_ids.append(slot.id)
    return remaining_slot_ids


def resolve_booked_event_summary(
    request: scheduling_request_entity.SchedulingRequest,
    requested_summary: str | None,
) -> str:
    normalized_summary = normalize_patient_text(requested_summary)
    if normalized_summary is not None:
        return normalized_summary
    first_name = normalize_patient_text(request.patient_first_name)
    last_name = normalize_patient_text(request.patient_last_name)
    if first_name is not None and last_name is not None:
        return f"Cita - {first_name} {last_name}"
    if first_name is not None:
        return f"Cita - {first_name}"
    return f"Cita - {request.whatsapp_user_id}"


def is_google_conflict_error(error_message: str) -> bool:
    normalized_message = error_message.lower()
    return "status=409" in normalized_message or "conflict" in normalized_message


def is_google_not_found_error(error_message: str) -> bool:
    normalized_message = error_message.lower()
    return "status=404" in normalized_message or "not found" in normalized_message
