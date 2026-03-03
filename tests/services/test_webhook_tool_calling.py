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
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.google_calendar_connection as google_calendar_connection_entity
import src.domain.entities.message as message_entity
import src.domain.entities.patient as patient_entity
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
    patient_repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
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
                    name="submit_consultation_reason_for_review",
                    args={
                        "consultation_reason": "Ansiedad",
                    },
                    call_id="call-1",
                )
            ],
        ),
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
        patient_repository=patient_repository,
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
    assert saved_requests[0].status == "AWAITING_CONSULTATION_REVIEW"
    assert len(provider.sent_messages) == 1
    assert "dame un momento" in provider.sent_messages[0]["text"].lower()
    assert len(llm_provider.calls) == 1
    tool_names = [tool.name for tool in llm_provider.calls[0].tools]
    assert tool_names == [
        "submit_consultation_reason_for_review",
        "handoff_to_human",
        "cancel_active_scheduling_request",
    ]


def test_webhook_recovers_when_reason_tool_is_called_again_after_approval() -> None:
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
    patient_repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
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
            status="COLLECTING_PREFERENCES",
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
                    name="submit_consultation_reason_for_review",
                    args={
                        "request_id": "req-1",
                        "consultation_reason": "ansiedad en el trabajo",
                    },
                    call_id="call-1",
                )
            ],
        ),
        llm_dto.AgentReplyDTO(
            content="",
            function_calls=[
                llm_dto.FunctionCallDTO(
                    name="request_schedule_approval",
                    args={
                        "request_id": "req-1",
                        "appointment_modality": "PRESENCIAL",
                        "patient_preference_note": "despues de las 4 pm o sabados",
                    },
                    call_id="call-2",
                )
            ],
        ),
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
        patient_repository=patient_repository,
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
            message_text="presencial, despues de las 4 pm o sabados",
        )
    ]

    service.process_payload({})

    saved_request = scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "AWAITING_PROFESSIONAL_SLOTS"
    assert saved_request.patient_preference_note == "despues de las 4 pm o sabados"
    assert (
        len(scheduling_repository.list_requests_by_conversation("tenant-1", "conversation-1")) == 1
    )
    assert len(provider.sent_messages) == 1
    assert "dame un momento" in provider.sent_messages[0]["text"].lower()
    assert len(llm_provider.calls) == 2
    first_call_tool_names = [tool.name for tool in llm_provider.calls[0].tools]
    second_call_tool_names = [tool.name for tool in llm_provider.calls[1].tools]
    assert first_call_tool_names == [
        "request_schedule_approval",
        "handoff_to_human",
        "cancel_active_scheduling_request",
    ]
    assert second_call_tool_names == [
        "request_schedule_approval",
        "handoff_to_human",
        "cancel_active_scheduling_request",
    ]


def test_webhook_waiting_professional_slots_silently_persists_inbound_message() -> None:
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
    patient_repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
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
            status="AWAITING_PROFESSIONAL_SLOTS",
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
        patient_repository=patient_repository,
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
            message_text="mi correo es jane@example.com",
        )
    ]

    service.process_payload({})

    saved_request = scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "AWAITING_PROFESSIONAL_SLOTS"
    assert len(provider.sent_messages) == 0
    assert len(llm_provider.calls) == 1


def test_webhook_waiting_professional_does_not_cancel_on_non_explicit_message() -> None:
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
    patient_repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
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
            status="AWAITING_PROFESSIONAL_SLOTS",
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
                    name="cancel_active_scheduling_request",
                    args={"reason": "ok"},
                    call_id="call-1",
                )
            ],
        ),
        llm_dto.AgentReplyDTO(content="NO"),
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
        patient_repository=patient_repository,
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
            message_text="ok",
        )
    ]

    service.process_payload({})

    saved_request = scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "AWAITING_PROFESSIONAL_SLOTS"
    assert len(provider.sent_messages) == 0
    assert len(llm_provider.calls) == 2


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
    patient_repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
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
            slot_options_map={"1": "slot-1"},
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
        patient_repository=patient_repository,
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
            message_text="1",
        )
    ]

    service.process_payload({})

    saved_request = scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "BOOKED"
    assert saved_request.selected_slot_id == "slot-1"
    assert saved_request.calendar_event_id == "event-1"
    assert google_provider.created_event_summaries == ["Jane Doe/ Psi. Alejandra Escobar"]
    created_patient = patient_repository.get_by_whatsapp_user("tenant-1", "wa-user-1")
    assert created_patient is not None
    assert created_patient.location == "Bogota"
    assert created_patient.email == "jane@example.com"
    assert len(provider.sent_messages) == 1
    assert "confirmada" in provider.sent_messages[0]["text"]


