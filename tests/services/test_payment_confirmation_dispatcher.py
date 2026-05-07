import datetime

import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.scheduling_repository_adapter as scheduling_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.message as message_entity
import src.domain.entities.scheduling_request as scheduling_request_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.domain.entities.whatsapp_user as whatsapp_user_entity
import src.services.exceptions as service_exceptions
import src.services.use_cases.payment_confirmation_dispatcher as dispatcher
import tests.fakes.fake_adapters as fake_adapters

TENANT_ID = "tenant-1"
WHATSAPP_USER_ID = "wa-user-1"
CONVERSATION_ID = "conv-1"
NOW = datetime.datetime(2026, 5, 4, 12, 0, tzinfo=datetime.UTC)


def _build_repos() -> tuple[
    conversation_repository_adapter.InMemoryConversationRepositoryAdapter,
    scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
    whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter,
]:
    store = in_memory_store.InMemoryStore()
    conversation_repository = conversation_repository_adapter.InMemoryConversationRepositoryAdapter(
        store
    )
    scheduling_repository = scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter(store)
    whatsapp_connection_repository = (
        whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter(store)
    )
    return conversation_repository, scheduling_repository, whatsapp_connection_repository


def _seed_conversation(
    repository: conversation_repository_adapter.InMemoryConversationRepositoryAdapter,
    *,
    inbound_minutes_ago: int | None,
) -> None:
    repository.save_whatsapp_user(
        whatsapp_user_entity.WhatsappUser(
            id=WHATSAPP_USER_ID,
            tenant_id=TENANT_ID,
            display_name="Paciente Test",
            created_at=NOW - datetime.timedelta(days=2),
        )
    )
    repository.save_conversation(
        conversation_entity.Conversation(
            id=CONVERSATION_ID,
            tenant_id=TENANT_ID,
            whatsapp_user_id=WHATSAPP_USER_ID,
            started_at=NOW - datetime.timedelta(days=1),
            updated_at=NOW - datetime.timedelta(hours=1),
            last_message_preview="hola",
            message_ids=[],
            control_mode="AI",
        )
    )
    if inbound_minutes_ago is not None:
        repository.save_message(
            message_entity.Message(
                id="msg-1",
                conversation_id=CONVERSATION_ID,
                tenant_id=TENANT_ID,
                direction="INBOUND",
                role="user",
                content="hola",
                provider_message_id="provider-msg-1",
                created_at=NOW - datetime.timedelta(minutes=inbound_minutes_ago),
            )
        )


def _seed_connection(
    repository: whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter,
    *,
    access_token: str | None,
    phone_number_id: str | None,
) -> None:
    repository.save(
        whatsapp_connection_entity.WhatsappConnection(
            tenant_id=TENANT_ID,
            phone_number_id=phone_number_id,
            business_account_id="waba-1",
            access_token=access_token,
            status="CONNECTED",
            embedded_signup_state=None,
            updated_at=NOW,
        )
    )


def _seed_open_request(
    repository: scheduling_repository_adapter.InMemorySchedulingRepositoryAdapter,
    *,
    request_id: str,
    source_appointment_id: str | None,
    status: str = "AWAITING_PAYMENT_CONFIRMATION",
) -> None:
    repository.save_request(
        scheduling_request_entity.SchedulingRequest(
            id=request_id,
            tenant_id=TENANT_ID,
            conversation_id=CONVERSATION_ID,
            whatsapp_user_id=WHATSAPP_USER_ID,
            request_kind="INITIAL",
            status=status,  # type: ignore[arg-type]
            round_number=1,
            patient_preference_note=None,
            rejection_summary=None,
            professional_note=None,
            slots=[],
            slot_options_map={},
            selected_slot_id=None,
            calendar_event_id=None,
            source_appointment_id=source_appointment_id,
            created_at=NOW - datetime.timedelta(hours=2),
            updated_at=NOW - datetime.timedelta(hours=2),
        )
    )


def test_no_op_when_conversation_does_not_exist() -> None:
    conversation_repo, scheduling_repo, connection_repo = _build_repos()
    whatsapp_provider = fake_adapters.FakeWhatsappProvider()
    id_generator = fake_adapters.SequenceIdGenerator(["msg-out-1"])
    clock = fake_adapters.FixedClock(NOW)

    dispatcher.confirm_payment_in_chat_if_open(
        tenant_id=TENANT_ID,
        whatsapp_user_id=WHATSAPP_USER_ID,
        patient_first_name="Ana",
        source_appointment_id=None,
        now_value=NOW,
        conversation_repository=conversation_repo,
        whatsapp_connection_repository=connection_repo,
        whatsapp_provider=whatsapp_provider,
        id_generator=id_generator,
        clock=clock,
        scheduling_repository=scheduling_repo,
    )

    assert whatsapp_provider.sent_messages == []


