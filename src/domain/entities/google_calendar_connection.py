import datetime
import typing

import pydantic


class GoogleCalendarConnection(pydantic.BaseModel):
    # REAUTH_REQUIRED: Google rejected our refresh_token with invalid_grant
    # (the user revoked access, the OAuth app is in testing mode and the
    # token aged out, or the token was rotated). The connection still has
    # the old refresh_token persisted but it is no longer usable; the user
    # has to re-run the OAuth flow to issue a new one. Keep the status
    # surfaced explicitly so the UI can prompt for reconnection instead of
    # silently failing every Calendar call with a 502.
    tenant_id: str
    professional_user_id: str
    status: typing.Literal["DISCONNECTED", "PENDING", "CONNECTED", "REAUTH_REQUIRED"]
    calendar_id: str | None
    timezone: str | None
    access_token: str | None
    refresh_token: str | None
    token_expires_at: datetime.datetime | None
    oauth_state: str | None
    scope: str | None
    updated_at: datetime.datetime
    connected_at: datetime.datetime | None
