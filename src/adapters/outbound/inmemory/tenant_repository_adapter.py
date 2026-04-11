import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.tenant as tenant_entity
import src.ports.tenant_repository_port as tenant_repository_port


class InMemoryTenantRepositoryAdapter(tenant_repository_port.TenantRepositoryPort):
    def __init__(self, store: in_memory_store.InMemoryStore) -> None:
        self._store = store

    def save(self, tenant: tenant_entity.Tenant) -> None:
        with self._store.lock:
            self._store.tenants_by_id[tenant.id] = tenant.model_copy(deep=True)
            self._store.flush()

    def get_by_id(self, tenant_id: str) -> tenant_entity.Tenant | None:
        with self._store.lock:
            tenant = self._store.tenants_by_id.get(tenant_id)
            if tenant is None:
                return None
            return tenant.model_copy(deep=True)

    def delete_with_data(self, tenant_id: str) -> bool:
        with self._store.lock:
            if tenant_id not in self._store.tenants_by_id:
                return False

            del self._store.tenants_by_id[tenant_id]

            users_to_delete = [
                u for u in self._store.users_by_id.values() if u.tenant_id == tenant_id
            ]
            for user in users_to_delete:
                self._store.users_by_id.pop(user.id, None)
                self._store.users_by_email.pop(user.email, None)

            self._store.agent_profile_by_tenant.pop(tenant_id, None)
            self._store.wa_connection_by_tenant.pop(tenant_id, None)
            self._store.google_calendar_connection_by_tenant.pop(tenant_id, None)

            self._store.connection_by_embedded_signup_state = {
                k: v
                for k, v in self._store.connection_by_embedded_signup_state.items()
                if v != tenant_id
            }
            self._store.google_calendar_connection_by_oauth_state = {
                k: v
                for k, v in self._store.google_calendar_connection_by_oauth_state.items()
                if v != tenant_id
            }
            self._store.tenant_by_phone_number_id = {
                k: v
                for k, v in self._store.tenant_by_phone_number_id.items()
                if v != tenant_id
            }

            conversation_ids_to_delete = [
                c.id
                for c in self._store.conversation_by_id.values()
                if c.tenant_id == tenant_id
            ]
            for conv_id in conversation_ids_to_delete:
                self._store.conversation_by_id.pop(conv_id, None)
                self._store.messages_by_conversation_id.pop(conv_id, None)

            self._store.conversation_by_tenant_and_wa_user = {
                k: v
                for k, v in self._store.conversation_by_tenant_and_wa_user.items()
                if k[0] != tenant_id
            }
            self._store.whatsapp_user_by_tenant_and_id = {
                k: v
                for k, v in self._store.whatsapp_user_by_tenant_and_id.items()
                if k[0] != tenant_id
            }
            self._store.patient_by_tenant_and_wa_user = {
                k: v
                for k, v in self._store.patient_by_tenant_and_wa_user.items()
                if k[0] != tenant_id
            }
            self._store.blacklist_by_tenant_and_wa_user = {
                k: v
                for k, v in self._store.blacklist_by_tenant_and_wa_user.items()
                if k[0] != tenant_id
            }
            self._store.conversation_processing_locks = {
                k: v
                for k, v in self._store.conversation_processing_locks.items()
                if k[0] != tenant_id
            }
            self._store.processed_events = {
                e for e in self._store.processed_events if e[0] != tenant_id
            }

            appointment_ids = self._store.manual_appointment_ids_by_tenant.pop(tenant_id, [])
            for appt_id in appointment_ids:
                self._store.manual_appointment_by_id.pop(appt_id, None)
            self._store.manual_appointment_ids_by_patient = {
                k: v
                for k, v in self._store.manual_appointment_ids_by_patient.items()
                if k[0] != tenant_id
            }

            request_ids = self._store.scheduling_request_ids_by_tenant.pop(tenant_id, [])
            for req_id in request_ids:
                self._store.scheduling_request_by_id.pop(req_id, None)
            self._store.scheduling_request_ids_by_conversation = {
                k: v
                for k, v in self._store.scheduling_request_ids_by_conversation.items()
                if k[0] != tenant_id
            }

            self._store.flush()
            return True
