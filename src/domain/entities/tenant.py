import datetime

import pydantic


class Tenant(pydantic.BaseModel):
    id: str
    name: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
