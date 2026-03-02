import abc

import src.domain.entities.patient as patient_entity


class PatientRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, patient: patient_entity.Patient) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_whatsapp_user(
        self, tenant_id: str, whatsapp_user_id: str
    ) -> patient_entity.Patient | None:
        raise NotImplementedError

    @abc.abstractmethod
    def list_by_tenant(self, tenant_id: str) -> list[patient_entity.Patient]:
        raise NotImplementedError
