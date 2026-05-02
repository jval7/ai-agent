import datetime

import src.services.scheduling_slot_formatter as scheduling_slot_formatter


def test_format_appointment_natural_with_end_renders_full_range_in_bogota() -> None:
    # 2026-05-16 14:00 UTC -> 09:00 Bogota; 15:00 UTC -> 10:00 Bogota
    start_at = datetime.datetime(2026, 5, 16, 14, 0, tzinfo=datetime.UTC)
    end_at = datetime.datetime(2026, 5, 16, 15, 0, tzinfo=datetime.UTC)

    result = scheduling_slot_formatter.format_appointment_natural(
        start_at=start_at,
        end_at=end_at,
        timezone_name="America/Bogota",
    )

    assert "sabado 16 de mayo de 2026" in result
    assert "9:00 am" in result
    assert "10:00 am" in result
    assert "hora Colombia" in result


def test_format_appointment_natural_without_end_uses_a_las_phrase() -> None:
    start_at = datetime.datetime(2026, 5, 16, 14, 0, tzinfo=datetime.UTC)

    result = scheduling_slot_formatter.format_appointment_natural(
        start_at=start_at,
        end_at=None,
        timezone_name="America/Bogota",
    )

    assert result == "sabado 16 de mayo de 2026 a las 9:00 am hora Colombia"


def test_format_appointment_natural_mexico_city_uses_hora_mexico_label() -> None:
    # 2026-05-16 15:00 UTC -> 10:00 Mexico_City (UTC-5); 16:00 UTC -> 11:00
    start_at = datetime.datetime(2026, 5, 16, 15, 0, tzinfo=datetime.UTC)
    end_at = datetime.datetime(2026, 5, 16, 16, 0, tzinfo=datetime.UTC)

    result = scheduling_slot_formatter.format_appointment_natural(
        start_at=start_at,
        end_at=end_at,
        timezone_name="America/Mexico_City",
    )

    assert "10:00 am" in result
    assert "hora México" in result
    assert "hora Colombia" not in result
