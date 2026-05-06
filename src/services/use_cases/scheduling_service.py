"""Facade for the scheduling domain.

This module is the single public API consumed by:
  - entrypoints (HTTP handlers and routers)
  - agentic tool handlers and guards
  - scheduling_inbox_service
  - container.py (wiring)

Implementation is split across four sub-modules under
``src/services/use_cases/scheduling/``:

  helpers.py          — pure utilities (normalizers, finders, DTO builder)
  slot_proposals.py   — submit reason, review decision, cancel, select slot,
                        escalate rejection
  booking.py          — book slot + calendar event, archive subsession,
                        reschedule, cancel booked, update payment, modality
  payment_approval.py — approve_payment (normal + reminder-reply branch)
  transitions.py      — handoff_to_human, close_session, attendance confirm,
                        auto-close

``SchedulingService`` owns the ``_run_transition_with_graph`` wrapper (and the
``SchedulingTransitionRuntimeAdapter``) because those depend on
``AgentWorkflowPort``, which is not injected into the sub-modules.

The public API surface (method names, signatures, return types) is unchanged so
all existing callers (tests, handlers, guards) continue to work without
modification.
"""

import typing

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
import src.services.use_cases.event_description_builder as event_description_builder_mod
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import src.services.use_cases.reminder_service as reminder_service_module
import src.services.use_cases.scheduling.booking as scheduling_booking
import src.services.use_cases.scheduling.helpers as scheduling_helpers
import src.services.use_cases.scheduling.payment_approval as scheduling_payment_approval
import src.services.use_cases.scheduling.slot_proposals as scheduling_slot_proposals
import src.services.use_cases.scheduling.transitions as scheduling_transitions
import src.services.use_cases.tag_service as tag_service_module

