import datetime
import typing

import pydantic

import src.domain.entities.scheduling_request as scheduling_request_entity
import src.domain.entities.scheduling_slot as scheduling_slot_entity
import src.infra.logs as app_logs
import src.ports.agent_profile_repository_port as agent_profile_repository_port
import src.ports.agent_workflow_port as agent_workflow_port
import src.ports.clock_port as clock_port
import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.id_generator_port as id_generator_port
import src.ports.manual_appointment_repository_port as manual_appointment_repository_port
import src.ports.patient_repository_port as patient_repository_port
import src.ports.scheduling_repository_port as scheduling_repository_port
import src.ports.task_scheduler_port as task_scheduler_port
import src.ports.tenant_repository_port as tenant_repository_port
import src.ports.whatsapp_connection_repository_port as whatsapp_connection_repository_port
import src.ports.whatsapp_provider_port as whatsapp_provider_port
import src.services.agentic.workflow_engine as workflow_engine
import src.services.dto.agent_workflow_dto as agent_workflow_dto
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.event_description_builder as event_description_builder_mod
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import src.services.use_cases.payment_confirmation_dispatcher as payment_confirmation_dispatcher
import src.services.use_cases.reminder_service as reminder_service_module
import src.services.use_cases.tag_service as tag_service_module

logger = app_logs.get_logger(__name__)


class _RescheduleSourceData(pydantic.BaseModel):
    """Data inherited by a RESCHEDULE child SR from its booking source.

    The source can be either an existing BOOKED SR or a manual_appointment
    referenced by a reminder-pre-positioned placeholder SR. This struct
    normalizes both cases so the child SR can be built uniformly.
    """

    whatsapp_user_id: str
    consultation_reason: str | None
    appointment_modality: typing.Literal["PRESENCIAL", "VIRTUAL"] | None
    patient_location: str | None
    patient_first_name: str | None
    patient_last_name: str | None
    patient_age: int | None
    source_appointment_id: str
    source_appointment_kind: typing.Literal["SCHEDULING_REQUEST", "MANUAL_APPOINTMENT"]


class SchedulingTransitionRuntimeAdapter(agent_workflow_port.SchedulingTransitionRuntimePort):
    def __init__(
        self,
        apply_transition: typing.Callable[
            [agent_workflow_dto.SchedulingTransitionInputDTO],
            object,
        ],
    ) -> None:
        self._apply_transition = apply_transition

    def validate_transition(
        self,
        input_dto: agent_workflow_dto.SchedulingTransitionInputDTO,
    ) -> None:
        del input_dto

    def apply_transition(
        self,
        input_dto: agent_workflow_dto.SchedulingTransitionInputDTO,
    ) -> object:
        return self._apply_transition(input_dto)

    def execute_side_effects(
        self,
        input_dto: agent_workflow_dto.SchedulingTransitionInputDTO,
        transition_result: object,
    ) -> None:
        del input_dto
        del transition_result

    def persist_transition(
        self,
        input_dto: agent_workflow_dto.SchedulingTransitionInputDTO,
        transition_result: object,
    ) -> None:
        del input_dto
        del transition_result

    def build_output(
        self,
        input_dto: agent_workflow_dto.SchedulingTransitionInputDTO,
        transition_result: object,
    ) -> object:
        del input_dto
        return transition_result


