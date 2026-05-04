import datetime
import logging
import typing

import pytest

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.blacklist_repository_adapter as blacklist_repository_adapter
import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.patient_repository_adapter as patient_repository_adapter
import src.adapters.outbound.inmemory.processed_webhook_event_repository_adapter as processed_webhook_event_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.blacklist_entry as blacklist_entry_entity
import src.domain.entities.patient as patient_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.infra.langsmith_tracer as langsmith_tracer
import src.services.agentic.conversation_message_sender as conversation_message_sender_mod
import src.services.agentic.prompt_builder as prompt_builder_mod
import src.services.agentic.runtime_context_resolver as runtime_context_resolver_mod
import src.services.agentic.tool_calling_orchestrator as tool_calling_orchestrator_mod
import src.services.agentic.tool_handlers.registry as tool_handler_registry_mod
import src.services.agentic.tool_handlers.set_contact_name_handler as set_contact_name_handler
import src.services.agentic.tool_registry as tool_definition_registry_mod
import src.services.dto.llm_dto as llm_dto
import src.services.dto.webhook_dto as webhook_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.webhook_service as webhook_service
import tests.fakes.fake_adapters as fake_adapters

LOGGER_NAME = "src.services.use_cases.webhook_service"


class WebhookTestContext(typing.NamedTuple):
    service: webhook_service.WebhookService
    provider: fake_adapters.FakeWhatsappProvider
    llm_provider: fake_adapters.FakeLlmProvider
    conversation_repository: conversation_repository_adapter.InMemoryConversationRepositoryAdapter
    processed_repository: (
        processed_webhook_event_repository_adapter.InMemoryProcessedWebhookEventRepositoryAdapter
    )
    blacklist_repository: blacklist_repository_adapter.InMemoryBlacklistRepositoryAdapter
    agent_profile_repository: agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter


def build_webhook_service(
    id_values: list[str],
    sleep_seconds: typing.Callable[[float], None] | None = None,
    existing_patient: patient_entity.Patient | None = None,
) -> WebhookTestContext:
    store = in_memory_store.InMemoryStore()
    conversation_repository = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(
        store
    )
    connection_repository = (
        whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter(store)
    )
    processed_repository = (
        processed_webhook_event_repository_adapter.InMemoryProcessedWebhookEventRepositoryAdapter(
            store
        )
    )
    blacklist_repository = blacklist_repository_adapter.InMemoryBlacklistRepositoryAdapter(store)
    agent_profile_repository = (
        agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(store)
    )
    patient_repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)

    now_value = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
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
    agent_profile_repository.save(
        agent_profile_entity.AgentProfile(
            tenant_id="tenant-1",
            system_prompt="tenant custom prompt",
            updated_at=now_value,
        )
    )
    if existing_patient is not None:
        patient_repository.save(existing_patient)

    provider = fake_adapters.FakeWhatsappProvider()
    llm_provider = fake_adapters.FakeLlmProvider(reply_content="assistant reply")
    id_generator = fake_adapters.SequenceIdGenerator(id_values)
    clock = fake_adapters.FixedClock(now_value)

    tracer = langsmith_tracer.LangsmithTracer(enabled=False)
    tool_def_registry = tool_definition_registry_mod.ToolDefinitionRegistry()
    handler_registry = tool_handler_registry_mod.ToolHandlerRegistry(
        handlers=[
            set_contact_name_handler.SetContactNameHandler(
                conversation_repository=conversation_repository
            ),
        ],
        tracer=tracer,
    )
    prompt_builder = prompt_builder_mod.RuntimePromptBuilder()
    effective_sleep = sleep_seconds if sleep_seconds is not None else (lambda _: None)
    orchestrator = tool_calling_orchestrator_mod.ToolCallingOrchestrator(
        llm_provider=llm_provider,
        tool_handler_registry=handler_registry,
        prompt_builder_instance=prompt_builder,
        tool_definition_registry=tool_def_registry,
        patient_repository=patient_repository,
        tracer=tracer,
        sleep_fn=effective_sleep,
    )
    runtime_resolver = runtime_context_resolver_mod.RuntimeContextResolver(
        scheduling_svc=None,
        conversation_repository=conversation_repository,
    )
    message_sender = conversation_message_sender_mod.ConversationMessageSender(
        whatsapp_provider=provider,
        conversation_repository=conversation_repository,
        id_generator=id_generator,
        clock=clock,
    )

    service = webhook_service.WebhookService(
        whatsapp_connection_repository=connection_repository,
        conversation_repository=conversation_repository,
        patient_repository=patient_repository,
        processed_webhook_event_repository=processed_repository,
        blacklist_repository=blacklist_repository,
        agent_profile_repository=agent_profile_repository,
        scheduling_service=None,
        whatsapp_provider=provider,
        id_generator=id_generator,
        clock=clock,
        context_message_limit=8,
        sleep_seconds=sleep_seconds,
        tool_calling_orchestrator=orchestrator,
        runtime_context_resolver=runtime_resolver,
        message_sender=message_sender,
    )

    return WebhookTestContext(
        service=service,
        provider=provider,
        llm_provider=llm_provider,
        conversation_repository=conversation_repository,
        processed_repository=processed_repository,
        blacklist_repository=blacklist_repository,
        agent_profile_repository=agent_profile_repository,
    )


