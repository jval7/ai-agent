import html as html_module
import json
import logging

import httpx

import src.infra.settings as app_settings
import src.ports.email_notifier_port as email_notifier_port
import src.services.exceptions as service_exceptions

logger = logging.getLogger(__name__)

_RESEND_API_URL = "https://api.resend.com/emails"

_BRAND_TEAL = "#006D77"
_BRAND_INK = "#181c1d"
_BRAND_INK_SOFT = "#40494a"
_BRAND_MUTED = "#6b7878"
_BRAND_FAINT = "#97a4a4"
_BRAND_SURFACE = "#f7fafa"
_BRAND_DIVIDER = "#ebeeee"
_FONT_BODY = (
    "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
)
_FONT_HEADLINE = "Manrope, Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"


def _render_branded_shell(title: str, body_html: str) -> str:
    safe_title = html_module.escape(title)
    return (
        "<!DOCTYPE html>"
        '<html lang="es">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{safe_title}</title>"
        "</head>"
        f'<body style="margin:0;padding:0;background-color:{_BRAND_SURFACE};'
        f'font-family:{_FONT_BODY};">'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
        f'style="background-color:{_BRAND_SURFACE};padding:40px 16px;">'
        '<tr><td align="center">'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" '
        'style="max-width:600px;width:100%;background-color:#ffffff;border-radius:16px;'
        'box-shadow:0 0 40px rgba(24,28,29,0.04);overflow:hidden;">'
        '<tr><td align="center" style="padding:32px 40px 8px 40px;">'
        f'<span style="font-family:{_FONT_HEADLINE};font-size:28px;font-weight:700;'
        f'color:{_BRAND_TEAL};letter-spacing:-0.02em;">Agendachat</span>'
        "</td></tr>"
        f'<tr><td style="padding:16px 40px 40px 40px;">{body_html}</td></tr>'
        f'<tr><td style="padding:24px 40px 32px 40px;border-top:1px solid {_BRAND_DIVIDER};">'
        f'<p style="margin:0;font-size:12px;line-height:18px;color:{_BRAND_MUTED};'
        'text-align:center;">'
        "Agendachat · Automatización conversacional para tu negocio"
        "</p></td></tr>"
        "</table>"
        f'<p style="margin:24px 0 0 0;font-size:11px;line-height:16px;color:{_BRAND_FAINT};'
        'text-align:center;">'
        "Si no esperabas este correo, podés ignorarlo de forma segura."
        "</p>"
        "</td></tr></table></body></html>"
    )


def _render_cta_button(label: str, url: str) -> str:
    safe_label = html_module.escape(label)
    safe_url = html_module.escape(url, quote=True)
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" '
        'style="margin:0 auto 24px auto;">'
        f'<tr><td style="background-color:{_BRAND_TEAL};border-radius:12px;">'
        f'<a href="{safe_url}" '
        f'style="display:inline-block;padding:14px 32px;font-family:{_FONT_BODY};'
        'font-size:16px;font-weight:600;color:#ffffff;text-decoration:none;">'
        f"{safe_label}"
        "</a></td></tr></table>"
    )


def _render_heading(text: str) -> str:
    safe_text = html_module.escape(text)
    return (
        f'<h1 style="margin:0 0 16px 0;font-family:{_FONT_HEADLINE};font-size:24px;'
        f'font-weight:700;color:{_BRAND_INK};line-height:32px;">{safe_text}</h1>'
    )


def _render_paragraph(text: str, color: str = _BRAND_INK_SOFT) -> str:
    safe_text = html_module.escape(text)
    return (
        f'<p style="margin:0 0 16px 0;font-size:16px;line-height:24px;color:{color};">'
        f"{safe_text}</p>"
    )


def _render_url_block(url: str, label: str = "O abrí este enlace en tu navegador:") -> str:
    safe_url = html_module.escape(url, quote=True)
    safe_label = html_module.escape(label)
    return (
        f'<p style="margin:0 0 8px 0;font-size:13px;line-height:20px;color:{_BRAND_MUTED};">'
        f"{safe_label}</p>"
        f'<p style="margin:0 0 24px 0;font-size:13px;line-height:20px;color:{_BRAND_TEAL};'
        'word-break:break-all;">'
        f'<a href="{safe_url}" style="color:{_BRAND_TEAL};text-decoration:underline;">'
        f"{safe_url}</a></p>"
    )


def _render_fineprint(text: str) -> str:
    safe_text = html_module.escape(text)
    return (
        f'<p style="margin:0;font-size:13px;line-height:20px;color:{_BRAND_FAINT};">{safe_text}</p>'
    )


