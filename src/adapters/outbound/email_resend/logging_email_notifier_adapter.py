import logging

import src.ports.email_notifier_port as email_notifier_port

logger = logging.getLogger(__name__)


class LoggingEmailNotifierAdapter(email_notifier_port.EmailNotifierPort):
    """Dev/CI adapter that logs emails instead of sending them."""

    def send_account_invitation(
        self,
        to_email: str,
        to_name: str | None,
        invitation_url: str,
        tenant_name: str,
    ) -> None:
        logger.info(
            "email.account_invitation.logged",
            extra={
                "event_data": {
                    "event": "email.account_invitation.logged",
                    "to_email": to_email,
                    "to_name": to_name,
                    "tenant_name": tenant_name,
                    "invitation_url": invitation_url,
                }
            },
        )

    def send_password_reset(
        self,
        to_email: str,
        reset_url: str,
    ) -> None:
        logger.info(
            "email.password_reset.logged",
            extra={
                "event_data": {
                    "event": "email.password_reset.logged",
                    "to_email": to_email,
                    "reset_url": reset_url,
                }
            },
        )

    def send_welcome(
        self,
        to_email: str,
        to_name: str | None,
        tenant_name: str,
        login_url: str,
    ) -> None:
        logger.info(
            "email.welcome.logged",
            extra={
                "event_data": {
                    "event": "email.welcome.logged",
                    "to_email": to_email,
                    "to_name": to_name,
                    "tenant_name": tenant_name,
                    "login_url": login_url,
                }
            },
        )
