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
    # Comportamiento conversacional del paciente
    "asks_about_price",  # explícitamente pregunta cuánto vale antes de agendar
    "asks_about_payment_method",  # pregunta por método de pago / moneda
    "asks_about_modality",  # pregunta presencial vs virtual
    "rejects_first_slot",  # rechaza el primer horario propuesto
    "accepts_first_slot",  # toma el primer horario sin pedir cambios
    "gives_minimal_info",  # solo responde lo que le preguntan; no ofrece extras
    "gives_all_info_upfront",  # entrega nombre, edad, motivo, etc. en el primer mensaje
    # Comportamiento esperado del bot (verificado por inferencia sobre OUTBOUND)
    "quotes_currency_per_location",  # bot solo cotiza en una moneda según ubicación; pide ubicación si la tarifa tiene varias monedas y no la sabe
    "hides_internal_handoff",  # bot NO le dice al paciente que envía/pasa/gestiona/comenta/comparte algo con el profesional
    "uses_pre_payment_vocabulary",  # bot NO usa "confirmar tu cita" antes del pago; usa "agendar" / "reservar" / "para continuar con el proceso de agendamiento"
    "omits_obvious_metadata",  # bot NO verbaliza metadata trivial al presentar servicios (modalidad única, cohort universal, aclaraciones autoimplícitas)
    "skips_payment_when_after_session",  # cuando payment_timing=AFTER_SESSION, bot NO pide pago/comprobante durante el agendamiento
    "quotes_price_on_demand",  # bot NO cotiza precios sin que el paciente los pida (excepto en mensaje pre-pago oficial del flujo de agendamiento)
    "respects_service_modalities",  # bot solo ofrece modalidades listadas en <modalities> del <service>; NO inventa VIRTUAL si el shape solo tiene PRESENCIAL
]


# Caps que describen comportamiento del BOT (no del paciente). Son TRANSVERSALES:
# se evaluan en cada conversacion sin necesidad de aparecer en los `required_combos`
# del shape. El runner las pasa al judge cuando la persona las declara, junto con
# las caps que vienen de los combos del shape.
#
# Si agregas una cap nueva al Literal `Capability` con categoria "bot_behavior" en
# `eval_query_service._CAPABILITIES_DOC`, agregala tambien aca para que el runner
# la presente al judge.
BOT_BEHAVIOR_CAPS: frozenset[Capability] = frozenset(
    {
        "quotes_currency_per_location",
        "hides_internal_handoff",
        "uses_pre_payment_vocabulary",
        "omits_obvious_metadata",
        "skips_payment_when_after_session",
        "quotes_price_on_demand",
        "respects_service_modalities",
    }
)


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

