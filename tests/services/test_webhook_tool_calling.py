import dataclasses
import datetime
import typing

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.blacklist_repository_adapter as blacklist_repository_adapter
import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.google_calendar_connection_repository_adapter as google_calendar_connection_repository_adapter
import src.adapters.outbound.inmemory.patient_repository_adapter as patient_repository_adapter
import src.adapters.outbound.inmemory.processed_webhook_event_repository_adapter as processed_webhook_event_repository_adapter
import src.adapters.outbound.inmemory.scheduling_repository_adapter as scheduling_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.task_scheduler_adapter as inmemory_task_scheduler_adapter
import src.adapters.outbound.inmemory.tenant_repository_adapter as tenant_repository_adapter
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.google_calendar_connection as google_calendar_connection_entity
import src.domain.entities.message as message_entity
import src.domain.entities.patient as patient_entity
import src.domain.entities.scheduling_request as scheduling_request_entity
import src.domain.entities.scheduling_slot as scheduling_slot_entity
import src.domain.entities.tenant as tenant_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.infra.langsmith_tracer as langsmith_tracer
import src.services.agentic.conversation_message_sender as conversation_message_sender_mod
import src.services.agentic.guards.waiting_professional_silent_guard as professional_silent_guard_mod
import src.services.agentic.prompt_builder as prompt_builder_mod
import src.services.agentic.runtime_context_resolver as runtime_context_resolver_mod
import src.services.agentic.tool_calling_orchestrator as tool_calling_orchestrator_mod
import src.services.agentic.tool_handlers.cancel_request_handler as cancel_request_handler
import src.services.agentic.tool_handlers.close_session_handler as close_session_handler
import src.services.agentic.tool_handlers.confirm_slot_handler as confirm_slot_handler
import src.services.agentic.tool_handlers.handoff_handler as handoff_handler
import src.services.agentic.tool_handlers.patient_profile_resolver as patient_profile_resolver
import src.services.agentic.tool_handlers.registry as tool_handler_registry
import src.services.agentic.tool_handlers.reject_proposed_slots_handler as reject_proposed_slots_handler
import src.services.agentic.tool_handlers.select_proposed_slot_handler as select_proposed_slot_handler
import src.services.agentic.tool_handlers.set_contact_name_handler as set_contact_name_handler
import src.services.agentic.tool_handlers.submit_consultation_reason_handler as submit_consultation_reason_handler
import src.services.agentic.tool_registry as tool_definition_registry_mod
import src.services.dto.llm_dto as llm_dto
import src.services.dto.webhook_dto as webhook_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.event_description_builder as event_description_builder_mod
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import src.services.use_cases.scheduling_service as scheduling_service
import src.services.use_cases.webhook_service as webhook_service
import tests.fakes.fake_adapters as fake_adapters

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


@dataclasses.dataclass
class ToolCallingTestContext:
    service: webhook_service.WebhookService
    provider: fake_adapters.FakeWhatsappProvider
    llm_provider: fake_adapters.FakeLlmProvider
    scheduling_repository: scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter
    conversation_repository: conversation_repository_adapter.InMemoryConversationRepositoryAdapter
    patient_repository: patient_repository_adapter.InMemoryPatientRepositoryAdapter
    agent_profile_repository: agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter
    id_generator: fake_adapters.SequenceIdGenerator
    clock: fake_adapters.FixedClock
    scheduling_use_case: scheduling_service.SchedulingService
    google_provider: fake_adapters.FakeGoogleCalendarProvider


def _build_new_components(
    scheduling_svc: scheduling_service.SchedulingService,
    conversation_repository: conversation_repository_adapter.InMemoryConversationRepositoryAdapter,
    patient_repository: patient_repository_adapter.InMemoryPatientRepositoryAdapter,
    llm_provider: fake_adapters.FakeLlmProvider,
    clock: fake_adapters.FixedClock,
    whatsapp_provider: fake_adapters.FakeWhatsappProvider,
    id_generator: fake_adapters.SequenceIdGenerator,
    google_service: google_calendar_onboarding_service.GoogleCalendarOnboardingService,
    sleep_fn: typing.Callable[[float], None] | None = None,
) -> dict[str, typing.Any]:
    """Builds the new refactored components for WebhookService."""
    tracer = langsmith_tracer.LangsmithTracer(enabled=False)
    tool_def_registry = tool_definition_registry_mod.ToolDefinitionRegistry()

    effective_sleep: typing.Callable[[float], None] = (
        sleep_fn if sleep_fn is not None else (lambda _: None)
    )
    resolver = patient_profile_resolver.PatientProfileResolver(
        scheduling_svc=scheduling_svc,
        patient_repository=patient_repository,
        clock=clock,
        google_calendar_onboarding_service=google_service,
        sleep_seconds=effective_sleep,
    )
    handler_registry = tool_handler_registry.ToolHandlerRegistry(
        handlers=[
            set_contact_name_handler.SetContactNameHandler(
                conversation_repository=conversation_repository
            ),
            close_session_handler.CloseSessionHandler(scheduling_svc=scheduling_svc),
            cancel_request_handler.CancelActiveRequestHandler(scheduling_svc=scheduling_svc),
            handoff_handler.HandoffToHumanHandler(scheduling_svc=scheduling_svc),
            submit_consultation_reason_handler.SubmitConsultationReasonHandler(
                scheduling_svc=scheduling_svc
            ),
            confirm_slot_handler.ConfirmSlotHandler(resolver=resolver),
            select_proposed_slot_handler.SelectProposedSlotHandler(scheduling_svc=scheduling_svc),
            reject_proposed_slots_handler.RejectProposedSlotsHandler(scheduling_svc=scheduling_svc),
        ],
        tracer=tracer,
    )
    prompt_builder = prompt_builder_mod.RuntimePromptBuilder()
    orchestrator = tool_calling_orchestrator_mod.ToolCallingOrchestrator(
        llm_provider=llm_provider,
        tool_handler_registry=handler_registry,
        prompt_builder_instance=prompt_builder,
        tool_definition_registry=tool_def_registry,
        patient_repository=patient_repository,
        tracer=tracer,
        sleep_fn=effective_sleep,
    )
    professional_silent_guard = professional_silent_guard_mod.WaitingProfessionalSilentGuard(
        scheduling_svc=scheduling_svc,
    )
    runtime_resolver = runtime_context_resolver_mod.RuntimeContextResolver(
        scheduling_svc=scheduling_svc,
        conversation_repository=conversation_repository,
    )
    message_sender = conversation_message_sender_mod.ConversationMessageSender(
        whatsapp_provider=whatsapp_provider,
        conversation_repository=conversation_repository,
        id_generator=id_generator,
        clock=clock,
    )
    return {
        "professional_silent_guard": professional_silent_guard,
        "tool_calling_orchestrator": orchestrator,
        "runtime_context_resolver": runtime_resolver,
        "message_sender": message_sender,
    }


