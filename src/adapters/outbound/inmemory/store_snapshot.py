import pydantic

import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.blacklist_entry as blacklist_entry_entity
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.message as message_entity
import src.domain.entities.tenant as tenant_entity
import src.domain.entities.user as user_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.domain.entities.whatsapp_user as whatsapp_user_entity


class ProcessedEventSnapshot(pydantic.BaseModel):
    tenant_id: str
    provider_event_id: str


class InMemoryStoreSnapshot(pydantic.BaseModel):
    tenants: list[tenant_entity.Tenant]
    users: list[user_entity.User]
    agent_profiles: list[agent_profile_entity.AgentProfile]
    whatsapp_connections: list[whatsapp_connection_entity.WhatsappConnection]
    whatsapp_users: list[whatsapp_user_entity.WhatsappUser]
    conversations: list[conversation_entity.Conversation]
    messages: list[message_entity.Message]
    processed_events: list[ProcessedEventSnapshot]
    blacklist_entries: list[blacklist_entry_entity.BlacklistEntry] = pydantic.Field(
        default_factory=list
    )
