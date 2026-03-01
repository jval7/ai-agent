import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.google_calendar_connection as google_calendar_connection_entity
import src.ports.google_calendar_connection_repository_port as google_calendar_connection_repository_port


class InMemoryGoogleCalendarConnectionRepositoryAdapter(
    google_calendar_connection_repository_port.GoogleCalendarConnectionRepositoryPort
):
    def __init__(self, store: in_memory_store.InMemoryStore) -> None:
        self._store = store

    def save(self, connection: google_calendar_connection_entity.GoogleCalendarConnection) -> None:
        with self._store.lock:
            existing_connection = self._store.google_calendar_connection_by_tenant.get(
                connection.tenant_id
            )
            if existing_connection is not None and existing_connection.oauth_state is not None:
                self._store.google_calendar_connection_by_oauth_state.pop(
                    existing_connection.oauth_state,
                    None,
                )

            connection_copy = connection.model_copy(deep=True)
            self._store.google_calendar_connection_by_tenant[connection.tenant_id] = connection_copy
            if connection.oauth_state is not None:
                self._store.google_calendar_connection_by_oauth_state[connection.oauth_state] = (
                    connection.tenant_id
                )
            self._store.flush()

    def get_by_tenant_id(
        self, tenant_id: str
    ) -> google_calendar_connection_entity.GoogleCalendarConnection | None:
        with self._store.lock:
            connection = self._store.google_calendar_connection_by_tenant.get(tenant_id)
            if connection is None:
                return None
            return connection.model_copy(deep=True)

    def get_by_oauth_state(
        self, oauth_state: str
    ) -> google_calendar_connection_entity.GoogleCalendarConnection | None:
        with self._store.lock:
            tenant_id = self._store.google_calendar_connection_by_oauth_state.get(oauth_state)
            if tenant_id is None:
                return None
            connection = self._store.google_calendar_connection_by_tenant.get(tenant_id)
            if connection is None:
                return None
            return connection.model_copy(deep=True)
