import datetime
import typing

import pydantic


class GoogleCalendarConnection(pydantic.BaseModel):
    tenant_id: str
    professional_user_id: str
    status: typing.Literal["DISCONNECTED", "PENDING", "CONNECTED"]
    calendar_id: str | None
    timezone: str | None
    access_token: str | None
    refresh_token: str | None
    token_expires_at: datetime.datetime | None
    oauth_state: str | None
    scope: str | None
    updated_at: datetime.datetime
    connected_at: datetime.datetime | None
