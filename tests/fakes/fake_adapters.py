import datetime
import typing

import src.adapters.outbound.inmemory.email_notifier_adapter as inmemory_email_notifier_adapter
import src.domain.entities.tenant as tenant_entity
import src.ports.clock_port as clock_port
import src.ports.google_calendar_provider_port as google_calendar_provider_port
import src.ports.id_generator_port as id_generator_port
import src.ports.llm_provider_port as llm_provider_port
import src.ports.tenant_repository_port as tenant_repository_port
import src.ports.whatsapp_provider_port as whatsapp_provider_port
import src.services.dto.google_calendar_dto as google_calendar_dto
import src.services.dto.llm_dto as llm_dto
import src.services.dto.webhook_dto as webhook_dto
import src.services.dto.whatsapp_dto as whatsapp_dto
import src.services.dto.whatsapp_template_dto as whatsapp_template_dto
import src.services.exceptions as service_exceptions

FakeEmailNotifier = inmemory_email_notifier_adapter.FakeEmailNotifierAdapter
SentEmail = inmemory_email_notifier_adapter.SentEmail

__all__ = [
    "FakeEmailNotifier",
    "SentEmail",
]


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
        self.queued_replies: list[llm_dto.AgentReplyDTO] = []
        self.queued_errors: list[service_exceptions.ExternalProviderError] = []

    def generate_reply(self, prompt_input: llm_dto.GenerateReplyInputDTO) -> llm_dto.AgentReplyDTO:
        if self.should_fail:
            raise service_exceptions.ExternalProviderError("simulated llm failure")
        if self.queued_errors:
            raise self.queued_errors.pop(0)
        self.calls.append(prompt_input)
        if self.queued_replies:
            return self.queued_replies.pop(0)
        return llm_dto.AgentReplyDTO(content=self.reply_content)


class FakeWhatsappProvider(whatsapp_provider_port.WhatsappProviderPort):
    def __init__(self) -> None:
        self.credential_by_code: dict[str, whatsapp_dto.EmbeddedSignupCredentialsDTO] = {}
        self.sent_messages: list[dict[str, str]] = []
        self.sent_template_body_parameters: list[list[str]] = []
        self.events: list[webhook_dto.IncomingMessageEventDTO] = []
        self.waba_subscriptions: list[dict[str, str]] = []
        self.phone_registrations: list[dict[str, str]] = []
        self.should_fail_subscription = False
        self.should_fail_phone_registration = False

    def build_embedded_signup_url(self, state: str) -> str:
        return f"https://example.test/embedded?state={state}"

    def exchange_code_for_credentials(
        self,
        code: str,
        *,
        from_js_sdk: bool = False,
        js_sdk_origin_url: str | None = None,
    ) -> whatsapp_dto.EmbeddedSignupCredentialsDTO:
        credentials = self.credential_by_code.get(code)
        if credentials is None:
            raise service_exceptions.ExternalProviderError("code not configured in fake provider")
        return credentials

    def resolve_credentials_from_token(
        self, access_token: str
    ) -> whatsapp_dto.EmbeddedSignupCredentialsDTO:
        for cred in self.credential_by_code.values():
            if cred.access_token == access_token:
                return cred
        raise service_exceptions.ExternalProviderError("token not configured in fake provider")

    def subscribe_app_to_waba(self, access_token: str, business_account_id: str) -> None:
        if self.should_fail_subscription:
            raise service_exceptions.ExternalProviderError("simulated subscribe failure")

        payload = {
            "access_token": access_token,
            "business_account_id": business_account_id,
        }
        self.waba_subscriptions.append(payload)

    def register_phone_number(
        self, access_token: str, phone_number_id: str, registration_pin: str | None = None
    ) -> None:
        if self.should_fail_phone_registration:
            raise service_exceptions.ExternalProviderError("simulated phone register failure")

        payload = {
            "access_token": access_token,
            "phone_number_id": phone_number_id,
        }
        self.phone_registrations.append(payload)

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

    def list_message_templates(
        self, access_token: str, waba_id: str
    ) -> list[whatsapp_template_dto.TemplateDTO]:
        del access_token
        del waba_id
        return []

    def create_message_template(
        self,
        access_token: str,
        waba_id: str,
        template: whatsapp_template_dto.CreateTemplateRequestDTO,
    ) -> whatsapp_template_dto.TemplateDTO:
        del access_token
        del waba_id
        return whatsapp_template_dto.TemplateDTO(
            id="fake-template-id",
            name=template.name,
            category=template.category,
            language=template.language,
            status="PENDING",
            components=list(template.components),
        )

    def delete_message_template(self, access_token: str, waba_id: str, template_name: str) -> None:
        del access_token
        del waba_id
        del template_name

    def send_template_message(
        self,
        access_token: str,
        phone_number_id: str,
        whatsapp_user_id: str,
        template_name: str,
        language_code: str,
        body_parameters: list[str],
    ) -> str:
        payload = {
            "access_token": access_token,
            "phone_number_id": phone_number_id,
            "whatsapp_user_id": whatsapp_user_id,
            "template_name": template_name,
            "language_code": language_code,
        }
        self.sent_messages.append(payload)
        self.sent_template_body_parameters.append(list(body_parameters))
        return f"outbound-template-{len(self.sent_messages)}"