def build_tool_calling_context(
    id_values: list[str],
    sleep_fn: typing.Callable[[float], None] | None = None,
    now_value: datetime.datetime = _NOW,
    calendar_timezone: str = "America/Bogota",
) -> ToolCallingTestContext:
    """Builds all shared infrastructure and returns a ToolCallingTestContext."""
    store = in_memory_store.InMemoryStore()
    conversation_repo = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(store)
    connection_repository = (
        whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter(store)
    )
    processed_repository = (
        processed_webhook_event_repository_adapter.InMemoryProcessedWebhookEventRepositoryAdapter(
            store
        )
    )
    blacklist_repo = blacklist_repository_adapter.InMemoryBlacklistRepositoryAdapter(store)
    agent_profile_repo = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(
        store
    )
    scheduling_repo = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    patient_repo = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
    calendar_connection_repository = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )

    connection_repository.save(
        whatsapp_connection_entity.WhatsappConnection(
            tenant_id="tenant-1",
            phone_number_id="phone-1",
            business_account_id="business-1",
            access_token="wa-token-1",
            status="CONNECTED",
            embedded_signup_state=None,
            updated_at=now_value,
        )
    )
    calendar_connection_repository.save(
        google_calendar_connection_entity.GoogleCalendarConnection(
            tenant_id="tenant-1",
            professional_user_id="user-1",
            status="CONNECTED",
            calendar_id="primary",
            timezone=calendar_timezone,
            access_token="google-access",
            refresh_token="google-refresh",
            token_expires_at=datetime.datetime(2026, 1, 1, 2, 0, tzinfo=datetime.UTC),
            oauth_state=None,
            scope="calendar",
            updated_at=now_value,
            connected_at=now_value,
        )
    )
    agent_profile_repo.save(
        agent_profile_entity.AgentProfile(
            tenant_id="tenant-1",
            system_prompt="tenant custom prompt",
            updated_at=now_value,
        )
    )

    provider = fake_adapters.FakeWhatsappProvider()
    llm_provider = fake_adapters.FakeLlmProvider(reply_content="unused")
    id_generator = fake_adapters.SequenceIdGenerator(id_values)
    clock = fake_adapters.FixedClock(now_value)
    google_provider = fake_adapters.FakeGoogleCalendarProvider()
    tenant_repo = tenant_repository_adapter.InMemoryTenantRepositoryAdapter(store)
    tenant_repo.save(
        tenant_entity.Tenant(
            id="tenant-1",
            name="Test Clinic",
            created_at=now_value,
            updated_at=now_value,
            professional_name="Test Professional",
        )
    )
    google_service = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_connection_repository,
        google_calendar_provider=google_provider,
        id_generator=id_generator,
        clock=clock,
        tenant_repository=tenant_repo,
    )
    task_sched = inmemory_task_scheduler_adapter.InMemoryTaskSchedulerAdapter()
    builder = event_description_builder_mod.EventDescriptionBuilder(
        agent_profile_repository=agent_profile_repo,
    )
    scheduling_use_case = scheduling_service.SchedulingService(
        scheduling_repository=scheduling_repo,
        conversation_repository=conversation_repo,
        google_calendar_onboarding_service=google_service,
        id_generator=id_generator,
        clock=clock,
        task_scheduler=task_sched,
        event_description_builder=builder,
        agent_profile_repository=agent_profile_repo,
    )

    service_kwargs: dict[str, typing.Any] = {}
    if sleep_fn is not None:
        service_kwargs["sleep_seconds"] = sleep_fn
    service = webhook_service.WebhookService(
        whatsapp_connection_repository=connection_repository,
        conversation_repository=conversation_repo,
        patient_repository=patient_repo,
        processed_webhook_event_repository=processed_repository,
        blacklist_repository=blacklist_repo,
        agent_profile_repository=agent_profile_repo,
        scheduling_service=scheduling_use_case,
        whatsapp_provider=provider,
        id_generator=id_generator,
        clock=clock,
        context_message_limit=8,
        **service_kwargs,
        **_build_new_components(
            scheduling_use_case,
            conversation_repo,
            patient_repo,
            llm_provider,
            clock,
            provider,
            id_generator,
            google_service=google_service,
            sleep_fn=sleep_fn,
        ),
    )

    return ToolCallingTestContext(
        service=service,
        provider=provider,
        llm_provider=llm_provider,
        scheduling_repository=scheduling_repo,
        conversation_repository=conversation_repo,
        patient_repository=patient_repo,
        agent_profile_repository=agent_profile_repo,
        id_generator=id_generator,
        clock=clock,
        scheduling_use_case=scheduling_use_case,
        google_provider=google_provider,
    )


