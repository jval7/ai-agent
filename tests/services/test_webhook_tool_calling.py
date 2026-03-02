import datetime

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.blacklist_repository_adapter as blacklist_repository_adapter
import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.google_calendar_connection_repository_adapter as google_calendar_connection_repository_adapter
import src.adapters.outbound.inmemory.processed_webhook_event_repository_adapter as processed_webhook_event_repository_adapter
import src.adapters.outbound.inmemory.scheduling_repository_adapter as scheduling_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.google_calendar_connection as google_calendar_connection_entity
import src.domain.entities.scheduling_request as scheduling_request_entity
import src.domain.entities.scheduling_slot as scheduling_slot_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.services.dto.llm_dto as llm_dto
import src.services.dto.webhook_dto as webhook_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import src.services.use_cases.scheduling_service as scheduling_service
import src.services.use_cases.webhook_service as webhook_service
import tests.fakes.fake_adapters as fake_adapters


def test_webhook_processes_function_call_and_then_sends_text_reply() -> None:
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
    scheduling_repository = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    calendar_connection_repository = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )

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
    calendar_connection_repository.save(
        google_calendar_connection_entity.GoogleCalendarConnection(
            tenant_id="tenant-1",
            professional_user_id="user-1",
            status="CONNECTED",
            calendar_id="primary",
            timezone="America/Bogota",
            access_token="google-access",
            refresh_token="google-refresh",
            token_expires_at=datetime.datetime(2026, 1, 1, 2, 0, tzinfo=datetime.UTC),
            oauth_state=None,
            scope="calendar",
            updated_at=now_value,
            connected_at=now_value,
        )
    )
    agent_profile_repository.save(
        agent_profile_entity.AgentProfile(
            tenant_id="tenant-1",
            system_prompt="tenant custom prompt",
            updated_at=now_value,
        )
    )

    provider = fake_adapters.FakeWhatsappProvider()
    llm_provider = fake_adapters.FakeLlmProvider(reply_content="unused")
    llm_provider.queued_replies = [
        llm_dto.AgentReplyDTO(
            content="",
            function_calls=[
                llm_dto.FunctionCallDTO(
                    name="request_schedule_approval",
                    args={
                        "patient_preference_note": "prefiere tarde",
                    },
                    call_id="call-1",
                )
            ],
        ),
        llm_dto.AgentReplyDTO(content="Perfecto, ya envié tu preferencia al profesional."),
    ]
    id_generator = fake_adapters.SequenceIdGenerator(
        ["conversation-1", "in-msg-1", "req-1", "out-msg-1"]
    )
    clock = fake_adapters.FixedClock(now_value)
    google_provider = fake_adapters.FakeGoogleCalendarProvider()
    google_service = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_connection_repository,
        google_calendar_provider=google_provider,
        id_generator=id_generator,
        clock=clock,
    )
    scheduling_use_case = scheduling_service.SchedulingService(
        scheduling_repository=scheduling_repository,
        conversation_repository=conversation_repository,
        google_calendar_onboarding_service=google_service,
        id_generator=id_generator,
        clock=clock,
    )

    service = webhook_service.WebhookService(
        whatsapp_connection_repository=connection_repository,
        conversation_repository=conversation_repository,
        processed_webhook_event_repository=processed_repository,
        blacklist_repository=blacklist_repository,
        agent_profile_repository=agent_profile_repository,
        scheduling_service=scheduling_use_case,
        llm_provider=llm_provider,
        whatsapp_provider=provider,
        id_generator=id_generator,
        clock=clock,
        default_system_prompt="default prompt",
        context_message_limit=8,
    )
    provider.events = [
        webhook_dto.IncomingMessageEventDTO(
            provider_event_id="evt-1",
            phone_number_id="phone-1",
            whatsapp_user_id="wa-user-1",
            whatsapp_user_name="Jane",
            message_id="wamid-in-1",
            message_type="text",
            source="CUSTOMER",
            message_text="hola quiero una cita",
        )
    ]

    service.process_payload({})

    saved_requests = scheduling_repository.list_requests_by_tenant("tenant-1")
    assert len(saved_requests) == 1
    assert saved_requests[0].status == "AWAITING_PROFESSIONAL_SLOTS"
    assert len(provider.sent_messages) == 1
    assert "envié tu preferencia" in provider.sent_messages[0]["text"]


