import datetime
import typing

import pydantic


class SchedulingSlot(pydantic.BaseModel):
    id: str
    start_at: datetime.datetime
    end_at: datetime.datetime
    timezone: str
    status: typing.Literal["PROPOSED", "REJECTED", "SELECTED", "BOOKED", "UNAVAILABLE"]

    @pydantic.model_validator(mode="after")
    def validate_range(self) -> "SchedulingSlot":
        if self.end_at <= self.start_at:
            raise ValueError("slot end_at must be greater than start_at")
        return self