def build_customer_text_event(
    provider_event_id: str = "evt-1",
    message_id: str = "wamid-in-1",
) -> webhook_dto.IncomingMessageEventDTO:
    return webhook_dto.IncomingMessageEventDTO(
        provider_event_id=provider_event_id,
        phone_number_id="phone-1",
        whatsapp_user_id="wa-user-1",
        whatsapp_user_name="Jane",
        message_id=message_id,
        message_type="text",
        source="CUSTOMER",
        message_text="hello",
    )


def build_professional_echo_event(
    provider_event_id: str = "echo-1",
    message_id: str = "wamid-out-1",
    message_type: str = "text",
    message_text: str = "professional reply",
) -> webhook_dto.IncomingMessageEventDTO:
    return webhook_dto.IncomingMessageEventDTO(
        provider_event_id=provider_event_id,
        phone_number_id="phone-1",
        whatsapp_user_id="wa-user-1",
        whatsapp_user_name=None,
        message_id=message_id,
        message_type=message_type,
        source="PROFESSIONAL_APP",
        message_text=message_text,
    )


def test_process_payload_creates_conversation_and_outbound_reply() -> None:
    ctx = build_webhook_service(["conversation-1", "in-msg-1", "out-msg-1"])
    ctx.provider.events = [build_customer_text_event()]

    result = ctx.service.process_payload({})

    assert result.status == "processed"
    assert len(ctx.provider.sent_messages) == 1
    assert ctx.provider.sent_messages[0]["text"] == "assistant reply"
    assert len(ctx.llm_provider.calls) == 1
    assert ctx.llm_provider.calls[0].system_prompt.startswith("tenant custom prompt")
    assert "### Runtime Context (Generated by Backend)" in ctx.llm_provider.calls[0].system_prompt

    conversation = ctx.conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    assert conversation.control_mode == "AI"
    messages = ctx.conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 2
    assert ctx.processed_repository.exists("tenant-1", "evt-1")


def test_process_payload_injects_known_patient_context_into_system_prompt() -> None:
    known_patient = patient_entity.Patient(
        tenant_id="tenant-1",
        whatsapp_user_id="wa-user-1",
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        age=29,
        location="Bogota",
        phone="573001112233",
        created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
    )
    ctx = build_webhook_service(
        ["conversation-1", "in-msg-1", "out-msg-1"],
        existing_patient=known_patient,
    )
    ctx.provider.events = [build_customer_text_event()]

    ctx.service.process_payload({})

    assert len(ctx.llm_provider.calls) == 1
    assert "Known patient profile" in ctx.llm_provider.calls[0].system_prompt
    assert "patient_full_name: Jane Doe" in ctx.llm_provider.calls[0].system_prompt
    assert "patient_location: Bogota" in ctx.llm_provider.calls[0].system_prompt


def test_process_payload_dedupes_same_event() -> None:
    ctx = build_webhook_service(["conversation-1", "in-msg-1", "out-msg-1"])
    ctx.provider.events = [build_customer_text_event()]

    ctx.service.process_payload({})
    ctx.service.process_payload({})

    conversation = ctx.conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    messages = ctx.conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 2
    assert len(ctx.provider.sent_messages) == 1


def test_process_payload_dedupes_same_message_id_with_different_event_id() -> None:
    ctx = build_webhook_service(["conversation-1", "in-msg-1", "out-msg-1"])
    ctx.provider.events = [
        build_customer_text_event(provider_event_id="evt-1", message_id="wamid-in-1"),
    ]

    ctx.service.process_payload({})

    ctx.provider.events = [
        build_customer_text_event(provider_event_id="evt-2", message_id="wamid-in-1"),
    ]
    ctx.service.process_payload({})

    conversation = ctx.conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    messages = ctx.conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 2
    assert len(ctx.provider.sent_messages) == 1
    assert ctx.processed_repository.exists("tenant-1", "evt-2")


