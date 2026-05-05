import datetime
import pathlib

import pydantic
import pytest

import scripts.coverage as coverage
import scripts.personas as personas_module
import src.domain.entities.agent_profile as agent_profile_entity

_FIXTURES_DIR = pathlib.Path(__file__).resolve().parent.parent / "fixtures" / "profiles"


def _shape(name: str, required_combos: list[list[personas_module.Capability]]) -> coverage.Shape:
    return coverage.Shape(
        metadata=coverage.ShapeMetadata(
            name=name, description="t", required_combos=required_combos
        ),
        agent_profile=agent_profile_entity.AgentProfile(
            tenant_id=f"{name}_tenant",
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        ),
    )


def _persona(
    persona_id: str, capabilities: list[personas_module.Capability]
) -> personas_module.Persona:
    return personas_module.Persona(
        id=persona_id,
        display_name=persona_id.title(),
        whatsapp_user_id=f"57300{persona_id}",
        persona_text="t",
        capabilities=capabilities,
    )


class TestDetectUncoveredCombos:
    def test_empty_required_combos_returns_empty(self) -> None:
        shape = _shape("smoke", [])
        assert coverage.detect_uncovered_combos(shape, []) == []
        assert coverage.detect_uncovered_combos(shape, [_persona("p1", ["new_patient"])]) == []

    def test_single_combo_covered_by_single_persona(self) -> None:
        shape = _shape("multi", [["local_patient", "asks_about_price"]])
        personas = [_persona("p1", ["local_patient", "asks_about_price"])]
        assert coverage.detect_uncovered_combos(shape, personas) == []

    def test_combo_uncovered_when_persona_misses_one_cap(self) -> None:
        # AND semantics dentro del combo: si la persona no tiene TODOS los caps
        # del combo, el combo queda uncovered aunque tenga otros caps.
        shape = _shape("multi", [["local_patient", "asks_about_price"]])
        personas = [_persona("p1", ["local_patient"])]  # falta asks_about_price
        assert coverage.detect_uncovered_combos(shape, personas) == [
            ["local_patient", "asks_about_price"]
        ]

    def test_or_between_combos_one_covered_one_not(self) -> None:
        shape = _shape(
            "multi",
            [
                ["local_patient", "asks_about_price"],
                ["foreign_patient", "asks_about_price"],
            ],
        )
        personas = [_persona("local", ["local_patient", "asks_about_price"])]
        assert coverage.detect_uncovered_combos(shape, personas) == [
            ["foreign_patient", "asks_about_price"]
        ]

    def test_combos_split_across_multiple_personas(self) -> None:
        shape = _shape(
            "split",
            [["local_patient"], ["foreign_patient"]],
        )
        personas = [
            _persona("p1", ["local_patient"]),
            _persona("p2", ["foreign_patient"]),
        ]
        assert coverage.detect_uncovered_combos(shape, personas) == []

    def test_uncovered_preserves_declaration_order(self) -> None:
        shape = _shape(
            "multi",
            [
                ["foreign_patient", "asks_about_price"],
                ["local_patient", "asks_about_price"],
                ["returning_patient"],
            ],
        )
        personas = [_persona("p1", ["new_patient"])]
        # Los 3 combos están descubiertos; el orden debe coincidir con la
        # declaración para que los reportes sean estables.
        assert coverage.detect_uncovered_combos(shape, personas) == [
            ["foreign_patient", "asks_about_price"],
            ["local_patient", "asks_about_price"],
            ["returning_patient"],
        ]


