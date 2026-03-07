import base64

import google.cloud.firestore as google_cloud_firestore

TENANTS_COLLECTION = "tenants"
USERS_COLLECTION = "users"
AGENT_PROFILES_COLLECTION = "agent_profiles"
WHATSAPP_CONNECTION_COLLECTION = "whatsapp_connection"
GOOGLE_CALENDAR_CONNECTION_COLLECTION = "google_calendar_connection"
WHATSAPP_USERS_COLLECTION = "whatsapp_users"
PATIENTS_COLLECTION = "patients"
MANUAL_APPOINTMENTS_COLLECTION = "manual_appointments"
CONVERSATIONS_COLLECTION = "conversations"
MESSAGES_COLLECTION = "messages"
CONVERSATION_LOOKUP_COLLECTION = "conversation_lookup"
SCHEDULING_REQUESTS_COLLECTION = "scheduling_requests"
PROCESSED_WEBHOOK_EVENTS_COLLECTION = "processed_webhook_events"
BLACKLIST_ENTRIES_COLLECTION = "blacklist_entries"
CONVERSATION_PROCESSING_LOCKS_COLLECTION = "conversation_processing_locks"

INDEXES_COLLECTION = "indexes"
USER_EMAIL_INDEX_COLLECTION = "user_email"
USER_ID_INDEX_COLLECTION = "user_id"
WHATSAPP_PHONE_INDEX_COLLECTION = "wa_phone_number"
WHATSAPP_SIGNUP_STATE_INDEX_COLLECTION = "wa_signup_state"
GOOGLE_OAUTH_STATE_INDEX_COLLECTION = "google_oauth_state"

REFRESH_TOKENS_COLLECTION = "refresh_tokens"


def _encode_key(value: str) -> str:
    encoded = base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def tenants_collection(
    client: google_cloud_firestore.Client,
) -> google_cloud_firestore.CollectionReference:
    return client.collection(TENANTS_COLLECTION)


def tenant_document(
    client: google_cloud_firestore.Client,
    tenant_id: str,
) -> google_cloud_firestore.DocumentReference:
    return tenants_collection(client).document(tenant_id)


def tenant_users_collection(
    client: google_cloud_firestore.Client,
    tenant_id: str,
) -> google_cloud_firestore.CollectionReference:
    return tenant_document(client, tenant_id).collection(USERS_COLLECTION)


def tenant_user_document(
    client: google_cloud_firestore.Client,
    tenant_id: str,
    user_id: str,
) -> google_cloud_firestore.DocumentReference:
    return tenant_users_collection(client, tenant_id).document(user_id)


def tenant_agent_profile_document(
    client: google_cloud_firestore.Client,
    tenant_id: str,
) -> google_cloud_firestore.DocumentReference:
    return (
        tenant_document(client, tenant_id).collection(AGENT_PROFILES_COLLECTION).document("default")
    )


def tenant_whatsapp_connection_document(
    client: google_cloud_firestore.Client,
    tenant_id: str,
) -> google_cloud_firestore.DocumentReference:
    return (
        tenant_document(client, tenant_id)
        .collection(WHATSAPP_CONNECTION_COLLECTION)
        .document("default")
    )


def tenant_google_calendar_connection_document(
    client: google_cloud_firestore.Client,
    tenant_id: str,
) -> google_cloud_firestore.DocumentReference:
    return (
        tenant_document(client, tenant_id)
        .collection(GOOGLE_CALENDAR_CONNECTION_COLLECTION)
        .document("default")
    )


def tenant_whatsapp_user_document(
    client: google_cloud_firestore.Client,
    tenant_id: str,
    whatsapp_user_id: str,
) -> google_cloud_firestore.DocumentReference:
    return (
        tenant_document(client, tenant_id)
        .collection(WHATSAPP_USERS_COLLECTION)
        .document(whatsapp_user_id)
    )


def tenant_patient_document(
    client: google_cloud_firestore.Client,
    tenant_id: str,
    whatsapp_user_id: str,
) -> google_cloud_firestore.DocumentReference:
    return (
        tenant_document(client, tenant_id)
        .collection(PATIENTS_COLLECTION)
        .document(whatsapp_user_id)
    )


def tenant_manual_appointments_collection(
    client: google_cloud_firestore.Client,
    tenant_id: str,
) -> google_cloud_firestore.CollectionReference:
    return tenant_document(client, tenant_id).collection(MANUAL_APPOINTMENTS_COLLECTION)


def tenant_manual_appointment_document(
    client: google_cloud_firestore.Client,
    tenant_id: str,
    appointment_id: str,
) -> google_cloud_firestore.DocumentReference:
    return tenant_manual_appointments_collection(client, tenant_id).document(appointment_id)


def tenant_conversation_document(
    client: google_cloud_firestore.Client,
    tenant_id: str,
    conversation_id: str,
) -> google_cloud_firestore.DocumentReference:
    return (
        tenant_document(client, tenant_id)
        .collection(CONVERSATIONS_COLLECTION)
        .document(conversation_id)
    )


def tenant_conversations_collection(
    client: google_cloud_firestore.Client,
    tenant_id: str,
) -> google_cloud_firestore.CollectionReference:
    return tenant_document(client, tenant_id).collection(CONVERSATIONS_COLLECTION)