def test_process_payload_skips_blacklisted_contact_without_creating_conversation() -> None:
    ctx = build_webhook_service(["conversation-1", "in-msg-1", "out-msg-1"])
    ctx.provider.events = [build_customer_text_event(provider_event_id="evt-blacklist")]
    ctx.blacklist_repository.save(
        blacklist_entry_entity.BlacklistEntry(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )

    ctx.service.process_payload({})

    assert len(ctx.llm_provider.calls) == 0
    assert len(ctx.provider.sent_messages) == 0
    conversation = ctx.conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is None
    assert ctx.processed_repository.exists("tenant-1", "evt-blacklist")


def test_process_payload_customer_message_in_human_mode_only_persists_inbound() -> None:
    ctx = build_webhook_service(["conversation-1", "in-msg-1", "professional-msg-1"])
    ctx.provider.events = [
        build_professional_echo_event(
            provider_event_id="evt-professional", message_id="wamid-professional-1"
        ),
        build_customer_text_event(provider_event_id="evt-customer", message_id="wamid-in-1"),
    ]

    ctx.service.process_payload({})

    assert len(ctx.llm_provider.calls) == 0
    assert len(ctx.provider.sent_messages) == 0
    conversation = ctx.conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    assert conversation.control_mode == "HUMAN"
    messages = ctx.conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 2
    assert messages[0].role == "human_agent"
    assert messages[1].role == "user"
    assert ctx.processed_repository.exists("tenant-1", "evt-professional")
    assert ctx.processed_repository.exists("tenant-1", "evt-customer")


def test_process_payload_skips_ai_when_assistant_disabled_globally() -> None:
    ctx = build_webhook_service(["conversation-1", "in-msg-1"])
    now_value = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    ctx.agent_profile_repository.save(
        agent_profile_entity.AgentProfile(
            tenant_id="tenant-1",
            system_prompt="tenant custom prompt",
            assistant_enabled=False,
            updated_at=now_value,
        )
    )
    ctx.provider.events = [build_customer_text_event()]

    ctx.service.process_payload({})

    assert len(ctx.llm_provider.calls) == 0
    assert len(ctx.provider.sent_messages) == 0
    conversation = ctx.conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    assert conversation.control_mode == "AI"
    messages = ctx.conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].direction == "INBOUND"
    assert ctx.processed_repository.exists("tenant-1", "evt-1")


def test_process_payload_professional_echo_creates_conversation_and_sets_human_mode() -> None:
    ctx = build_webhook_service(["conversation-1", "professional-msg-1"])
    ctx.provider.events = [
        build_professional_echo_event(
            provider_event_id="evt-professional", message_id="wamid-professional-1"
        )
    ]

    ctx.service.process_payload({})

    conversation = ctx.conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    assert conversation.control_mode == "HUMAN"
    messages = ctx.conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 1
    assert messages[0].direction == "OUTBOUND"
    assert messages[0].role == "human_agent"
    assert messages[0].content == "professional reply"
    assert ctx.processed_repository.exists("tenant-1", "evt-professional")


def test_process_payload_professional_non_text_echo_persists_marker_and_sets_human_mode() -> None:
    ctx = build_webhook_service(["conversation-1", "professional-msg-1"])
    ctx.provider.events = [
        build_professional_echo_event(
            provider_event_id="evt-professional-img",
            message_id="wamid-professional-img-1",
            message_type="image",
            message_text="[professional_app_non_text:image]",
        )
    ]

    ctx.service.process_payload({})

    conversation = ctx.conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    assert conversation.control_mode == "HUMAN"
    messages = ctx.conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 1
    assert messages[0].role == "human_agent"
    assert messages[0].content == "[professional_app_non_text:image]"
    assert ctx.processed_repository.exists("tenant-1", "evt-professional-img")


