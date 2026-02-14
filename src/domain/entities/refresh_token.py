import datetime

import pydantic


class RefreshTokenRecord(pydantic.BaseModel):
    jti: str
    user_id: str
    tenant_id: str
    token_hash: str
    expires_at: datetime.datetime
    revoked_at: datetime.datetime | None
    created_at: datetime.datetime