class SchedulingService:
    def __init__(
        self,
        scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
        conversation_repository: conversation_repository_port.ConversationRepositoryPort,
        google_calendar_onboarding_service: (
            google_calendar_onboarding_service.GoogleCalendarOnboardingService
        ),
        id_generator: id_generator_port.IdGeneratorPort,
        clock: clock_port.ClockPort,
        task_scheduler: task_scheduler_port.TaskSchedulerPort,
        event_description_builder: event_description_builder_mod.EventDescriptionBuilder,
        auto_close_delay_seconds: int = 3600,
        agent_workflow: agent_workflow_port.AgentWorkflowPort | None = None,
        tag_service: tag_service_module.TagService | None = None,
        reminder_service: reminder_service_module.ReminderService | None = None,
        patient_repository: patient_repository_port.PatientRepositoryPort | None = None,
        manual_appointment_repository: (
            manual_appointment_repository_port.ManualAppointmentRepositoryPort | None
        ) = None,
        whatsapp_provider: whatsapp_provider_port.WhatsappProviderPort | None = None,
        whatsapp_connection_repository: (
            whatsapp_connection_repository_port.WhatsappConnectionRepositoryPort | None
        ) = None,
        agent_profile_repository: (
            agent_profile_repository_port.AgentProfileRepositoryPort | None
        ) = None,
        tenant_repository: tenant_repository_port.TenantRepositoryPort | None = None,
    ) -> None:
        self._scheduling_repository = scheduling_repository
        self._conversation_repository = conversation_repository
        self._google_calendar_onboarding_service = google_calendar_onboarding_service
        self._id_generator = id_generator
        self._clock = clock
        self._task_scheduler = task_scheduler
        self._auto_close_delay_seconds = auto_close_delay_seconds
        self._tag_service = tag_service
        self._reminder_service = reminder_service
        self._patient_repository = patient_repository
        self._manual_appointment_repository = manual_appointment_repository
        self._whatsapp_provider = whatsapp_provider
        self._whatsapp_connection_repository = whatsapp_connection_repository
        self._event_description_builder = event_description_builder
        self._agent_profile_repository = agent_profile_repository
        self._tenant_repository = tenant_repository
        self._agent_workflow: agent_workflow_port.AgentWorkflowPort
        if agent_workflow is None:
            self._agent_workflow = workflow_engine.LangGraphAgentWorkflowEngine()
        else:
            self._agent_workflow = agent_workflow

    def _is_eval_tenant(self, tenant_id: str) -> bool:
        """Return True when the tenant is flagged as an eval tenant.

        Defaults to False when the tenant is not found or no repository is
        wired, so regular prod tenants are never affected.
        """
        if self._tenant_repository is None:
            return False
        tenant = self._tenant_repository.get_by_id(tenant_id)
        if tenant is None:
            return False
        return tenant.is_eval_tenant

    def _sync_tags_after_status_change(
        self,
        tenant_id: str,
        conversation_id: str,
        new_status: str,
    ) -> None:
        if self._tag_service is None:
            return
        self._tag_service.sync_scheduling_tags(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status=new_status,
        )

    def list_requests_by_tenant(
        self,
        tenant_id: str,
        status: str | None = None,
    ) -> scheduling_dto.SchedulingRequestListResponseDTO:
        requests = self._scheduling_repository.list_requests_by_tenant(tenant_id, status)
        sorted_requests = sorted(requests, key=lambda item: item.updated_at, reverse=True)
        items = [self._to_summary_dto(item) for item in sorted_requests]
        return scheduling_dto.SchedulingRequestListResponseDTO(items=items)

    def list_requests_by_conversation(
        self,
        tenant_id: str,
        conversation_id: str,
    ) -> scheduling_dto.SchedulingRequestListResponseDTO:
        requests = self._scheduling_repository.list_requests_by_conversation(
            tenant_id, conversation_id
        )
        sorted_requests = sorted(requests, key=lambda item: item.updated_at, reverse=True)
        items = [self._to_summary_dto(item) for item in sorted_requests]
        return scheduling_dto.SchedulingRequestListResponseDTO(items=items)

    def _run_transition_with_graph(
        self,
        action: typing.Literal[
            "SUBMIT_CONSULTATION_REASON",
            "RESOLVE_CONSULTATION_REVIEW",
            "SELECT_SLOT_FOR_CONFIRMATION",
            "CONFIRM_SLOT_AND_CREATE_EVENT",
            "CANCEL_ACTIVE_REQUEST",
            "HANDOFF_TO_HUMAN",
            "RESCHEDULE_BOOKED_SLOT",
            "CANCEL_BOOKED_SLOT",
            "UPDATE_BOOKED_PAYMENT",
            "APPROVE_PAYMENT",
            "ESCALATE_PATIENT_SLOT_REJECTION",
            "CLOSE_SESSION",
            "CHANGE_BOOKED_MODALITY",
            "SUBMIT_RESCHEDULE_FOR_REVIEW",
            "CONFIRM_RESCHEDULED_SLOT",
        ],
        payload: object | None,
        apply_transition: typing.Callable[
            [agent_workflow_dto.SchedulingTransitionInputDTO],
            object,
        ],
    ) -> object:
        runtime_adapter = SchedulingTransitionRuntimeAdapter(
            apply_transition=apply_transition,
        )
        transition_result = self._agent_workflow.run_scheduling_transition(
            input_dto=agent_workflow_dto.SchedulingTransitionInputDTO(
                action=action,
                payload=payload,
            ),
            runtime_port=runtime_adapter,
        )
        return transition_result.result

    def submit_consultation_reason_for_review(
        self,
        tenant_id: str,
        conversation_id: str,
        whatsapp_user_id: str,
        input_dto: scheduling_dto.SubmitConsultationReasonForReviewToolInputDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        transition_result = self._run_transition_with_graph(
            action="SUBMIT_CONSULTATION_REASON",
            payload={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "whatsapp_user_id": whatsapp_user_id,
                "input": input_dto,
            },
            apply_transition=lambda _: self._submit_consultation_reason_for_review_impl(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                whatsapp_user_id=whatsapp_user_id,
                input_dto=input_dto,
            ),
        )
        return typing.cast(scheduling_dto.SchedulingRequestSummaryDTO, transition_result)

    def resolve_consultation_review(
        self,
        tenant_id: str,
        conversation_id: str,
        request_id: str,
        input_dto: scheduling_dto.ConsultationReviewDecisionDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        transition_result = self._run_transition_with_graph(
            action="RESOLVE_CONSULTATION_REVIEW",
            payload={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "request_id": request_id,
                "input": input_dto,
            },
            apply_transition=lambda _: self._resolve_consultation_review_impl(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                request_id=request_id,
                input_dto=input_dto,
            ),
        )
        return typing.cast(scheduling_dto.SchedulingRequestSummaryDTO, transition_result)

    def cancel_active_request(
        self,
        tenant_id: str,
        conversation_id: str,
        input_dto: scheduling_dto.CancelActiveSchedulingRequestInputDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        transition_result = self._run_transition_with_graph(
            action="CANCEL_ACTIVE_REQUEST",
            payload={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "input": input_dto,
            },
            apply_transition=lambda _: self._cancel_active_request_impl(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                input_dto=input_dto,
            ),
        )
        return typing.cast(scheduling_dto.SchedulingRequestSummaryDTO, transition_result)

    def confirm_selected_slot_and_create_event(
        self,
        tenant_id: str,
        conversation_id: str,
        input_dto: scheduling_dto.ConfirmSelectedSlotInputDTO,
    ) -> scheduling_dto.ConfirmSelectedSlotResponseDTO:
        transition_result = self._run_transition_with_graph(
            action="CONFIRM_SLOT_AND_CREATE_EVENT",
            payload={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "input": input_dto,
            },
            apply_transition=lambda _: self._confirm_selected_slot_and_create_event_impl(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                input_dto=input_dto,
            ),
        )
        return typing.cast(scheduling_dto.ConfirmSelectedSlotResponseDTO, transition_result)

    def select_slot_for_confirmation(
        self,
        tenant_id: str,
        conversation_id: str,
        request_id: str,
        slot_id: str,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        transition_result = self._run_transition_with_graph(
            action="SELECT_SLOT_FOR_CONFIRMATION",
            payload={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "request_id": request_id,
                "slot_id": slot_id,
            },
            apply_transition=lambda _: self._select_slot_for_confirmation_impl(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                request_id=request_id,
                slot_id=slot_id,
            ),
        )
        return typing.cast(scheduling_dto.SchedulingRequestSummaryDTO, transition_result)

    def approve_payment(
        self,
        tenant_id: str,
        conversation_id: str,
        request_id: str,
        input_dto: scheduling_dto.PaymentReviewDecisionDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        transition_result = self._run_transition_with_graph(
            action="APPROVE_PAYMENT",
            payload={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "request_id": request_id,
                "input": input_dto,
            },
            apply_transition=lambda _: self._approve_payment_impl(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                request_id=request_id,
                input_dto=input_dto,
            ),
        )
        return typing.cast(scheduling_dto.SchedulingRequestSummaryDTO, transition_result)

    def reschedule_booked_slot(
        self,
        tenant_id: str,
        request_id: str,
        input_dto: scheduling_dto.RescheduleBookedSlotInputDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        transition_result = self._run_transition_with_graph(
            action="RESCHEDULE_BOOKED_SLOT",
            payload={
                "tenant_id": tenant_id,
                "request_id": request_id,
                "input": input_dto,
            },
            apply_transition=lambda _: self._reschedule_booked_slot_impl(
                tenant_id=tenant_id,
                request_id=request_id,
                input_dto=input_dto,
            ),
        )
        return typing.cast(scheduling_dto.SchedulingRequestSummaryDTO, transition_result)

    def cancel_booked_slot(
        self,
        tenant_id: str,
        request_id: str,
        input_dto: scheduling_dto.CancelBookedSlotInputDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        transition_result = self._run_transition_with_graph(
            action="CANCEL_BOOKED_SLOT",
            payload={
                "tenant_id": tenant_id,
                "request_id": request_id,
                "input": input_dto,
            },
            apply_transition=lambda _: self._cancel_booked_slot_impl(
                tenant_id=tenant_id,
                request_id=request_id,
                input_dto=input_dto,
            ),
        )
        return typing.cast(scheduling_dto.SchedulingRequestSummaryDTO, transition_result)

    def update_booked_payment(
        self,
        tenant_id: str,
        request_id: str,
        input_dto: scheduling_dto.UpdateBookedSlotPaymentInputDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        transition_result = self._run_transition_with_graph(
            action="UPDATE_BOOKED_PAYMENT",
            payload={
                "tenant_id": tenant_id,
                "request_id": request_id,
                "input": input_dto,
            },
            apply_transition=lambda _: self._update_booked_payment_impl(
                tenant_id=tenant_id,
                request_id=request_id,
                input_dto=input_dto,
            ),
        )
        return typing.cast(scheduling_dto.SchedulingRequestSummaryDTO, transition_result)

    def change_booked_modality(
        self,
        tenant_id: str,
        request_id: str,
        input_dto: scheduling_dto.ChangeBookedModalityInputDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        transition_result = self._run_transition_with_graph(
            action="CHANGE_BOOKED_MODALITY",
            payload={
                "tenant_id": tenant_id,
                "request_id": request_id,
                "input": input_dto,
            },
            apply_transition=lambda _: self._change_booked_modality_impl(
                tenant_id=tenant_id,
                request_id=request_id,
                input_dto=input_dto,
            ),
        )
        return typing.cast(scheduling_dto.SchedulingRequestSummaryDTO, transition_result)

    def handoff_to_human(
        self,
        tenant_id: str,
        conversation_id: str,
        input_dto: scheduling_dto.HandoffToHumanInputDTO,
    ) -> dict[str, str]:
        transition_result = self._run_transition_with_graph(
            action="HANDOFF_TO_HUMAN",
            payload={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "input": input_dto,
            },
            apply_transition=lambda _: self._handoff_to_human_impl(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                input_dto=input_dto,
            ),
        )
        return typing.cast(dict[str, str], transition_result)

    def close_session(
        self,
        tenant_id: str,
        conversation_id: str,
    ) -> dict[str, str]:
        transition_result = self._run_transition_with_graph(
            action="CLOSE_SESSION",
            payload={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
            },
            apply_transition=lambda _: self._close_session_impl(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
            ),
        )
        return typing.cast(dict[str, str], transition_result)

    def submit_reschedule_for_review(
        self,
        tenant_id: str,
        conversation_id: str,
        whatsapp_user_id: str,
        input_dto: scheduling_dto.SubmitRescheduleForReviewToolInputDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        transition_result = self._run_transition_with_graph(
            action="SUBMIT_RESCHEDULE_FOR_REVIEW",
            payload={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "whatsapp_user_id": whatsapp_user_id,
                "input": input_dto,
            },
            apply_transition=lambda _: self._submit_reschedule_for_review_impl(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                whatsapp_user_id=whatsapp_user_id,
                input_dto=input_dto,
            ),
        )
        return typing.cast(scheduling_dto.SchedulingRequestSummaryDTO, transition_result)

    def confirm_rescheduled_slot(
        self,
        tenant_id: str,
        conversation_id: str,
        input_dto: scheduling_dto.ConfirmRescheduledSlotInputDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        transition_result = self._run_transition_with_graph(
            action="CONFIRM_RESCHEDULED_SLOT",
            payload={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "input": input_dto,
            },
            apply_transition=lambda _: self._confirm_rescheduled_slot_impl(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                input_dto=input_dto,
            ),
        )
        return typing.cast(scheduling_dto.SchedulingRequestSummaryDTO, transition_result)

    def escalate_patient_slot_rejection(
        self,
        tenant_id: str,
        request_id: str,
        patient_preference_note: str,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        transition_result = self._run_transition_with_graph(
            action="ESCALATE_PATIENT_SLOT_REJECTION",
            payload={
                "tenant_id": tenant_id,
                "request_id": request_id,
                "patient_preference_note": patient_preference_note,
            },
            apply_transition=lambda _: self._escalate_patient_slot_rejection_impl(
                tenant_id=tenant_id,
                request_id=request_id,
                patient_preference_note=patient_preference_note,
            ),
        )
        return typing.cast(scheduling_dto.SchedulingRequestSummaryDTO, transition_result)

    def _submit_consultation_reason_for_review_impl(
        self,
        tenant_id: str,
        conversation_id: str,
        whatsapp_user_id: str,
        input_dto: scheduling_dto.SubmitConsultationReasonForReviewToolInputDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        conversation = self._conversation_repository.get_conversation_by_id(
            tenant_id, conversation_id
        )
        if conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")

        now_value = self._clock.now()
        existing_requests = self._scheduling_repository.list_requests_by_conversation(
            tenant_id,
            conversation_id,
        )
        request = self._resolve_request_for_consultation_submission(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            existing_requests=existing_requests,
            request_id=input_dto.request_id,
        )
        if request is None:
            active_scheduling_request = self._find_latest_request_by_statuses(
                requests=existing_requests,
                statuses=("AWAITING_PATIENT_CHOICE",),
            )
            if active_scheduling_request is not None:
                raise service_exceptions.InvalidStateError(
                    "schedule options are already available; ask the patient to choose one numbered slot"
                )
            request = scheduling_request_entity.SchedulingRequest(
                id=self._id_generator.new_id(),
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                whatsapp_user_id=whatsapp_user_id,
                request_kind="INITIAL",
                status="AWAITING_CONSULTATION_REVIEW",
                round_number=len(existing_requests) + 1,
                patient_preference_note=None,
                rejection_summary=None,
                professional_note=None,
                slots=[],
                slot_options_map={},
                selected_slot_id=None,
                calendar_event_id=None,
                created_at=now_value,
                updated_at=now_value,
            )

        if request.status in ("BOOKED", "HUMAN_HANDOFF", "CONSULTATION_REJECTED", "CANCELLED"):
            raise service_exceptions.InvalidStateError(
                "cannot submit consultation reason for a closed scheduling request"
            )
        if request.status == "AWAITING_PATIENT_CHOICE":
            raise service_exceptions.InvalidStateError(
                "schedule options are already available; ask the patient to choose one numbered slot"
            )

        consultation_reason = self._coalesce_patient_text(
            primary=input_dto.consultation_reason,
            fallback=request.consultation_reason,
        )
        if consultation_reason is None:
            raise service_exceptions.InvalidStateError(
                "missing required patient data: consultation_reason; ask only for the consultation reason now"
            )

        request.consultation_reason = consultation_reason
        if input_dto.appointment_modality is not None:
            request.appointment_modality = input_dto.appointment_modality
            request.patient_location = self._resolve_location(
                appointment_modality=input_dto.appointment_modality,
                patient_location=input_dto.patient_location,
                fallback_patient_location=request.patient_location,
                tenant_id=tenant_id,
            )
        request.professional_note = None
        request.rejection_summary = None
        request.set_status("AWAITING_CONSULTATION_REVIEW", now_value)
        self._scheduling_repository.save_request(request)
        self._sync_tags_after_status_change(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status=request.status,
        )
        logger.info(
            "scheduling.consultation_review_requested",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.consultation_review_requested",
                    message="consultation reason submitted for professional review",
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation_id,
                        "request_id": request.id,
                        "status": request.status,
                    },
                )
            },
        )
        return self._to_summary_dto(request)

    def _resolve_consultation_review_impl(
        self,
        tenant_id: str,
        conversation_id: str,
        request_id: str,
        input_dto: scheduling_dto.ConsultationReviewDecisionDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        request = self._scheduling_repository.get_request_by_id(tenant_id, request_id)
        if request is None:
            raise service_exceptions.EntityNotFoundError("scheduling request not found")
        if request.conversation_id != conversation_id:
            raise service_exceptions.AuthorizationError(
                "scheduling request does not belong to conversation"
            )
        if request.status != "AWAITING_CONSULTATION_REVIEW":
            raise service_exceptions.InvalidStateError(
                "scheduling request is not waiting for consultation review"
            )

        now_value = self._clock.now()
        professional_note = self._normalize_patient_text(input_dto.professional_note)

        if input_dto.decision == "REQUEST_MORE_INFO":
            if professional_note is None:
                raise service_exceptions.InvalidStateError(
                    "professional_note is required when requesting more information"
                )
            request.professional_note = professional_note
            request.set_status("AWAITING_CONSULTATION_DETAILS", now_value)
        else:
            request.professional_note = professional_note
            request.set_status("CONSULTATION_REJECTED", now_value)

        self._scheduling_repository.save_request(request)
        self._sync_tags_after_status_change(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status=request.status,
        )
        logger.info(
            "scheduling.consultation_review_resolved",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.consultation_review_resolved",
                    message="consultation review resolved by professional",
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation_id,
                        "request_id": request.id,
                        "decision": input_dto.decision,
                        "status": request.status,
                    },
                )
            },
        )
        return self._to_summary_dto(request)

    def _cancel_active_request_impl(
        self,
        tenant_id: str,
        conversation_id: str,
        input_dto: scheduling_dto.CancelActiveSchedulingRequestInputDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        conversation = self._conversation_repository.get_conversation_by_id(
            tenant_id, conversation_id
        )
        if conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")

        request_list = self._scheduling_repository.list_requests_by_conversation(
            tenant_id,
            conversation_id,
        )
        open_request = self._find_latest_request_by_statuses(
            requests=request_list,
            statuses=(
                "AWAITING_CONSULTATION_REVIEW",
                "AWAITING_CONSULTATION_DETAILS",
                "AWAITING_PATIENT_CHOICE",
                "AWAITING_PAYMENT_CONFIRMATION",
            ),
        )
        if open_request is None:
            raise service_exceptions.EntityNotFoundError("no active scheduling request found")

        now_value = self._clock.now()
        open_request.set_status("CANCELLED", now_value)
        cancellation_reason = self._normalize_patient_text(input_dto.reason)
        if cancellation_reason is not None:
            open_request.professional_note = cancellation_reason
        self._scheduling_repository.save_request(open_request)
        self._sync_tags_after_status_change(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status=open_request.status,
        )
        logger.info(
            "scheduling.request_cancelled",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.request_cancelled",
                    message="scheduling request cancelled by patient",
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation_id,
                        "request_id": open_request.id,
                    },
                )
            },
        )
        return self._to_summary_dto(open_request)

    def _book_slot_and_create_event(
        self,
        tenant_id: str,
        conversation_id: str,
        request: scheduling_request_entity.SchedulingRequest,
        selected_slot: scheduling_slot_entity.SchedulingSlot,
        event_summary: str,
        attendee_emails: list[str],
        reminder_payment_status: typing.Literal["PAID", "PENDING"],
        now_value: datetime.datetime,
    ) -> scheduling_dto.ConfirmSelectedSlotResponseDTO:
        """Create a calendar event and transition the request to BOOKED.

        Checks for conflicts first and returns SLOT_CONFLICT if one is found.
        Schedules the auto-close task and the appointment reminder after a
        successful booking.

        When the tenant has ``is_eval_tenant=True`` the Calendar integration is
        skipped entirely (no conflict check, no event creation).  The request
        still transitions to BOOKED with ``calendar_event_id=None``.
        """
        is_eval = self._is_eval_tenant(tenant_id)

        if not is_eval:
            has_conflict = self._google_calendar_onboarding_service.has_conflict(
                tenant_id=tenant_id,
                start_at=selected_slot.start_at,
                end_at=selected_slot.end_at,
            )
            if has_conflict:
                return self._mark_selected_slot_conflict(request, selected_slot, now_value)

        with_meet = request.appointment_modality == "VIRTUAL"
        if request.appointment_modality is None:
            logger.warning(
                "scheduling.confirm_slot.missing_modality",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="scheduling.confirm_slot.missing_modality",
                        message="appointment_modality is None; defaulting to PRESENCIAL",
                        data={"tenant_id": tenant_id, "request_id": request.id},
                    )
                },
            )

        calendar_event_id: str | None = None
        meet_url: str | None = None

        if is_eval:
            logger.info(
                "scheduling.calendar.skipped_for_eval_tenant",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="scheduling.calendar.skipped_for_eval_tenant",
                        message="calendar event creation skipped for eval tenant",
                        data={"tenant_id": tenant_id, "request_id": request.id},
                    )
                },
            )
        else:
            try:
                normalized_summary = event_summary.strip()
                if not normalized_summary:
                    raise service_exceptions.InvalidStateError("event summary cannot be empty")
                event_description_result = self._event_description_builder.build(
                    tenant_id=tenant_id,
                    modality=request.appointment_modality,
                    payment_status=request.payment_status,
                )
                event_description = event_description_result.description
                event_location = event_description_result.location
                event = self._google_calendar_onboarding_service.create_event(
                    tenant_id=tenant_id,
                    start_at=selected_slot.start_at,
                    end_at=selected_slot.end_at,
                    summary=normalized_summary,
                    attendee_emails=attendee_emails,
                    with_meet=with_meet,
                    description=event_description,
                    location=event_location,
                )
                calendar_event_id = event.event_id
                meet_url = event.meet_url
            except service_exceptions.ExternalProviderError as error:
                if self._is_google_conflict_error(str(error)):
                    return self._mark_selected_slot_conflict(request, selected_slot, now_value)
                raise

        for slot in request.slots:
            if slot.id == selected_slot.id:
                slot.status = "BOOKED"
            elif slot.status == "PROPOSED":
                slot.status = "REJECTED"

        request.selected_slot_id = selected_slot.id
        request.calendar_event_id = calendar_event_id
        request.set_status("BOOKED", now_value)
        self._scheduling_repository.save_request(request)
        self._sync_tags_after_status_change(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status=request.status,
        )
        self._schedule_auto_close_task(tenant_id, request.id)
        if self._reminder_service is not None and not is_eval:
            self._reminder_service.maybe_schedule_reminder(
                tenant_id=tenant_id,
                source_type="SCHEDULING_REQUEST",
                source_id=request.id,
                patient_whatsapp_user_id=request.whatsapp_user_id,
                patient_name=request.patient_first_name or "Paciente",
                appointment_start_at=selected_slot.start_at,
                payment_status=reminder_payment_status,
                appointment_modality=request.appointment_modality,
                meet_url=meet_url,
            )
        return scheduling_dto.ConfirmSelectedSlotResponseDTO(
            status="BOOKED",
            request_id=request.id,
            selected_slot_id=selected_slot.id,
            calendar_event_id=calendar_event_id,
            remaining_slot_ids=[],
        )

    def _confirm_selected_slot_and_create_event_impl(
        self,
        tenant_id: str,
        conversation_id: str,
        input_dto: scheduling_dto.ConfirmSelectedSlotInputDTO,
    ) -> scheduling_dto.ConfirmSelectedSlotResponseDTO:
        request = self._scheduling_repository.get_request_by_id(tenant_id, input_dto.request_id)
        if request is None:
            raise service_exceptions.EntityNotFoundError("scheduling request not found")
        if request.conversation_id != conversation_id:
            raise service_exceptions.AuthorizationError(
                "scheduling request does not belong to conversation"
            )
        if request.status != "AWAITING_PATIENT_CHOICE":
            raise service_exceptions.InvalidStateError(
                "scheduling request is not waiting for patient choice"
            )

        selected_slot = self._find_selectable_slot(request, input_dto.slot_id)
        if selected_slot is None:
            raise service_exceptions.InvalidStateError("selected slot is not available")

        # Persist the resolved patient name on the request so reminder
        # messages and the admin reminders list show the actual name instead
        # of the "Paciente" fallback. The resolver fills these from the
        # collected patient profile right before this call.
        if input_dto.patient_first_name is not None:
            request.patient_first_name = input_dto.patient_first_name
        if input_dto.patient_last_name is not None:
            request.patient_last_name = input_dto.patient_last_name

        now_value = self._clock.now()
        return self._book_slot_and_create_event(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            request=request,
            selected_slot=selected_slot,
            event_summary=input_dto.event_summary,
            attendee_emails=input_dto.attendee_emails,
            reminder_payment_status="PAID",
            now_value=now_value,
        )

    def _archive_conversation_subsession_after_booking(
        self,
        tenant_id: str,
        conversation_id: str,
        scheduling_request_id: str,
        calendar_event_id: str,
        now_value: datetime.datetime,
    ) -> None:
        conversation = self._conversation_repository.get_conversation_by_id(
            tenant_id,
            conversation_id,
        )
        if conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")

        active_messages = self._conversation_repository.list_messages(
            tenant_id,
            conversation_id,
        )
        sorted_active_messages = sorted(active_messages, key=lambda item: item.created_at)
        conversation.archive_current_session(
            scheduling_request_id=scheduling_request_id,
            calendar_event_id=calendar_event_id,
            messages=sorted_active_messages,
            now=now_value,
        )
        self._conversation_repository.save_conversation(conversation)
        self._conversation_repository.delete_messages(tenant_id, conversation_id)
        logger.info(
            "scheduling.subsession_archived_after_booking",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.subsession_archived_after_booking",
                    message="conversation messages archived into subsession after booking",
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation_id,
                        "request_id": scheduling_request_id,
                        "calendar_event_id": calendar_event_id,
                        "archived_messages_count": len(sorted_active_messages),
                        "subsessions_count": len(conversation.subsessions),
                    },
                )
            },
        )

    def _archive_conversation_subsession_manual_close(
        self,
        tenant_id: str,
        conversation_id: str,
        now_value: datetime.datetime,
    ) -> None:
        conversation = self._conversation_repository.get_conversation_by_id(
            tenant_id,
            conversation_id,
        )
        if conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")

        active_messages = self._conversation_repository.list_messages(
            tenant_id,
            conversation_id,
        )
        sorted_active_messages = sorted(active_messages, key=lambda item: item.created_at)
        conversation.archive_manual_close(
            messages=sorted_active_messages,
            now=now_value,
        )
        self._conversation_repository.save_conversation(conversation)
        self._conversation_repository.delete_messages(tenant_id, conversation_id)
        logger.info(
            "scheduling.subsession_archived_manual_close",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.subsession_archived_manual_close",
                    message="conversation messages archived into subsession via manual close",
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation_id,
                        "archived_messages_count": len(sorted_active_messages),
                        "subsessions_count": len(conversation.subsessions),
                    },
                )
            },
        )

    def _get_payment_timing(
        self, tenant_id: str
    ) -> typing.Literal["BEFORE_SESSION", "AFTER_SESSION"]:
        """Return the current payment_timing for the tenant.

        Falls back to "BEFORE_SESSION" when no agent profile repo is wired
        (e.g. unit tests that don't inject it) — preserves existing behavior.
        """
        if self._agent_profile_repository is None:
            return "BEFORE_SESSION"
        profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        if profile is None:
            return "BEFORE_SESSION"
        return profile.payment_timing

    def _select_slot_for_confirmation_impl(
        self,
        tenant_id: str,
        conversation_id: str,
        request_id: str,
        slot_id: str,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        request = self._scheduling_repository.get_request_by_id(tenant_id, request_id)
        if request is None:
            raise service_exceptions.EntityNotFoundError("scheduling request not found")
        if request.conversation_id != conversation_id:
            raise service_exceptions.AuthorizationError(
                "scheduling request does not belong to conversation"
            )
        if request.status != "AWAITING_PATIENT_CHOICE":
            raise service_exceptions.InvalidStateError(
                "scheduling request is not waiting for patient choice"
            )

        selected_slot = self._find_selectable_slot(request, slot_id)
        if selected_slot is None:
            raise service_exceptions.InvalidStateError("selected slot is not available")

        payment_timing = self._get_payment_timing(tenant_id)
        now_value = self._clock.now()

        for slot in request.slots:
            if slot.id == selected_slot.id:
                slot.status = "SELECTED"
            elif slot.status == "SELECTED":
                slot.status = "PROPOSED"

        request.selected_slot_id = selected_slot.id

        if payment_timing == "AFTER_SESSION" or request.request_kind == "RESCHEDULE":
            # AFTER_SESSION: skip the payment step entirely. Keep the request
            # in AWAITING_PATIENT_CHOICE with selected_slot_id set so the
            # runtime resolver derives state=COLLECTING_CONFIRMATION_DATA and
            # the bot collects email/age/etc. Once collected, the bot calls
            # confirm_selected_slot_and_create_event which books the event
            # with the patient's email (Calendar invite goes out) and
            # persists patient_first_name on the request (so reminders show
            # the real name, not "Paciente").
            # RESCHEDULE: also skip payment — the appointment was already paid
            # (or payment is not required again for rescheduling).
            request.updated_at = now_value
            self._scheduling_repository.save_request(request)
            logger.info(
                "scheduling.slot_selected_skip_payment",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="scheduling.slot_selected_skip_payment",
                        message="slot selected; payment step skipped (AFTER_SESSION or RESCHEDULE)",
                        data={
                            "tenant_id": tenant_id,
                            "conversation_id": conversation_id,
                            "request_id": request.id,
                            "slot_id": selected_slot.id,
                            "reason": "RESCHEDULE"
                            if request.request_kind == "RESCHEDULE"
                            else "AFTER_SESSION",
                        },
                    )
                },
            )
            return self._to_summary_dto(request)

        # BEFORE_SESSION: standard flow — await payment confirmation.
        request.set_status("AWAITING_PAYMENT_CONFIRMATION", now_value)
        self._scheduling_repository.save_request(request)
        self._sync_tags_after_status_change(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status=request.status,
        )
        logger.info(
            "scheduling.slot_selected",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.slot_selected",
                    message="patient slot selection persisted",
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation_id,
                        "request_id": request.id,
                        "slot_id": selected_slot.id,
                    },
                )
            },
        )
        return self._to_summary_dto(request)

    def _approve_payment_impl(
        self,
        tenant_id: str,
        conversation_id: str,
        request_id: str,
        input_dto: scheduling_dto.PaymentReviewDecisionDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        request = self._scheduling_repository.get_request_by_id(tenant_id, request_id)
        if request is None:
            raise service_exceptions.EntityNotFoundError("scheduling request not found")
        if request.conversation_id != conversation_id:
            raise service_exceptions.AuthorizationError(
                "scheduling request does not belong to conversation"
            )
        if request.status != "AWAITING_PAYMENT_CONFIRMATION":
            raise service_exceptions.InvalidStateError(
                "scheduling request is not awaiting payment confirmation"
            )

        now_value = self._clock.now()
        if input_dto.decision == "APPROVE":
            if (
                request.source_appointment_id is not None
                and request.source_appointment_kind is not None
            ):
                # Reminder-reply flow: the appointment already exists and is BOOKED.
                # Mark the source as PAID, close this synthetic request, and notify patient.
                self._approve_payment_from_reminder(request, input_dto, now_value)
            else:
                # Original scheduling flow: transition to slot selection.
                request.payment_status = "PAID"
                request.payment_amount_cop = input_dto.payment_amount_cop
                request.payment_currency = input_dto.payment_currency
                request.payment_updated_at = now_value
                request.set_status("AWAITING_PATIENT_CHOICE", now_value)

        if input_dto.professional_note is not None:
            request.professional_note = input_dto.professional_note

        request.updated_at = now_value
        self._scheduling_repository.save_request(request)
        if input_dto.decision == "APPROVE":
            self._sync_tags_after_status_change(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                new_status=request.status,
            )
        logger.info(
            "scheduling.payment_review_resolved",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.payment_review_resolved",
                    message="professional resolved payment review",
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation_id,
                        "request_id": request.id,
                        "decision": input_dto.decision,
                    },
                )
            },
        )
        return self._to_summary_dto(request)

    def _approve_payment_from_reminder(
        self,
        request: scheduling_request_entity.SchedulingRequest,
        input_dto: scheduling_dto.PaymentReviewDecisionDTO,
        now_value: datetime.datetime,
    ) -> None:
        """Handle payment approval for a synthetic reminder-reply SchedulingRequest.

        Marks the source appointment as PAID, closes the synthetic request, and
        sends a freeform confirmation message to the patient via WhatsApp.
        All operations are best-effort after the first: failures are logged but
        do not bubble up to the caller — the payment approval must not fail just
        because a side-effect went wrong.
        """
        source_id = request.source_appointment_id
        source_kind = request.source_appointment_kind
        tenant_id = request.tenant_id

        # 1. Update payment_status on the source appointment.
        if source_kind == "MANUAL_APPOINTMENT":
            if self._manual_appointment_repository is not None:
                source_appt = self._manual_appointment_repository.get_by_id(
                    tenant_id, source_id or ""
                )
                if source_appt is None:
                    logger.warning(
                        "scheduling.approve_reminder_payment.source_not_found",
                        extra={
                            "tenant_id": tenant_id,
                            "source_kind": source_kind,
                            "source_id": source_id,
                        },
                    )
                else:
                    source_appt.payment_status = "PAID"
                    source_appt.payment_amount_cop = input_dto.payment_amount_cop
                    source_appt.payment_currency = input_dto.payment_currency
                    source_appt.payment_updated_at = now_value
                    source_appt.updated_at = now_value
                    self._manual_appointment_repository.save(source_appt)
        elif source_kind == "SCHEDULING_REQUEST":
            source_req = self._scheduling_repository.get_request_by_id(tenant_id, source_id or "")
            if source_req is None:
                logger.warning(
                    "scheduling.approve_reminder_payment.source_not_found",
                    extra={
                        "tenant_id": tenant_id,
                        "source_kind": source_kind,
                        "source_id": source_id,
                    },
                )
            else:
                source_req.payment_status = "PAID"
                source_req.payment_amount_cop = input_dto.payment_amount_cop
                source_req.payment_currency = input_dto.payment_currency
                source_req.payment_updated_at = now_value
                source_req.updated_at = now_value
                self._scheduling_repository.save_request(source_req)

        # 2. Close the synthetic request.
        request.set_status("SESSION_CLOSED", now_value)

        # 3. Send freeform confirmation + archive subsession (if chat is open
        # within Meta's 24h window). The dispatcher itself handles the
        # archive_manual_close + delete_messages so we don't need to call
        # _archive_conversation_subsession_manual_close beforehand.
        if self._whatsapp_provider is not None and self._whatsapp_connection_repository is not None:
            payment_confirmation_dispatcher.confirm_payment_in_chat_if_open(
                tenant_id=tenant_id,
                whatsapp_user_id=request.whatsapp_user_id,
                patient_first_name=request.patient_first_name,
                source_appointment_id=request.source_appointment_id,
                now_value=now_value,
                conversation_repository=self._conversation_repository,
                whatsapp_connection_repository=self._whatsapp_connection_repository,
                whatsapp_provider=self._whatsapp_provider,
                id_generator=self._id_generator,
                clock=self._clock,
                scheduling_repository=self._scheduling_repository,
            )
        else:
            # No whatsapp wiring: still archive subsession so the synthetic
            # request leaves the active list.
            self._archive_conversation_subsession_manual_close(
                tenant_id=tenant_id,
                conversation_id=request.conversation_id,
                now_value=now_value,
            )

        logger.info(
            "scheduling.approve_reminder_payment.done",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.approve_reminder_payment.done",
                    message="reminder payment approved: source marked PAID, session closed",
                    data={
                        "tenant_id": tenant_id,
                        "synthetic_request_id": request.id,
                        "source_kind": source_kind,
                        "source_id": source_id,
                    },
                )
            },
        )

    def _reschedule_booked_slot_impl(
        self,
        tenant_id: str,
        request_id: str,
        input_dto: scheduling_dto.RescheduleBookedSlotInputDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        request = self._scheduling_repository.get_request_by_id(tenant_id, request_id)
        if request is None:
            raise service_exceptions.EntityNotFoundError("scheduling request not found")
        if request.calendar_event_id is None:
            raise service_exceptions.InvalidStateError(
                "booked scheduling request has no calendar event"
            )

        booked_slot = self._find_booked_slot(request)
        if booked_slot is None:
            raise service_exceptions.InvalidStateError(
                "booked scheduling request has no booked slot"
            )

        event_summary = self._resolve_booked_event_summary(
            request=request,
            requested_summary=input_dto.event_summary,
        )
        reschedule_attendee_emails: list[str] = []
        if self._patient_repository is not None:
            reschedule_patient = self._patient_repository.get_by_whatsapp_user(
                tenant_id, request.whatsapp_user_id
            )
            if reschedule_patient is not None:
                reschedule_attendee_emails = [reschedule_patient.email]
        updated_event = self._google_calendar_onboarding_service.update_event(
            tenant_id=tenant_id,
            event_id=request.calendar_event_id,
            start_at=input_dto.start_at,
            end_at=input_dto.end_at,
            timezone=input_dto.timezone,
            summary=event_summary,
            attendee_emails=reschedule_attendee_emails,
        )

        if self._reminder_service is not None:
            self._reminder_service.cancel_reminders_for_source(
                tenant_id=tenant_id,
                source_type="SCHEDULING_REQUEST",
                source_id=request.id,
            )
        booked_slot.start_at = updated_event.start_at
        booked_slot.end_at = updated_event.end_at
        booked_slot.timezone = input_dto.timezone
        now_value = self._clock.now()
        request.updated_at = now_value
        self._scheduling_repository.save_request(request)
        if self._reminder_service is not None:
            self._reminder_service.maybe_schedule_reminder(
                tenant_id=tenant_id,
                source_type="SCHEDULING_REQUEST",
                source_id=request.id,
                patient_whatsapp_user_id=request.whatsapp_user_id,
                patient_name=request.patient_first_name or "Paciente",
                appointment_start_at=input_dto.start_at,
                payment_status="PAID",
                appointment_modality=request.appointment_modality,
                meet_url=updated_event.meet_url,
            )
        logger.info(
            "scheduling.booked_slot_rescheduled",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.booked_slot_rescheduled",
                    message="booked scheduling request rescheduled",
                    data={
                        "tenant_id": tenant_id,
                        "request_id": request.id,
                        "calendar_event_id": request.calendar_event_id,
                    },
                )
            },
        )
        return self._to_summary_dto(request)

    def _cancel_booked_slot_impl(
        self,
        tenant_id: str,
        request_id: str,
        input_dto: scheduling_dto.CancelBookedSlotInputDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        request = self._scheduling_repository.get_request_by_id(tenant_id, request_id)
        if request is None:
            raise service_exceptions.EntityNotFoundError("scheduling request not found")

        calendar_event_id = request.calendar_event_id
        if calendar_event_id is not None:
            try:
                self._google_calendar_onboarding_service.delete_event(
                    tenant_id=tenant_id,
                    event_id=calendar_event_id,
                )
            except service_exceptions.ExternalProviderError as error:
                if not self._is_google_not_found_error(str(error)):
                    raise

        now_value = self._clock.now()
        for slot in request.slots:
            if slot.status in ("BOOKED", "SELECTED"):
                slot.status = "REJECTED"
        request.calendar_event_id = None
        request.selected_slot_id = None
        normalized_reason = self._normalize_patient_text(input_dto.reason)
        if normalized_reason is not None:
            request.professional_note = normalized_reason
        if self._reminder_service is not None:
            self._reminder_service.cancel_reminders_for_source(
                tenant_id=tenant_id,
                source_type="SCHEDULING_REQUEST",
                source_id=request.id,
            )
        request.updated_at = now_value
        self._scheduling_repository.save_request(request)
        logger.info(
            "scheduling.booked_slot_cancelled",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.booked_slot_cancelled",
                    message="booked scheduling request cancelled from agenda",
                    data={
                        "tenant_id": tenant_id,
                        "request_id": request.id,
                    },
                )
            },
        )
        return self._to_summary_dto(request)

    def _update_booked_payment_impl(
        self,
        tenant_id: str,
        request_id: str,
        input_dto: scheduling_dto.UpdateBookedSlotPaymentInputDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        request = self._scheduling_repository.get_request_by_id(tenant_id, request_id)
        if request is None:
            raise service_exceptions.EntityNotFoundError("scheduling request not found")
        now_value = self._clock.now()
        request.payment_amount_cop = input_dto.payment_amount_cop
        request.payment_currency = input_dto.payment_currency
        request.payment_method = input_dto.payment_method
        request.payment_status = input_dto.payment_status
        request.payment_updated_at = now_value
        request.updated_at = now_value
        self._scheduling_repository.save_request(request)
        logger.info(
            "scheduling.booked_payment_updated",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.booked_payment_updated",
                    message="booked scheduling request payment updated",
                    data={
                        "tenant_id": tenant_id,
                        "request_id": request.id,
                        "payment_status": request.payment_status,
                        "payment_method": request.payment_method,
                        "payment_amount_cop": request.payment_amount_cop,
                        "payment_currency": request.payment_currency,
                    },
                )
            },
        )
        return self._to_summary_dto(request)

    def _change_booked_modality_impl(
        self,
        tenant_id: str,
        request_id: str,
        input_dto: scheduling_dto.ChangeBookedModalityInputDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        request = self._scheduling_repository.get_request_by_id(tenant_id, request_id)
        if request is None:
            raise service_exceptions.EntityNotFoundError("scheduling request not found")
        if request.status != "BOOKED":
            raise service_exceptions.InvalidStateError("only BOOKED requests can change modality")

        booked_slot = self._find_booked_slot(request)
        if booked_slot is None:
            raise service_exceptions.InvalidStateError("no booked slot found in request")

        now_value = self._clock.now()
        if booked_slot.start_at <= now_value:
            raise service_exceptions.InvalidStateError(
                "cannot change modality for past appointments"
            )

        # Idempotency: same modality → noop
        if request.appointment_modality == input_dto.new_modality:
            return self._to_summary_dto(request)

        is_eval = self._is_eval_tenant(tenant_id)
        new_modality = input_dto.new_modality
        with_meet = new_modality == "VIRTUAL"

        new_meet_url: str | None = None
        if not is_eval and request.calendar_event_id is not None:
            attendee_emails: list[str] = []
            if self._patient_repository is not None:
                patient = self._patient_repository.get_by_whatsapp_user(
                    tenant_id, request.whatsapp_user_id
                )
                if patient is not None:
                    attendee_emails = [patient.email]

            event_description_result = self._event_description_builder.build(
                tenant_id=tenant_id,
                modality=new_modality,
                payment_status=request.payment_status,
            )
            event_summary = self._resolve_booked_event_summary(
                request=request,
                requested_summary=None,
            )
            updated_event = self._google_calendar_onboarding_service.update_event(
                tenant_id=tenant_id,
                event_id=request.calendar_event_id,
                start_at=booked_slot.start_at,
                end_at=booked_slot.end_at,
                timezone=booked_slot.timezone,
                summary=event_summary,
                attendee_emails=attendee_emails,
                description=event_description_result.description,
                location=event_description_result.location,
                with_meet=with_meet,
            )
            new_meet_url = updated_event.meet_url

        request.appointment_modality = new_modality
        request.updated_at = now_value
        self._scheduling_repository.save_request(request)

        if self._reminder_service is not None and not is_eval:
            self._reminder_service.cancel_reminders_for_source(
                tenant_id=tenant_id,
                source_type="SCHEDULING_REQUEST",
                source_id=request.id,
            )
            reminder_payment_status: typing.Literal["PAID", "PENDING"] = (
                "PAID" if request.payment_status == "PAID" else "PENDING"
            )
            self._reminder_service.maybe_schedule_reminder(
                tenant_id=tenant_id,
                source_type="SCHEDULING_REQUEST",
                source_id=request.id,
                patient_whatsapp_user_id=request.whatsapp_user_id,
                patient_name=request.patient_first_name or "Paciente",
                appointment_start_at=booked_slot.start_at,
                payment_status=reminder_payment_status,
                appointment_modality=new_modality,
                meet_url=new_meet_url,
            )

        logger.info(
            "scheduling.modality_changed",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.modality_changed",
                    message="booked appointment modality changed",
                    data={
                        "tenant_id": tenant_id,
                        "request_id": request.id,
                        "new_modality": new_modality,
                        "calendar_event_id": request.calendar_event_id,
                    },
                )
            },
        )
        return self._to_summary_dto(request)

    def _handoff_to_human_impl(
        self,
        tenant_id: str,
        conversation_id: str,
        input_dto: scheduling_dto.HandoffToHumanInputDTO,
    ) -> dict[str, str]:
        conversation = self._conversation_repository.get_conversation_by_id(
            tenant_id, conversation_id
        )
        if conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")

        now_value = self._clock.now()
        conversation.set_control_mode("HUMAN", now_value)
        self._conversation_repository.save_conversation(conversation)

        request_list = self._scheduling_repository.list_requests_by_conversation(
            tenant_id,
            conversation_id,
        )
        for request in request_list:
            if request.status in (
                "BOOKED",
                "HUMAN_HANDOFF",
                "CONSULTATION_REJECTED",
                "CANCELLED",
            ):
                continue
            request.professional_note = input_dto.summary_for_professional
            self._scheduling_repository.save_request(request)

        self._sync_tags_after_status_change(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status="HUMAN_HANDOFF",
        )
        logger.info(
            "scheduling.handoff_to_human",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.handoff_to_human",
                    message="conversation switched to human due scheduling handoff",
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation_id,
                        "reason": input_dto.reason,
                    },
                )
            },
        )
        return {
            "status": "HUMAN_HANDOFF",
            "control_mode": "HUMAN",
        }

    def _close_session_impl(
        self,
        tenant_id: str,
        conversation_id: str,
    ) -> dict[str, str]:
        request_list = self._scheduling_repository.list_requests_by_conversation(
            tenant_id,
            conversation_id,
        )
        terminal_statuses = {
            "SESSION_CLOSED",
            "CANCELLED",
            "CONSULTATION_REJECTED",
            "HUMAN_HANDOFF",
        }
        booked_request = None
        active_requests: list[scheduling_request_entity.SchedulingRequest] = []
        for request in request_list:
            if request.status in terminal_statuses:
                continue
            active_requests.append(request)
            if request.status == "BOOKED":
                booked_request = request

        now_value = self._clock.now()

        if booked_request is not None:
            self._archive_conversation_subsession_after_booking(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                scheduling_request_id=booked_request.id,
                calendar_event_id=booked_request.calendar_event_id or "",
                now_value=now_value,
            )
        else:
            self._archive_conversation_subsession_manual_close(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                now_value=now_value,
            )

        for request in active_requests:
            request.set_status("SESSION_CLOSED", now_value)
            self._scheduling_repository.save_request(request)

        self._sync_tags_after_status_change(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status="SESSION_CLOSED",
        )

        logger.info(
            "scheduling.session_closed",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.session_closed",
                    message="conversation session closed and archived",
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation_id,
                        "closed_request_ids": [request.id for request in active_requests],
                    },
                )
            },
        )
        return {
            "status": "SESSION_CLOSED",
        }

    def close_attendance_confirmation(
        self,
        tenant_id: str,
        conversation_id: str,
    ) -> dict[str, str]:
        """Close the session immediately when the patient confirms attendance.

        Finds the active AWAITING_ATTENDANCE_CONFIRMATION request for the
        conversation, archives the subsession via manual-close, and transitions
        the request to SESSION_CLOSED.  Returns a no-op result if no such
        request exists (idempotent).
        """
        request_list = self._scheduling_repository.list_requests_by_conversation(
            tenant_id,
            conversation_id,
        )
        attendance_request = self._find_latest_request_by_statuses(
            requests=request_list,
            statuses=("AWAITING_ATTENDANCE_CONFIRMATION",),
        )
        if attendance_request is None:
            logger.info(
                "scheduling.close_attendance_skipped",
                extra={
                    "tenant_id": tenant_id,
                    "conversation_id": conversation_id,
                },
            )
            return {"status": "skipped", "action": "no_active_attendance_request"}

        now_value = self._clock.now()
        self._archive_conversation_subsession_manual_close(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            now_value=now_value,
        )
        attendance_request.set_status("SESSION_CLOSED", now_value)
        self._scheduling_repository.save_request(attendance_request)
        self._sync_tags_after_status_change(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status="SESSION_CLOSED",
        )
        logger.info(
            "scheduling.attendance_confirmed_session_closed",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.attendance_confirmed_session_closed",
                    message="patient confirmed attendance; session closed immediately",
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation_id,
                        "request_id": attendance_request.id,
                    },
                )
            },
        )
        return {"status": "SESSION_CLOSED", "action": "closed"}

    def auto_close_booked_request(
        self,
        tenant_id: str,
        scheduling_request_id: str,
    ) -> dict[str, str]:
        request = self._scheduling_repository.get_request_by_id(tenant_id, scheduling_request_id)
        if request is None:
            raise service_exceptions.EntityNotFoundError("scheduling request not found")

        if request.status not in ("BOOKED", "AWAITING_ATTENDANCE_CONFIRMATION"):
            logger.info(
                "scheduling.auto_close_skipped",
                extra={
                    "request_id": scheduling_request_id,
                    "current_status": request.status,
                },
            )
            return {"status": request.status, "action": "skipped"}

        now_value = self._clock.now()
        if request.status == "BOOKED":
            self._archive_conversation_subsession_after_booking(
                tenant_id=tenant_id,
                conversation_id=request.conversation_id,
                scheduling_request_id=request.id,
                calendar_event_id=request.calendar_event_id or "",
                now_value=now_value,
            )
        else:
            # AWAITING_ATTENDANCE_CONFIRMATION: reminder-reply request with no calendar event.
            self._archive_conversation_subsession_manual_close(
                tenant_id=tenant_id,
                conversation_id=request.conversation_id,
                now_value=now_value,
            )
        request.set_status("SESSION_CLOSED", now_value)
        self._scheduling_repository.save_request(request)
        self._sync_tags_after_status_change(
            tenant_id=tenant_id,
            conversation_id=request.conversation_id,
            new_status=request.status,
        )

        logger.info(
            "scheduling.auto_close_completed",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.auto_close_completed",
                    message="session auto-closed after timeout",
                    data={
                        "tenant_id": tenant_id,
                        "request_id": scheduling_request_id,
                    },
                )
            },
        )
        return {"status": "SESSION_CLOSED", "action": "closed"}

    def _schedule_auto_close_task(self, tenant_id: str, scheduling_request_id: str) -> None:
        try:
            task_name = self._task_scheduler.schedule_auto_close(
                tenant_id=tenant_id,
                scheduling_request_id=scheduling_request_id,
                delay_seconds=self._auto_close_delay_seconds,
            )
            logger.info(
                "scheduling.auto_close_task_enqueued",
                extra={
                    "task_name": task_name,
                    "scheduling_request_id": scheduling_request_id,
                    "delay_seconds": self._auto_close_delay_seconds,
                },
            )
        except service_exceptions.ExternalProviderError:
            logger.warning(
                "scheduling.auto_close_task_failed",
                extra={"scheduling_request_id": scheduling_request_id},
                exc_info=True,
            )

    def _escalate_patient_slot_rejection_impl(
        self,
        tenant_id: str,
        request_id: str,
        patient_preference_note: str,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        request = self._scheduling_repository.get_request_by_id(tenant_id, request_id)
        if request is None:
            raise service_exceptions.EntityNotFoundError("scheduling request not found")
        if request.status != "AWAITING_PATIENT_CHOICE":
            raise service_exceptions.InvalidStateError(
                "scheduling request is not waiting for patient choice"
            )

        now_value = self._clock.now()
        normalized_note = self._normalize_patient_text(patient_preference_note)
        request.patient_preference_note = normalized_note
        request.selected_slot_id = None
        request.set_status("AWAITING_CONSULTATION_REVIEW", now_value)
        self._scheduling_repository.save_request(request)
        self._sync_tags_after_status_change(
            tenant_id=tenant_id,
            conversation_id=request.conversation_id,
            new_status=request.status,
        )

        logger.info(
            "scheduling.patient_slot_rejection_escalated",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.patient_slot_rejection_escalated",
                    message="patient rejected proposed slots; escalated back for professional review",
                    data={
                        "tenant_id": tenant_id,
                        "request_id": request.id,
                        "patient_preference_note": normalized_note,
                    },
                )
            },
        )
        return self._to_summary_dto(request)

    def _submit_reschedule_for_review_impl(
        self,
        tenant_id: str,
        conversation_id: str,
        whatsapp_user_id: str,
        input_dto: scheduling_dto.SubmitRescheduleForReviewToolInputDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        # 1. Load and validate the original SR.
        original_request = self._scheduling_repository.get_request_by_id(
            tenant_id, input_dto.original_request_id
        )
        if original_request is None:
            raise service_exceptions.EntityNotFoundError("scheduling request not found")
        if original_request.tenant_id != tenant_id:
            raise service_exceptions.AuthorizationError(
                "scheduling request does not belong to tenant"
            )

        # 2. Resolve the data source for the RESCHEDULE child.
        # Two valid entry points:
        #   (a) BOOKED SR — the patient comes back later (NO_ACTIVE_REQUEST flow)
        #       and the bot reschedules the previous booking directly.
        #   (b) AWAITING_ATTENDANCE_CONFIRMATION + RETRY placeholder — the
        #       reminder pre-positioned a synthetic SR; the real appointment
        #       lives in source_appointment_id (either a SR or a manual_appt).
        source_data = self._resolve_reschedule_source_data(
            tenant_id=tenant_id,
            original_request=original_request,
        )

        # 3. Verify no active reschedule SR already exists for the resolved
        #    source (not the input) — the input may be a placeholder while
        #    the source is the actual booking.
        existing_requests = self._scheduling_repository.list_requests_by_conversation(
            tenant_id,
            conversation_id,
        )
        for req in existing_requests:
            if (
                req.request_kind == "RESCHEDULE"
                and req.source_appointment_id == source_data.source_appointment_id
                and req.status
                not in (
                    "SESSION_CLOSED",
                    "CANCELLED",
                    "CONSULTATION_REJECTED",
                    "HUMAN_HANDOFF",
                )
            ):
                raise service_exceptions.InvalidStateError(
                    "ya hay un reagendamiento en curso para esta cita"
                )

        # 4. Create the child RESCHEDULE SR inheriting data from the source.
        now_value = self._clock.now()
        open_requests = self._scheduling_repository.list_requests_by_conversation(
            tenant_id,
            conversation_id,
        )
        new_request = scheduling_request_entity.SchedulingRequest(
            id=self._id_generator.new_id(),
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            whatsapp_user_id=source_data.whatsapp_user_id,
            request_kind="RESCHEDULE",
            status="AWAITING_CONSULTATION_REVIEW",
            round_number=len(open_requests) + 1,
            patient_preference_note=input_dto.reason,
            rejection_summary=None,
            professional_note=None,
            consultation_reason=source_data.consultation_reason,
            appointment_modality=source_data.appointment_modality,
            patient_location=source_data.patient_location,
            patient_first_name=source_data.patient_first_name,
            patient_last_name=source_data.patient_last_name,
            patient_age=source_data.patient_age,
            slots=[],
            slot_options_map={},
            selected_slot_id=None,
            calendar_event_id=None,
            source_appointment_id=source_data.source_appointment_id,
            source_appointment_kind=source_data.source_appointment_kind,
            payment_status="PAID",
            created_at=now_value,
            updated_at=now_value,
        )

        # 4. Persist.
        self._scheduling_repository.save_request(new_request)

        # 5. Sync tags.
        self._sync_tags_after_status_change(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status=new_request.status,
        )

        logger.info(
            "scheduling.reschedule_for_review_submitted",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.reschedule_for_review_submitted",
                    message="reschedule request created for professional review",
                    data={
                        "tenant_id": tenant_id,
                        "conversation_id": conversation_id,
                        "new_request_id": new_request.id,
                        "original_request_id": input_dto.original_request_id,
                    },
                )
            },
        )
        return self._to_summary_dto(new_request)

    def _resolve_reschedule_source_data(
        self,
        tenant_id: str,
        original_request: scheduling_request_entity.SchedulingRequest,
    ) -> _RescheduleSourceData:
        if original_request.status == "BOOKED":
            return _RescheduleSourceData(
                whatsapp_user_id=original_request.whatsapp_user_id,
                consultation_reason=original_request.consultation_reason,
                appointment_modality=original_request.appointment_modality,
                patient_location=original_request.patient_location,
                patient_first_name=original_request.patient_first_name,
                patient_last_name=original_request.patient_last_name,
                patient_age=original_request.patient_age,
                source_appointment_id=original_request.id,
                source_appointment_kind="SCHEDULING_REQUEST",
            )

        # Reminder pre-position placeholder: real booking lives in source_*.
        is_placeholder = (
            original_request.status == "AWAITING_ATTENDANCE_CONFIRMATION"
            and original_request.request_kind == "RETRY"
            and original_request.source_appointment_id is not None
        )
        if not is_placeholder:
            raise service_exceptions.InvalidStateError(
                "solo se puede reagendar una cita en estado BOOKED"
            )

        source_id = original_request.source_appointment_id
        source_kind = original_request.source_appointment_kind
        assert source_id is not None  # checked by is_placeholder

        if source_kind == "SCHEDULING_REQUEST":
            real_source = self._scheduling_repository.get_request_by_id(tenant_id, source_id)
            if real_source is None:
                raise service_exceptions.EntityNotFoundError("source scheduling request not found")
            return _RescheduleSourceData(
                whatsapp_user_id=real_source.whatsapp_user_id,
                consultation_reason=real_source.consultation_reason,
                appointment_modality=real_source.appointment_modality,
                patient_location=real_source.patient_location,
                patient_first_name=real_source.patient_first_name,
                patient_last_name=real_source.patient_last_name,
                patient_age=real_source.patient_age,
                source_appointment_id=source_id,
                source_appointment_kind="SCHEDULING_REQUEST",
            )

        if source_kind == "MANUAL_APPOINTMENT":
            if self._manual_appointment_repository is None:
                raise service_exceptions.InvalidStateError(
                    "manual appointment repository not configured"
                )
            manual = self._manual_appointment_repository.get_by_id(tenant_id, source_id)
            if manual is None:
                raise service_exceptions.EntityNotFoundError("source manual appointment not found")
            patient = (
                self._patient_repository.get_by_whatsapp_user(
                    tenant_id, manual.patient_whatsapp_user_id
                )
                if self._patient_repository is not None
                else None
            )
            inferred_modality: typing.Literal["PRESENCIAL", "VIRTUAL"] = (
                "VIRTUAL" if manual.is_virtual else "PRESENCIAL"
            )
            return _RescheduleSourceData(
                whatsapp_user_id=manual.patient_whatsapp_user_id,
                consultation_reason=manual.summary,
                appointment_modality=inferred_modality,
                patient_location=patient.location if patient is not None else None,
                patient_first_name=patient.first_name if patient is not None else None,
                patient_last_name=patient.last_name if patient is not None else None,
                patient_age=patient.age if patient is not None else None,
                source_appointment_id=source_id,
                source_appointment_kind="MANUAL_APPOINTMENT",
            )

        raise service_exceptions.InvalidStateError("unknown source appointment kind for reschedule")

    def _confirm_rescheduled_slot_impl(
        self,
        tenant_id: str,
        conversation_id: str,
        input_dto: scheduling_dto.ConfirmRescheduledSlotInputDTO,
    ) -> scheduling_dto.SchedulingRequestSummaryDTO:
        # 1. Load and validate the RESCHEDULE SR.
        reschedule_request = self._scheduling_repository.get_request_by_id(
            tenant_id, input_dto.request_id
        )
        if reschedule_request is None:
            raise service_exceptions.EntityNotFoundError("scheduling request not found")
        if reschedule_request.request_kind != "RESCHEDULE":
            raise service_exceptions.InvalidStateError(
                "scheduling request is not a reschedule request"
            )
        if reschedule_request.status != "AWAITING_PATIENT_CHOICE":
            raise service_exceptions.InvalidStateError(
                "scheduling request is not waiting for patient choice"
            )
        if reschedule_request.selected_slot_id is None:
            raise service_exceptions.InvalidStateError(
                "no slot selected yet; call select_proposed_slot first"
            )

        # 2. Find the selected slot in the RESCHEDULE SR.
        selected_slot: scheduling_slot_entity.SchedulingSlot | None = None
        for slot in reschedule_request.slots:
            if slot.id == reschedule_request.selected_slot_id:
                selected_slot = slot
                break
        if selected_slot is None:
            raise service_exceptions.InvalidStateError(
                "selected slot not found in reschedule request"
            )

        # 3. Get the source appointment id + kind.
        source_id = reschedule_request.source_appointment_id
        source_kind = reschedule_request.source_appointment_kind
        if source_id is None or source_kind is None:
            raise service_exceptions.InvalidStateError(
                "reschedule request has no source appointment reference"
            )

        # 4. Resolve the source's calendar_event_id (we keep the same Google
        #    Calendar event; only its time changes).
        calendar_event_id: str | None = None
        source_request: scheduling_request_entity.SchedulingRequest | None = None
        manual_appt = None
        if source_kind == "SCHEDULING_REQUEST":
            source_request = self._scheduling_repository.get_request_by_id(tenant_id, source_id)
            if source_request is None:
                raise service_exceptions.EntityNotFoundError("source scheduling request not found")
            calendar_event_id = source_request.calendar_event_id
        elif source_kind == "MANUAL_APPOINTMENT":
            if self._manual_appointment_repository is None:
                raise service_exceptions.InvalidStateError(
                    "manual appointment repository not configured"
                )
            manual_appt = self._manual_appointment_repository.get_by_id(tenant_id, source_id)
            if manual_appt is None:
                raise service_exceptions.EntityNotFoundError("source manual appointment not found")
            calendar_event_id = manual_appt.calendar_event_id
        if calendar_event_id is None:
            raise service_exceptions.InvalidStateError(
                "source appointment has no calendar event to reschedule"
            )

        # 5. Update the Google Calendar event in place.
        attendee_emails: list[str] = []
        if self._patient_repository is not None:
            patient = self._patient_repository.get_by_whatsapp_user(
                tenant_id, reschedule_request.whatsapp_user_id
            )
            if patient is not None:
                attendee_emails = [patient.email]
        event_summary = self._resolve_booked_event_summary(
            request=reschedule_request,
            requested_summary=None,
        )
        self._google_calendar_onboarding_service.update_event(
            tenant_id=tenant_id,
            event_id=calendar_event_id,
            start_at=selected_slot.start_at,
            end_at=selected_slot.end_at,
            timezone=selected_slot.timezone,
            summary=event_summary,
            attendee_emails=attendee_emails,
        )

        now_value = self._clock.now()

        # 6. Cancel reminders bound to the old source — the new reminder will
        #    point at the RESCHEDULE child (now the active booking).
        if self._reminder_service is not None:
            self._reminder_service.cancel_reminders_for_source(
                tenant_id=tenant_id,
                source_type=source_kind,
                source_id=source_id,
            )

        # 7. Detach the calendar event from the old source so the agenda does
        #    not render it as a duplicate appointment.
        if source_request is not None:
            source_request.calendar_event_id = None
            if source_request.status == "BOOKED":
                source_request.set_status("SESSION_CLOSED", now_value)
            else:
                source_request.updated_at = now_value
            self._scheduling_repository.save_request(source_request)
        if manual_appt is not None and self._manual_appointment_repository is not None:
            manual_appt.status = "CANCELLED"
            manual_appt.cancelled_at = now_value
            manual_appt.updated_at = now_value
            self._manual_appointment_repository.save(manual_appt)

        # 8. Promote the RESCHEDULE child to BOOKED. It now owns the calendar
        #    event and is the active appointment for this conversation, so the
        #    resolver will treat the conversation as POST_BOOKING_FOLLOWUP.
        for slot in reschedule_request.slots:
            if slot.id == reschedule_request.selected_slot_id:
                slot.status = "BOOKED"
                slot.start_at = selected_slot.start_at
                slot.end_at = selected_slot.end_at
                break
        reschedule_request.calendar_event_id = calendar_event_id
        reschedule_request.set_status("BOOKED", now_value)
        self._scheduling_repository.save_request(reschedule_request)

        # 9. Schedule the next reminder pointing at the new BOOKED SR.
        if self._reminder_service is not None:
            self._reminder_service.maybe_schedule_reminder(
                tenant_id=tenant_id,
                source_type="SCHEDULING_REQUEST",
                source_id=reschedule_request.id,
                patient_whatsapp_user_id=reschedule_request.whatsapp_user_id,
                patient_name=reschedule_request.patient_first_name or "Paciente",
                appointment_start_at=selected_slot.start_at,
                payment_status="PAID",
                appointment_modality=reschedule_request.appointment_modality,
            )

        # 10. Close any other open SRs in this conversation (notably the
        #     reminder pre-position placeholder, which is still in
        #     AWAITING_ATTENDANCE_CONFIRMATION otherwise).
        open_statuses = {
            "AWAITING_CONSULTATION_REVIEW",
            "AWAITING_CONSULTATION_DETAILS",
            "AWAITING_PATIENT_CHOICE",
            "AWAITING_PAYMENT_CONFIRMATION",
            "AWAITING_ATTENDANCE_CONFIRMATION",
        }
        all_requests = self._scheduling_repository.list_requests_by_conversation(
            tenant_id, conversation_id
        )
        for other_request in all_requests:
            if other_request.id == reschedule_request.id:
                continue
            if other_request.status in open_statuses:
                other_request.set_status("SESSION_CLOSED", now_value)
                self._scheduling_repository.save_request(other_request)

        # 11. Sync tags to BOOKED.
        self._sync_tags_after_status_change(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            new_status="BOOKED",
        )

        logger.info(
            "scheduling.rescheduled_slot_confirmed",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="scheduling.rescheduled_slot_confirmed",
                    message="rescheduled slot confirmed; child promoted to BOOKED",
                    data={
                        "tenant_id": tenant_id,
                        "reschedule_request_id": reschedule_request.id,
                        "source_appointment_id": source_id,
                        "source_appointment_kind": source_kind,
                    },
                )
            },
        )
        return self._to_summary_dto(reschedule_request)

    def _resolve_request_for_consultation_submission(
        self,
        tenant_id: str,
        conversation_id: str,
        existing_requests: list[scheduling_request_entity.SchedulingRequest],
        request_id: str | None,
    ) -> scheduling_request_entity.SchedulingRequest | None:
        if request_id is not None:
            request = self._scheduling_repository.get_request_by_id(tenant_id, request_id)
            if request is None:
                raise service_exceptions.EntityNotFoundError("scheduling request not found")
            if request.conversation_id != conversation_id:
                raise service_exceptions.AuthorizationError(
                    "scheduling request does not belong to conversation"
                )
            return request

        return self._find_latest_request_by_statuses(
            requests=existing_requests,
            statuses=(
                "AWAITING_CONSULTATION_DETAILS",
                "AWAITING_CONSULTATION_REVIEW",
            ),
        )

    def _find_latest_request_by_statuses(
        self,
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

    def _find_selectable_slot(
        self,
        request: scheduling_request_entity.SchedulingRequest,
        slot_id: str,
    ) -> scheduling_slot_entity.SchedulingSlot | None:
        for slot in request.slots:
            if slot.id == slot_id and slot.status in ("PROPOSED", "SELECTED"):
                return slot
        return None

    def _find_booked_slot(
        self,
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

    def _list_remaining_slot_ids(
        self,
        request: scheduling_request_entity.SchedulingRequest,
    ) -> list[str]:
        remaining_slot_ids: list[str] = []
        for slot in request.slots:
            if slot.status == "PROPOSED":
                remaining_slot_ids.append(slot.id)
        return remaining_slot_ids

    def _mark_selected_slot_conflict(
        self,
        request: scheduling_request_entity.SchedulingRequest,
        selected_slot: scheduling_slot_entity.SchedulingSlot,
        now_value: datetime.datetime,
    ) -> scheduling_dto.ConfirmSelectedSlotResponseDTO:
        for slot in request.slots:
            if slot.id == selected_slot.id:
                slot.status = "UNAVAILABLE"
                break

        if request.selected_slot_id == selected_slot.id:
            request.selected_slot_id = None

        remaining_slot_ids = self._list_remaining_slot_ids(request)
        if remaining_slot_ids:
            request.set_status("AWAITING_PATIENT_CHOICE", now_value)
        else:
            request.set_status("AWAITING_CONSULTATION_REVIEW", now_value)
        self._scheduling_repository.save_request(request)
        self._sync_tags_after_status_change(
            tenant_id=request.tenant_id,
            conversation_id=request.conversation_id,
            new_status=request.status,
        )
        return scheduling_dto.ConfirmSelectedSlotResponseDTO(
            status="SLOT_CONFLICT",
            request_id=request.id,
            selected_slot_id=None,
            calendar_event_id=None,
            remaining_slot_ids=remaining_slot_ids,
        )

    def _is_google_conflict_error(self, error_message: str) -> bool:
        normalized_message = error_message.lower()
        return "status=409" in normalized_message or "conflict" in normalized_message

    def _is_google_not_found_error(self, error_message: str) -> bool:
        normalized_message = error_message.lower()
        return "status=404" in normalized_message or "not found" in normalized_message

    def _resolve_booked_event_summary(
        self,
        request: scheduling_request_entity.SchedulingRequest,
        requested_summary: str | None,
    ) -> str:
        normalized_summary = self._normalize_patient_text(requested_summary)
        if normalized_summary is not None:
            return normalized_summary
        first_name = self._normalize_patient_text(request.patient_first_name)
        last_name = self._normalize_patient_text(request.patient_last_name)
        if first_name is not None and last_name is not None:
            return f"Cita - {first_name} {last_name}"
        if first_name is not None:
            return f"Cita - {first_name}"
        return f"Cita - {request.whatsapp_user_id}"

    def _coalesce_patient_text(
        self,
        primary: str | None,
        fallback: str | None,
    ) -> str | None:
        normalized_primary = self._normalize_patient_text(primary)
        if normalized_primary is not None:
            return normalized_primary
        return self._normalize_patient_text(fallback)

    def _coalesce_patient_age(
        self,
        primary: int | str | None,
        fallback: int | None,
    ) -> int | None:
        normalized_primary = self._normalize_patient_age(primary)
        if normalized_primary is not None:
            return normalized_primary
        return fallback

    def _normalize_patient_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        if normalized_value == "":
            return None
        return normalized_value

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

    def _resolve_location(
        self,
        appointment_modality: str,
        patient_location: str | None,
        fallback_patient_location: str | None,
        tenant_id: str | None = None,
    ) -> str:
        if appointment_modality == "PRESENCIAL":
            # Read main_city from AgentProfile; fall back to generic label when
            # not configured so no hardcoded city leaks into production messages.
            if tenant_id is not None and self._agent_profile_repository is not None:
                profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
                if (
                    profile is not None
                    and profile.identity is not None
                    and profile.identity.main_city
                ):
                    return profile.identity.main_city
            return "Presencial"

        normalized_location = self._normalize_patient_text(patient_location)
        if normalized_location is None:
            normalized_location = self._normalize_patient_text(fallback_patient_location)
        if normalized_location is None:
            raise service_exceptions.InvalidStateError(
                "missing required patient data: patient_location; ask only for the patient's location now"
            )
        return normalized_location

    def _to_summary_dto(
        self,
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
