import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.patient as patient_entity
import src.ports.patient_repository_port as patient_repository_port


class InMemoryPatientRepositoryAdapter(patient_repository_port.PatientRepositoryPort):
    def __init__(self, store: in_memory_store.InMemoryStore) -> None:
        self._store = store

    def save(self, patient: patient_entity.Patient) -> None:
        with self._store.lock:
            patient_key = (patient.tenant_id, patient.whatsapp_user_id)
            self._store.patient_by_tenant_and_wa_user[patient_key] = patient.model_copy(deep=True)
            self._store.flush()

    def get_by_whatsapp_user(
        self, tenant_id: str, whatsapp_user_id: str
    ) -> patient_entity.Patient | None:
        with self._store.lock:
            patient_key = (tenant_id, whatsapp_user_id)
            patient = self._store.patient_by_tenant_and_wa_user.get(patient_key)
            if patient is None:
                return None
            return patient.model_copy(deep=True)

    def list_by_tenant(self, tenant_id: str) -> list[patient_entity.Patient]:
        with self._store.lock:
            items: list[patient_entity.Patient] = []
            for (
                current_tenant_id,
                _,
            ), patient in self._store.patient_by_tenant_and_wa_user.items():
                if current_tenant_id != tenant_id:
                    continue
                items.append(patient.model_copy(deep=True))
            return items

    def delete(self, tenant_id: str, whatsapp_user_id: str) -> None:
        with self._store.lock:
            patient_key = (tenant_id, whatsapp_user_id)
            self._store.patient_by_tenant_and_wa_user.pop(patient_key, None)
            self._store.flush()