def build_default_event(
    message_text: str = "hello",
) -> webhook_dto.IncomingMessageEventDTO:
    return webhook_dto.IncomingMessageEventDTO(
        provider_event_id="evt-1",
        phone_number_id="phone-1",
        whatsapp_user_id="wa-user-1",
        whatsapp_user_name="Jane",
        message_id="wamid-in-1",
        message_type="text",
        source="CUSTOMER",
        message_text=message_text,
    )


def test_webhook_processes_function_call_and_then_sends_text_reply() -> None:
    ctx = build_tool_calling_context(
        id_values=["conversation-1", "in-msg-1", "req-1", "out-msg-1"],
    )
    ctx.llm_provider.queued_replies = [
        llm_dto.AgentReplyDTO(
            content="",
            function_calls=[
                llm_dto.FunctionCallDTO(
                    name="submit_consultation_reason_for_review",
                    args={
                        "consultation_reason": "Ansiedad",
                    },
                    call_id="call-1",
                )
            ],
        ),
    ]
    ctx.provider.events = [build_default_event("hola quiero una cita")]

    ctx.service.process_payload({})

    saved_requests = ctx.scheduling_repository.list_requests_by_tenant("tenant-1")
    assert len(saved_requests) == 1
    assert saved_requests[0].status == "AWAITING_CONSULTATION_REVIEW"
    assert len(ctx.provider.sent_messages) == 1
    assert "dame un momento" in ctx.provider.sent_messages[0]["text"].lower()
    assert len(ctx.llm_provider.calls) == 1
    tool_names = [tool.name for tool in ctx.llm_provider.calls[0].tools]
    assert tool_names == [
        "submit_consultation_reason_for_review",
        "handoff_to_human",
        "cancel_active_scheduling_request",
        "close_session",
        "submit_reschedule_for_review",
    ]


def test_webhook_recovers_when_reason_tool_is_called_again_after_approval() -> None:
    ctx = build_tool_calling_context(id_values=["in-msg-1", "out-msg-1"])
    now_value = ctx.clock.now()
    ctx.conversation_repository.save_conversation(
        conversation_entity.Conversation(
            id="conversation-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            started_at=now_value,
            updated_at=now_value,
            last_message_preview=None,
            message_ids=[],
            control_mode="AI",
        )
    )
    ctx.scheduling_repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-1",
            tenant_id="tenant-1",
            conversation_id="conversation-1",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="AWAITING_CONSULTATION_DETAILS",
            round_number=1,
            patient_preference_note=None,
            rejection_summary=None,
            professional_note="Aprobado",
            patient_first_name=None,
            patient_last_name=None,
            patient_age=None,
            consultation_reason="ansiedad en el trabajo",
            consultation_details=None,
            appointment_modality=None,
            patient_location=None,
            slots=[],
            slot_options_map={},
            selected_slot_id=None,
            calendar_event_id=None,
            created_at=now_value,
            updated_at=now_value,
        )
    )
    ctx.llm_provider.queued_replies = [
        llm_dto.AgentReplyDTO(
            content="",
            function_calls=[
                llm_dto.FunctionCallDTO(
                    name="submit_consultation_reason_for_review",
                    args={
                        "request_id": "req-1",
                        "consultation_reason": "ansiedad en el trabajo",
                        "appointment_modality": "PRESENCIAL",
                    },
                    call_id="call-1",
                )
            ],
        ),
    ]
    ctx.provider.events = [build_default_event("presencial, despues de las 4 pm o sabados")]

    ctx.service.process_payload({})

    saved_request = ctx.scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "AWAITING_CONSULTATION_REVIEW"
    assert saved_request.appointment_modality == "PRESENCIAL"
    assert (
        len(ctx.scheduling_repository.list_requests_by_conversation("tenant-1", "conversation-1"))
        == 1
    )
    assert len(ctx.provider.sent_messages) == 1
    assert "dame un momento" in ctx.provider.sent_messages[0]["text"].lower()
    assert len(ctx.llm_provider.calls) == 1


def test_webhook_responds_when_awaiting_consultation_review() -> None:
    ctx = build_tool_calling_context(id_values=["in-msg-1", "out-msg-1"])
    now_value = ctx.clock.now()
    ctx.conversation_repository.save_conversation(
        conversation_entity.Conversation(
            id="conversation-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            started_at=now_value,
            updated_at=now_value,
            last_message_preview=None,
            message_ids=[],
            control_mode="AI",
        )
    )
    ctx.scheduling_repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-1",
            tenant_id="tenant-1",
            conversation_id="conversation-1",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="AWAITING_CONSULTATION_REVIEW",
            round_number=1,
            patient_preference_note="despues de las 4 pm",
            rejection_summary=None,
            professional_note=None,
            slots=[],
            slot_options_map={},
            selected_slot_id=None,
            calendar_event_id=None,
            created_at=now_value,
            updated_at=now_value,
        )
    )
    ctx.provider.events = [build_default_event("mi correo es jane@example.com")]

    ctx.service.process_payload({})

    saved_request = ctx.scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "AWAITING_CONSULTATION_REVIEW"
    assert len(ctx.provider.sent_messages) == 1
    assert len(ctx.llm_provider.calls) == 1


