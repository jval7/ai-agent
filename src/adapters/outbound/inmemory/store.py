import pathlib
import threading

import pydantic

import src.adapters.outbound.inmemory.store_snapshot as store_snapshot
import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.message as message_entity
import src.domain.entities.tenant as tenant_entity
import src.domain.entities.user as user_entity
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.domain.entities.whatsapp_user as whatsapp_user_entity


class InMemoryStorePersistenceError(Exception):
    """Raised when loading or writing the JSON memory snapshot fails."""


class InMemoryStore:
    def __init__(self, persistence_file_path: str | None = None) -> None:
        self.lock = threading.RLock()
        self._persistence_file_path = persistence_file_path

        self.tenants_by_id: dict[str, tenant_entity.Tenant] = {}
        self.users_by_email: dict[str, user_entity.User] = {}
        self.users_by_id: dict[str, user_entity.User] = {}
        self.agent_profile_by_tenant: dict[str, agent_profile_entity.AgentProfile] = {}
        self.wa_connection_by_tenant: dict[str, whatsapp_connection_entity.WhatsappConnection] = {}
        self.connection_by_embedded_signup_state: dict[str, str] = {}
        self.tenant_by_phone_number_id: dict[str, str] = {}
        self.conversation_by_tenant_and_wa_user: dict[
            tuple[str, str], conversation_entity.Conversation
        ] = {}
        self.conversation_by_id: dict[str, conversation_entity.Conversation] = {}
        self.messages_by_conversation_id: dict[str, list[message_entity.Message]] = {}
        self.whatsapp_user_by_tenant_and_id: dict[
            tuple[str, str], whatsapp_user_entity.WhatsappUser
        ] = {}
        self.processed_events: set[tuple[str, str]] = set()

        self._load_from_disk()

    def reset_state(self) -> None:
        with self.lock:
            self._clear_state()
            self.flush()

    def flush(self) -> None:
        if self._persistence_file_path is None:
            return

        with self.lock:
            snapshot_path = pathlib.Path(self._persistence_file_path)
            snapshot = self._build_snapshot()

            try:
                snapshot_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_snapshot_path = snapshot_path.with_name(f"{snapshot_path.name}.tmp")
                tmp_snapshot_path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
                tmp_snapshot_path.replace(snapshot_path)
            except OSError as error:
                raise InMemoryStorePersistenceError(
                    f"failed to write memory snapshot at '{snapshot_path}'"
                ) from error

    def _load_from_disk(self) -> None:
        if self._persistence_file_path is None:
            return

        snapshot_path = pathlib.Path(self._persistence_file_path)
        if not snapshot_path.exists():
            return

        try:
            snapshot_raw = snapshot_path.read_text(encoding="utf-8")
        except OSError as error:
            raise InMemoryStorePersistenceError(
                f"failed to read memory snapshot at '{snapshot_path}'"
            ) from error

        if not snapshot_raw.strip():
            return

        try:
            snapshot = store_snapshot.InMemoryStoreSnapshot.model_validate_json(snapshot_raw)
        except pydantic.ValidationError as error:
            raise InMemoryStorePersistenceError(
                f"invalid memory snapshot format at '{snapshot_path}'"
            ) from error

        self._restore_from_snapshot(snapshot)

    def _build_snapshot(self) -> store_snapshot.InMemoryStoreSnapshot:
        users: list[user_entity.User] = []
        for user in self.users_by_id.values():
            users.append(user.model_copy(deep=True))

        messages: list[message_entity.Message] = []
        for message_list in self.messages_by_conversation_id.values():
            for message in message_list:
                messages.append(message.model_copy(deep=True))

        processed_event_items: list[store_snapshot.ProcessedEventSnapshot] = []
        for tenant_id, provider_event_id in self.processed_events:
            processed_event_items.append(
                store_snapshot.ProcessedEventSnapshot(
                    tenant_id=tenant_id,
                    provider_event_id=provider_event_id,
                )
            )

        return store_snapshot.InMemoryStoreSnapshot(
            tenants=[item.model_copy(deep=True) for item in self.tenants_by_id.values()],
            users=users,
            agent_profiles=[
                item.model_copy(deep=True) for item in self.agent_profile_by_tenant.values()
            ],
            whatsapp_connections=[
                item.model_copy(deep=True) for item in self.wa_connection_by_tenant.values()
            ],
            whatsapp_users=[
                item.model_copy(deep=True) for item in self.whatsapp_user_by_tenant_and_id.values()
            ],
            conversations=[item.model_copy(deep=True) for item in self.conversation_by_id.values()],
            messages=messages,
            processed_events=processed_event_items,
        )

    def _restore_from_snapshot(self, snapshot: store_snapshot.InMemoryStoreSnapshot) -> None:
        self._clear_state()

        for tenant in snapshot.tenants:
            tenant_copy = tenant.model_copy(deep=True)
            self.tenants_by_id[tenant_copy.id] = tenant_copy

        for user in snapshot.users:
            user_copy = user.model_copy(deep=True)
            self.users_by_id[user_copy.id] = user_copy
            self.users_by_email[user_copy.email] = user_copy

        for agent_profile in snapshot.agent_profiles:
            profile_copy = agent_profile.model_copy(deep=True)
            self.agent_profile_by_tenant[profile_copy.tenant_id] = profile_copy

        for connection in snapshot.whatsapp_connections:
            connection_copy = connection.model_copy(deep=True)
            self.wa_connection_by_tenant[connection_copy.tenant_id] = connection_copy
            if connection_copy.embedded_signup_state is not None:
                self.connection_by_embedded_signup_state[connection_copy.embedded_signup_state] = (
                    connection_copy.tenant_id
                )
            if connection_copy.phone_number_id is not None:
                self.tenant_by_phone_number_id[connection_copy.phone_number_id] = (
                    connection_copy.tenant_id
                )

        for whatsapp_user in snapshot.whatsapp_users:
            whatsapp_user_copy = whatsapp_user.model_copy(deep=True)
            user_key = (whatsapp_user_copy.tenant_id, whatsapp_user_copy.id)
            self.whatsapp_user_by_tenant_and_id[user_key] = whatsapp_user_copy

        for conversation in snapshot.conversations:
            conversation_copy = conversation.model_copy(deep=True)
            conversation_key = (conversation_copy.tenant_id, conversation_copy.whatsapp_user_id)
            self.conversation_by_id[conversation_copy.id] = conversation_copy
            self.conversation_by_tenant_and_wa_user[conversation_key] = conversation_copy

        for message in snapshot.messages:
            message_copy = message.model_copy(deep=True)
            conversation_messages = self.messages_by_conversation_id.get(
                message_copy.conversation_id
            )
            if conversation_messages is None:
                conversation_messages = []
                self.messages_by_conversation_id[message_copy.conversation_id] = (
                    conversation_messages
                )
            conversation_messages.append(message_copy)

        for processed_event in snapshot.processed_events:
            event_key = (processed_event.tenant_id, processed_event.provider_event_id)
            self.processed_events.add(event_key)

    def _clear_state(self) -> None:
        self.tenants_by_id = {}
        self.users_by_email = {}
        self.users_by_id = {}
        self.agent_profile_by_tenant = {}
        self.wa_connection_by_tenant = {}
        self.connection_by_embedded_signup_state = {}
        self.tenant_by_phone_number_id = {}
        self.conversation_by_tenant_and_wa_user = {}
        self.conversation_by_id = {}
        self.messages_by_conversation_id = {}
        self.whatsapp_user_by_tenant_and_id = {}
        self.processed_events = set()
