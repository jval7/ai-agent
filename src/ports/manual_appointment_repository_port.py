import abc

import src.domain.entities.manual_appointment as manual_appointment_entity


class ManualAppointmentRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, appointment: manual_appointment_entity.ManualAppointment) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_id(
        self,
        tenant_id: str,
        appointment_id: str,
    ) -> manual_appointment_entity.ManualAppointment | None:
        raise NotImplementedError

    @abc.abstractmethod
    def list_by_tenant(
        self,
        tenant_id: str,
        status: str | None = None,
    ) -> list[manual_appointment_entity.ManualAppointment]:
        raise NotImplementedError

    @abc.abstractmethod
    def list_by_patient(
        self,
        tenant_id: str,
        patient_whatsapp_user_id: str,
        status: str | None = None,
    ) -> list[manual_appointment_entity.ManualAppointment]:
        raise NotImplementedError
