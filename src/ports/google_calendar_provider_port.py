import abc
import datetime

import src.services.dto.google_calendar_dto as google_calendar_dto


class GoogleCalendarProviderPort(abc.ABC):
    @abc.abstractmethod
    def build_oauth_connect_url(self, state: str, scopes: list[str]) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def exchange_code_for_tokens(self, code: str) -> google_calendar_dto.GoogleOauthTokensDTO:
        raise NotImplementedError

    @abc.abstractmethod
    def refresh_access_token(self, refresh_token: str) -> google_calendar_dto.GoogleOauthTokensDTO:
        raise NotImplementedError

    @abc.abstractmethod
    def get_primary_calendar_metadata(
        self, access_token: str
    ) -> google_calendar_dto.GoogleCalendarMetadataDTO:
        raise NotImplementedError

    @abc.abstractmethod
    def list_busy_intervals(
        self,
        access_token: str,
        calendar_id: str,
        time_min: datetime.datetime,
        time_max: datetime.datetime,
        timezone: str,
    ) -> list[google_calendar_dto.GoogleCalendarBusyIntervalDTO]:
        raise NotImplementedError

    @abc.abstractmethod
    def create_event(
        self,
        access_token: str,
        calendar_id: str,
        start_at: datetime.datetime,
        end_at: datetime.datetime,
        timezone: str,
        summary: str,
    ) -> google_calendar_dto.GoogleCalendarEventDTO:
        raise NotImplementedError