def test_webhook_confirm_slot_without_ids_auto_resolves_single_active_slot() -> None:
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
    scheduling_repository = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    calendar_connection_repository = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )

    now_value = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    conversation_repository.save_conversation(
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
    scheduling_repository.save_request(
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
                    status="PROPOSED",
                )
            ],
            selected_slot_id=None,
            calendar_event_id=None,
            created_at=now_value,
            updated_at=now_value,
        )
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
            timezone="America/Bogota",
            access_token="google-access",
            refresh_token="google-refresh",
            token_expires_at=datetime.datetime(2026, 1, 1, 2, 0, tzinfo=datetime.UTC),
            oauth_state=None,
            scope="calendar",
            updated_at=now_value,
            connected_at=now_value,
        )
    )
    agent_profile_repository.save(
        agent_profile_entity.AgentProfile(
            tenant_id="tenant-1",
            system_prompt="tenant custom prompt",
            updated_at=now_value,
        )
    )

    provider = fake_adapters.FakeWhatsappProvider()
    llm_provider = fake_adapters.FakeLlmProvider(reply_content="unused")
    llm_provider.queued_replies = [
        llm_dto.AgentReplyDTO(
            content="",
            function_calls=[
                llm_dto.FunctionCallDTO(
                    name="confirm_selected_slot_and_create_event",
                    args={},
                    call_id="call-1",
                )
            ],
        ),
        llm_dto.AgentReplyDTO(content="Perfecto, tu cita quedó confirmada."),
    ]
    id_generator = fake_adapters.SequenceIdGenerator(["in-msg-1", "out-msg-1"])
    clock = fake_adapters.FixedClock(now_value)
    google_provider = fake_adapters.FakeGoogleCalendarProvider()
    google_service = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_connection_repository,
        google_calendar_provider=google_provider,
        id_generator=id_generator,
        clock=clock,
    )
    scheduling_use_case = scheduling_service.SchedulingService(
        scheduling_repository=scheduling_repository,
        conversation_repository=conversation_repository,
        google_calendar_onboarding_service=google_service,
        id_generator=id_generator,
        clock=clock,
    )

    service = webhook_service.WebhookService(
        whatsapp_connection_repository=connection_repository,
        conversation_repository=conversation_repository,
        processed_webhook_event_repository=processed_repository,
        blacklist_repository=blacklist_repository,
        agent_profile_repository=agent_profile_repository,
        scheduling_service=scheduling_use_case,
        llm_provider=llm_provider,
        whatsapp_provider=provider,
        id_generator=id_generator,
        clock=clock,
        default_system_prompt="default prompt",
        context_message_limit=8,
    )
    provider.events = [
        webhook_dto.IncomingMessageEventDTO(
            provider_event_id="evt-1",
            phone_number_id="phone-1",
            whatsapp_user_id="wa-user-1",
            whatsapp_user_name="Jane",
            message_id="wamid-in-1",
            message_type="text",
            source="CUSTOMER",
            message_text="si esta bien",
        )
    ]

    service.process_payload({})

    saved_request = scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "BOOKED"
    assert saved_request.selected_slot_id == "slot-1"
    assert saved_request.calendar_event_id == "event-1"
    assert len(provider.sent_messages) == 1
    assert "confirmada" in provider.sent_messages[0]["text"]


def test_webhook_confirm_slot_without_ids_maps_day_and_time_mention() -> None:
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
    scheduling_repository = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    calendar_connection_repository = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )

    now_value = datetime.datetime(2026, 3, 1, tzinfo=datetime.UTC)
    conversation_repository.save_conversation(
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
    scheduling_repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id="req-1",
            tenant_id="tenant-1",
            conversation_id="conversation-1",
            whatsapp_user_id="wa-user-1",
            request_kind="INITIAL",
            status="AWAITING_PATIENT_CHOICE",
            round_number=1,
            patient_preference_note="prefiere virtual en la manana",
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
                scheduling_slot_entity.SchedulingSlot(
                    id="slot-3",
                    start_at=datetime.datetime(2026, 3, 2, 11, 0, tzinfo=datetime.UTC),
                    end_at=datetime.datetime(2026, 3, 2, 12, 0, tzinfo=datetime.UTC),
                    timezone="UTC",
                    status="PROPOSED",
                ),
            ],
            selected_slot_id=None,
            calendar_event_id=None,
            created_at=now_value,
            updated_at=now_value,
        )
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
            timezone="UTC",
            access_token="google-access",
            refresh_token="google-refresh",
            token_expires_at=datetime.datetime(2026, 3, 1, 2, 0, tzinfo=datetime.UTC),
            oauth_state=None,
            scope="calendar",
            updated_at=now_value,
            connected_at=now_value,
        )
    )
    agent_profile_repository.save(
        agent_profile_entity.AgentProfile(
            tenant_id="tenant-1",
            system_prompt="tenant custom prompt",
            updated_at=now_value,
        )
    )

    provider = fake_adapters.FakeWhatsappProvider()
    llm_provider = fake_adapters.FakeLlmProvider(reply_content="unused")
    llm_provider.queued_replies = [
        llm_dto.AgentReplyDTO(
            content="",
            function_calls=[
                llm_dto.FunctionCallDTO(
                    name="confirm_selected_slot_and_create_event",
                    args={},
                    call_id="call-1",
                )
            ],
        ),
        llm_dto.AgentReplyDTO(content="Perfecto, tu cita quedó confirmada."),
    ]
    id_generator = fake_adapters.SequenceIdGenerator(["in-msg-1", "out-msg-1"])
    clock = fake_adapters.FixedClock(now_value)
    google_provider = fake_adapters.FakeGoogleCalendarProvider()
    google_service = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_connection_repository,
        google_calendar_provider=google_provider,
        id_generator=id_generator,
        clock=clock,
    )
    scheduling_use_case = scheduling_service.SchedulingService(
        scheduling_repository=scheduling_repository,
        conversation_repository=conversation_repository,
        google_calendar_onboarding_service=google_service,
        id_generator=id_generator,
        clock=clock,
    )

    service = webhook_service.WebhookService(
        whatsapp_connection_repository=connection_repository,
        conversation_repository=conversation_repository,
        processed_webhook_event_repository=processed_repository,
        blacklist_repository=blacklist_repository,
        agent_profile_repository=agent_profile_repository,
        scheduling_service=scheduling_use_case,
        llm_provider=llm_provider,
        whatsapp_provider=provider,
        id_generator=id_generator,
        clock=clock,
        default_system_prompt="default prompt",
        context_message_limit=8,
    )
    provider.events = [
        webhook_dto.IncomingMessageEventDTO(
            provider_event_id="evt-1",
            phone_number_id="phone-1",
            whatsapp_user_id="wa-user-1",
            whatsapp_user_name="Jane",
            message_id="wamid-in-1",
            message_type="text",
            source="CUSTOMER",
            message_text="si el 2 a las 8 am",
        )
    ]

    service.process_payload({})

    saved_request = scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "BOOKED"
    assert saved_request.selected_slot_id == "slot-1"
    assert saved_request.calendar_event_id == "event-1"
    assert len(provider.sent_messages) == 1
    assert "confirmada" in provider.sent_messages[0]["text"]