def test_webhook_confirm_slot_without_ids_auto_resolves_single_active_slot() -> None:
    ctx = build_tool_calling_context(id_values=["in-msg-1", "conf-req-1", "out-msg-1"])
    now_value = ctx.clock.now()
    ctx.conversation_repository.save_conversation(
        conversation_entity.Conversation(
            id="conversation-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            started_at=now_value,
            updated_at=now_value,
            last_message_preview=None,
            message_ids=[],
            control_mode="AI",
        )
    )
    ctx.scheduling_repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-1",
            tenant_id="tenant-1",
            conversation_id="conversation-1",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="AWAITING_PATIENT_CHOICE",
            round_number=1,
            patient_preference_note="prefiere tarde",
            rejection_summary=None,
            professional_note=None,
            slots=[
                scheduling_slot_entity.SchedulingSlot(
                    id="slot-1",
                    start_at=datetime.datetime(2026, 1, 2, 10, 0, tzinfo=datetime.UTC),
                    end_at=datetime.datetime(2026, 1, 2, 11, 0, tzinfo=datetime.UTC),
                    timezone="America/Bogota",
                    status="SELECTED",
                )
            ],
            slot_options_map={"1": "slot-1"},
            selected_slot_id="slot-1",
            calendar_event_id=None,
            created_at=now_value,
            updated_at=now_value,
        )
    )
    ctx.llm_provider.queued_replies = [
        llm_dto.AgentReplyDTO(
            content="",
            function_calls=[
                llm_dto.FunctionCallDTO(
                    name="confirm_selected_slot_and_create_event",
                    args={
                        "patient_full_name": "Jane Doe",
                        "patient_email": "jane@example.com",
                        "patient_age": 29,
                        "consultation_reason": "Ansiedad",
                        "patient_location": "Bogota",
                    },
                    call_id="call-1",
                )
            ],
        ),
        llm_dto.AgentReplyDTO(content="Perfecto, tu cita quedó confirmada."),
    ]
    ctx.provider.events = [build_default_event("1")]

    ctx.service.process_payload({})

    saved_request = ctx.scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "BOOKED"
    assert saved_request.selected_slot_id == "slot-1"
    assert saved_request.calendar_event_id == "event-1"
    assert ctx.google_provider.created_event_summaries == ["Test Professional/Jane Doe"]
    created_patient = ctx.patient_repository.get_by_whatsapp_user("tenant-1", "wa-user-1")
    assert created_patient is not None
    assert created_patient.location == "Bogota"
    assert created_patient.email == "jane@example.com"
    assert len(ctx.provider.sent_messages) == 1
    assert "confirmada" in ctx.provider.sent_messages[0]["text"]
    active_messages = ctx.conversation_repository.list_messages("tenant-1", "conversation-1")
    assert len(active_messages) == 2
    saved_conversation = ctx.conversation_repository.get_conversation_by_id(
        "tenant-1",
        "conversation-1",
    )
    assert saved_conversation is not None
    assert len(saved_conversation.subsessions) == 0


def test_webhook_confirm_slot_resolves_slot_from_previous_user_choice_message() -> None:
    ctx = build_tool_calling_context(
        id_values=["in-msg-1", "conf-req-1", "out-msg-1"],
        now_value=_NOW + datetime.timedelta(minutes=20),
    )
    now_value = _NOW
    conversation = conversation_entity.Conversation(
        id="conversation-1",
        tenant_id="tenant-1",
        whatsapp_user_id="wa-user-1",
        started_at=now_value,
        updated_at=now_value,
        last_message_preview=None,
        message_ids=[],
        control_mode="AI",
    )
    ctx.conversation_repository.save_conversation(conversation)
    ctx.scheduling_repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-1",
            tenant_id="tenant-1",
            conversation_id="conversation-1",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="AWAITING_PATIENT_CHOICE",
            round_number=1,
            patient_preference_note="despues de las 4 pm",
            rejection_summary=None,
            professional_note=None,
            slots=[
                scheduling_slot_entity.SchedulingSlot(
                    id="slot-1",
                    start_at=datetime.datetime(2026, 1, 4, 21, 0, tzinfo=datetime.UTC),
                    end_at=datetime.datetime(2026, 1, 4, 22, 0, tzinfo=datetime.UTC),
                    timezone="America/Bogota",
                    status="PROPOSED",
                ),
                scheduling_slot_entity.SchedulingSlot(
                    id="slot-2",
                    start_at=datetime.datetime(2026, 1, 4, 22, 0, tzinfo=datetime.UTC),
                    end_at=datetime.datetime(2026, 1, 4, 23, 0, tzinfo=datetime.UTC),
                    timezone="America/Bogota",
                    status="PROPOSED",
                ),
                scheduling_slot_entity.SchedulingSlot(
                    id="slot-3",
                    start_at=datetime.datetime(2026, 1, 5, 21, 0, tzinfo=datetime.UTC),
                    end_at=datetime.datetime(2026, 1, 5, 22, 0, tzinfo=datetime.UTC),
                    timezone="America/Bogota",
                    status="SELECTED",
                ),
                scheduling_slot_entity.SchedulingSlot(
                    id="slot-4",
                    start_at=datetime.datetime(2026, 1, 5, 22, 0, tzinfo=datetime.UTC),
                    end_at=datetime.datetime(2026, 1, 5, 23, 0, tzinfo=datetime.UTC),
                    timezone="America/Bogota",
                    status="PROPOSED",
                ),
            ],
            slot_options_map={
                "1": "slot-1",
                "2": "slot-2",
                "3": "slot-3",
                "4": "slot-4",
            },
            selected_slot_id="slot-3",
            calendar_event_id=None,
            created_at=now_value,
            updated_at=now_value,
        )
    )

    existing_messages: list[tuple[str, typing.Literal["assistant", "user"], str]] = [
        (
            "msg-assistant-1",
            "assistant",
            "Estas son las opciones: 1, 2, 3 y 4. ¿Cual prefieres?",
        ),
        ("msg-user-1", "user", "tres"),
        ("msg-assistant-2", "assistant", "¿Cual es tu nombre?"),
        ("msg-user-2", "user", "Jhon"),
        ("msg-assistant-3", "assistant", "¿Cual es tu apellido?"),
        ("msg-user-3", "user", "Valderrama"),
        ("msg-assistant-4", "assistant", "¿Cual es tu correo?"),
        ("msg-user-4", "user", "jhonjj1993@gmail.com"),
        ("msg-assistant-5", "assistant", "¿Cual es tu edad?"),
        ("msg-user-5", "user", "33"),
        ("msg-assistant-6", "assistant", "¿Cual es el motivo de consulta?"),
        ("msg-user-6", "user", "ansiedad"),
        ("msg-assistant-7", "assistant", "¿Cual es tu ubicacion?"),
    ]
    for index, (message_id, role, content) in enumerate(existing_messages):
        direction: typing.Literal["INBOUND", "OUTBOUND"] = "INBOUND"
        if role == "assistant":
            direction = "OUTBOUND"
        created_at = now_value + datetime.timedelta(minutes=index + 1)
        ctx.conversation_repository.save_message(
            message_entity.Message(
                id=message_id,
                conversation_id="conversation-1",
                tenant_id="tenant-1",
                direction=direction,
                role=role,
                content=content,
                provider_message_id=None,
                created_at=created_at,
            )
        )
        conversation.append_message(message_id, content, created_at)
    ctx.conversation_repository.save_conversation(conversation)

    ctx.llm_provider.queued_replies = [
        llm_dto.AgentReplyDTO(
            content="",
            function_calls=[
                llm_dto.FunctionCallDTO(
                    name="confirm_selected_slot_and_create_event",
                    args={
                        "patient_first_name": "Jhon",
                        "patient_last_name": "Valderrama",
                        "patient_email": "jhonjj1993@gmail.com",
                        "patient_age": 33,
                        "consultation_reason": "ansiedad",
                        "patient_location": "cali",
                    },
                    call_id="call-1",
                )
            ],
        ),
        llm_dto.AgentReplyDTO(content="Perfecto, tu cita quedó confirmada."),
    ]
    ctx.provider.events = [build_default_event("3")]

    ctx.service.process_payload({})

    saved_request = ctx.scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "BOOKED"
    assert saved_request.selected_slot_id == "slot-3"
    assert saved_request.calendar_event_id == "event-1"
    assert len(ctx.llm_provider.calls) == 2
    assert len(ctx.provider.sent_messages) == 1
    assert "confirmada" in ctx.provider.sent_messages[0]["text"]


