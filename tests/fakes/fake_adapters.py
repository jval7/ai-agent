import datetime
import typing

import src.ports.clock_port as clock_port
import src.ports.id_generator_port as id_generator_port
import src.ports.llm_provider_port as llm_provider_port
import src.ports.whatsapp_provider_port as whatsapp_provider_port
import src.services.dto.llm_dto as llm_dto
import src.services.dto.webhook_dto as webhook_dto
import src.services.dto.whatsapp_dto as whatsapp_dto
import src.services.exceptions as service_exceptions


class FixedClock(clock_port.ClockPort):
    def __init__(self, current: datetime.datetime) -> None:
        self.current = current

    def now(self) -> datetime.datetime:
        return self.current

    def now_epoch_seconds(self) -> int:
        return int(self.current.timestamp())

    def advance(self, seconds: int) -> None:
        self.current = self.current + datetime.timedelta(seconds=seconds)


class SequenceIdGenerator(id_generator_port.IdGeneratorPort):
    def __init__(self, values: list[str]) -> None:
        self._values = values
        self._index = 0

    def new_id(self) -> str:
        if self._index >= len(self._values):
            raise ValueError("id sequence exhausted")
        value = self._values[self._index]
        self._index += 1
        return value

    def new_token(self) -> str:
        return self.new_id()


class FakeLlmProvider(llm_provider_port.LlmProviderPort):
    def __init__(self, reply_content: str) -> None:
        self.reply_content = reply_content
        self.calls: list[llm_dto.GenerateReplyInputDTO] = []
        self.should_fail = False

    def generate_reply(self, prompt_input: llm_dto.GenerateReplyInputDTO) -> llm_dto.AgentReplyDTO:
        if self.should_fail:
            raise service_exceptions.ExternalProviderError("simulated llm failure")
        self.calls.append(prompt_input)
        return llm_dto.AgentReplyDTO(content=self.reply_content)


class FakeWhatsappProvider(whatsapp_provider_port.WhatsappProviderPort):
    def __init__(self) -> None:
        self.credential_by_code: dict[str, whatsapp_dto.EmbeddedSignupCredentialsDTO] = {}
        self.sent_messages: list[dict[str, str]] = []
        self.events: list[webhook_dto.IncomingMessageEventDTO] = []

    def build_embedded_signup_url(self, state: str) -> str:
        return f"https://example.test/embedded?state={state}"

    def exchange_code_for_credentials(self, code: str) -> whatsapp_dto.EmbeddedSignupCredentialsDTO:
        credentials = self.credential_by_code.get(code)
        if credentials is None:
            raise service_exceptions.ExternalProviderError("code not configured in fake provider")
        return credentials

    def send_text_message(
        self,
        access_token: str,
        phone_number_id: str,
        whatsapp_user_id: str,
        text: str,
    ) -> str:
        payload = {
            "access_token": access_token,
            "phone_number_id": phone_number_id,
            "whatsapp_user_id": whatsapp_user_id,
            "text": text,
        }
        self.sent_messages.append(payload)
        return f"outbound-{len(self.sent_messages)}"

    def parse_incoming_message_events(
        self, payload: dict[str, typing.Any]
    ) -> list[webhook_dto.IncomingMessageEventDTO]:
        del payload
        return list(self.events)