def test_webhook_confirm_slot_retries_network_error_and_handoffs_to_human() -> None:
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
    scheduling_repository = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    calendar_connection_repository = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )

    now_value = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    conversation_repository.save_conversation(
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
    scheduling_repository.save_request(
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
                    status="PROPOSED",
                )
            ],
            selected_slot_id=None,
            calendar_event_id=None,
            created_at=now_value,
            updated_at=now_value,
        )
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
            timezone="America/Bogota",
            access_token="google-access",
            refresh_token="google-refresh",
            token_expires_at=datetime.datetime(2026, 1, 1, 2, 0, tzinfo=datetime.UTC),
            oauth_state=None,
            scope="calendar",
            updated_at=now_value,
            connected_at=now_value,
        )
    )
    agent_profile_repository.save(
        agent_profile_entity.AgentProfile(
            tenant_id="tenant-1",
            system_prompt="tenant custom prompt",
            updated_at=now_value,
        )
    )

    provider = fake_adapters.FakeWhatsappProvider()
    llm_provider = fake_adapters.FakeLlmProvider(reply_content="unused")
    llm_provider.queued_replies = [
        llm_dto.AgentReplyDTO(
            content="",
            function_calls=[
                llm_dto.FunctionCallDTO(
                    name="confirm_selected_slot_and_create_event",
                    args={"request_id": "req-1", "slot_id": "slot-1"},
                    call_id="call-1",
                )
            ],
        ),
        llm_dto.AgentReplyDTO(content="Te paso con el profesional para continuar."),
    ]
    id_generator = fake_adapters.SequenceIdGenerator(["in-msg-1", "out-msg-1"])
    clock = fake_adapters.FixedClock(now_value)
    google_provider = fake_adapters.FakeGoogleCalendarProvider()
    google_provider.busy_interval_errors = [
        service_exceptions.ExternalProviderError("network error calling google calendar"),
        service_exceptions.ExternalProviderError("network error calling google calendar"),
        service_exceptions.ExternalProviderError("network error calling google calendar"),
        service_exceptions.ExternalProviderError("network error calling google calendar"),
    ]
    google_service = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_connection_repository,
        google_calendar_provider=google_provider,
        id_generator=id_generator,
        clock=clock,
    )
    scheduling_use_case = scheduling_service.SchedulingService(
        scheduling_repository=scheduling_repository,
        conversation_repository=conversation_repository,
        google_calendar_onboarding_service=google_service,
        id_generator=id_generator,
        clock=clock,
    )
    retry_delays: list[float] = []

    def capture_sleep(seconds: float) -> None:
        retry_delays.append(seconds)

    service = webhook_service.WebhookService(
        whatsapp_connection_repository=connection_repository,
        conversation_repository=conversation_repository,
        processed_webhook_event_repository=processed_repository,
        blacklist_repository=blacklist_repository,
        agent_profile_repository=agent_profile_repository,
        scheduling_service=scheduling_use_case,
        llm_provider=llm_provider,
        whatsapp_provider=provider,
        id_generator=id_generator,
        clock=clock,
        default_system_prompt="default prompt",
        context_message_limit=8,
        sleep_seconds=capture_sleep,
    )
    provider.events = [
        webhook_dto.IncomingMessageEventDTO(
            provider_event_id="evt-1",
            phone_number_id="phone-1",
            whatsapp_user_id="wa-user-1",
            whatsapp_user_name="Jane",
            message_id="wamid-in-1",
            message_type="text",
            source="CUSTOMER",
            message_text="quiero ese horario",
        )
    ]

    service.process_payload({})

    saved_request = scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "HUMAN_HANDOFF"
    saved_conversation = conversation_repository.get_conversation_by_id(
        "tenant-1",
        "conversation-1",
    )
    assert saved_conversation is not None
    assert saved_conversation.control_mode == "HUMAN"
    assert retry_delays == [1.0, 2.0, 4.0]


