import datetime

import src.domain.entities.conversation as conversation_entity
import src.domain.entities.message as message_entity

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
_LATER = datetime.datetime(2026, 1, 1, 1, tzinfo=datetime.UTC)


def _build_conversation(
    *,
    control_mode: str = "AI",
    messages: list[message_entity.Message] | None = None,
) -> conversation_entity.Conversation:
    msgs = messages or []
    return conversation_entity.Conversation(
        id="conv-1",
        tenant_id="tenant-1",
        whatsapp_user_id="wa-1",
        started_at=_NOW,
        updated_at=_NOW,
        last_message_preview="active" if msgs else None,
        message_ids=[m.id for m in msgs],
        messages=msgs,
        control_mode=control_mode,  # type: ignore[arg-type]
    )


def _build_message(role: str = "user", direction: str = "INBOUND") -> message_entity.Message:
    return message_entity.Message(
        id="msg-1",
        conversation_id="conv-1",
        tenant_id="tenant-1",
        direction=direction,  # type: ignore[arg-type]
        role=role,  # type: ignore[arg-type]
        content="hola",
        provider_message_id="prov-1",
        created_at=_NOW,
    )


def test_archive_manual_close_resets_control_mode_to_ai_with_messages() -> None:
    """Closing a session that was in HUMAN flips it back to AI, so the next
    incoming message reopens the conversation with the bot in control."""
    msg = _build_message()
    conversation = _build_conversation(control_mode="HUMAN", messages=[msg])

    conversation.archive_manual_close(messages=[msg], now=_LATER)

    assert conversation.control_mode == "AI"
    assert conversation.last_message_preview is None
    assert len(conversation.subsessions) == 1


def test_archive_manual_close_resets_control_mode_to_ai_when_no_messages() -> None:
    conversation = _build_conversation(control_mode="HUMAN")

    conversation.archive_manual_close(messages=[], now=_LATER)

    assert conversation.control_mode == "AI"
    assert conversation.last_message_preview is None
    assert len(conversation.subsessions) == 0


def test_archive_current_session_resets_control_mode_to_ai() -> None:
    msg = _build_message()
    conversation = _build_conversation(control_mode="HUMAN", messages=[msg])

    conversation.archive_current_session(
        scheduling_request_id="req-1",
        calendar_event_id="cal-1",
        messages=[msg],
        now=_LATER,
    )

    assert conversation.control_mode == "AI"
    assert conversation.last_message_preview is None
    assert len(conversation.subsessions) == 1
    assert conversation.subsessions[0].archived_reason == "APPOINTMENT_BOOKED"


def test_archive_keeps_control_mode_ai_when_already_ai() -> None:
    conversation = _build_conversation(control_mode="AI")

    conversation.archive_manual_close(messages=[], now=_LATER)

    assert conversation.control_mode == "AI"