def test_process_payload_resumes_ai_after_manual_mode_switch_back_to_ai() -> None:
    ctx = build_webhook_service(
        ["conversation-1", "professional-msg-1", "in-msg-1", "in-msg-2", "out-msg-1"]
    )
    ctx.provider.events = [
        build_professional_echo_event(
            provider_event_id="evt-professional", message_id="wamid-professional-1"
        ),
        build_customer_text_event(provider_event_id="evt-customer-1", message_id="wamid-in-1"),
    ]

    ctx.service.process_payload({})

    conversation = ctx.conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    assert conversation.control_mode == "HUMAN"

    conversation.set_control_mode("AI", datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    ctx.conversation_repository.save_conversation(conversation)
    ctx.provider.events = [
        build_customer_text_event(provider_event_id="evt-customer-2", message_id="wamid-in-2")
    ]

    ctx.service.process_payload({})

    assert len(ctx.llm_provider.calls) == 1
    assert len(ctx.provider.sent_messages) == 1
    refreshed_conversation = ctx.conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert refreshed_conversation is not None
    assert refreshed_conversation.control_mode == "AI"
    messages = ctx.conversation_repository.list_messages("tenant-1", refreshed_conversation.id)
    assert len(messages) == 4
    assert ctx.processed_repository.exists("tenant-1", "evt-customer-2")


def test_process_payload_retries_empty_llm_response_and_succeeds() -> None:
    retry_delays: list[float] = []

    def capture_sleep(seconds: float) -> None:
        retry_delays.append(seconds)

    ctx = build_webhook_service(
        ["conversation-1", "in-msg-1", "out-msg-1"],
        sleep_seconds=capture_sleep,
    )
    ctx.provider.events = [build_customer_text_event()]
    ctx.llm_provider.queued_errors = [
        service_exceptions.ExternalProviderError("gemini returned empty content")
    ]
    ctx.llm_provider.queued_replies = [llm_dto.AgentReplyDTO(content="assistant after retry")]

    ctx.service.process_payload({})

    assert len(ctx.provider.sent_messages) == 1
    assert ctx.provider.sent_messages[0]["text"] == "assistant after retry"
    assert retry_delays == [0.5]
    assert ctx.processed_repository.exists("tenant-1", "evt-1")
    conversation = ctx.conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    messages = ctx.conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 2


def test_process_payload_sends_fallback_after_exhausting_empty_llm_response_retries() -> None:
    retry_delays: list[float] = []

    def capture_sleep(seconds: float) -> None:
        retry_delays.append(seconds)

    ctx = build_webhook_service(
        ["conversation-1", "in-msg-1", "out-msg-1"],
        sleep_seconds=capture_sleep,
    )
    ctx.provider.events = [build_customer_text_event()]
    ctx.llm_provider.queued_errors = [
        service_exceptions.ExternalProviderError("gemini returned empty content"),
        service_exceptions.ExternalProviderError("gemini returned empty content"),
        service_exceptions.ExternalProviderError("gemini returned empty content"),
    ]

    ctx.service.process_payload({})

    assert retry_delays == [0.5, 1.0]
    assert ctx.processed_repository.exists("tenant-1", "evt-1")
    assert len(ctx.provider.sent_messages) == 1
    assert "problema tecnico" in ctx.provider.sent_messages[0]["text"].lower()
    conversation = ctx.conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    messages = ctx.conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 2
    assert messages[0].direction == "INBOUND"
    assert messages[1].direction == "OUTBOUND"


def test_process_payload_sends_fallback_on_llm_failure_and_marks_event_processed() -> None:
    ctx = build_webhook_service(["conversation-1", "in-msg-1", "out-msg-1"])
    ctx.provider.events = [build_customer_text_event()]
    ctx.llm_provider.should_fail = True

    ctx.service.process_payload({})

    assert ctx.processed_repository.exists("tenant-1", "evt-1")
    assert len(ctx.provider.sent_messages) == 1
    assert "dificultad tecnica" in ctx.provider.sent_messages[0]["text"].lower()
    conversation = ctx.conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    messages = ctx.conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 2
    assert messages[0].direction == "INBOUND"
    assert messages[1].direction == "OUTBOUND"


def test_process_payload_logs_blacklist_event(caplog: pytest.LogCaptureFixture) -> None:
    ctx = build_webhook_service(["conversation-1", "in-msg-1", "out-msg-1"])
    ctx.provider.events = [build_customer_text_event(provider_event_id="evt-blacklist")]
    ctx.blacklist_repository.save(
        blacklist_entry_entity.BlacklistEntry(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)

    ctx.service.process_payload({})

    events = [
        record.__dict__.get("event_data", {}).get("event")
        for record in caplog.records
        if isinstance(record.__dict__.get("event_data"), dict)
    ]
    assert "webhook.blacklist_blocked" in events


def test_process_payload_logs_ai_failure(caplog: pytest.LogCaptureFixture) -> None:
    ctx = build_webhook_service(["conversation-1", "in-msg-1", "out-msg-1"])
    ctx.provider.events = [build_customer_text_event()]
    ctx.llm_provider.should_fail = True
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

    ctx.service.process_payload({})

    events = [
        record.__dict__.get("event_data", {}).get("event")
        for record in caplog.records
        if isinstance(record.__dict__.get("event_data"), dict)
    ]
    assert "webhook.ai_reply_failed" in events
    assert "webhook.ai_reply_fallback_sent" in events
