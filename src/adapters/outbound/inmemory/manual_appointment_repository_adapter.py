import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.manual_appointment as manual_appointment_entity
import src.ports.manual_appointment_repository_port as manual_appointment_repository_port


class InMemoryManualAppointmentRepositoryAdapter(
    manual_appointment_repository_port.ManualAppointmentRepositoryPort
):
    def __init__(self, store: in_memory_store.InMemoryStore) -> None:
        self._store = store

    def save(self, appointment: manual_appointment_entity.ManualAppointment) -> None:
        with self._store.lock:
            appointment_copy = appointment.model_copy(deep=True)
            previous_appointment = self._store.manual_appointment_by_id.get(appointment.id)
            if previous_appointment is None:
                tenant_ids = self._store.manual_appointment_ids_by_tenant.get(appointment.tenant_id)
                if tenant_ids is None:
                    tenant_ids = []
                    self._store.manual_appointment_ids_by_tenant[appointment.tenant_id] = tenant_ids
                tenant_ids.append(appointment.id)

                patient_key = (
                    appointment.tenant_id,
                    appointment.patient_whatsapp_user_id,
                )
                patient_ids = self._store.manual_appointment_ids_by_patient.get(patient_key)
                if patient_ids is None:
                    patient_ids = []
                    self._store.manual_appointment_ids_by_patient[patient_key] = patient_ids
                patient_ids.append(appointment.id)

            self._store.manual_appointment_by_id[appointment.id] = appointment_copy
            self._store.flush()

    def get_by_id(
        self,
        tenant_id: str,
        appointment_id: str,
    ) -> manual_appointment_entity.ManualAppointment | None:
        with self._store.lock:
            appointment = self._store.manual_appointment_by_id.get(appointment_id)
            if appointment is None:
                return None
            if appointment.tenant_id != tenant_id:
                return None
            return appointment.model_copy(deep=True)

    def list_by_tenant(
        self,
        tenant_id: str,
        status: str | None = None,
    ) -> list[manual_appointment_entity.ManualAppointment]:
        with self._store.lock:
            appointment_ids = self._store.manual_appointment_ids_by_tenant.get(tenant_id, [])
            items: list[manual_appointment_entity.ManualAppointment] = []
            for appointment_id in appointment_ids:
                appointment = self._store.manual_appointment_by_id.get(appointment_id)
                if appointment is None:
                    continue
                if status is not None and appointment.status != status:
                    continue
                items.append(appointment.model_copy(deep=True))
            return items

    def list_by_patient(
        self,
        tenant_id: str,
        patient_whatsapp_user_id: str,
        status: str | None = None,
    ) -> list[manual_appointment_entity.ManualAppointment]:
        with self._store.lock:
            patient_key = (tenant_id, patient_whatsapp_user_id)
            appointment_ids = self._store.manual_appointment_ids_by_patient.get(patient_key, [])
            items: list[manual_appointment_entity.ManualAppointment] = []
            for appointment_id in appointment_ids:
                appointment = self._store.manual_appointment_by_id.get(appointment_id)
                if appointment is None:
                    continue
                if status is not None and appointment.status != status:
                    continue
                items.append(appointment.model_copy(deep=True))
            return items