class TestAssertCombosCovered:
    def test_no_raise_when_all_combos_covered(self) -> None:
        shape = _shape("ok", [["local_patient"]])
        coverage.assert_combos_covered(shape, [_persona("p1", ["local_patient"])])

    def test_no_raise_when_required_combos_empty(self) -> None:
        shape = _shape("smoke", [])
        coverage.assert_combos_covered(shape, [])

    def test_raises_with_uncovered_combos_in_message(self) -> None:
        shape = _shape("gap", [["returning_patient"]])
        personas = [_persona("p1", ["new_patient"])]
        with pytest.raises(coverage.CoverageGapError) as exc_info:
            coverage.assert_combos_covered(shape, personas)
        message = str(exc_info.value)
        assert "shape='gap'" in message
        assert "returning_patient" in message

    def test_raises_with_all_uncovered_combos_listed(self) -> None:
        shape = _shape(
            "multi-gap",
            [
                ["local_patient", "asks_about_price"],
                ["foreign_patient", "asks_about_payment_method"],
            ],
        )
        personas = [_persona("p1", ["new_patient"])]
        with pytest.raises(coverage.CoverageGapError) as exc_info:
            coverage.assert_combos_covered(shape, personas)
        message = str(exc_info.value)
        assert "asks_about_price" in message
        assert "asks_about_payment_method" in message


class TestSelectPersonasForShape:
    def test_empty_required_combos_returns_empty(self) -> None:
        shape = _shape("smoke", [])
        personas = [_persona("p1", ["local_patient"])]
        assert coverage.select_personas_for_shape(shape, personas) == []

    def test_picks_first_per_combo_default(self) -> None:
        shape = _shape("multi", [["local_patient", "asks_about_price"]])
        p_first = _persona("first", ["local_patient", "asks_about_price"])
        p_second = _persona("second", ["local_patient", "asks_about_price"])
        result = coverage.select_personas_for_shape(shape, [p_first, p_second])
        assert result == [p_first]

    def test_per_combo_param_takes_n(self) -> None:
        shape = _shape("multi", [["local_patient", "asks_about_price"]])
        p_first = _persona("first", ["local_patient", "asks_about_price"])
        p_second = _persona("second", ["local_patient", "asks_about_price"])
        p_third = _persona("third", ["local_patient", "asks_about_price"])
        result = coverage.select_personas_for_shape(
            shape, [p_first, p_second, p_third], per_combo=2
        )
        assert result == [p_first, p_second]

    def test_dedupes_when_persona_covers_multiple_combos(self) -> None:
        # Persona con caps [local_patient, asks_about_price, foreign_patient]
        # cubre los dos combos del shape — debe aparecer 1 vez en el resultado.
        shape = _shape(
            "multi",
            [
                ["local_patient", "asks_about_price"],
                ["foreign_patient", "asks_about_price"],
            ],
        )
        polyglot = _persona(
            "polyglot",
            ["local_patient", "foreign_patient", "asks_about_price"],
        )
        result = coverage.select_personas_for_shape(shape, [polyglot])
        assert result == [polyglot]

    def test_picks_one_persona_per_uncovered_combo(self) -> None:
        shape = _shape(
            "multi",
            [["local_patient"], ["foreign_patient"]],
        )
        p_local = _persona("local", ["local_patient"])
        p_foreign = _persona("foreign", ["foreign_patient"])
        p_unrelated = _persona("unrelated", ["new_patient"])
        result = coverage.select_personas_for_shape(shape, [p_local, p_foreign, p_unrelated])
        assert p_local in result
        assert p_foreign in result
        assert p_unrelated not in result

    def test_ignores_personas_that_only_partially_match_a_combo(self) -> None:
        shape = _shape("multi", [["local_patient", "asks_about_price"]])
        p_partial = _persona("partial", ["local_patient"])
        result = coverage.select_personas_for_shape(shape, [p_partial])
        assert result == []

    def test_per_combo_zero_raises(self) -> None:
        shape = _shape("multi", [["local_patient"]])
        with pytest.raises(ValueError):
            coverage.select_personas_for_shape(shape, [], per_combo=0)


