import pydantic

import src.ports.email_notifier_port as email_notifier_port


class SentEmail(pydantic.BaseModel):
    kind: str
    to_email: str
    to_name: str | None = None
    url: str | None = None
    tenant_name: str | None = None
    login_url: str | None = None


class FakeEmailNotifierAdapter(email_notifier_port.EmailNotifierPort):
    def __init__(self, should_fail: bool = False) -> None:
        self.sent_emails: list[SentEmail] = []
        self.should_fail = should_fail

    def send_account_invitation(
        self,
        to_email: str,
        to_name: str | None,
        invitation_url: str,
        tenant_name: str,
    ) -> None:
        if self.should_fail:
            import src.services.exceptions as service_exceptions

            raise service_exceptions.ExternalProviderError("simulated email failure")
        self.sent_emails.append(
            SentEmail(
                kind="account_invitation",
                to_email=to_email,
                to_name=to_name,
                url=invitation_url,
                tenant_name=tenant_name,
            )
        )

    def send_password_reset(
        self,
        to_email: str,
        reset_url: str,
    ) -> None:
        if self.should_fail:
            import src.services.exceptions as service_exceptions

            raise service_exceptions.ExternalProviderError("simulated email failure")
        self.sent_emails.append(
            SentEmail(
                kind="password_reset",
                to_email=to_email,
                url=reset_url,
            )
        )

    def send_welcome(
        self,
        to_email: str,
        to_name: str | None,
        tenant_name: str,
        login_url: str,
    ) -> None:
        if self.should_fail:
            import src.services.exceptions as service_exceptions

            raise service_exceptions.ExternalProviderError("simulated email failure")
        self.sent_emails.append(
            SentEmail(
                kind="welcome",
                to_email=to_email,
                to_name=to_name,
                tenant_name=tenant_name,
                login_url=login_url,
            )
        )
