import datetime
import typing

import pydantic


class WhatsappConnection(pydantic.BaseModel):
    tenant_id: str
    phone_number_id: str | None
    business_account_id: str | None
    access_token: str | None
    status: typing.Literal["DISCONNECTED", "PENDING", "CONNECTED"]
    embedded_signup_state: str | None
    updated_at: datetime.datetime
