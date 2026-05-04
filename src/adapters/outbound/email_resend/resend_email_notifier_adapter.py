import json
import logging

import httpx

import src.infra.settings as app_settings
import src.ports.email_notifier_port as email_notifier_port
import src.services.exceptions as service_exceptions

logger = logging.getLogger(__name__)

_RESEND_API_URL = "https://api.resend.com/emails"


class ResendEmailNotifierAdapter(email_notifier_port.EmailNotifierPort):
    def __init__(
        self,
        settings: app_settings.Settings,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        self._client = http_client if http_client is not None else httpx.Client(timeout=15.0)

    def send_account_invitation(
        self,
        to_email: str,
        to_name: str | None,
        invitation_url: str,
        tenant_name: str,
    ) -> None:
        display_name = to_name or to_email
        subject = f"Invitación a {tenant_name} — configura tu cuenta"
        html_body = (
            f"<p>Hola {display_name},</p>"
            f"<p>Has sido invitado a <strong>{tenant_name}</strong>.</p>"
            f"<p>Haz clic en el siguiente enlace para configurar tu contraseña y activar tu cuenta:</p>"
            f'<p><a href="{invitation_url}">{invitation_url}</a></p>'
            f"<p>Este enlace es válido por 7 días y solo puede usarse una vez.</p>"
            f"<p>Si no esperabas esta invitación, ignora este mensaje.</p>"
        )
        text_body = (
            f"Hola {display_name},\n\n"
            f"Has sido invitado a {tenant_name}.\n\n"
            f"Configura tu cuenta en: {invitation_url}\n\n"
            f"Este enlace es válido por 7 días y solo puede usarse una vez.\n"
        )
        self._send(to_email=to_email, subject=subject, html=html_body, text=text_body)

    def send_password_reset(
        self,
        to_email: str,
        reset_url: str,
    ) -> None:
        subject = "Restablece tu contraseña"
        html_body = (
            f"<p>Recibimos una solicitud para restablecer la contraseña de tu cuenta.</p>"
            f"<p>Haz clic en el siguiente enlace para continuar:</p>"
            f'<p><a href="{reset_url}">{reset_url}</a></p>'
            f"<p>Este enlace es válido por 30 minutos y solo puede usarse una vez.</p>"
            f"<p>Si no solicitaste este cambio, ignora este mensaje.</p>"
        )
        text_body = (
            f"Recibimos una solicitud para restablecer la contraseña de tu cuenta.\n\n"
            f"Restablece tu contraseña en: {reset_url}\n\n"
            f"Este enlace es válido por 30 minutos y solo puede usarse una vez.\n"
        )
        self._send(to_email=to_email, subject=subject, html=html_body, text=text_body)

    def send_welcome(
        self,
        to_email: str,
        to_name: str | None,
        tenant_name: str,
        login_url: str,
    ) -> None:
        display_name = to_name or to_email
        subject = f"Bienvenido a {tenant_name}"
        html_body = (
            f"<p>Hola {display_name},</p>"
            f"<p>Tu cuenta en <strong>{tenant_name}</strong> está lista.</p>"
            f'<p>Inicia sesión en: <a href="{login_url}">{login_url}</a></p>'
        )
        text_body = (
            f"Hola {display_name},\n\n"
            f"Tu cuenta en {tenant_name} está lista.\n\n"
            f"Inicia sesión en: {login_url}\n"
        )
        self._send(to_email=to_email, subject=subject, html=html_body, text=text_body)

    def _send(self, to_email: str, subject: str, html: str, text: str) -> None:
        api_key = self._settings.resend_api_key
        if not api_key:
            raise service_exceptions.ExternalProviderError("resend api key is not configured")
        from_address = f"{self._settings.resend_from_name} <{self._settings.resend_from_email}>"
        payload = {
            "from": from_address,
            "to": [to_email],
            "subject": subject,
            "html": html,
            "text": text,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = self._client.post(_RESEND_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            response_payload = response.json()
        except httpx.TimeoutException as error:
            raise service_exceptions.ExternalProviderError(
                "timeout while sending email via resend"
            ) from error
        except httpx.RequestError as error:
            raise service_exceptions.ExternalProviderError(
                f"network error while sending email via resend: {error}"
            ) from error
        except httpx.HTTPStatusError as error:
            response_text = error.response.text.strip()
            if response_text:
                raise service_exceptions.ExternalProviderError(
                    f"resend rejected request: {response_text}"
                ) from error
            raise service_exceptions.ExternalProviderError("resend rejected request") from error
        except json.JSONDecodeError as error:
            raise service_exceptions.ExternalProviderError(
                "invalid response from resend"
            ) from error

        if not isinstance(response_payload, dict):
            raise service_exceptions.ExternalProviderError("invalid payload format from resend")
        email_id = response_payload.get("id")
        if not isinstance(email_id, str) or not email_id:
            raise service_exceptions.ExternalProviderError("resend did not return email id")
        logger.info(
            "email.sent",
            extra={
                "event_data": {
                    "event": "email.sent",
                    "to_email": to_email,
                    "subject": subject,
                    "resend_id": email_id,
                }
            },
        )
