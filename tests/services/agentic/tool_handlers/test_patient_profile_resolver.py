"""Unit tests for PatientProfileResolver internal helpers.

Focuses on _normalize_patient_age, which previously rejected natural-language
inputs like "33 años" because it required pure-digit strings — pushing the bot
to re-ask the patient for their age in run-time.
"""

from __future__ import annotations

import unittest.mock

import src.services.agentic.tool_handlers.patient_profile_resolver as resolver_module


def _make_resolver() -> resolver_module.PatientProfileResolver:
    """Build a resolver with mocked deps; only internal helpers are exercised."""
    return resolver_module.PatientProfileResolver(
        scheduling_svc=unittest.mock.MagicMock(),
        patient_repository=unittest.mock.MagicMock(),
        clock=unittest.mock.MagicMock(),
        google_calendar_onboarding_service=unittest.mock.MagicMock(),
        sleep_seconds=lambda _: None,
    )


def test_normalize_patient_age_int_passthrough() -> None:
    resolver = _make_resolver()
    assert resolver._normalize_patient_age(33) == 33


def test_normalize_patient_age_pure_digit_string() -> None:
    resolver = _make_resolver()
    assert resolver._normalize_patient_age("33") == 33


def test_normalize_patient_age_with_anos_suffix() -> None:
    """Real case from Sandra Posso conversation: patient typed '33 años'."""
    resolver = _make_resolver()
    assert resolver._normalize_patient_age("33 años") == 33


def test_normalize_patient_age_with_natural_phrase() -> None:
    resolver = _make_resolver()
    assert resolver._normalize_patient_age("tengo 33") == 33
    assert resolver._normalize_patient_age("33 anos") == 33
    assert resolver._normalize_patient_age("28yr") == 28


def test_normalize_patient_age_none_and_empty() -> None:
    resolver = _make_resolver()
    assert resolver._normalize_patient_age(None) is None
    assert resolver._normalize_patient_age("") is None
    assert resolver._normalize_patient_age("   ") is None


def test_normalize_patient_age_no_digits() -> None:
    resolver = _make_resolver()
    assert resolver._normalize_patient_age("treinta y tres") is None
    assert resolver._normalize_patient_age("xyz") is None


def test_normalize_patient_age_takes_first_integer() -> None:
    """Multi-number inputs take the first \\d{1,3} match — downstream
    range check rejects nonsensical values."""
    resolver = _make_resolver()
    assert resolver._normalize_patient_age("33 años, vivo en cra 5") == 33