def test_webhook_confirm_slot_uses_existing_patient_context_without_overwriting_profile() -> None:
    ctx = build_tool_calling_context(id_values=["in-msg-1", "conf-req-1", "out-msg-1"])
    now_value = ctx.clock.now()
    ctx.conversation_repository.save_conversation(
        conversation_entity.Conversation(
            id="conversation-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            started_at=now_value,
            updated_at=now_value,
            last_message_preview=None,
            message_ids=[],
            control_mode="AI",
        )
    )
    ctx.patient_repository.save(
        patient_entity.Patient(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            age=29,
            location="Bogota",
            phone="573001112233",
            created_at=now_value,
        )
    )
    ctx.scheduling_repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-1",
            tenant_id="tenant-1",
            conversation_id="conversation-1",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="AWAITING_PATIENT_CHOICE",
            round_number=1,
            patient_preference_note="prefiere tarde",
            rejection_summary=None,
            professional_note=None,
            slots=[
                scheduling_slot_entity.SchedulingSlot(
                    id="slot-1",
                    start_at=datetime.datetime(2026, 1, 2, 10, 0, tzinfo=datetime.UTC),
                    end_at=datetime.datetime(2026, 1, 2, 11, 0, tzinfo=datetime.UTC),
                    timezone="America/Bogota",
                    status="SELECTED",
                )
            ],
            slot_options_map={"1": "slot-1"},
            selected_slot_id="slot-1",
            calendar_event_id=None,
            created_at=now_value,
            updated_at=now_value,
        )
    )
    ctx.llm_provider.queued_replies = [
        llm_dto.AgentReplyDTO(
            content="",
            function_calls=[
                llm_dto.FunctionCallDTO(
                    name="confirm_selected_slot_and_create_event",
                    args={
                        "request_id": "req-1",
                        "slot_id": "slot-1",
                        "patient_first_name": "Otro",
                        "patient_location": "Cali",
                    },
                    call_id="call-1",
                )
            ],
        ),
        llm_dto.AgentReplyDTO(content="Perfecto, tu cita quedó confirmada."),
    ]
    ctx.provider.events = [build_default_event("1")]

    ctx.service.process_payload({})

    saved_request = ctx.scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "BOOKED"
    assert ctx.google_provider.created_event_summaries == ["Test Professional/Jane Doe"]
    persisted_patient = ctx.patient_repository.get_by_whatsapp_user("tenant-1", "wa-user-1")
    assert persisted_patient is not None
    assert persisted_patient.first_name == "Jane"
    assert persisted_patient.location == "Bogota"


