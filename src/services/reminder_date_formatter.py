"""Format an appointment datetime as a natural-language Spanish string.

Used by reminder_service when building the body_parameters of an outgoing
reminder template message. The output is meant to be read aloud inside a
sentence such as "te envío la confirmación de la sesión de <fecha>".

Rules (relative to ``now``):

- Same day  → "hoy <día_semana> <día> de <mes> a la(s) <hora> <am/pm>"
- +1 day    → "mañana <día_semana> <día> de <mes> a la(s) <hora> <am/pm>"
- +2 days   → "pasado mañana <día_semana> <día> de <mes> a la(s) <hora> <am/pm>"
- 3..7 days → "el <día_semana> <día> de <mes> a la(s) <hora> <am/pm>"
- >7 days   → "el <día_semana> <día> de <mes> de <año> a la(s) <hora> <am/pm>"

Both datetimes are converted to the given timezone before formatting.
"""

import datetime
import zoneinfo

_SPANISH_WEEKDAY_NAMES = (
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
)
_SPANISH_MONTH_NAMES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def format_natural_date(
    appointment_at: datetime.datetime,
    now: datetime.datetime,
    timezone_name: str = "America/Bogota",
) -> str:
    timezone = zoneinfo.ZoneInfo(timezone_name)
    appointment_local = appointment_at.astimezone(timezone)
    now_local = now.astimezone(timezone)

    days_diff = (appointment_local.date() - now_local.date()).days

    weekday = _SPANISH_WEEKDAY_NAMES[appointment_local.weekday()]
    month = _SPANISH_MONTH_NAMES[appointment_local.month - 1]
    day = appointment_local.day
    year = appointment_local.year
    hour_text = _format_spanish_hour(appointment_local)

    if days_diff == 0:
        return f"hoy {weekday} {day} de {month} {hour_text}"
    if days_diff == 1:
        return f"mañana {weekday} {day} de {month} {hour_text}"
    if days_diff == 2:
        return f"pasado mañana {weekday} {day} de {month} {hour_text}"
    if 3 <= days_diff <= 7:
        return f"el {weekday} {day} de {month} {hour_text}"
    return f"el {weekday} {day} de {month} de {year} {hour_text}"


def _format_spanish_hour(value: datetime.datetime) -> str:
    hour_24 = value.hour
    minute = value.minute
    period = "pm" if hour_24 >= 12 else "am"

    hour_12 = hour_24 % 12
    if hour_12 == 0:
        hour_12 = 12

    article = "la" if hour_12 == 1 else "las"

    if minute == 0:
        return f"a {article} {hour_12} {period}"
    return f"a {article} {hour_12}:{minute:02d} {period}"
