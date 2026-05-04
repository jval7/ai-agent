import datetime
import enum

import pydantic


class InvitationPurpose(enum.StrEnum):
    ACCOUNT_SETUP = "account_setup"
    PASSWORD_RESET = "password_reset"


class InvitationToken(pydantic.BaseModel):
    token_hash: str
    user_id: str
    tenant_id: str
    purpose: InvitationPurpose
    expires_at: datetime.datetime
    consumed_at: datetime.datetime | None
    created_at: datetime.datetime
