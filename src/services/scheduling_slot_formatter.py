import datetime
import zoneinfo

_SPANISH_WEEKDAY_NAMES = (
    "lunes",
    "martes",
    "miercoles",
    "jueves",
    "viernes",
    "sabado",
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


def format_slot_option_line(
    option_number: str,
    start_at: datetime.datetime,
    timezone_name: str,
) -> str:
    localized_start = _localize_datetime(start_at, timezone_name)
    date_text = _format_spanish_date(localized_start)
    start_time_text = _format_spanish_time(localized_start)
    return f"{option_number}) {date_text} a las {start_time_text} - {timezone_name}"


def _localize_datetime(
    value: datetime.datetime,
    timezone_name: str,
) -> datetime.datetime:
    try:
        timezone = zoneinfo.ZoneInfo(timezone_name)
    except zoneinfo.ZoneInfoNotFoundError:
        return value

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone)
    return value.astimezone(timezone)


def _format_spanish_date(value: datetime.datetime) -> str:
    weekday_name = _SPANISH_WEEKDAY_NAMES[value.weekday()]
    month_name = _SPANISH_MONTH_NAMES[value.month - 1]
    return f"{weekday_name} {value.day} de {month_name}"


def _format_spanish_time(value: datetime.datetime) -> str:
    hour_12 = value.hour % 12
    if hour_12 == 0:
        hour_12 = 12
    period = "am"
    if value.hour >= 12:
        period = "pm"
    return f"{hour_12}:{value.minute:02d} {period}"