def test_sends_text_and_archives_when_inbound_within_24h() -> None:
    conversation_repo, scheduling_repo, connection_repo = _build_repos()
    _seed_conversation(conversation_repo, inbound_minutes_ago=60)
    _seed_connection(connection_repo, access_token="token-1", phone_number_id="phone-1")
    whatsapp_provider = fake_adapters.FakeWhatsappProvider()
    id_generator = fake_adapters.SequenceIdGenerator(["msg-out-1"])
    clock = fake_adapters.FixedClock(NOW)

    dispatcher.confirm_payment_in_chat_if_open(
        tenant_id=TENANT_ID,
        whatsapp_user_id=WHATSAPP_USER_ID,
        patient_first_name="Ana",
        source_appointment_id=None,
        now_value=NOW,
        conversation_repository=conversation_repo,
        whatsapp_connection_repository=connection_repo,
        whatsapp_provider=whatsapp_provider,
        id_generator=id_generator,
        clock=clock,
        scheduling_repository=scheduling_repo,
    )

    assert len(whatsapp_provider.sent_messages) == 1
    sent = whatsapp_provider.sent_messages[0]
    assert sent["whatsapp_user_id"] == WHATSAPP_USER_ID
    assert "Ana" in sent["text"]
    assert "pago fue confirmado" in sent["text"]

    conversation = conversation_repo.get_conversation_by_whatsapp_user(TENANT_ID, WHATSAPP_USER_ID)
    assert conversation is not None
    assert conversation.message_ids == []
    assert len(conversation.subsessions) == 1
    assert conversation.subsessions[0].archived_reason == "MANUAL_CLOSE"


def test_falls_back_to_paciente_when_first_name_missing() -> None:
    conversation_repo, scheduling_repo, connection_repo = _build_repos()
    _seed_conversation(conversation_repo, inbound_minutes_ago=10)
    _seed_connection(connection_repo, access_token="token-1", phone_number_id="phone-1")
    whatsapp_provider = fake_adapters.FakeWhatsappProvider()
    id_generator = fake_adapters.SequenceIdGenerator(["msg-out-1"])
    clock = fake_adapters.FixedClock(NOW)

    dispatcher.confirm_payment_in_chat_if_open(
        tenant_id=TENANT_ID,
        whatsapp_user_id=WHATSAPP_USER_ID,
        patient_first_name=None,
        source_appointment_id=None,
        now_value=NOW,
        conversation_repository=conversation_repo,
        whatsapp_connection_repository=connection_repo,
        whatsapp_provider=whatsapp_provider,
        id_generator=id_generator,
        clock=clock,
        scheduling_repository=scheduling_repo,
    )

    assert len(whatsapp_provider.sent_messages) == 1
    assert "Paciente" in whatsapp_provider.sent_messages[0]["text"]


def test_skips_send_when_inbound_outside_24h_but_still_archives() -> None:
    conversation_repo, scheduling_repo, connection_repo = _build_repos()
    _seed_conversation(conversation_repo, inbound_minutes_ago=24 * 60 + 10)
    _seed_connection(connection_repo, access_token="token-1", phone_number_id="phone-1")
    whatsapp_provider = fake_adapters.FakeWhatsappProvider()
    id_generator = fake_adapters.SequenceIdGenerator([])
    clock = fake_adapters.FixedClock(NOW)

    dispatcher.confirm_payment_in_chat_if_open(
        tenant_id=TENANT_ID,
        whatsapp_user_id=WHATSAPP_USER_ID,
        patient_first_name="Ana",
        source_appointment_id=None,
        now_value=NOW,
        conversation_repository=conversation_repo,
        whatsapp_connection_repository=connection_repo,
        whatsapp_provider=whatsapp_provider,
        id_generator=id_generator,
        clock=clock,
        scheduling_repository=scheduling_repo,
    )

    assert whatsapp_provider.sent_messages == []
    conversation = conversation_repo.get_conversation_by_whatsapp_user(TENANT_ID, WHATSAPP_USER_ID)
    assert conversation is not None
    assert len(conversation.subsessions) == 1