class FakeGoogleCalendarProvider(google_calendar_provider_port.GoogleCalendarProviderPort):
    def __init__(self) -> None:
        self.oauth_url_state: list[str] = []
        self.tokens_by_code: dict[str, google_calendar_dto.GoogleOauthTokensDTO] = {}
        self.refreshed_tokens_by_refresh_token: dict[
            str, google_calendar_dto.GoogleOauthTokensDTO
        ] = {}
        self.metadata = google_calendar_dto.GoogleCalendarMetadataDTO(
            calendar_id="primary",
            timezone="America/Bogota",
        )
        self.busy_intervals: list[google_calendar_dto.GoogleCalendarBusyIntervalDTO] = []
        self.list_busy_intervals_call_count: int = 0
        self.created_events: list[google_calendar_dto.GoogleCalendarEventDTO] = []
        self.created_event_summaries: list[str] = []
        self.created_event_descriptions: list[str | None] = []
        self.last_create_attendee_emails: list[list[str]] = []
        self.last_create_with_meet: list[bool] = []
        self.deleted_event_ids: list[str] = []
        self.updated_events: list[google_calendar_dto.GoogleCalendarEventDTO] = []
        self.updated_event_summaries: list[str] = []
        self.updated_event_descriptions: list[str | None] = []
        self.last_update_attendee_emails: list[list[str]] = []
        self.last_update_with_meet: list[bool | None] = []
        self.busy_interval_errors: list[service_exceptions.ExternalProviderError] = []
        self.create_event_errors: list[service_exceptions.ExternalProviderError] = []
        self.delete_event_errors: list[service_exceptions.ExternalProviderError] = []
        self.update_event_errors: list[service_exceptions.ExternalProviderError] = []

    def build_oauth_connect_url(self, state: str, scopes: list[str]) -> str:
        del scopes
        self.oauth_url_state.append(state)
        return f"https://example.test/google-oauth?state={state}"

    def exchange_code_for_tokens(self, code: str) -> google_calendar_dto.GoogleOauthTokensDTO:
        tokens = self.tokens_by_code.get(code)
        if tokens is None:
            raise service_exceptions.ExternalProviderError("code not configured in fake google")
        return tokens.model_copy(deep=True)

    def refresh_access_token(self, refresh_token: str) -> google_calendar_dto.GoogleOauthTokensDTO:
        tokens = self.refreshed_tokens_by_refresh_token.get(refresh_token)
        if tokens is None:
            raise service_exceptions.ExternalProviderError(
                "refresh token not configured in fake google"
            )
        return tokens.model_copy(deep=True)

    def get_primary_calendar_metadata(
        self, access_token: str
    ) -> google_calendar_dto.GoogleCalendarMetadataDTO:
        del access_token
        return self.metadata.model_copy(deep=True)

    def list_busy_intervals(
        self,
        access_token: str,
        calendar_id: str,
        time_min: datetime.datetime,
        time_max: datetime.datetime,
        timezone: str,
    ) -> list[google_calendar_dto.GoogleCalendarBusyIntervalDTO]:
        if self.busy_interval_errors:
            raise self.busy_interval_errors.pop(0)
        del access_token
        del calendar_id
        del time_min
        del time_max
        del timezone
        self.list_busy_intervals_call_count += 1
        return [item.model_copy(deep=True) for item in self.busy_intervals]

    def create_event(
        self,
        access_token: str,
        calendar_id: str,
        start_at: datetime.datetime,
        end_at: datetime.datetime,
        timezone: str,
        summary: str,
        attendee_emails: list[str],
        with_meet: bool,
        conference_request_id: str,
        description: str | None = None,
        location: str | None = None,
    ) -> google_calendar_dto.GoogleCalendarEventDTO:
        if self.create_event_errors:
            raise self.create_event_errors.pop(0)
        del access_token
        del calendar_id
        del timezone
        del conference_request_id
        del location
        self.created_event_summaries.append(summary)
        self.created_event_descriptions.append(description)
        self.last_create_attendee_emails.append(list(attendee_emails))
        self.last_create_with_meet.append(with_meet)
        meet_url = "https://meet.google.com/fake-meet" if with_meet else None
        event = google_calendar_dto.GoogleCalendarEventDTO(
            event_id=f"event-{len(self.created_events) + 1}",
            start_at=start_at,
            end_at=end_at,
            meet_url=meet_url,
        )
        self.created_events.append(event)
        return event.model_copy(deep=True)

    def delete_event(
        self,
        access_token: str,
        calendar_id: str,
        event_id: str,
    ) -> None:
        if self.delete_event_errors:
            raise self.delete_event_errors.pop(0)
        del access_token
        del calendar_id
        self.deleted_event_ids.append(event_id)

    def update_event(
        self,
        access_token: str,
        calendar_id: str,
        event_id: str,
        start_at: datetime.datetime,
        end_at: datetime.datetime,
        timezone: str,
        summary: str,
        attendee_emails: list[str],
        description: str | None = None,
        location: str | None = None,
        with_meet: bool | None = None,
        conference_request_id: str | None = None,
    ) -> google_calendar_dto.GoogleCalendarEventDTO:
        if self.update_event_errors:
            raise self.update_event_errors.pop(0)
        del access_token
        del calendar_id
        del timezone
        del location
        del conference_request_id
        self.updated_event_summaries.append(summary)
        self.updated_event_descriptions.append(description)
        self.last_update_attendee_emails.append(list(attendee_emails))
        self.last_update_with_meet.append(with_meet)
        meet_url: str | None = None
        if with_meet is True:
            meet_url = "https://meet.google.com/fake-meet"
        elif with_meet is False:
            meet_url = None
        event = google_calendar_dto.GoogleCalendarEventDTO(
            event_id=event_id,
            start_at=start_at,
            end_at=end_at,
            meet_url=meet_url,
        )
        self.updated_events.append(event)
        return event.model_copy(deep=True)


class FakeTenantRepository(tenant_repository_port.TenantRepositoryPort):
    def __init__(self) -> None:
        self._tenants: dict[str, tenant_entity.Tenant] = {}

    def save(self, tenant: tenant_entity.Tenant) -> None:
        self._tenants[tenant.id] = tenant.model_copy(deep=True)

    def get_by_id(self, tenant_id: str) -> tenant_entity.Tenant | None:
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            return None
        return tenant.model_copy(deep=True)

    def delete_with_data(self, tenant_id: str) -> bool:
        if tenant_id not in self._tenants:
            return False
        del self._tenants[tenant_id]
        return True

    def list_all(self, include_admin: bool = False) -> list[tenant_entity.Tenant]:
        result = []
        for tenant in self._tenants.values():
            if not include_admin and tenant.is_admin_tenant:
                continue
            result.append(tenant.model_copy(deep=True))
        return result

    def get_admin_tenant(self) -> tenant_entity.Tenant | None:
        for tenant in self._tenants.values():
            if tenant.is_admin_tenant:
                return tenant.model_copy(deep=True)
        return None
