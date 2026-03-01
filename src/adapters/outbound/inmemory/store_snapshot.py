import pydantic

import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.blacklist_entry as blacklist_entry_entity
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.google_calendar_connection as google_calendar_connection_entity
import src.domain.entities.message as message_entity
import src.domain.entities.scheduling_request as scheduling_request_entity
import src.domain.entities.tenant as tenant_entity
import src.domain.entities.user as user_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.domain.entities.whatsapp_user as whatsapp_user_entity


class ProcessedEventSnapshot(pydantic.BaseModel):
    tenant_id: str
    provider_event_id: str


class InMemoryStoreSnapshot(pydantic.BaseModel):
    tenants: list[tenant_entity.Tenant] = pydantic.Field(default_factory=list)
    users: list[user_entity.User] = pydantic.Field(default_factory=list)
    agent_profiles: list[agent_profile_entity.AgentProfile] = pydantic.Field(default_factory=list)
    whatsapp_connections: list[whatsapp_connection_entity.WhatsappConnection] = pydantic.Field(
        default_factory=list
    )
    google_calendar_connections: list[
        google_calendar_connection_entity.GoogleCalendarConnection
    ] = pydantic.Field(default_factory=list)
    whatsapp_users: list[whatsapp_user_entity.WhatsappUser] = pydantic.Field(default_factory=list)
    conversations: list[conversation_entity.Conversation] = pydantic.Field(default_factory=list)
    scheduling_requests: list[scheduling_request_entity.SchedulingRequest] = pydantic.Field(
        default_factory=list
    )
    messages: list[message_entity.Message] = pydantic.Field(default_factory=list)
    processed_events: list[ProcessedEventSnapshot] = pydantic.Field(default_factory=list)
    blacklist_entries: list[blacklist_entry_entity.BlacklistEntry] = pydantic.Field(
        default_factory=list
    )
