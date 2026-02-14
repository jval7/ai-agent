import datetime

import pydantic


class WhatsappUser(pydantic.BaseModel):
    id: str
    tenant_id: str
    display_name: str | None
    created_at: datetime.datetime
