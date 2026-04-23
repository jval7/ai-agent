import datetime
import zoneinfo

import src.services.reminder_date_formatter as reminder_date_formatter

_BOGOTA = zoneinfo.ZoneInfo("America/Bogota")


def _now(year: int, month: int, day: int, hour: int = 9) -> datetime.datetime:
    return datetime.datetime(year, month, day, hour, 0, tzinfo=_BOGOTA)


def test_format_natural_date_today() -> None:
    now = _now(2026, 4, 22, hour=8)  # Wednesday
    appointment = datetime.datetime(2026, 4, 22, 13, 0, tzinfo=_BOGOTA)
    result = reminder_date_formatter.format_natural_date(appointment, now)
    assert result == "hoy miércoles 22 de abril a la 1 pm"


def test_format_natural_date_tomorrow() -> None:
    now = _now(2026, 4, 21)  # Tuesday
    appointment = datetime.datetime(2026, 4, 22, 13, 0, tzinfo=_BOGOTA)  # Wednesday
    result = reminder_date_formatter.format_natural_date(appointment, now)
    assert result == "mañana miércoles 22 de abril a la 1 pm"


def test_format_natural_date_day_after_tomorrow() -> None:
    now = _now(2026, 4, 20)  # Monday
    appointment = datetime.datetime(2026, 4, 22, 10, 0, tzinfo=_BOGOTA)  # Wednesday
    result = reminder_date_formatter.format_natural_date(appointment, now)
    assert result == "pasado mañana miércoles 22 de abril a las 10 am"


def test_format_natural_date_within_week() -> None:
    now = _now(2026, 4, 20)  # Monday
    appointment = datetime.datetime(2026, 4, 25, 15, 30, tzinfo=_BOGOTA)  # Saturday (5 days)
    result = reminder_date_formatter.format_natural_date(appointment, now)
    assert result == "el sábado 25 de abril a las 3:30 pm"


def test_format_natural_date_far_future_includes_year() -> None:
    now = _now(2026, 4, 21)
    appointment = datetime.datetime(2026, 11, 8, 10, 0, tzinfo=_BOGOTA)  # Sunday in ~200 days
    result = reminder_date_formatter.format_natural_date(appointment, now)
    assert result == "el domingo 8 de noviembre de 2026 a las 10 am"


def test_format_natural_date_handles_noon_and_midnight() -> None:
    now = _now(2026, 4, 20)
    appointment_noon = datetime.datetime(2026, 4, 21, 12, 0, tzinfo=_BOGOTA)
    appointment_midnight = datetime.datetime(2026, 4, 21, 0, 0, tzinfo=_BOGOTA)

    noon_result = reminder_date_formatter.format_natural_date(appointment_noon, now)
    midnight_result = reminder_date_formatter.format_natural_date(appointment_midnight, now)

    assert noon_result == "mañana martes 21 de abril a las 12 pm"
    assert midnight_result == "mañana martes 21 de abril a las 12 am"


def test_format_natural_date_converts_utc_input_to_bogota() -> None:
    # 2026-04-22 18:00 UTC = 2026-04-22 13:00 Bogota (mismo día).
    now = datetime.datetime(2026, 4, 22, 12, 0, tzinfo=datetime.UTC)  # 07:00 Bogota
    appointment = datetime.datetime(2026, 4, 22, 18, 0, tzinfo=datetime.UTC)
    result = reminder_date_formatter.format_natural_date(appointment, now)
    assert result == "hoy miércoles 22 de abril a la 1 pm"
