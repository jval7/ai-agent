import datetime

import pydantic


class ProcessedWebhookEvent(pydantic.BaseModel):
    provider_event_id: str
    tenant_id: str
    processed_at: datetime.datetime