def _render_greeting(to_name: str | None) -> str:
    if not to_name:
        return ""
    safe_name = html_module.escape(to_name)
    return (
        f'<p style="margin:0 0 16px 0;font-size:16px;line-height:24px;color:{_BRAND_INK};">'
        f"Hola {safe_name},</p>"
    )


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
        del tenant_name  # invitation copy is brand-centric, tenant name no longer surfaces here
        subject = "Invitación a Agendachat"
        body_html = (
            _render_heading("Invitación a Agendachat")
            + _render_greeting(to_name)
            + _render_paragraph(
                "Es un gusto para nosotros acompañarte en este proceso de automatización "
                "para tu negocio."
            )
            + _render_paragraph("Para empezar, configurá tu contraseña y activá tu cuenta:")
            + _render_cta_button("Crear mi cuenta", invitation_url)
            + _render_url_block(invitation_url)
            + _render_fineprint("Este enlace es válido por 7 días y solo puede usarse una vez.")
        )
        html_body = _render_branded_shell(subject, body_html)
        text_body = self._render_invitation_text(to_name=to_name, invitation_url=invitation_url)
        self._send(to_email=to_email, subject=subject, html=html_body, text=text_body)

    def send_password_reset(
        self,
        to_email: str,
        reset_url: str,
    ) -> None:
        subject = "Restablece tu contraseña en Agendachat"
        body_html = (
            _render_heading("Restablece tu contraseña")
            + _render_paragraph(
                "Recibimos una solicitud para restablecer la contraseña de tu cuenta."
            )
            + _render_paragraph("Hacé click abajo para crear una nueva:")
            + _render_cta_button("Crear nueva contraseña", reset_url)
            + _render_url_block(reset_url)
            + _render_fineprint(
                "Este enlace es válido por 30 minutos y solo puede usarse una vez. "
                "Si no solicitaste este cambio, ignorá este mensaje."
            )
        )
        html_body = _render_branded_shell(subject, body_html)
        text_body = self._render_password_reset_text(reset_url=reset_url)
        self._send(to_email=to_email, subject=subject, html=html_body, text=text_body)

    def send_welcome(
        self,
        to_email: str,
        to_name: str | None,
        tenant_name: str,
        login_url: str,
    ) -> None:
        del tenant_name  # welcome copy is brand-centric
        subject = "Bienvenido a Agendachat"
        body_html = (
            _render_heading("Tu cuenta está lista")
            + _render_greeting(to_name)
            + _render_paragraph(
                "Tu cuenta en Agendachat está activa. Desde tu panel podés conectar "
                "tu WhatsApp, configurar tu agenda y dejar al asistente trabajando "
                "por vos."
            )
            + _render_cta_button("Ir a mi panel", login_url)
            + _render_fineprint("Cualquier consulta, respondé este correo y te contestamos.")
        )
        html_body = _render_branded_shell(subject, body_html)
        text_body = self._render_welcome_text(to_name=to_name, login_url=login_url)
        self._send(to_email=to_email, subject=subject, html=html_body, text=text_body)

    def _render_invitation_text(self, to_name: str | None, invitation_url: str) -> str:
        greeting = f"Hola {to_name},\n\n" if to_name else ""
        return (
            f"{greeting}"
            "Es un gusto para nosotros acompañarte en este proceso de automatización "
            "para tu negocio.\n\n"
            "Para empezar, configurá tu contraseña y activá tu cuenta acá:\n"
            f"{invitation_url}\n\n"
            "Este enlace es válido por 7 días y solo puede usarse una vez.\n\n"
            "Si no esperabas esta invitación, ignorá este mensaje.\n\n"
            "— Equipo Agendachat\n"
        )

    def _render_password_reset_text(self, reset_url: str) -> str:
        return (
            "Recibimos una solicitud para restablecer la contraseña de tu cuenta.\n\n"
            f"Creá una nueva acá: {reset_url}\n\n"
            "Este enlace es válido por 30 minutos y solo puede usarse una vez.\n"
            "Si no solicitaste este cambio, ignorá este mensaje.\n\n"
            "— Equipo Agendachat\n"
        )

    def _render_welcome_text(self, to_name: str | None, login_url: str) -> str:
        greeting = f"Hola {to_name},\n\n" if to_name else ""
        return (
            f"{greeting}"
            "Tu cuenta en Agendachat está activa. Desde tu panel podés conectar tu "
            "WhatsApp, configurar tu agenda y dejar al asistente trabajando por vos.\n\n"
            f"Ingresá a: {login_url}\n\n"
            "Cualquier consulta, respondé este correo y te contestamos.\n\n"
            "— Equipo Agendachat\n"
        )

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