def test_webhook_confirm_slot_requires_patient_location_for_new_patient() -> None:
    ctx = build_tool_calling_context(id_values=["in-msg-1", "out-msg-1"])
    now_value = ctx.clock.now()
    ctx.conversation_repository.save_conversation(
        conversation_entity.Conversation(
            id="conversation-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            started_at=now_value,
            updated_at=now_value,
            last_message_preview=None,
            message_ids=[],
            control_mode="AI",
        )
    )
    ctx.scheduling_repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-1",
            tenant_id="tenant-1",
            conversation_id="conversation-1",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="AWAITING_PATIENT_CHOICE",
            round_number=1,
            patient_preference_note="prefiere tarde",
            rejection_summary=None,
            professional_note=None,
            slots=[
                scheduling_slot_entity.SchedulingSlot(
                    id="slot-1",
                    start_at=datetime.datetime(2026, 1, 2, 10, 0, tzinfo=datetime.UTC),
                    end_at=datetime.datetime(2026, 1, 2, 11, 0, tzinfo=datetime.UTC),
                    timezone="America/Bogota",
                    status="SELECTED",
                )
            ],
            slot_options_map={"1": "slot-1"},
            selected_slot_id="slot-1",
            calendar_event_id=None,
            created_at=now_value,
            updated_at=now_value,
        )
    )
    ctx.llm_provider.queued_replies = [
        llm_dto.AgentReplyDTO(
            content="",
            function_calls=[
                llm_dto.FunctionCallDTO(
                    name="confirm_selected_slot_and_create_event",
                    args={
                        "request_id": "req-1",
                        "slot_id": "slot-1",
                        "patient_first_name": "Jane",
                        "patient_last_name": "Doe",
                        "patient_email": "jane@example.com",
                        "patient_age": 29,
                        "consultation_reason": "Ansiedad",
                    },
                    call_id="call-1",
                )
            ],
        ),
        llm_dto.AgentReplyDTO(content="Necesito tu ubicacion para confirmar la cita."),
    ]
    ctx.provider.events = [build_default_event("1")]

    ctx.service.process_payload({})

    saved_request = ctx.scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "AWAITING_PATIENT_CHOICE"
    assert ctx.google_provider.created_event_summaries == []
    assert ctx.patient_repository.get_by_whatsapp_user("tenant-1", "wa-user-1") is None
    assert "ubicacion" in ctx.provider.sent_messages[0]["text"].lower()


def test_webhook_select_proposed_slot_via_orchestrator() -> None:
    """Orchestrator calls select_proposed_slot when patient picks a slot by number."""
    now_value = datetime.datetime(2026, 3, 1, tzinfo=datetime.UTC)
    ctx = build_tool_calling_context(
        id_values=["in-msg-1", "out-msg-1"],
        now_value=now_value,
        calendar_timezone="UTC",
    )
    ctx.conversation_repository.save_conversation(
        conversation_entity.Conversation(
            id="conversation-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            started_at=now_value,
            updated_at=now_value,
            last_message_preview=None,
            message_ids=[],
            control_mode="AI",
        )
    )
    ctx.scheduling_repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-1",
            tenant_id="tenant-1",
            conversation_id="conversation-1",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="AWAITING_PATIENT_CHOICE",
            round_number=1,
            patient_preference_note=None,
            rejection_summary=None,
            professional_note=None,
            slots=[
                scheduling_slot_entity.SchedulingSlot(
                    id="slot-1",
                    start_at=datetime.datetime(2026, 3, 2, 8, 0, tzinfo=datetime.UTC),
                    end_at=datetime.datetime(2026, 3, 2, 9, 0, tzinfo=datetime.UTC),
                    timezone="UTC",
                    status="PROPOSED",
                ),
                scheduling_slot_entity.SchedulingSlot(
                    id="slot-2",
                    start_at=datetime.datetime(2026, 3, 2, 9, 0, tzinfo=datetime.UTC),
                    end_at=datetime.datetime(2026, 3, 2, 10, 0, tzinfo=datetime.UTC),
                    timezone="UTC",
                    status="PROPOSED",
                ),
            ],
            slot_options_map={"1": "slot-1", "2": "slot-2"},
            selected_slot_id=None,
            calendar_event_id=None,
            created_at=now_value,
            updated_at=now_value,
        )
    )
    # Orchestrator calls select_proposed_slot, then LLM generates payment message
    ctx.llm_provider.queued_replies = [
        llm_dto.AgentReplyDTO(
            content="",
            function_calls=[
                llm_dto.FunctionCallDTO(
                    name="select_proposed_slot",
                    args={"slot_option_number": "1"},
                    call_id="call-1",
                )
            ],
        ),
        llm_dto.AgentReplyDTO(content="Perfecto, elegiste la opcion 1. El pago es X."),
    ]
    ctx.provider.events = [build_default_event("quiero el 1")]

    ctx.service.process_payload({})

    saved_request = ctx.scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.selected_slot_id == "slot-1"
    assert len(ctx.provider.sent_messages) == 1
    assert "perfecto" in ctx.provider.sent_messages[0]["text"].lower()
    assert len(ctx.llm_provider.calls) == 2