def test_webhook_confirm_slot_unknown_error_handoffs_without_retry() -> None:
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
    scheduling_repository = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    calendar_connection_repository = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )

    now_value = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    conversation_repository.save_conversation(
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
    scheduling_repository.save_request(
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
                    status="PROPOSED",
                )
            ],
            selected_slot_id=None,
            calendar_event_id=None,
            created_at=now_value,
            updated_at=now_value,
        )
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
            timezone="America/Bogota",
            access_token="google-access",
            refresh_token="google-refresh",
            token_expires_at=datetime.datetime(2026, 1, 1, 2, 0, tzinfo=datetime.UTC),
            oauth_state=None,
            scope="calendar",
            updated_at=now_value,
            connected_at=now_value,
        )
    )
    agent_profile_repository.save(
        agent_profile_entity.AgentProfile(
            tenant_id="tenant-1",
            system_prompt="tenant custom prompt",
            updated_at=now_value,
        )
    )

    provider = fake_adapters.FakeWhatsappProvider()
    llm_provider = fake_adapters.FakeLlmProvider(reply_content="unused")
    llm_provider.queued_replies = [
        llm_dto.AgentReplyDTO(
            content="",
            function_calls=[
                llm_dto.FunctionCallDTO(
                    name="confirm_selected_slot_and_create_event",
                    args={"request_id": "req-1", "slot_id": "slot-1"},
                    call_id="call-1",
                )
            ],
        ),
        llm_dto.AgentReplyDTO(content="Te paso con el profesional para continuar."),
    ]
    id_generator = fake_adapters.SequenceIdGenerator(["in-msg-1", "out-msg-1"])
    clock = fake_adapters.FixedClock(now_value)
    google_provider = fake_adapters.FakeGoogleCalendarProvider()
    google_provider.busy_interval_errors = [
        service_exceptions.ExternalProviderError("google calendar unexpected provider issue")
    ]
    google_service = google_calendar_onboarding_service.GoogleCalendarOnboardingService(
        google_calendar_connection_repository=calendar_connection_repository,
        google_calendar_provider=google_provider,
        id_generator=id_generator,
        clock=clock,
    )
    scheduling_use_case = scheduling_service.SchedulingService(
        scheduling_repository=scheduling_repository,
        conversation_repository=conversation_repository,
        google_calendar_onboarding_service=google_service,
        id_generator=id_generator,
        clock=clock,
    )
    retry_delays: list[float] = []

    def capture_sleep(seconds: float) -> None:
        retry_delays.append(seconds)

    service = webhook_service.WebhookService(
        whatsapp_connection_repository=connection_repository,
        conversation_repository=conversation_repository,
        processed_webhook_event_repository=processed_repository,
        blacklist_repository=blacklist_repository,
        agent_profile_repository=agent_profile_repository,
        scheduling_service=scheduling_use_case,
        llm_provider=llm_provider,
        whatsapp_provider=provider,
        id_generator=id_generator,
        clock=clock,
        default_system_prompt="default prompt",
        context_message_limit=8,
        sleep_seconds=capture_sleep,
    )
    provider.events = [
        webhook_dto.IncomingMessageEventDTO(
            provider_event_id="evt-1",
            phone_number_id="phone-1",
            whatsapp_user_id="wa-user-1",
            whatsapp_user_name="Jane",
            message_id="wamid-in-1",
            message_type="text",
            source="CUSTOMER",
            message_text="quiero ese horario",
        )
    ]

    service.process_payload({})

    saved_request = scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "HUMAN_HANDOFF"
    saved_conversation = conversation_repository.get_conversation_by_id(
        "tenant-1",
        "conversation-1",
    )
    assert saved_conversation is not None
    assert saved_conversation.control_mode == "HUMAN"
    assert retry_delays == []