def test_skips_send_when_no_inbound_messages() -> None:
    conversation_repo, scheduling_repo, connection_repo = _build_repos()
    _seed_conversation(conversation_repo, inbound_minutes_ago=None)
    _seed_connection(connection_repo, access_token="token-1", phone_number_id="phone-1")
    whatsapp_provider = fake_adapters.FakeWhatsappProvider()
    id_generator = fake_adapters.SequenceIdGenerator([])
    clock = fake_adapters.FixedClock(NOW)

    dispatcher.confirm_payment_in_chat_if_open(
        tenant_id=TENANT_ID,
        whatsapp_user_id=WHATSAPP_USER_ID,
        patient_first_name="Ana",
        source_appointment_id=None,
        now_value=NOW,
        conversation_repository=conversation_repo,
        whatsapp_connection_repository=connection_repo,
        whatsapp_provider=whatsapp_provider,
        id_generator=id_generator,
        clock=clock,
        scheduling_repository=scheduling_repo,
    )

    assert whatsapp_provider.sent_messages == []


def test_skips_send_when_connection_missing_token_but_archives() -> None:
    conversation_repo, scheduling_repo, connection_repo = _build_repos()
    _seed_conversation(conversation_repo, inbound_minutes_ago=10)
    _seed_connection(connection_repo, access_token=None, phone_number_id="phone-1")
    whatsapp_provider = fake_adapters.FakeWhatsappProvider()
    id_generator = fake_adapters.SequenceIdGenerator([])
    clock = fake_adapters.FixedClock(NOW)

    dispatcher.confirm_payment_in_chat_if_open(
        tenant_id=TENANT_ID,
        whatsapp_user_id=WHATSAPP_USER_ID,
        patient_first_name="Ana",
        source_appointment_id=None,
        now_value=NOW,
        conversation_repository=conversation_repo,
        whatsapp_connection_repository=connection_repo,
        whatsapp_provider=whatsapp_provider,
        id_generator=id_generator,
        clock=clock,
        scheduling_repository=scheduling_repo,
    )

    assert whatsapp_provider.sent_messages == []
    conversation = conversation_repo.get_conversation_by_whatsapp_user(TENANT_ID, WHATSAPP_USER_ID)
    assert conversation is not None
    assert len(conversation.subsessions) == 1


class _FailingWhatsappProvider(fake_adapters.FakeWhatsappProvider):
    def send_text_message(
        self,
        access_token: str,
        phone_number_id: str,
        whatsapp_user_id: str,
        text: str,
    ) -> str:
        del access_token, phone_number_id, whatsapp_user_id, text
        raise service_exceptions.ExternalProviderError("simulated meta failure")


def test_swallows_send_failure_and_still_archives() -> None:
    conversation_repo, scheduling_repo, connection_repo = _build_repos()
    _seed_conversation(conversation_repo, inbound_minutes_ago=10)
    _seed_connection(connection_repo, access_token="token-1", phone_number_id="phone-1")
    whatsapp_provider = _FailingWhatsappProvider()
    id_generator = fake_adapters.SequenceIdGenerator([])
    clock = fake_adapters.FixedClock(NOW)

    dispatcher.confirm_payment_in_chat_if_open(
        tenant_id=TENANT_ID,
        whatsapp_user_id=WHATSAPP_USER_ID,
        patient_first_name="Ana",
        source_appointment_id=None,
        now_value=NOW,
        conversation_repository=conversation_repo,
        whatsapp_connection_repository=connection_repo,
        whatsapp_provider=whatsapp_provider,
        id_generator=id_generator,
        clock=clock,
        scheduling_repository=scheduling_repo,
    )

    conversation = conversation_repo.get_conversation_by_whatsapp_user(TENANT_ID, WHATSAPP_USER_ID)
    assert conversation is not None
    assert len(conversation.subsessions) == 1


def test_closes_open_synthetic_request_matching_source_appointment() -> None:
    conversation_repo, scheduling_repo, connection_repo = _build_repos()
    _seed_conversation(conversation_repo, inbound_minutes_ago=10)
    _seed_connection(connection_repo, access_token="token-1", phone_number_id="phone-1")
    _seed_open_request(
        scheduling_repo,
        request_id="req-match",
        source_appointment_id="appt-123",
    )
    _seed_open_request(
        scheduling_repo,
        request_id="req-other",
        source_appointment_id="appt-other",
    )
    whatsapp_provider = fake_adapters.FakeWhatsappProvider()
    id_generator = fake_adapters.SequenceIdGenerator(["msg-out-1"])
    clock = fake_adapters.FixedClock(NOW)

    dispatcher.confirm_payment_in_chat_if_open(
        tenant_id=TENANT_ID,
        whatsapp_user_id=WHATSAPP_USER_ID,
        patient_first_name="Ana",
        source_appointment_id="appt-123",
        now_value=NOW,
        conversation_repository=conversation_repo,
        whatsapp_connection_repository=connection_repo,
        whatsapp_provider=whatsapp_provider,
        id_generator=id_generator,
        clock=clock,
        scheduling_repository=scheduling_repo,
    )

    matching = scheduling_repo.get_request_by_id(TENANT_ID, "req-match")
    other = scheduling_repo.get_request_by_id(TENANT_ID, "req-other")
    assert matching is not None
    assert matching.status == "SESSION_CLOSED"
    assert matching.professional_note == "closed_by_payment_confirmation"
    assert other is not None
    assert other.status == "AWAITING_PAYMENT_CONFIRMATION"