def tenant_conversation_lookup_document(
    client: google_cloud_firestore.Client,
    tenant_id: str,
    whatsapp_user_id: str,
) -> google_cloud_firestore.DocumentReference:
    return (
        tenant_document(client, tenant_id)
        .collection(CONVERSATION_LOOKUP_COLLECTION)
        .document(whatsapp_user_id)
    )


def conversation_messages_collection(
    client: google_cloud_firestore.Client,
    tenant_id: str,
    conversation_id: str,
) -> google_cloud_firestore.CollectionReference:
    return tenant_conversation_document(client, tenant_id, conversation_id).collection(
        MESSAGES_COLLECTION
    )


def conversation_message_document(
    client: google_cloud_firestore.Client,
    tenant_id: str,
    conversation_id: str,
    message_id: str,
) -> google_cloud_firestore.DocumentReference:
    return conversation_messages_collection(client, tenant_id, conversation_id).document(message_id)


def tenant_scheduling_request_document(
    client: google_cloud_firestore.Client,
    tenant_id: str,
    request_id: str,
) -> google_cloud_firestore.DocumentReference:
    return (
        tenant_document(client, tenant_id)
        .collection(SCHEDULING_REQUESTS_COLLECTION)
        .document(request_id)
    )


def tenant_scheduling_requests_collection(
    client: google_cloud_firestore.Client,
    tenant_id: str,
) -> google_cloud_firestore.CollectionReference:
    return tenant_document(client, tenant_id).collection(SCHEDULING_REQUESTS_COLLECTION)


def tenant_processed_webhook_event_document(
    client: google_cloud_firestore.Client,
    tenant_id: str,
    provider_event_id: str,
) -> google_cloud_firestore.DocumentReference:
    event_key = _encode_key(provider_event_id)
    return (
        tenant_document(client, tenant_id)
        .collection(PROCESSED_WEBHOOK_EVENTS_COLLECTION)
        .document(event_key)
    )


def tenant_blacklist_entry_document(
    client: google_cloud_firestore.Client,
    tenant_id: str,
    whatsapp_user_id: str,
) -> google_cloud_firestore.DocumentReference:
    return (
        tenant_document(client, tenant_id)
        .collection(BLACKLIST_ENTRIES_COLLECTION)
        .document(whatsapp_user_id)
    )


def tenant_blacklist_entries_collection(
    client: google_cloud_firestore.Client,
    tenant_id: str,
) -> google_cloud_firestore.CollectionReference:
    return tenant_document(client, tenant_id).collection(BLACKLIST_ENTRIES_COLLECTION)


def user_email_index_document(
    client: google_cloud_firestore.Client,
    email: str,
) -> google_cloud_firestore.DocumentReference:
    email_key = _encode_key(email)
    return (
        client.collection(INDEXES_COLLECTION)
        .document(USER_EMAIL_INDEX_COLLECTION)
        .collection(USER_EMAIL_INDEX_COLLECTION)
        .document(email_key)
    )


def user_id_index_document(
    client: google_cloud_firestore.Client,
    user_id: str,
) -> google_cloud_firestore.DocumentReference:
    return (
        client.collection(INDEXES_COLLECTION)
        .document(USER_ID_INDEX_COLLECTION)
        .collection(USER_ID_INDEX_COLLECTION)
        .document(user_id)
    )


def whatsapp_phone_index_document(
    client: google_cloud_firestore.Client,
    phone_number_id: str,
) -> google_cloud_firestore.DocumentReference:
    phone_key = _encode_key(phone_number_id)
    return (
        client.collection(INDEXES_COLLECTION)
        .document(WHATSAPP_PHONE_INDEX_COLLECTION)
        .collection(WHATSAPP_PHONE_INDEX_COLLECTION)
        .document(phone_key)
    )


def whatsapp_signup_state_index_document(
    client: google_cloud_firestore.Client,
    signup_state: str,
) -> google_cloud_firestore.DocumentReference:
    state_key = _encode_key(signup_state)
    return (
        client.collection(INDEXES_COLLECTION)
        .document(WHATSAPP_SIGNUP_STATE_INDEX_COLLECTION)
        .collection(WHATSAPP_SIGNUP_STATE_INDEX_COLLECTION)
        .document(state_key)
    )


def google_oauth_state_index_document(
    client: google_cloud_firestore.Client,
    oauth_state: str,
) -> google_cloud_firestore.DocumentReference:
    state_key = _encode_key(oauth_state)
    return (
        client.collection(INDEXES_COLLECTION)
        .document(GOOGLE_OAUTH_STATE_INDEX_COLLECTION)
        .collection(GOOGLE_OAUTH_STATE_INDEX_COLLECTION)
        .document(state_key)
    )


def tenant_conversation_processing_lock_document(
    client: google_cloud_firestore.Client,
    tenant_id: str,
    conversation_id: str,
) -> google_cloud_firestore.DocumentReference:
    return (
        tenant_document(client, tenant_id)
        .collection(CONVERSATION_PROCESSING_LOCKS_COLLECTION)
        .document(conversation_id)
    )


def refresh_token_document(
    client: google_cloud_firestore.Client,
    jti: str,
) -> google_cloud_firestore.DocumentReference:
    return client.collection(REFRESH_TOKENS_COLLECTION).document(jti)
