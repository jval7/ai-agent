import src.adapters.outbound.inmemory.store as in_memory_store
import src.ports.memory_admin_port as memory_admin_port


class InMemoryMemoryAdminAdapter(memory_admin_port.MemoryAdminPort):
    def __init__(self, store: in_memory_store.InMemoryStore) -> None:
        self._store = store

    def reset_state(self) -> None:
        self._store.reset_state()