def test_does_not_close_request_when_scheduling_repository_missing() -> None:
    conversation_repo, scheduling_repo, connection_repo = _build_repos()
    _seed_conversation(conversation_repo, inbound_minutes_ago=10)
    _seed_connection(connection_repo, access_token="token-1", phone_number_id="phone-1")
    _seed_open_request(
        scheduling_repo,
        request_id="req-match",
        source_appointment_id="appt-123",
    )
    whatsapp_provider = fake_adapters.FakeWhatsappProvider()
    id_generator = fake_adapters.SequenceIdGenerator(["msg-out-1"])
    clock = fake_adapters.FixedClock(NOW)

    dispatcher.confirm_payment_in_chat_if_open(
        tenant_id=TENANT_ID,
        whatsapp_user_id=WHATSAPP_USER_ID,
        patient_first_name="Ana",
        source_appointment_id="appt-123",
        now_value=NOW,
        conversation_repository=conversation_repo,
        whatsapp_connection_repository=connection_repo,
        whatsapp_provider=whatsapp_provider,
        id_generator=id_generator,
        clock=clock,
        scheduling_repository=None,
    )

    untouched = scheduling_repo.get_request_by_id(TENANT_ID, "req-match")
    assert untouched is not None
    assert untouched.status == "AWAITING_PAYMENT_CONFIRMATION"


def test_does_not_close_request_when_source_appointment_id_missing() -> None:
    conversation_repo, scheduling_repo, connection_repo = _build_repos()
    _seed_conversation(conversation_repo, inbound_minutes_ago=10)
    _seed_connection(connection_repo, access_token="token-1", phone_number_id="phone-1")
    _seed_open_request(
        scheduling_repo,
        request_id="req-match",
        source_appointment_id="appt-123",
    )
    whatsapp_provider = fake_adapters.FakeWhatsappProvider()
    id_generator = fake_adapters.SequenceIdGenerator(["msg-out-1"])
    clock = fake_adapters.FixedClock(NOW)

    dispatcher.confirm_payment_in_chat_if_open(
        tenant_id=TENANT_ID,
        whatsapp_user_id=WHATSAPP_USER_ID,
        patient_first_name="Ana",
        source_appointment_id=None,
        now_value=NOW,
        conversation_repository=conversation_repo,
        whatsapp_connection_repository=connection_repo,
        whatsapp_provider=whatsapp_provider,
        id_generator=id_generator,
        clock=clock,
        scheduling_repository=scheduling_repo,
    )

    untouched = scheduling_repo.get_request_by_id(TENANT_ID, "req-match")
    assert untouched is not None
    assert untouched.status == "AWAITING_PAYMENT_CONFIRMATION"


def test_skips_already_closed_request_with_matching_source() -> None:
    conversation_repo, scheduling_repo, connection_repo = _build_repos()
    _seed_conversation(conversation_repo, inbound_minutes_ago=10)
    _seed_connection(connection_repo, access_token="token-1", phone_number_id="phone-1")
    _seed_open_request(
        scheduling_repo,
        request_id="req-cancelled",
        source_appointment_id="appt-123",
        status="CANCELLED",
    )
    whatsapp_provider = fake_adapters.FakeWhatsappProvider()
    id_generator = fake_adapters.SequenceIdGenerator(["msg-out-1"])
    clock = fake_adapters.FixedClock(NOW)

    dispatcher.confirm_payment_in_chat_if_open(
        tenant_id=TENANT_ID,
        whatsapp_user_id=WHATSAPP_USER_ID,
        patient_first_name="Ana",
        source_appointment_id="appt-123",
        now_value=NOW,
        conversation_repository=conversation_repo,
        whatsapp_connection_repository=connection_repo,
        whatsapp_provider=whatsapp_provider,
        id_generator=id_generator,
        clock=clock,
        scheduling_repository=scheduling_repo,
    )

    untouched = scheduling_repo.get_request_by_id(TENANT_ID, "req-cancelled")
    assert untouched is not None
    assert untouched.status == "CANCELLED"
