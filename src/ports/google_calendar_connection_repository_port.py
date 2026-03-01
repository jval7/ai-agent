import abc

import src.domain.entities.google_calendar_connection as google_calendar_connection_entity


class GoogleCalendarConnectionRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, connection: google_calendar_connection_entity.GoogleCalendarConnection) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_tenant_id(
        self, tenant_id: str
    ) -> google_calendar_connection_entity.GoogleCalendarConnection | None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_oauth_state(
        self, oauth_state: str
    ) -> google_calendar_connection_entity.GoogleCalendarConnection | None:
        raise NotImplementedError
