import datetime

import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.blacklist_entry as blacklist_entry_entity
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.google_calendar_connection as google_calendar_connection_entity
import src.domain.entities.message as message_entity
import src.domain.entities.patient as patient_entity
import src.domain.entities.scheduling_request as scheduling_request_entity
import src.domain.entities.scheduling_slot as scheduling_slot_entity
import src.domain.entities.tenant as tenant_entity
import src.domain.entities.user as user_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.domain.entities.whatsapp_user as whatsapp_user_entity


def test_chat_reset_clears_operational_data_but_keeps_integrations() -> None:
    now_value = datetime.datetime(2026, 3, 2, tzinfo=datetime.UTC)
    store = in_memory_store.InMemoryStore()

    tenant = tenant_entity.Tenant(
        id="tenant-1",
        name="Acme",
        created_at=now_value,
        updated_at=now_value,
    )
    user = user_entity.User(
        id="user-1",
        tenant_id="tenant-1",
        email="owner@acme.com",
        password_hash="hash",
        role="owner",
        is_active=True,
        created_at=now_value,
    )
    agent_profile = agent_profile_entity.AgentProfile(
        tenant_id="tenant-1",
        system_prompt="custom prompt",
        updated_at=now_value,
    )
    wa_connection = whatsapp_connection_entity.WhatsappConnection(
        tenant_id="tenant-1",
        phone_number_id="phone-1",
        business_account_id="waba-1",
        access_token="wa-token",
        status="CONNECTED",
        embedded_signup_state="state-1",
        updated_at=now_value,
    )
    google_connection = google_calendar_connection_entity.GoogleCalendarConnection(
        tenant_id="tenant-1",
        professional_user_id="user-1",
        status="CONNECTED",
        calendar_id="primary",
        timezone="America/Bogota",
        access_token="google-access",
        refresh_token="google-refresh",
        token_expires_at=now_value + datetime.timedelta(hours=1),
        oauth_state="oauth-state-1",
        scope="calendar",
        updated_at=now_value,
        connected_at=now_value,
    )
    whatsapp_user = whatsapp_user_entity.WhatsappUser(
        id="wa-user-1",
        tenant_id="tenant-1",
        display_name="Jane",
        created_at=now_value,
    )
    patient = patient_entity.Patient(
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
    conversation = conversation_entity.Conversation(
        id="conv-1",
        tenant_id="tenant-1",
        whatsapp_user_id="wa-user-1",
        started_at=now_value,
        updated_at=now_value,
        last_message_preview=None,
        message_ids=[],
        control_mode="AI",
    )
    scheduling_request = scheduling_request_entity.SchedulingRequest(
        id="req-1",
        tenant_id="tenant-1",
        conversation_id="conv-1",
        whatsapp_user_id="wa-user-1",
        request_kind="INITIAL",
        status="AWAITING_PATIENT_CHOICE",
        round_number=1,
        patient_preference_note="despues de las 4pm",
        rejection_summary=None,
        professional_note=None,
        patient_first_name="Jane",
        patient_last_name="Doe",
        patient_age=29,
        consultation_reason="Ansiedad",
        consultation_details="Dificultad para dormir",
        appointment_modality="VIRTUAL",
        patient_location="Bogota",
        slots=[
            scheduling_slot_entity.SchedulingSlot(
                id="slot-1",
                start_at=now_value + datetime.timedelta(days=1),
                end_at=now_value + datetime.timedelta(days=1, hours=1),
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
    message = message_entity.Message(
        id="msg-1",
        conversation_id="conv-1",
        tenant_id="tenant-1",
        direction="INBOUND",
        role="user",
        content="Hola",
        provider_message_id="wamid-1",
        created_at=now_value,
    )
    blacklist_entry = blacklist_entry_entity.BlacklistEntry(
        tenant_id="tenant-1",
        whatsapp_user_id="wa-user-1",
        created_at=now_value,
    )

    store.tenants_by_id[tenant.id] = tenant
    store.users_by_id[user.id] = user
    store.users_by_email[user.email] = user
    store.agent_profile_by_tenant[agent_profile.tenant_id] = agent_profile
    store.wa_connection_by_tenant[wa_connection.tenant_id] = wa_connection
    if wa_connection.embedded_signup_state is not None:
        store.connection_by_embedded_signup_state[wa_connection.embedded_signup_state] = (
            wa_connection.tenant_id
        )
    if wa_connection.phone_number_id is not None:
        store.tenant_by_phone_number_id[wa_connection.phone_number_id] = wa_connection.tenant_id
    store.google_calendar_connection_by_tenant[google_connection.tenant_id] = google_connection
    if google_connection.oauth_state is not None:
        store.google_calendar_connection_by_oauth_state[google_connection.oauth_state] = (
            google_connection.tenant_id
        )
    store.whatsapp_user_by_tenant_and_id[(whatsapp_user.tenant_id, whatsapp_user.id)] = (
        whatsapp_user
    )
    store.patient_by_tenant_and_wa_user[(patient.tenant_id, patient.whatsapp_user_id)] = patient
    store.conversation_by_id[conversation.id] = conversation
    store.conversation_by_tenant_and_wa_user[
        (conversation.tenant_id, conversation.whatsapp_user_id)
    ] = conversation
    store.scheduling_request_by_id[scheduling_request.id] = scheduling_request
    store.scheduling_request_ids_by_tenant[scheduling_request.tenant_id] = [scheduling_request.id]
    store.scheduling_request_ids_by_conversation[
        (scheduling_request.tenant_id, conversation.id)
    ] = [scheduling_request.id]
    store.messages_by_conversation_id[conversation.id] = [message]
    store.processed_events.add(("tenant-1", "provider-evt-1"))
    store.blacklist_by_tenant_and_wa_user[
        (blacklist_entry.tenant_id, blacklist_entry.whatsapp_user_id)
    ] = blacklist_entry

    store.reset_chat_state()

    assert "tenant-1" in store.tenants_by_id
    assert "user-1" in store.users_by_id
    assert "owner@acme.com" in store.users_by_email
    assert "tenant-1" in store.agent_profile_by_tenant
    assert "tenant-1" in store.wa_connection_by_tenant
    assert "state-1" in store.connection_by_embedded_signup_state
    assert "phone-1" in store.tenant_by_phone_number_id
    assert "tenant-1" in store.google_calendar_connection_by_tenant
    assert "oauth-state-1" in store.google_calendar_connection_by_oauth_state

    assert store.whatsapp_user_by_tenant_and_id == {}
    assert store.patient_by_tenant_and_wa_user == {}
    assert store.conversation_by_tenant_and_wa_user == {}
    assert store.conversation_by_id == {}
    assert store.scheduling_request_by_id == {}
    assert store.scheduling_request_ids_by_tenant == {}
    assert store.scheduling_request_ids_by_conversation == {}
    assert store.messages_by_conversation_id == {}
    assert store.processed_events == set()
    assert store.blacklist_by_tenant_and_wa_user == {}
