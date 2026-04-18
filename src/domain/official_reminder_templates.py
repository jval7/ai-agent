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
        name="appointment_reminder_attendance",
        language="es",
        category="UTILITY",
        body_text=(
            "Hola {{1}}, te recordamos tu cita agendada para el {{2}}. "
            "Te esperamos. Responde este mensaje si necesitas reagendar."
        ),
        example_values=["Juan García", "15/01/2026 10:00"],
    ),
    "PAYMENT": OfficialReminderTemplate(
        kind="PAYMENT",
        name="appointment_reminder_payment",
        language="es",
        category="UTILITY",
        body_text=(
            "Hola {{1}}, te recordamos tu cita agendada para el {{2}}. "
            "Aún no hemos recibido tu pago; por favor recuerda pagarlo antes de la cita "
            "para confirmarla."
        ),
        example_values=["Juan García", "15/01/2026 10:00"],
    ),
}


def get(kind: OfficialReminderKind) -> OfficialReminderTemplate:
    return OFFICIAL_REMINDER_TEMPLATES[kind]


def by_name(name: str) -> OfficialReminderKind | None:
    for kind, template in OFFICIAL_REMINDER_TEMPLATES.items():
        if template.name == name:
            return kind
    return None