def test_webhook_select_proposed_slot_auto_confirms_for_known_patient() -> None:
    """Short-circuit: when known_patient covers everything and missing_fields
    is empty, the orchestrator auto-calls confirm_selected_slot_and_create_event
    after select_proposed_slot — without bouncing back to the LLM. The LLM was
    asking the patient for data we already had ~30% of the time despite the
    explicit prompt instructions."""
    ctx = build_tool_calling_context(
        id_values=[
            "in-msg-1",
            "conf-req-1",
            "evt-1",
            "out-msg-1",
            "subsess-1",
            "out-msg-2",
        ],
        calendar_timezone="UTC",
    )
    now_value = ctx.clock.now()
    # AFTER_SESSION skips the payment step so select_proposed_slot lands the
    # request straight in COLLECTING_CONFIRMATION_DATA — exactly the state
    # where the short-circuit should fire when the patient is already known.
    ctx.agent_profile_repository.save(
        agent_profile_entity.AgentProfile(
            tenant_id="tenant-1",
            system_prompt="tenant custom prompt",
            payment_timing="AFTER_SESSION",
            updated_at=now_value,
        )
    )
    ctx.conversation_repository.save_conversation(
        conversation_entity.Conversation(
            id="conversation-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            started_at=now_value,
            updated_at=now_value,
            last_message_preview=None,
            message_ids=[],
            control_mode="AI",
        )
    )
    # Seed a known patient so the resolver short-circuits missing_fields to [].
    ctx.patient_repository.save(
        patient_entity.Patient(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            first_name="Jhon",
            last_name="Valderrama",
            email="jhon@example.com",
            age=33,
            location="Cali",
            phone="573127457050",
            created_at=now_value,
        )
    )
    ctx.scheduling_repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-1",
            tenant_id="tenant-1",
            conversation_id="conversation-1",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="AWAITING_PATIENT_CHOICE",
            round_number=1,
            patient_preference_note=None,
            rejection_summary=None,
            professional_note=None,
            slots=[
                scheduling_slot_entity.SchedulingSlot(
                    id="slot-1",
                    start_at=datetime.datetime(2026, 3, 2, 8, 0, tzinfo=datetime.UTC),
                    end_at=datetime.datetime(2026, 3, 2, 9, 0, tzinfo=datetime.UTC),
                    timezone="UTC",
                    status="PROPOSED",
                ),
            ],
            slot_options_map={"1": "slot-1"},
            selected_slot_id=None,
            calendar_event_id=None,
            consultation_reason="control",
            appointment_modality="PRESENCIAL",
            patient_first_name="Jhon",
            patient_last_name="Valderrama",
            patient_age=33,
            created_at=now_value,
            updated_at=now_value,
        )
    )
    # The LLM only needs to call select_proposed_slot. The orchestrator should
    # auto-call confirm_selected_slot_and_create_event right after. The LLM
    # then gets a second turn to generate the booking confirmation message —
    # by that point the state is POST_BOOKING_FOLLOWUP, no data-asking prompt.
    ctx.llm_provider.queued_replies = [
        llm_dto.AgentReplyDTO(
            content="",
            function_calls=[
                llm_dto.FunctionCallDTO(
                    name="select_proposed_slot",
                    args={"slot_option_number": "1"},
                    call_id="call-1",
                )
            ],
        ),
        llm_dto.AgentReplyDTO(content="¡Listo, Jhon! Tu cita queda agendada."),
    ]
    ctx.provider.events = [build_default_event("si ese me sirve")]

    ctx.service.process_payload({})

    saved_request = ctx.scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.selected_slot_id == "slot-1"
    # Short-circuit should have auto-called confirm_selected_slot_and_create_event
    # so the request ends up BOOKED with a calendar event, even though the LLM
    # only ever called select_proposed_slot.
    assert saved_request.status == "BOOKED"
    assert saved_request.calendar_event_id is not None


def test_webhook_patient_choice_allows_explicit_handoff_to_human() -> None:
    """Orchestrator calls handoff_to_human directly in AWAITING_PATIENT_CHOICE state."""
    now_value = datetime.datetime(2026, 3, 1, tzinfo=datetime.UTC)
    ctx = build_tool_calling_context(
        id_values=["in-msg-1", "out-msg-1"],
        now_value=now_value,
    )
    ctx.conversation_repository.save_conversation(
        conversation_entity.Conversation(
            id="conversation-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            started_at=now_value,
            updated_at=now_value,
            last_message_preview=None,
            message_ids=[],
            control_mode="AI",
        )
    )
    ctx.scheduling_repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-1",
            tenant_id="tenant-1",
            conversation_id="conversation-1",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="AWAITING_PATIENT_CHOICE",
            round_number=1,
            patient_preference_note="despues de las 4 pm",
            rejection_summary=None,
            professional_note=None,
            appointment_modality="PRESENCIAL",
            patient_location="Cali",
            slots=[
                scheduling_slot_entity.SchedulingSlot(
                    id="slot-1",
                    start_at=datetime.datetime(2026, 3, 2, 21, 0, tzinfo=datetime.UTC),
                    end_at=datetime.datetime(2026, 3, 2, 22, 0, tzinfo=datetime.UTC),
                    timezone="America/Bogota",
                    status="PROPOSED",
                )
            ],
            slot_options_map={"1": "slot-1"},
            selected_slot_id=None,
            calendar_event_id=None,
            created_at=now_value,
            updated_at=now_value,
        )
    )
    # In the new flow, the orchestrator calls handoff_to_human directly (1 LLM call with tool)
    # then the tool handler switches to HUMAN mode and generates an ACK message
    ctx.llm_provider.queued_replies = [
        llm_dto.AgentReplyDTO(
            content="",
            function_calls=[
                llm_dto.FunctionCallDTO(
                    name="handoff_to_human",
                    args={
                        "reason": "patient_requested_human",
                        "summary_for_professional": "El paciente pidio hablar con un humano.",
                    },
                    call_id="call-1",
                )
            ],
        ),
        llm_dto.AgentReplyDTO(content="Te comunico con un agente."),
    ]
    ctx.provider.events = [build_default_event("transfiereme con un humano")]

    ctx.service.process_payload({})

    saved_request = ctx.scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "AWAITING_PATIENT_CHOICE"
    conversation = ctx.conversation_repository.get_conversation_by_id("tenant-1", "conversation-1")
    assert conversation is not None
    assert conversation.control_mode == "HUMAN"
    assert len(ctx.provider.sent_messages) == 1
    assert len(ctx.llm_provider.calls) >= 1