logger = app_logs.get_logger(__name__)


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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Read-only queries
    # ------------------------------------------------------------------

    def list_requests_by_tenant(
        self,
        tenant_id: str,
        status: str | None = None,
    ) -> scheduling_dto.SchedulingRequestListResponseDTO:
        requests = self._scheduling_repository.list_requests_by_tenant(tenant_id, status)
        sorted_requests = sorted(requests, key=lambda item: item.updated_at, reverse=True)
        items = [scheduling_helpers.to_summary_dto(item) for item in sorted_requests]
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
        items = [scheduling_helpers.to_summary_dto(item) for item in sorted_requests]
        return scheduling_dto.SchedulingRequestListResponseDTO(items=items)

    # ------------------------------------------------------------------
    # Slot proposal transitions (public facade)
    # ------------------------------------------------------------------

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
            apply_transition=lambda _: scheduling_slot_proposals.submit_consultation_reason_for_review_impl(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                whatsapp_user_id=whatsapp_user_id,
                input_dto=input_dto,
                scheduling_repository=self._scheduling_repository,
                conversation_repository=self._conversation_repository,
                id_generator=self._id_generator,
                clock=self._clock,
                tag_service=self._tag_service,
                agent_profile_repository=self._agent_profile_repository,
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
            apply_transition=lambda _: scheduling_slot_proposals.resolve_consultation_review_impl(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                request_id=request_id,
                input_dto=input_dto,
                scheduling_repository=self._scheduling_repository,
                clock=self._clock,
                tag_service=self._tag_service,
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
            apply_transition=lambda _: scheduling_slot_proposals.cancel_active_request_impl(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                input_dto=input_dto,
                scheduling_repository=self._scheduling_repository,
                conversation_repository=self._conversation_repository,
                clock=self._clock,
                tag_service=self._tag_service,
            ),
        )
        return typing.cast(scheduling_dto.SchedulingRequestSummaryDTO, transition_result)

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
            apply_transition=lambda _: scheduling_slot_proposals.select_slot_for_confirmation_impl(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                request_id=request_id,
                slot_id=slot_id,
                scheduling_repository=self._scheduling_repository,
                clock=self._clock,
                tag_service=self._tag_service,
                agent_profile_repository=self._agent_profile_repository,
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
            apply_transition=lambda _: scheduling_slot_proposals.escalate_patient_slot_rejection_impl(
                tenant_id=tenant_id,
                request_id=request_id,
                patient_preference_note=patient_preference_note,
                scheduling_repository=self._scheduling_repository,
                clock=self._clock,
                tag_service=self._tag_service,
            ),
        )
        return typing.cast(scheduling_dto.SchedulingRequestSummaryDTO, transition_result)

    # ------------------------------------------------------------------
    # Booking transitions (public facade)
    # ------------------------------------------------------------------

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
            apply_transition=lambda _: scheduling_booking.confirm_selected_slot_and_create_event_impl(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                input_dto=input_dto,
                scheduling_repository=self._scheduling_repository,
                gcal_onboarding_service=self._google_calendar_onboarding_service,
                event_description_builder=self._event_description_builder,
                task_scheduler=self._task_scheduler,
                auto_close_delay_seconds=self._auto_close_delay_seconds,
                clock=self._clock,
                tag_service=self._tag_service,
                reminder_service=self._reminder_service,
                is_eval_tenant=self._is_eval_tenant(tenant_id),
            ),
        )
        return typing.cast(scheduling_dto.ConfirmSelectedSlotResponseDTO, transition_result)

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
            apply_transition=lambda _: scheduling_booking.reschedule_booked_slot_impl(
                tenant_id=tenant_id,
                request_id=request_id,
                input_dto=input_dto,
                scheduling_repository=self._scheduling_repository,
                gcal_onboarding_service=self._google_calendar_onboarding_service,
                clock=self._clock,
                patient_repository=self._patient_repository,
                reminder_service=self._reminder_service,
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
            apply_transition=lambda _: scheduling_booking.cancel_booked_slot_impl(
                tenant_id=tenant_id,
                request_id=request_id,
                input_dto=input_dto,
                scheduling_repository=self._scheduling_repository,
                gcal_onboarding_service=self._google_calendar_onboarding_service,
                clock=self._clock,
                reminder_service=self._reminder_service,
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
            apply_transition=lambda _: scheduling_booking.update_booked_payment_impl(
                tenant_id=tenant_id,
                request_id=request_id,
                input_dto=input_dto,
                scheduling_repository=self._scheduling_repository,
                clock=self._clock,
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
            apply_transition=lambda _: scheduling_booking.change_booked_modality_impl(
                tenant_id=tenant_id,
                request_id=request_id,
                input_dto=input_dto,
                scheduling_repository=self._scheduling_repository,
                gcal_onboarding_service=self._google_calendar_onboarding_service,
                event_description_builder=self._event_description_builder,
                clock=self._clock,
                patient_repository=self._patient_repository,
                reminder_service=self._reminder_service,
                is_eval_tenant=self._is_eval_tenant(tenant_id),
            ),
        )
        return typing.cast(scheduling_dto.SchedulingRequestSummaryDTO, transition_result)

    # ------------------------------------------------------------------
    # Payment approval (public facade)
    # ------------------------------------------------------------------

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
            apply_transition=lambda _: scheduling_payment_approval.approve_payment_impl(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                request_id=request_id,
                input_dto=input_dto,
                scheduling_repository=self._scheduling_repository,
                conversation_repository=self._conversation_repository,
                clock=self._clock,
                id_generator=self._id_generator,
                tag_service=self._tag_service,
                manual_appointment_repository=self._manual_appointment_repository,
                whatsapp_provider=self._whatsapp_provider,
                whatsapp_connection_repository=self._whatsapp_connection_repository,
            ),
        )
        return typing.cast(scheduling_dto.SchedulingRequestSummaryDTO, transition_result)

    # ------------------------------------------------------------------
    # Session lifecycle transitions (public facade)
    # ------------------------------------------------------------------

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
            apply_transition=lambda _: scheduling_transitions.handoff_to_human_impl(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                input_dto=input_dto,
                scheduling_repository=self._scheduling_repository,
                conversation_repository=self._conversation_repository,
                clock=self._clock,
                tag_service=self._tag_service,
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
            apply_transition=lambda _: scheduling_transitions.close_session_impl(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                scheduling_repository=self._scheduling_repository,
                conversation_repository=self._conversation_repository,
                clock=self._clock,
                tag_service=self._tag_service,
            ),
        )
        return typing.cast(dict[str, str], transition_result)

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
        return scheduling_transitions.close_attendance_confirmation(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            scheduling_repository=self._scheduling_repository,
            conversation_repository=self._conversation_repository,
            clock=self._clock,
            tag_service=self._tag_service,
        )

    def auto_close_booked_request(
        self,
        tenant_id: str,
        scheduling_request_id: str,
    ) -> dict[str, str]:
        return scheduling_transitions.auto_close_booked_request(
            tenant_id=tenant_id,
            scheduling_request_id=scheduling_request_id,
            scheduling_repository=self._scheduling_repository,
            conversation_repository=self._conversation_repository,
            clock=self._clock,
            tag_service=self._tag_service,
        )
