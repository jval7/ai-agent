import abc
import datetime

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
    def count_by_tenant(self, tenant_id: str, status: str | None = None) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def sum_paid_revenue_since(self, tenant_id: str, since: datetime.datetime) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def list_by_patient(
        self,
        tenant_id: str,
        patient_whatsapp_user_id: str,
        status: str | None = None,
    ) -> list[manual_appointment_entity.ManualAppointment]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_latest_activity(self, tenant_id: str) -> datetime.datetime | None:
        raise NotImplementedError