PSICOLOGA_PERSONAS: list[Persona] = [
    Persona(
        id="diego_local_asks_price",
        display_name="Diego Hernandez",
        whatsapp_user_id="573001110001",
        persona_text=(
            "Tienes 38 anios, vives en Cali. Llevas meses con mucho estres "
            "laboral y queres empezar terapia para manejarlo. Preferis ir "
            "presencial al consultorio. "
            "Comportamiento: Lo primero que preguntas es cuanto vale."
        ),
        capabilities=[
            "local_patient",
            "new_patient",
            "asks_about_price",
            # Comportamiento esperado del bot al cotizar tarifas multi-moneda.
            # Se verifica observando los OUTBOUND, no es algo que la persona
            # ejerza directamente (es assertion del shape multicurrency).
            "quotes_currency_per_location",
            # Cap transversal: el bot no debe exponer al paciente que envía/
            # pasa/gestiona algo con el profesional. Se verifica por OUTBOUND.
            "hides_internal_handoff",
            # Cap transversal: el bot debe usar vocabulario apropiado para
            # pre-pago — "agendar"/"reservar", NO "confirmar cita".
            "uses_pre_payment_vocabulary",
            # Cap transversal: el bot omite metadata trivial al presentar
            # servicios (modalidad unica, cohort universal). Por OUTBOUND.
            "omits_obvious_metadata",
            # Cap CONDICIONAL al shape: cuando payment_timing=AFTER_SESSION,
            # el bot NO debe pedir pago ni comprobante en agendamiento.
            # En shapes BEFORE_SESSION es no-op (verified=true automatico).
            "skips_payment_when_after_session",
            # Cap transversal: el bot NO debe cotizar precios sin que se
            # pidan. Diego pregunta de entrada -> trivialmente verified=true,
            # pero la cap igual se mide para asegurar que el bot no
            # anticipa precios en mensajes anteriores a la pregunta.
            "quotes_price_on_demand",
            # Cap transversal: el bot solo ofrece modalidades listadas en
            # <modalities> del <service>. Diego es local + presencial,
            # comportamiento congruente con los shapes existentes.
            "respects_service_modalities",
        ],
    ),
    Persona(
        id="bruno_foreign_asks_price",
        display_name="Bruno Schneider",
        whatsapp_user_id="573001110002",
        persona_text=(
            "Tienes 42 anios, vives en Berlin, Alemania. Llevas tiempo "
            "considerando empezar terapia y queres saber si te conviene "
            "virtual desde Europa. "
            "Comportamiento: Lo primero que preguntas es cuanto vale."
        ),
        capabilities=[
            "foreign_patient",
            "new_patient",
            "asks_about_price",
            "quotes_currency_per_location",  # ver Diego — assertion del bot
            "hides_internal_handoff",  # transversal — assertion del bot
            "uses_pre_payment_vocabulary",  # transversal — assertion del bot
            "omits_obvious_metadata",  # transversal — assertion del bot
            "skips_payment_when_after_session",  # condicional al shape — no-op fuera de AFTER_SESSION
            "quotes_price_on_demand",  # transversal — assertion del bot
            # Cap focal de Bruno: el bot NO debe inventar VIRTUAL para un
            # paciente foreign cuando el shape solo soporta PRESENCIAL. Si
            # el servicio no aplica para el paciente, debe ofrecer
            # alternativas o usar handoff — no inventar modalidad.
            "respects_service_modalities",
        ],
    ),
    Persona(
        id="patricia_returning",
        display_name="Patricia Mendez",
        whatsapp_user_id="573001110003",
        persona_text=(
            "Tienes 50 anios, vives en Cali. Sos paciente desde hace meses — "
            "ya tuviste tu valoracion inicial y queres agendar una cita de "
            "control para seguir el tratamiento. "
            "Comportamiento: Tomas el primer horario que te ofrezcan sin pedir cambios."
        ),
        capabilities=[
            "local_patient",
            "returning_patient",
            "accepts_first_slot",
            "hides_internal_handoff",  # transversal — assertion del bot
            "uses_pre_payment_vocabulary",  # transversal — assertion del bot
            "omits_obvious_metadata",  # transversal — assertion del bot
            "skips_payment_when_after_session",  # condicional al shape — no-op fuera de AFTER_SESSION
            "quotes_price_on_demand",  # transversal — assertion del bot
            "respects_service_modalities",  # transversal — assertion del bot
        ],
    ),
    # Paciente nuevo silencioso: solo dice "Hola" y deja que el bot lleve.
    # No pregunta precio. Con esta persona el rubric `quotes_price_on_demand`
    # ejercita el caso negativo (¿el bot anticipa precios sin pregunta?). Las
    # otras personas nuevas ya preguntan precio (Diego, Bruno) y la cap
    # quedaria trivial verified=true para ellas. Patricia es returning y
    # tiene flujo distinto (cita de control). Ana cubre el gap.
    Persona(
        id="ana_local_no_asks_price",
        display_name="Ana Restrepo",
        whatsapp_user_id="573001110004",
        persona_text=(
            "Tienes 32 anios, vives en Cali. Llevas tiempo con ansiedad y "
            "queres empezar terapia. Preferis ir presencial al consultorio. "
            "Comportamiento: solo dices 'Hola' al inicio y respondes con "
            "frases cortas a lo que el bot te pregunte. NO preguntas el "
            "precio, NO preguntas modalidad, NO ofreces datos extra a menos "
            "que te los pidan."
        ),
        capabilities=[
            "local_patient",
            "new_patient",
            "gives_minimal_info",
            "hides_internal_handoff",  # transversal — assertion del bot
            "uses_pre_payment_vocabulary",  # transversal — assertion del bot
            "omits_obvious_metadata",  # transversal — assertion del bot
            "skips_payment_when_after_session",  # condicional al shape
            # Cap focal de esta persona: el bot NO debe cotizar precios sin
            # que se pidan. Ana nunca pregunta -> verified=false si el bot
            # lista precios espontaneamente en el saludo (caso del screenshot).
            "quotes_price_on_demand",
            "respects_service_modalities",  # transversal — assertion del bot
        ],
    ),
]

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
