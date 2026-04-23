import typing

import pydantic

OfficialReminderKind = typing.Literal["ATTENDANCE", "PAYMENT"]


class OfficialReminderTemplate(pydantic.BaseModel):
    kind: OfficialReminderKind
    name: str
    language: str
    category: str
    body_text: str
    example_values: list[str]


OFFICIAL_REMINDER_TEMPLATES: dict[OfficialReminderKind, OfficialReminderTemplate] = {
    "ATTENDANCE": OfficialReminderTemplate(
        kind="ATTENDANCE",
        name="recordatorio_de_asistencia",
        language="es",
        category="UTILITY",
        body_text=(
            "Hola {{1}} feliz día, te envío la confirmación de la sesión de {{2}} "
            "de forma {{3}}, más detalles en el correo de agendamiento de google "
            "calendar."
        ),
        example_values=[
            "Juan García",
            "mañana miércoles 22 de abril a la 1 pm",
            "virtual por Google Meet",
        ],
    ),
    "PAYMENT": OfficialReminderTemplate(
        kind="PAYMENT",
        name="recordatorio_de_pago",
        language="es",
        category="UTILITY",
        body_text=(
            "Hola {{1}} feliz día, recuerda que para la confirmación de tu sesión "
            "{{2}} debes realizar el pago por los siguientes canales: {{3}}. "
            "Envía tu comprobante al chat antes de tu sesión. Pregunta por nuestros "
            "paquetes 👌🏻"
        ),
        example_values=[
            "Juan García",
            "el lunes 8 de noviembre de 2026 a las 10 am",
            "Nequi: 300 123 4567 / Bancolombia ahorros 1234-5678-9012",
        ],
    ),
}


def get(kind: OfficialReminderKind) -> OfficialReminderTemplate:
    return OFFICIAL_REMINDER_TEMPLATES[kind]


def by_name(name: str) -> OfficialReminderKind | None:
    for kind, template in OFFICIAL_REMINDER_TEMPLATES.items():
        if template.name == name:
            return kind
    return None
