"""Vocabulario fijo de capabilities + pool de personas para load test / eval.

`Capability` es un Literal cerrado: agregar un tag nuevo requiere editar la
lista aquí y, por contrato del plan, anotar al menos una persona y un shape
que lo ejerciten. Evita que devs agreguen tags ad-hoc en comentarios libres
y que el vocabulario se pudra.

`PSICOLOGA_PERSONAS` y `ORTODONCIA_PERSONAS` empiezan VACÍAS por diseño: el
skill `/persona-from-combo` (Fase 2) las puebla a medida que los shapes lo
demanden, garantizando que cada persona existe porque algún combo concreto
la justifica. No agregar personas a mano sin pasar por el skill.
"""

from __future__ import annotations

import dataclasses
import typing

Capability = typing.Literal[
    # Ubicación del paciente
    "local_patient",  # paciente reside o agenda dentro del país del consultorio
    "foreign_patient",  # paciente reside fuera del país (afecta moneda y modalidad)
    # Cohort
    "new_patient",  # primer contacto; no existe Patient previo
    "returning_patient",  # ya tiene Patient registrado; requiere pre-seed
    # Comportamiento conversacional
    "asks_about_price",  # explícitamente pregunta cuánto vale antes de agendar
    "asks_about_payment_method",  # pregunta por método de pago / moneda
    "asks_about_modality",  # pregunta presencial vs virtual
    "rejects_first_slot",  # rechaza el primer horario propuesto
    "accepts_first_slot",  # toma el primer horario sin pedir cambios
    "gives_minimal_info",  # solo responde lo que le preguntan; no ofrece extras
    "gives_all_info_upfront",  # entrega nombre, edad, motivo, etc. en el primer mensaje
]


@dataclasses.dataclass(frozen=True)
class Persona:
    """Paciente simulado con capabilities anotadas.

    `id` es estable (CI / reportes). `whatsapp_user_id` es la base que el
    runner combina con `RUN_ID` para crear conversaciones limpias por corrida.
    `persona_text` se inyecta literalmente en el system prompt del LLM-paciente.
    `capabilities` documentan QUÉ comportamientos esta persona promete ejercer.
    """

    id: str
    display_name: str
    whatsapp_user_id: str
    persona_text: str
    capabilities: list[Capability]


# ---------------------------------------------------------------------------
# Pool de personas (POBLADO POR EL SKILL — no agregar a mano)
# ---------------------------------------------------------------------------
# El skill `/persona-from-combo` itera sobre los shapes en
# `tests/fixtures/profiles/*.json` y agrega personas cuyo set de capabilities
# cubra los `required_combos` declarados. Mantener vacío hasta Fase 3.
# ---------------------------------------------------------------------------

PSICOLOGA_PERSONAS: list[Persona] = []

ORTODONCIA_PERSONAS: list[Persona] = []

ALL_PERSONAS: list[Persona] = [*PSICOLOGA_PERSONAS, *ORTODONCIA_PERSONAS]


def get_personas_by_profile(profile: str) -> list[Persona]:
    """Selección legacy por flag --profile (psicologa | ortodoncista).

    Hasta que el skill puebla las listas, retorna `[]`. El caller (load_test
    legacy mode) debe detectar la lista vacía y abortar con un mensaje claro.
    """
    if profile == "ortodoncista":
        return ORTODONCIA_PERSONAS
    if profile == "psicologa":
        return PSICOLOGA_PERSONAS
    raise ValueError(f"Unknown profile: {profile!r}")