def test_webhook_confirm_slot_resolves_slot_from_previous_user_choice_message() -> None:
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
    patient_repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
    calendar_connection_repository = google_calendar_connection_repository_adapter.InMemoryGoogleCalendarConnectionRepositoryAdapter(
        store
    )

    now_value = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
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
    conversation_repository.save_conversation(conversation)
    scheduling_repository.save_request(
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
                    status="PROPOSED",
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
        conversation_repository.save_message(
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
    conversation_repository.save_conversation(conversation)

    provider = fake_adapters.FakeWhatsappProvider()
    llm_provider = fake_adapters.FakeLlmProvider(reply_content="unused")
    llm_provider.queued_replies = [
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
    id_generator = fake_adapters.SequenceIdGenerator(["in-msg-1", "out-msg-1"])
    clock = fake_adapters.FixedClock(now_value + datetime.timedelta(minutes=20))
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
        patient_repository=patient_repository,
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
            message_text="3",
        )
    ]

    service.process_payload({})

    saved_request = scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "BOOKED"
    assert saved_request.selected_slot_id == "slot-3"
    assert saved_request.calendar_event_id == "event-1"
    assert len(llm_provider.calls) == 2
    assert len(provider.sent_messages) == 1
    assert "confirmada" in provider.sent_messages[0]["text"]


def test_webhook_confirm_slot_uses_existing_patient_context_without_overwriting_profile() -> None:
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
    patient_repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
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
    patient_repository.save(
        patient_entity.Patient(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-user-1",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            age=29,
            consultation_reason="Ansiedad",
            location="Bogota",
            phone="573001112233",
            created_at=now_value,
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
            slot_options_map={"1": "slot-1"},
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
        patient_repository=patient_repository,
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
            message_text="1",
        )
    ]

    service.process_payload({})

    saved_request = scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "BOOKED"
    assert google_provider.created_event_summaries == ["Jane Doe/ Psi. Alejandra Escobar"]
    persisted_patient = patient_repository.get_by_whatsapp_user("tenant-1", "wa-user-1")
    assert persisted_patient is not None
    assert persisted_patient.first_name == "Jane"
    assert persisted_patient.location == "Bogota"


def test_webhook_confirm_slot_requires_patient_location_for_new_patient() -> None:
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
    patient_repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
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
            slot_options_map={"1": "slot-1"},
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
        patient_repository=patient_repository,
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
            message_text="1",
        )
    ]

    service.process_payload({})

    saved_request = scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "AWAITING_PATIENT_CHOICE"
    assert google_provider.created_event_summaries == []
    assert patient_repository.get_by_whatsapp_user("tenant-1", "wa-user-1") is None
    assert "ubicacion" in provider.sent_messages[0]["text"].lower()


def test_webhook_requires_numeric_slot_option_before_continuing() -> None:
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
    patient_repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
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
            slot_options_map={"1": "slot-1", "2": "slot-2", "3": "slot-3"},
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
    llm_provider.queued_replies = []
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
        patient_repository=patient_repository,
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
    assert saved_request.status == "AWAITING_PATIENT_CHOICE"
    assert saved_request.selected_slot_id is None
    assert saved_request.calendar_event_id is None
    assert google_provider.created_event_summaries == []
    assert len(provider.sent_messages) == 1
    assert "solo con el numero" in provider.sent_messages[0]["text"].lower()
    assert "de marzo a las" in provider.sent_messages[0]["text"].lower()
    assert "T08:00:00" not in provider.sent_messages[0]["text"]
    assert len(llm_provider.calls) == 1


def test_webhook_reopens_schedule_request_when_patient_rejects_offered_slots() -> None:
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
    patient_repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
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
                    name="request_schedule_approval",
                    args={
                        "request_id": "req-1",
                        "appointment_modality": "PRESENCIAL",
                        "patient_preference_note": "no puedo ese horario, prefiero despues de las 6 pm",
                    },
                    call_id="call-1",
                )
            ],
        ),
        llm_dto.AgentReplyDTO(content="YES"),
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
        patient_repository=patient_repository,
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
            message_text="no puedo ese horario, tienes despues de las 6 pm?",
        )
    ]

    service.process_payload({})

    saved_request = scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "AWAITING_PROFESSIONAL_SLOTS"
    assert (
        saved_request.patient_preference_note
        == "no puedo ese horario, prefiero despues de las 6 pm"
    )
    assert saved_request.slots == []
    assert saved_request.slot_options_map == {}
    assert len(provider.sent_messages) == 1
    assert "dame un momento" in provider.sent_messages[0]["text"].lower()
    assert len(llm_provider.calls) == 1


def test_webhook_patient_choice_allows_explicit_handoff_to_human() -> None:
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
    patient_repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
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
                    name="handoff_to_human",
                    args={
                        "reason": "patient_requested_human",
                        "summary_for_professional": "El paciente pidio hablar con un humano.",
                    },
                    call_id="call-1",
                )
            ],
        ),
        llm_dto.AgentReplyDTO(content="YES"),
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
        patient_repository=patient_repository,
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
            message_text="transfiereme con un humano",
        )
    ]

    service.process_payload({})

    saved_request = scheduling_repository.get_request_by_id("tenant-1", "req-1")
    assert saved_request is not None
    assert saved_request.status == "HUMAN_HANDOFF"
    conversation = conversation_repository.get_conversation_by_id("tenant-1", "conversation-1")
    assert conversation is not None
    assert conversation.control_mode == "HUMAN"
    assert len(provider.sent_messages) == 1
    assert "te comunico" in provider.sent_messages[0]["text"].lower()
    assert len(llm_provider.calls) == 2


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
    patient_repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
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
            slot_options_map={"1": "slot-1"},
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
        patient_repository=patient_repository,
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
            message_text="1",
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
    patient_repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
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
            slot_options_map={"1": "slot-1"},
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
        patient_repository=patient_repository,
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
            message_text="1",
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
