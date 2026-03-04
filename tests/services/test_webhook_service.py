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
import src.services.dto.llm_dto as llm_dto
import src.services.dto.scheduling_dto as scheduling_dto
import src.services.dto.webhook_dto as webhook_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.webhook_service as webhook_service
import tests.fakes.fake_adapters as fake_adapters

LOGGER_NAME = "src.services.use_cases.webhook_service"


def build_webhook_service(
    id_values: list[str],
    sleep_seconds: typing.Callable[[float], None] | None = None,
    existing_patient: patient_entity.Patient | None = None,
) -> tuple[
    webhook_service.WebhookService,
    fake_adapters.FakeWhatsappProvider,
    fake_adapters.FakeLlmProvider,
    conversation_repository_adapter.InMemoryConversationRepositoryAdapter,
    processed_webhook_event_repository_adapter.InMemoryProcessedWebhookEventRepositoryAdapter,
    blacklist_repository_adapter.InMemoryBlacklistRepositoryAdapter,
]:
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

    service = webhook_service.WebhookService(
        whatsapp_connection_repository=connection_repository,
        conversation_repository=conversation_repository,
        patient_repository=patient_repository,
        processed_webhook_event_repository=processed_repository,
        blacklist_repository=blacklist_repository,
        agent_profile_repository=agent_profile_repository,
        scheduling_service=None,
        llm_provider=llm_provider,
        whatsapp_provider=provider,
        id_generator=id_generator,
        clock=clock,
        default_system_prompt="default prompt",
        context_message_limit=8,
        sleep_seconds=sleep_seconds,
    )

    return (
        service,
        provider,
        llm_provider,
        conversation_repository,
        processed_repository,
        blacklist_repository,
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


def build_owner_echo_event(
    provider_event_id: str = "echo-1",
    message_id: str = "wamid-out-1",
    message_type: str = "text",
    message_text: str = "owner reply",
) -> webhook_dto.IncomingMessageEventDTO:
    return webhook_dto.IncomingMessageEventDTO(
        provider_event_id=provider_event_id,
        phone_number_id="phone-1",
        whatsapp_user_id="wa-user-1",
        whatsapp_user_name=None,
        message_id=message_id,
        message_type=message_type,
        source="OWNER_APP",
        message_text=message_text,
    )


def test_process_payload_creates_conversation_and_outbound_reply() -> None:
    (
        service,
        provider,
        llm_provider,
        conversation_repository,
        processed_repository,
        _,
    ) = build_webhook_service(["conversation-1", "in-msg-1", "out-msg-1"])
    provider.events = [build_customer_text_event()]

    result = service.process_payload({})

    assert result.status == "processed"
    assert len(provider.sent_messages) == 1
    assert provider.sent_messages[0]["text"] == "assistant reply"
    assert len(llm_provider.calls) == 1
    assert llm_provider.calls[0].system_prompt.startswith("tenant custom prompt")
    assert "### Runtime Context (Generated by Backend)" in llm_provider.calls[0].system_prompt

    conversation = conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    assert conversation.control_mode == "AI"
    messages = conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 2
    assert processed_repository.exists("tenant-1", "evt-1")


def test_process_payload_injects_known_patient_context_into_system_prompt() -> None:
    known_patient = patient_entity.Patient(
        tenant_id="tenant-1",
        whatsapp_user_id="wa-user-1",
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        age=29,
        consultation_reason="Ansiedad",
        location="Bogota",
        phone="573001112233",
        created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
    )
    (
        service,
        provider,
        llm_provider,
        _,
        _,
        _,
    ) = build_webhook_service(
        ["conversation-1", "in-msg-1", "out-msg-1"],
        existing_patient=known_patient,
    )
    provider.events = [build_customer_text_event()]

    service.process_payload({})

    assert len(llm_provider.calls) == 1
    assert "Known patient profile" in llm_provider.calls[0].system_prompt
    assert "patient_full_name: Jane Doe" in llm_provider.calls[0].system_prompt
    assert "patient_location: Bogota" in llm_provider.calls[0].system_prompt


def test_process_payload_dedupes_same_event() -> None:
    service, provider, _, conversation_repository, _, _ = build_webhook_service(
        ["conversation-1", "in-msg-1", "out-msg-1"]
    )
    provider.events = [build_customer_text_event()]

    service.process_payload({})
    service.process_payload({})

    conversation = conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    messages = conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 2
    assert len(provider.sent_messages) == 1


def test_process_payload_dedupes_same_message_id_with_different_event_id() -> None:
    (
        service,
        provider,
        _,
        conversation_repository,
        processed_repository,
        _,
    ) = build_webhook_service(["conversation-1", "in-msg-1", "out-msg-1"])
    provider.events = [
        build_customer_text_event(provider_event_id="evt-1", message_id="wamid-in-1"),
    ]

    service.process_payload({})

    provider.events = [
        build_customer_text_event(provider_event_id="evt-2", message_id="wamid-in-1"),
    ]
    service.process_payload({})

    conversation = conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    messages = conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 2
    assert len(provider.sent_messages) == 1
    assert processed_repository.exists("tenant-1", "evt-2")


def test_process_payload_skips_blacklisted_contact_without_creating_conversation() -> None:
    (
        service,
        provider,
        llm_provider,
        conversation_repository,
        processed_repository,
        blacklist_repository,
    ) = build_webhook_service(["conversation-1", "in-msg-1", "out-msg-1"])
    provider.events = [build_customer_text_event(provider_event_id="evt-blacklist")]
    blacklist_repository.save(
        blacklist_entry_entity.BlacklistEntry(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )

    service.process_payload({})

    assert len(llm_provider.calls) == 0
    assert len(provider.sent_messages) == 0
    conversation = conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is None
    assert processed_repository.exists("tenant-1", "evt-blacklist")


def test_process_payload_customer_message_in_human_mode_only_persists_inbound() -> None:
    (
        service,
        provider,
        llm_provider,
        conversation_repository,
        processed_repository,
        _,
    ) = build_webhook_service(["conversation-1", "in-msg-1", "owner-msg-1"])
    provider.events = [
        build_owner_echo_event(provider_event_id="evt-owner", message_id="wamid-owner-1"),
        build_customer_text_event(provider_event_id="evt-customer", message_id="wamid-in-1"),
    ]

    service.process_payload({})

    assert len(llm_provider.calls) == 0
    assert len(provider.sent_messages) == 0
    conversation = conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    assert conversation.control_mode == "HUMAN"
    messages = conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 2
    assert messages[0].role == "human_agent"
    assert messages[1].role == "user"
    assert processed_repository.exists("tenant-1", "evt-owner")
    assert processed_repository.exists("tenant-1", "evt-customer")


def test_process_payload_owner_echo_creates_conversation_and_sets_human_mode() -> None:
    (
        service,
        provider,
        _,
        conversation_repository,
        processed_repository,
        _,
    ) = build_webhook_service(["conversation-1", "owner-msg-1"])
    provider.events = [
        build_owner_echo_event(provider_event_id="evt-owner", message_id="wamid-owner-1")
    ]

    service.process_payload({})

    conversation = conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    assert conversation.control_mode == "HUMAN"
    messages = conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 1
    assert messages[0].direction == "OUTBOUND"
    assert messages[0].role == "human_agent"
    assert messages[0].content == "owner reply"
    assert processed_repository.exists("tenant-1", "evt-owner")


def test_process_payload_owner_non_text_echo_persists_marker_and_sets_human_mode() -> None:
    (
        service,
        provider,
        _,
        conversation_repository,
        processed_repository,
        _,
    ) = build_webhook_service(["conversation-1", "owner-msg-1"])
    provider.events = [
        build_owner_echo_event(
            provider_event_id="evt-owner-img",
            message_id="wamid-owner-img-1",
            message_type="image",
            message_text="[owner_app_non_text:image]",
        )
    ]

    service.process_payload({})

    conversation = conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    assert conversation.control_mode == "HUMAN"
    messages = conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 1
    assert messages[0].role == "human_agent"
    assert messages[0].content == "[owner_app_non_text:image]"
    assert processed_repository.exists("tenant-1", "evt-owner-img")


def test_process_payload_resumes_ai_after_manual_mode_switch_back_to_ai() -> None:
    (
        service,
        provider,
        llm_provider,
        conversation_repository,
        processed_repository,
        _,
    ) = build_webhook_service(
        ["conversation-1", "owner-msg-1", "in-msg-1", "in-msg-2", "out-msg-1"]
    )
    provider.events = [
        build_owner_echo_event(provider_event_id="evt-owner", message_id="wamid-owner-1"),
        build_customer_text_event(provider_event_id="evt-customer-1", message_id="wamid-in-1"),
    ]

    service.process_payload({})

    conversation = conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    assert conversation.control_mode == "HUMAN"

    conversation.set_control_mode("AI", datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    conversation_repository.save_conversation(conversation)
    provider.events = [
        build_customer_text_event(provider_event_id="evt-customer-2", message_id="wamid-in-2")
    ]

    service.process_payload({})

    assert len(llm_provider.calls) == 1
    assert len(provider.sent_messages) == 1
    refreshed_conversation = conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert refreshed_conversation is not None
    assert refreshed_conversation.control_mode == "AI"
    messages = conversation_repository.list_messages("tenant-1", refreshed_conversation.id)
    assert len(messages) == 4
    assert processed_repository.exists("tenant-1", "evt-customer-2")


def test_process_payload_retries_empty_llm_response_and_succeeds() -> None:
    retry_delays: list[float] = []

    def capture_sleep(seconds: float) -> None:
        retry_delays.append(seconds)

    (
        service,
        provider,
        llm_provider,
        conversation_repository,
        processed_repository,
        _,
    ) = build_webhook_service(
        ["conversation-1", "in-msg-1", "out-msg-1"],
        sleep_seconds=capture_sleep,
    )
    provider.events = [build_customer_text_event()]
    llm_provider.queued_errors = [
        service_exceptions.ExternalProviderError("gemini returned empty content")
    ]
    llm_provider.queued_replies = [llm_dto.AgentReplyDTO(content="assistant after retry")]

    service.process_payload({})

    assert len(provider.sent_messages) == 1
    assert provider.sent_messages[0]["text"] == "assistant after retry"
    assert retry_delays == [0.5]
    assert processed_repository.exists("tenant-1", "evt-1")
    conversation = conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    messages = conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 2


def test_process_payload_sends_fallback_after_exhausting_empty_llm_response_retries() -> None:
    retry_delays: list[float] = []

    def capture_sleep(seconds: float) -> None:
        retry_delays.append(seconds)

    (
        service,
        provider,
        llm_provider,
        conversation_repository,
        processed_repository,
        _,
    ) = build_webhook_service(
        ["conversation-1", "in-msg-1", "out-msg-1"],
        sleep_seconds=capture_sleep,
    )
    provider.events = [build_customer_text_event()]
    llm_provider.queued_errors = [
        service_exceptions.ExternalProviderError("gemini returned empty content"),
        service_exceptions.ExternalProviderError("gemini returned empty content"),
        service_exceptions.ExternalProviderError("gemini returned empty content"),
    ]

    service.process_payload({})

    assert retry_delays == [0.5, 1.0]
    assert processed_repository.exists("tenant-1", "evt-1")
    assert len(provider.sent_messages) == 1
    assert "problema tecnico" in provider.sent_messages[0]["text"].lower()
    conversation = conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    messages = conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 2
    assert messages[0].direction == "INBOUND"
    assert messages[1].direction == "OUTBOUND"


def test_process_payload_sends_fallback_on_llm_failure_and_marks_event_processed() -> None:
    (
        service,
        provider,
        llm_provider,
        conversation_repository,
        processed_repository,
        _,
    ) = build_webhook_service(["conversation-1", "in-msg-1", "out-msg-1"])
    provider.events = [build_customer_text_event()]
    llm_provider.should_fail = True

    service.process_payload({})

    assert processed_repository.exists("tenant-1", "evt-1")
    assert len(provider.sent_messages) == 1
    assert "dificultad tecnica" in provider.sent_messages[0]["text"].lower()
    conversation = conversation_repository.get_conversation_by_whatsapp_user(
        "tenant-1", "wa-user-1"
    )
    assert conversation is not None
    messages = conversation_repository.list_messages("tenant-1", conversation.id)
    assert len(messages) == 2
    assert messages[0].direction == "INBOUND"
    assert messages[1].direction == "OUTBOUND"


def test_process_payload_logs_blacklist_event(caplog: pytest.LogCaptureFixture) -> None:
    (
        service,
        provider,
        _,
        _,
        _,
        blacklist_repository,
    ) = build_webhook_service(["conversation-1", "in-msg-1", "out-msg-1"])
    provider.events = [build_customer_text_event(provider_event_id="evt-blacklist")]
    blacklist_repository.save(
        blacklist_entry_entity.BlacklistEntry(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)

    service.process_payload({})

    events = [
        record.__dict__.get("event_data", {}).get("event")
        for record in caplog.records
        if isinstance(record.__dict__.get("event_data"), dict)
    ]
    assert "webhook.blacklist_blocked" in events


def test_process_payload_logs_ai_failure(caplog: pytest.LogCaptureFixture) -> None:
    service, provider, llm_provider, _, _, _ = build_webhook_service(
        ["conversation-1", "in-msg-1", "out-msg-1"]
    )
    provider.events = [build_customer_text_event()]
    llm_provider.should_fail = True
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

    service.process_payload({})

    events = [
        record.__dict__.get("event_data", {}).get("event")
        for record in caplog.records
        if isinstance(record.__dict__.get("event_data"), dict)
    ]
    assert "webhook.ai_reply_failed" in events
    assert "webhook.ai_reply_fallback_sent" in events


def test_compute_missing_confirmation_fields_does_not_require_phone_with_whatsapp_id() -> None:
    service, _, _, _, _, _ = build_webhook_service(["conversation-1"])
    request = scheduling_dto.SchedulingRequestSummaryDTO(
        request_id="req-1",
        conversation_id="conversation-1",
        whatsapp_user_id="573127457050",
        request_kind="INITIAL",
        status="AWAITING_PATIENT_CHOICE",
        round_number=1,
        patient_preference_note="despues de las 4 pm",
        rejection_summary=None,
        professional_note=None,
        patient_first_name="Jhon",
        patient_last_name="Valderrama",
        patient_age=33,
        consultation_reason="ansiedad",
        consultation_details=None,
        appointment_modality="VIRTUAL",
        patient_location="Cali",
        slot_options_map={"1": "slot-1"},
        selected_slot_id="slot-1",
        calendar_event_id=None,
        created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        slots=[],
    )

    missing_fields = service._compute_missing_confirmation_fields(
        request=request,
        known_patient=None,
    )

    assert "patient_email" in missing_fields
    assert "patient_phone" not in missing_fields