def test_webhook_confirm_slot_retries_network_error_and_handoffs_to_human() -> None:
    retry_delays: list[float] = []

    def capture_sleep(seconds: float) -> None:
        retry_delays.append(seconds)

    ctx = build_tool_calling_context(
        id_values=["in-msg-1", "out-msg-1"],
        sleep_fn=capture_sleep,
    )
    now_value = ctx.clock.now()
    ctx.conversation_repository.save_conversation(
        conversation_entity.Conversation(
            id="conversation-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            started_at=now_value,
            updated_at=now_value,
            last_message_preview=None,
            message_ids=[],
            control_mode="AI",
        )
    )
    ctx.scheduling_repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-1",
            tenant_id="tenant-1",
            conversation_id="conversation-1",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="AWAITING_PATIENT_CHOICE",
            round_number=1,
            patient_preference_note="prefiere tarde",
            rejection_summary=None,
            professional_note=None,
            slots=[
                scheduling_slot_entity.SchedulingSlot(
                    id="slot-1",
                    start_at=datetime.datetime(2026, 1, 2, 10, 0, tzinfo=datetime.UTC),
                    end_at=datetime.datetime(2026, 1, 2, 11, 0, tzinfo=datetime.UTC),
                    timezone="America/Bogota",
                    status="SELECTED",
                )
            ],
            slot_options_map={"1": "slot-1"},
            selected_slot_id="slot-1",
            calendar_event_id=None,
            created_at=now_value,
            updated_at=now_value,
        )
    )
    ctx.llm_provider.queued_replies = [
        llm_dto.AgentReplyDTO(
            content="",
            function_calls=[
                llm_dto.FunctionCallDTO(
                    name="confirm_selected_slot_and_create_event",
                    args={
                        "request_id": "req-1",
                        "slot_id": "slot-1",
                        "patient_first_name": "Jane",
                        "patient_last_name": "Doe",
                        "patient_email": "jane@example.com",
                        "patient_age": 29,
                        "consultation_reason": "Ansiedad",
                        "patient_location": "Bogota",
                    },
                    call_id="call-1",
                )
            ],
        ),
        llm_dto.AgentReplyDTO(content="Te paso con el profesional para continuar."),
    ]
    ctx.google_provider.busy_interval_errors = [
        service_exceptions.ExternalProviderError("network error calling google calendar"),
        service_exceptions.ExternalProviderError("network error calling google calendar"),
        service_exceptions.ExternalProviderError("network error calling google calendar"),
        service_exceptions.ExternalProviderError("network error calling google calendar"),
    ]
    ctx.provider.events = [build_default_event("1")]

    ctx.service.process_payload({})

    saved_request = ctx.scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "AWAITING_PATIENT_CHOICE"
    saved_conversation = ctx.conversation_repository.get_conversation_by_id(
        "tenant-1",
        "conversation-1",
    )
    assert saved_conversation is not None
    assert saved_conversation.control_mode == "HUMAN"
    assert retry_delays == [1.0, 2.0, 4.0]


def test_webhook_confirm_slot_unknown_error_handoffs_without_retry() -> None:
    retry_delays: list[float] = []

    def capture_sleep(seconds: float) -> None:
        retry_delays.append(seconds)

    ctx = build_tool_calling_context(
        id_values=["in-msg-1", "out-msg-1"],
        sleep_fn=capture_sleep,
    )
    now_value = ctx.clock.now()
    ctx.conversation_repository.save_conversation(
        conversation_entity.Conversation(
            id="conversation-1",
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            started_at=now_value,
            updated_at=now_value,
            last_message_preview=None,
            message_ids=[],
            control_mode="AI",
        )
    )
    ctx.scheduling_repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-1",
            tenant_id="tenant-1",
            conversation_id="conversation-1",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="AWAITING_PATIENT_CHOICE",
            round_number=1,
            patient_preference_note="prefiere tarde",
            rejection_summary=None,
            professional_note=None,
            slots=[
                scheduling_slot_entity.SchedulingSlot(
                    id="slot-1",
                    start_at=datetime.datetime(2026, 1, 2, 10, 0, tzinfo=datetime.UTC),
                    end_at=datetime.datetime(2026, 1, 2, 11, 0, tzinfo=datetime.UTC),
                    timezone="America/Bogota",
                    status="SELECTED",
                )
            ],
            slot_options_map={"1": "slot-1"},
            selected_slot_id="slot-1",
            calendar_event_id=None,
            created_at=now_value,
            updated_at=now_value,
        )
    )
    ctx.llm_provider.queued_replies = [
        llm_dto.AgentReplyDTO(
            content="",
            function_calls=[
                llm_dto.FunctionCallDTO(
                    name="confirm_selected_slot_and_create_event",
                    args={
                        "request_id": "req-1",
                        "slot_id": "slot-1",
                        "patient_first_name": "Jane",
                        "patient_last_name": "Doe",
                        "patient_email": "jane@example.com",
                        "patient_age": 29,
                        "consultation_reason": "Ansiedad",
                        "patient_location": "Bogota",
                    },
                    call_id="call-1",
                )
            ],
        ),
        llm_dto.AgentReplyDTO(content="Te paso con el profesional para continuar."),
    ]
    ctx.google_provider.busy_interval_errors = [
        service_exceptions.ExternalProviderError("google calendar unexpected provider issue")
    ]
    ctx.provider.events = [build_default_event("1")]

    ctx.service.process_payload({})

    saved_request = ctx.scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "AWAITING_PATIENT_CHOICE"
    saved_conversation = ctx.conversation_repository.get_conversation_by_id(
        "tenant-1",
        "conversation-1",
    )
    assert saved_conversation is not None
    assert saved_conversation.control_mode == "HUMAN"
    assert retry_delays == []
