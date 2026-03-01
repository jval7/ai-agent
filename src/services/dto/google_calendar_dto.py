import datetime

import pydantic


class GoogleOauthSessionResponseDTO(pydantic.BaseModel):
    state: str
    connect_url: str


class GoogleOauthCompleteDTO(pydantic.BaseModel):
    code: str
    state: str


class GoogleOauthTokensDTO(pydantic.BaseModel):
    access_token: str
    refresh_token: str | None
    expires_in_seconds: int
    scope: str | None
    token_type: str | None


class GoogleCalendarMetadataDTO(pydantic.BaseModel):
    calendar_id: str
    timezone: str


class GoogleCalendarBusyIntervalDTO(pydantic.BaseModel):
    start_at: datetime.datetime
    end_at: datetime.datetime


class GoogleCalendarEventDTO(pydantic.BaseModel):
    event_id: str
    start_at: datetime.datetime
    end_at: datetime.datetime


class GoogleCalendarConnectionStatusDTO(pydantic.BaseModel):
    tenant_id: str
    status: str
    calendar_id: str | None
    professional_timezone: str | None
    connected_at: datetime.datetime | None


class GoogleCalendarAvailabilityResponseDTO(pydantic.BaseModel):
    tenant_id: str
    calendar_id: str
    timezone: str
    busy_intervals: list[GoogleCalendarBusyIntervalDTO]
