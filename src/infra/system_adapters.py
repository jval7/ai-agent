import datetime
import secrets
import uuid

import src.ports.clock_port as clock_port
import src.ports.id_generator_port as id_generator_port


class SystemClockAdapter(clock_port.ClockPort):
    def now(self) -> datetime.datetime:
        return datetime.datetime.now(tz=datetime.UTC)

    def now_epoch_seconds(self) -> int:
        return int(self.now().timestamp())


class UuidIdGeneratorAdapter(id_generator_port.IdGeneratorPort):
    def new_id(self) -> str:
        return str(uuid.uuid4())

    def new_token(self) -> str:
        return secrets.token_urlsafe(32)
