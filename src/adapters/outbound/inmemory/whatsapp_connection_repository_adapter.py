import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.whatsapp_connection as whatsapp_connection_entity
import src.ports.whatsapp_connection_repository_port as whatsapp_connection_repository_port


class InMemoryWhatsappConnectionRepositoryAdapter(
    whatsapp_connection_repository_port.WhatsappConnectionRepositoryPort
):
    def __init__(self, store: in_memory_store.InMemoryStore) -> None:
        self._store = store

    def save(self, connection: whatsapp_connection_entity.WhatsappConnection) -> None:
        with self._store.lock:
            existing_connection = self._store.wa_connection_by_tenant.get(connection.tenant_id)
            if existing_connection is not None:
                if existing_connection.embedded_signup_state is not None:
                    self._store.connection_by_embedded_signup_state.pop(
                        existing_connection.embedded_signup_state, None
                    )
                if existing_connection.phone_number_id is not None:
                    self._store.tenant_by_phone_number_id.pop(
                        existing_connection.phone_number_id, None
                    )

            connection_copy = connection.model_copy(deep=True)
            self._store.wa_connection_by_tenant[connection.tenant_id] = connection_copy
            if connection.embedded_signup_state is not None:
                self._store.connection_by_embedded_signup_state[
                    connection.embedded_signup_state
                ] = connection.tenant_id
            if connection.phone_number_id is not None:
                self._store.tenant_by_phone_number_id[connection.phone_number_id] = (
                    connection.tenant_id
                )
            self._store.flush()

    def get_by_tenant_id(
        self, tenant_id: str
    ) -> whatsapp_connection_entity.WhatsappConnection | None:
        with self._store.lock:
            connection = self._store.wa_connection_by_tenant.get(tenant_id)
            if connection is None:
                return None
            return connection.model_copy(deep=True)

    def get_by_phone_number_id(
        self, phone_number_id: str
    ) -> whatsapp_connection_entity.WhatsappConnection | None:
        with self._store.lock:
            tenant_id = self._store.tenant_by_phone_number_id.get(phone_number_id)
            if tenant_id is None:
                return None
            connection = self._store.wa_connection_by_tenant.get(tenant_id)
            if connection is None:
                return None
            return connection.model_copy(deep=True)

    def get_by_embedded_signup_state(
        self, embedded_signup_state: str
    ) -> whatsapp_connection_entity.WhatsappConnection | None:
        with self._store.lock:
            tenant_id = self._store.connection_by_embedded_signup_state.get(embedded_signup_state)
            if tenant_id is None:
                return None
            connection = self._store.wa_connection_by_tenant.get(tenant_id)
            if connection is None:
                return None
            return connection.model_copy(deep=True)
