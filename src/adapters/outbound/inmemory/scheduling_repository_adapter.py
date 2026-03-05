import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.scheduling_request as scheduling_request_entity
import src.ports.scheduling_repository_port as scheduling_repository_port


class InMemorySchedulingRepositoryAdapter(scheduling_repository_port.SchedulingRepositoryPort):
    def __init__(self, store: in_memory_store.InMemoryStore) -> None:
        self._store = store

    def save_request(self, request: scheduling_request_entity.SchedulingRequest) -> None:
        with self._store.lock:
            request_copy = request.model_copy(deep=True)
            previous_request = self._store.scheduling_request_by_id.get(request.id)
            if previous_request is None:
                tenant_ids = self._store.scheduling_request_ids_by_tenant.get(request.tenant_id)
                if tenant_ids is None:
                    tenant_ids = []
                    self._store.scheduling_request_ids_by_tenant[request.tenant_id] = tenant_ids
                tenant_ids.append(request.id)

                conversation_key = (request.tenant_id, request.conversation_id)
                conversation_ids = self._store.scheduling_request_ids_by_conversation.get(
                    conversation_key
                )
                if conversation_ids is None:
                    conversation_ids = []
                    self._store.scheduling_request_ids_by_conversation[conversation_key] = (
                        conversation_ids
                    )
                conversation_ids.append(request.id)

            self._store.scheduling_request_by_id[request.id] = request_copy
            self._store.flush()

    def get_request_by_id(
        self, tenant_id: str, request_id: str
    ) -> scheduling_request_entity.SchedulingRequest | None:
        with self._store.lock:
            request = self._store.scheduling_request_by_id.get(request_id)
            if request is None:
                return None
            if request.tenant_id != tenant_id:
                return None
            return request.model_copy(deep=True)

    def delete_request(self, tenant_id: str, request_id: str) -> None:
        with self._store.lock:
            request = self._store.scheduling_request_by_id.get(request_id)
            if request is None:
                return
            if request.tenant_id != tenant_id:
                return

            self._store.scheduling_request_by_id.pop(request_id, None)

            tenant_request_ids = self._store.scheduling_request_ids_by_tenant.get(tenant_id)
            if tenant_request_ids is not None:
                filtered_tenant_ids = [
                    current_id for current_id in tenant_request_ids if current_id != request_id
                ]
                if filtered_tenant_ids:
                    self._store.scheduling_request_ids_by_tenant[tenant_id] = filtered_tenant_ids
                else:
                    self._store.scheduling_request_ids_by_tenant.pop(tenant_id, None)

            conversation_key = (tenant_id, request.conversation_id)
            conversation_request_ids = self._store.scheduling_request_ids_by_conversation.get(
                conversation_key
            )
            if conversation_request_ids is not None:
                filtered_conversation_ids = [
                    current_id
                    for current_id in conversation_request_ids
                    if current_id != request_id
                ]
                if filtered_conversation_ids:
                    self._store.scheduling_request_ids_by_conversation[conversation_key] = (
                        filtered_conversation_ids
                    )
                else:
                    self._store.scheduling_request_ids_by_conversation.pop(conversation_key, None)

            self._store.flush()

    def list_requests_by_tenant(
        self, tenant_id: str, status: str | None = None
    ) -> list[scheduling_request_entity.SchedulingRequest]:
        with self._store.lock:
            request_ids = self._store.scheduling_request_ids_by_tenant.get(tenant_id, [])
            result: list[scheduling_request_entity.SchedulingRequest] = []
            for request_id in request_ids:
                request = self._store.scheduling_request_by_id.get(request_id)
                if request is None:
                    continue
                if status is not None and request.status != status:
                    continue
                result.append(request.model_copy(deep=True))
            return result

    def list_requests_by_conversation(
        self, tenant_id: str, conversation_id: str
    ) -> list[scheduling_request_entity.SchedulingRequest]:
        with self._store.lock:
            conversation_key = (tenant_id, conversation_id)
            request_ids = self._store.scheduling_request_ids_by_conversation.get(
                conversation_key, []
            )
            result: list[scheduling_request_entity.SchedulingRequest] = []
            for request_id in request_ids:
                request = self._store.scheduling_request_by_id.get(request_id)
                if request is None:
                    continue
                result.append(request.model_copy(deep=True))
            return result
