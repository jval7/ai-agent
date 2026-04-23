import re

import src.domain.official_reminder_templates as official_reminder_templates

# Meta template name rule: lowercase snake_case, starts with letter, max 512 chars.
_META_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,511}$")


def test_template_names_comply_with_meta_naming_rules() -> None:
    for kind, template in official_reminder_templates.OFFICIAL_REMINDER_TEMPLATES.items():
        assert _META_NAME_PATTERN.match(template.name), (
            f"Template name '{template.name}' for kind '{kind}' "
            "does not comply with Meta naming rules"
        )


def test_by_name_returns_correct_kind_for_attendance() -> None:
    attendance_template = official_reminder_templates.OFFICIAL_REMINDER_TEMPLATES["ATTENDANCE"]
    result = official_reminder_templates.by_name(attendance_template.name)
    assert result == "ATTENDANCE"


def test_by_name_returns_correct_kind_for_payment() -> None:
    payment_template = official_reminder_templates.OFFICIAL_REMINDER_TEMPLATES["PAYMENT"]
    result = official_reminder_templates.by_name(payment_template.name)
    assert result == "PAYMENT"


def test_by_name_returns_none_for_unknown_name() -> None:
    result = official_reminder_templates.by_name("some_random_custom_template")
    assert result is None


def test_get_returns_attendance_template() -> None:
    template = official_reminder_templates.get("ATTENDANCE")
    assert template.kind == "ATTENDANCE"
    assert template.category == "UTILITY"
    assert template.language == "es"
    assert "{{1}}" in template.body_text
    assert "{{2}}" in template.body_text


def test_get_returns_payment_template() -> None:
    template = official_reminder_templates.get("PAYMENT")
    assert template.kind == "PAYMENT"
    assert template.category == "UTILITY"
    assert template.language == "es"
    assert "{{1}}" in template.body_text
    assert "{{2}}" in template.body_text


def test_all_templates_have_example_values() -> None:
    for kind, template in official_reminder_templates.OFFICIAL_REMINDER_TEMPLATES.items():
        assert len(template.example_values) >= 2, (
            f"Template '{kind}' must have at least 2 example values for {{{{1}}}} and {{{{2}}}}"
        )


def test_template_names_are_unique() -> None:
    names = [t.name for t in official_reminder_templates.OFFICIAL_REMINDER_TEMPLATES.values()]
    assert len(names) == len(set(names)), "Official template names must be unique"
