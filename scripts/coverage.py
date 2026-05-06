"""Shape fixtures + coverage matching basado en combos para evaluación dev.

Un `Shape` es un snapshot profession-agnóstico de `AgentProfile` que ejercita
una configuración específica del prompt (multi-moneda, cohorts separados, etc.).

`Shape.metadata.required_combos` declara los grupos de capabilities que tienen
que aparecer JUNTOS en alguna persona. AND dentro del combo, OR entre combos.

Ejemplo: `shape_multicurrency` con
    required_combos = [
        ["local_patient", "asks_about_price"],
        ["foreign_patient", "asks_about_price"],
    ]
exige que el pool tenga AL MENOS una persona con (local_patient AND
asks_about_price) Y otra con (foreign_patient AND asks_about_price). Si
falta cualquiera, el matcher levanta `CoverageGapError`.

Flujo:
  1. `load_shape(path)` deserializa el JSON con validación Pydantic.
  2. `detect_uncovered_combos(shape, personas)` devuelve los combos huérfanos.
  3. `assert_combos_covered(shape, personas)` raise si hay gaps.
  4. `select_personas_for_shape(shape, personas, per_combo=1)` toma `per_combo`
     personas por combo, dedupeando si una cubre múltiples combos.
"""

from __future__ import annotations

import json
import pathlib
import typing

import pydantic

import scripts.personas as personas_module
import src.domain.entities.agent_profile as agent_profile_entity


class CoverageGapError(Exception):
    """Una shape requiere combos que ninguna persona cubre simultáneamente."""


class ShapeMetadata(pydantic.BaseModel):
    name: str
    description: str
    required_combos: list[list[personas_module.Capability]] = []


class Shape(pydantic.BaseModel):
    metadata: ShapeMetadata
    agent_profile: agent_profile_entity.AgentProfile


def load_shape(path: pathlib.Path) -> Shape:
    """Carga y valida un shape JSON. Pydantic falla si el AgentProfile o
    cualquier capability dentro de `required_combos` no es válido.
    """
    raw = json.loads(path.read_text())
    return Shape.model_validate(raw)


def load_shapes_from_dir(directory: pathlib.Path) -> list[Shape]:
    """Carga todos los `*.json` de un directorio en orden alfabético.

    Los nombres de archivo no son significativos — el `metadata.name` es la
    identidad del shape.
    """
    if not directory.is_dir():
        raise FileNotFoundError(f"shapes directory not found: {directory}")
    return [load_shape(path) for path in sorted(directory.glob("*.json"))]


def detect_uncovered_combos(
    shape: Shape, personas: typing.Sequence[personas_module.Persona]
) -> list[list[personas_module.Capability]]:
    """Combos donde ninguna persona tiene TODOS los caps del combo.

    Un combo está cubierto si existe AL MENOS una persona cuyo set de
    capabilities sea superset del combo. La forma del retorno preserva el
    orden de declaración de `required_combos` para que los reportes sean
    estables entre runs.
    """
    uncovered: list[list[personas_module.Capability]] = []
    for combo in shape.metadata.required_combos:
        combo_set = set(combo)
        if not any(combo_set.issubset(p.capabilities) for p in personas):
            uncovered.append(combo)
    return uncovered


def assert_combos_covered(shape: Shape, personas: typing.Sequence[personas_module.Persona]) -> None:
    """Raise `CoverageGapError` si `detect_uncovered_combos` no está vacío.

    El runner del load_test debe llamar esto antes de iniciar conversaciones
    para fallar fast en vez de descubrir el gap a mitad de la corrida.
    """
    uncovered = detect_uncovered_combos(shape, personas)
    if uncovered:
        raise CoverageGapError(f"shape={shape.metadata.name!r} uncovered combos: {uncovered}")


def _shape_has_multi_currency(shape: Shape) -> bool:
    """True si algun service del shape tiene una tariff con multiples currencies."""
    for svc in shape.agent_profile.services:
        for tariff in svc.tariffs:
            currencies = {p.currency for p in tariff.prices}
            if len(currencies) > 1:
                return True
    return False


# Pre-requisitos de shape para caps `bot_behavior`. Las caps que no aparecen
# aqui aplican a TODO shape (default). Cuando una cap requiere ciertas
# condiciones del AgentProfile que el shape no cumple, el runner la filtra
# antes de pasarla al juez para evitar fails por construccion (ej. Bruno
# declarando `quotes_currency_per_location` en shape_minimal mono-currency).
_CAP_SHAPE_REQUIREMENTS: dict[personas_module.Capability, typing.Callable[[Shape], bool]] = {
    "quotes_currency_per_location": _shape_has_multi_currency,
}


def cap_applies_to_shape(cap: personas_module.Capability, shape: Shape) -> bool:
    """Returns True si la cap es evaluable contra este shape.

    Default True: caps sin requirements aplican siempre. Las caps que
    necesitan ciertas condiciones del AgentProfile (ej. multi-currency)
    devuelven False cuando el shape no las cumple.
    """
    requirement = _CAP_SHAPE_REQUIREMENTS.get(cap)
    if requirement is None:
        return True
    return requirement(shape)


def select_personas_for_shape(
    shape: Shape,
    personas: typing.Sequence[personas_module.Persona],
    per_combo: int = 1,
) -> list[personas_module.Persona]:
    """Por cada combo, toma las primeras `per_combo` personas que lo cubren.

    Dedupe por `persona.id`: si una persona cubre múltiples combos, aparece
    UNA sola vez en el resultado (corre 1 conversación que satisface todos
    los combos para los que aplica).

    Si `required_combos` está vacío, retorna lista vacía — el shape no ejercita
    nada y no hay personas a elegir.
    """
    if per_combo < 1:
        raise ValueError(f"per_combo must be >= 1, got {per_combo}")
    chosen: dict[str, personas_module.Persona] = {}
    for combo in shape.metadata.required_combos:
        combo_set = set(combo)
        matching = [p for p in personas if combo_set.issubset(p.capabilities)]
        for persona in matching[:per_combo]:
            chosen[persona.id] = persona
    return list(chosen.values())