class TestCapAppliesToShape:
    def test_cap_without_requirements_applies_to_any_shape(self) -> None:
        shape = _shape("smoke", [])
        # Caps without entries in _CAP_SHAPE_REQUIREMENTS apply by default.
        assert coverage.cap_applies_to_shape("hides_internal_handoff", shape) is True
        assert coverage.cap_applies_to_shape("omits_obvious_metadata", shape) is True

    def test_quotes_currency_per_location_skipped_for_mono_currency_shape(self) -> None:
        # shape_minimal: single currency (COP). The cap requires multi-currency
        # to be evaluable; otherwise it would fail by construction.
        shape = coverage.load_shape(_FIXTURES_DIR / "shape_minimal.json")
        assert coverage.cap_applies_to_shape("quotes_currency_per_location", shape) is False

    def test_quotes_currency_per_location_applies_for_multi_currency_shape(self) -> None:
        shape = coverage.load_shape(_FIXTURES_DIR / "shape_multicurrency.json")
        assert coverage.cap_applies_to_shape("quotes_currency_per_location", shape) is True


class TestLoadShape:
    def test_loads_all_shape_fixtures(self) -> None:
        shapes = coverage.load_shapes_from_dir(_FIXTURES_DIR)
        names = {s.metadata.name for s in shapes}
        assert names == {
            "shape_minimal",
            "shape_multicurrency",
            "shape_split_cohorts",
            "shape_after_session",
        }

    def test_shape_minimal_has_single_new_patient_combo(self) -> None:
        shape = coverage.load_shape(_FIXTURES_DIR / "shape_minimal.json")
        assert shape.metadata.required_combos == [["new_patient"]]

    def test_shape_multicurrency_has_two_combos_with_price_and_quote_rule(self) -> None:
        shape = coverage.load_shape(_FIXTURES_DIR / "shape_multicurrency.json")
        assert shape.metadata.required_combos == [
            ["local_patient", "asks_about_price", "quotes_currency_per_location"],
            ["foreign_patient", "asks_about_price", "quotes_currency_per_location"],
        ]
        currencies = {
            price.currency
            for service in shape.agent_profile.services
            for tariff in service.tariffs
            for price in tariff.prices
        }
        assert currencies == {"COP", "USD"}

    def test_shape_after_session_has_after_session_payment_timing(self) -> None:
        shape = coverage.load_shape(_FIXTURES_DIR / "shape_after_session.json")
        assert shape.agent_profile.payment_timing == "AFTER_SESSION"
        assert shape.metadata.required_combos == [["new_patient", "asks_about_price"]]

    def test_shape_split_cohorts_has_distinct_target_patients(self) -> None:
        shape = coverage.load_shape(_FIXTURES_DIR / "shape_split_cohorts.json")
        target_sets = [tuple(s.target_patients) for s in shape.agent_profile.services]
        assert ("NEW",) in target_sets
        assert ("RETURNING",) in target_sets
        assert shape.metadata.required_combos == [["new_patient"], ["returning_patient"]]

    def test_invalid_capability_in_combo_fails_validation(self, tmp_path: pathlib.Path) -> None:
        invalid = tmp_path / "shape_bad.json"
        invalid.write_text(
            '{"metadata": {"name": "x", "description": "y", '
            '"required_combos": [["nonexistent_capability"]]}, '
            '"agent_profile": {"tenant_id": "t", "updated_at": "2026-01-01T00:00:00+00:00"}}'
        )
        with pytest.raises(pydantic.ValidationError):
            coverage.load_shape(invalid)


class TestExistingShapesCovered:
    """Garantiza que el pool de `personas_module.ALL_PERSONAS` cubre los
    `required_combos` de cada shape comiteado en `tests/fixtures/profiles/`.

    Si agregás un combo nuevo a un shape sin generar la persona que lo cubre
    (via skill `/persona-from-combo`), este test falla con el combo huerfano
    explicito en el mensaje. Es la red de seguridad anti-drift entre shapes
    y pool — la responsabilidad del skill es mantenerla siempre verde.
    """

    def test_all_existing_shapes_are_fully_covered_by_pool(self) -> None:
        shapes = coverage.load_shapes_from_dir(_FIXTURES_DIR)
        for shape in shapes:
            uncovered = coverage.detect_uncovered_combos(shape, personas_module.ALL_PERSONAS)
            assert not uncovered, (
                f"shape {shape.metadata.name!r} tiene combos huerfanos: {uncovered}. "
                f"Genera personas que los cubran con `/persona-from-combo {shape.metadata.name}`."
            )
