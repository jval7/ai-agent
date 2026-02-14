import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.user as user_entity
import src.ports.user_repository_port as user_repository_port


class InMemoryUserRepositoryAdapter(user_repository_port.UserRepositoryPort):
    def __init__(self, store: in_memory_store.InMemoryStore) -> None:
        self._store = store

    def save(self, user: user_entity.User) -> None:
        with self._store.lock:
            user_copy = user.model_copy(deep=True)
            self._store.users_by_email[user.email] = user_copy
            self._store.users_by_id[user.id] = user_copy
            self._store.flush()

    def get_by_email(self, email: str) -> user_entity.User | None:
        with self._store.lock:
            user = self._store.users_by_email.get(email.lower())
            if user is None:
                return None
            return user.model_copy(deep=True)

    def get_by_id(self, user_id: str) -> user_entity.User | None:
        with self._store.lock:
            user = self._store.users_by_id.get(user_id)
            if user is None:
                return None
            return user.model_copy(deep=True)
