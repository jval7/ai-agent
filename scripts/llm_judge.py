"""LLM-as-judge para el eval framework.

Llama a Gemini con structured output para verificar si las capabilities
declaradas por una persona se ejercieron efectivamente en el transcript
de la conversacion.

Granularidad: 1 llamada por conversacion. El juez ve todo el transcript
y devuelve UN verdict con N verifications (una por cap declarada).

Si Gemini falla (timeout, error de parseo, schema mismatch), retorna un
JudgeVerdict con `error` poblado y `overall="none"` en lugar de raisear.
El caller puede continuar aunque el juez falle — el verdict es informacion,
no critico para el runner.
"""

from __future__ import annotations

import datetime
import json
import logging
import typing

from google import genai
from google.api_core import exceptions as google_api_exceptions

import src.domain.entities.eval_run as eval_run_entity

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Glosario de capabilities (hardcoded en el prompt)
# ---------------------------------------------------------------------------

_GLOSSARY: dict[str, str] = {
    # Comportamentales del paciente — requieren evidencia INBOUND directa.
    "asks_about_price": (
        "el paciente pregunta cuanto vale la consulta o servicio en algun mensaje INBOUND"
    ),
    "asks_about_payment_method": (
        "el paciente pregunta como o por que medio se paga en algun mensaje INBOUND"
    ),
    "asks_about_modality": (
        "el paciente pregunta si la cita puede ser virtual o presencial en algun mensaje INBOUND"
    ),
    "rejects_first_slot": (
        "el paciente rechaza explicitamente el primer horario propuesto y pide otro"
    ),
    "accepts_first_slot": (
        "el paciente acepta el primer horario que el bot le ofrece sin pedir cambios"
    ),
    "gives_minimal_info": (
        "el paciente solo responde lo que el bot le pregunta, sin ofrecer informacion "
        "adicional no solicitada"
    ),
    "gives_all_info_upfront": (
        "en su primer mensaje INBOUND el paciente entrega multiples datos sin que el "
        "bot los pida (ej. nombre + motivo + modalidad juntos)"
    ),
    # Inferenciales por comportamiento del flujo — pueden verificarse por como
    # bot/paciente se comportan, sin necesidad de declaracion explicita del paciente.
    "local_patient": (
        "la conversacion procede como con un paciente local del pais del consultorio "
        "(Colombia): el bot cotiza precio en COP, ofrece modalidad presencial, da "
        "metodo de pago local (Nequi/transferencia), o el paciente menciona ciudad "
        "colombiana o residencia en el pais. Inferencia comportamental aceptable."
    ),
    "foreign_patient": (
        "la conversacion procede como con un paciente extranjero: el bot cotiza precio "
        "en USD u otra moneda extranjera, sugiere modalidad virtual, da metodo de pago "
        "internacional (Zelle/Wise), o el paciente menciona explicitamente vivir fuera "
        "del pais. Inferencia comportamental aceptable."
    ),
    "new_patient": (
        "la conversacion se centra en un paciente nuevo: el bot le pide nombre/edad/"
        "motivo porque no los tiene, no hay referencias a sesiones previas o tratamiento "
        "en curso, el bot trata el caso como primera consulta. Si el bot saluda por "
        "nombre desde el primer mensaje sin que el paciente lo de, NO es new_patient. "
        "Inferencia comportamental aceptable."
    ),
    "returning_patient": (
        "la conversacion se centra en un paciente conocido por el sistema: el bot saluda "
        "por nombre desde el primer mensaje sin pedir datos basicos, hay referencias a "
        "tratamiento previo, sesiones anteriores, cita de control, o el paciente "
        "menciona seguir tratamiento. Inferencia comportamental aceptable."
    ),
}

# Caps que pueden verificarse por inferencia comportamental (criterio b).
# Las demas requieren evidencia INBOUND directa (criterio a).
_INFERENTIAL_CAPS = frozenset(
    {"local_patient", "foreign_patient", "new_patient", "returning_patient"}
)

_SYSTEM_INSTRUCTION = """\
Eres un evaluador de conversaciones simuladas entre un paciente y un asistente de agenda.

Tu tarea es verificar si las capabilities declaradas por el paciente se ejercieron
efectivamente en el transcript de la conversacion.

Glosario de capabilities:

Comportamentales del paciente (requieren evidencia INBOUND directa):
- asks_about_price: el paciente pregunta cuanto vale en algun mensaje INBOUND
- asks_about_payment_method: pregunta como/por que medio se paga
- asks_about_modality: pregunta si la cita es virtual o presencial
- rejects_first_slot: rechaza explicitamente el primer horario propuesto
- accepts_first_slot: acepta el primer horario sin pedir cambios
- gives_minimal_info: solo responde lo que le preguntan, sin extras no solicitados
- gives_all_info_upfront: en el primer mensaje da nombre + motivo + modalidad

Inferenciales por flujo (pueden verificarse por como bot/paciente se comportan):
- local_patient: el flujo procede en COP, presencial, Nequi, o ciudad colombiana
- foreign_patient: el flujo procede en USD/EUR, virtual, Zelle/Wise, o paciente vive fuera
- new_patient: el bot pide nombre/edad/motivo (no los conoce); no hay sesiones previas
- returning_patient: el bot saluda por nombre sin pedirlo; referencias a tratamiento previo

Reglas:

1. Solo evalua las capabilities en "declared_capabilities". Ignora cualquier otra.

2. Para cada capability, verified=true si CUALQUIERA de estos dos criterios se cumple:

   (a) Evidencia EXPLICITA: hay un mensaje INBOUND donde el paciente declara o
       ejerce la capability directamente (ej. "Cuanto vale la consulta?" para
       asks_about_price).

   (b) Evidencia COMPORTAMENTAL (solo para caps inferenciales — local_patient,
       foreign_patient, new_patient, returning_patient): el flujo de la conversacion
       es consistente con la capability, observando como el bot trata al paciente,
       que datos pide o no, en que moneda cotiza, que metodo de pago ofrece, o como
       el paciente actua. Ejemplos:
       - new_patient verified si el bot pide nombre/edad porque no los tiene.
       - returning_patient verified si el bot saluda por nombre desde el primer mensaje.
       - local_patient verified si el bot cotizo en COP y ofrecio Nequi.
       - foreign_patient verified si el bot cotizo en USD y ofrecio Zelle.

3. evidence:
   - Si aplico criterio (a): quote textual breve del mensaje INBOUND.
   - Si aplico criterio (b): descripcion textual del flujo observado, citando
     turno y direccion (ej. "el bot pide nombre y edad en turno 2 (OUTBOUND),
     indicando que no conocia al paciente").
   - null si verified=false.

4. reasoning: 1-2 lineas indicando que criterio aplico y por que.

5. overall: "all_verified" si todas verificadas, "partial" si algunas, "none" si ninguna.

Importante: para caps NO inferenciales (asks_about_price, gives_minimal_info, etc.),
solo aplica criterio (a). Si no hay evidencia INBOUND directa, verified=false aunque
el flujo sea consistente.

Responde SOLO con JSON valido segun el schema indicado. Sin texto adicional.
"""

# ---------------------------------------------------------------------------
# Schema JSON para structured output
# ---------------------------------------------------------------------------

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "verifications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "capability": {"type": "string"},
                    "verified": {"type": "boolean"},
                    # Vertex AI no acepta `type: ["string", "null"]` (JSON Schema
                    # 2020-12). Usar `nullable: true` + `type: "string"`.
                    "evidence": {"type": "string", "nullable": True},
                    "reasoning": {"type": "string", "nullable": True},
                },
                "required": ["capability", "verified"],
            },
        },
        "overall": {
            "type": "string",
            "enum": ["all_verified", "partial", "none"],
        },
    },
    "required": ["verifications", "overall"],
}


def _build_user_prompt(
    persona_id: str,
    declared_capabilities: list[str],
    transcript: list[eval_run_entity.EvalRunConversationMessage],
) -> str:
    """Construye el mensaje de usuario para el juez."""
    caps_str = ", ".join(declared_capabilities)
    lines = [
        f"Persona: {persona_id}",
        f"Declared capabilities: [{caps_str}]",
        "",
        "Transcript:",
    ]
    for i, msg in enumerate(transcript, start=1):
        lines.append(f"[{i}] [{msg.direction}] {msg.content}")

    return "\n".join(lines)


def _compute_overall(
    verifications: list[eval_run_entity.CapabilityVerification],
) -> typing.Literal["all_verified", "partial", "none"]:
    if not verifications:
        return "none"
    verified_count = sum(1 for v in verifications if v.verified)
    if verified_count == 0:
        return "none"
    if verified_count == len(verifications):
        return "all_verified"
    return "partial"


def judge_conversation(
    persona_id: str,
    declared_capabilities: list[str],
    transcript: list[eval_run_entity.EvalRunConversationMessage],
    gemini_client: genai.Client,
    model: str = "gemini-2.5-flash",
    timeout_seconds: float = 30.0,
) -> eval_run_entity.JudgeVerdict:
    """Llama Gemini con structured output para verificar capabilities.

    Si falla (timeout, parse error, schema mismatch), retorna un JudgeVerdict
    con error="<razon>" y overall="none". El runner no debe abortar si el juez
    falla — el verdict es informacion, no critico.
    """
    judged_at = datetime.datetime.now(tz=datetime.UTC)

    if not declared_capabilities:
        return eval_run_entity.JudgeVerdict(
            declared_capabilities=[],
            verifications=[],
            overall="none",
            judge_model=model,
            judged_at=judged_at,
            error="no declared capabilities to verify",
        )

    user_prompt = _build_user_prompt(persona_id, declared_capabilities, transcript)

    try:
        response = gemini_client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=_RESPONSE_SCHEMA,
                temperature=0.0,
            ),
        )
    except google_api_exceptions.DeadlineExceeded as exc:
        logger.warning("judge_conversation: Gemini timeout para %s: %s", persona_id, exc)
        return eval_run_entity.JudgeVerdict(
            declared_capabilities=declared_capabilities,
            verifications=[],
            overall="none",
            judge_model=model,
            judged_at=judged_at,
            error=f"timeout: {exc}",
        )
    except google_api_exceptions.GoogleAPIError as exc:
        logger.warning("judge_conversation: Gemini API error para %s: %s", persona_id, exc)
        return eval_run_entity.JudgeVerdict(
            declared_capabilities=declared_capabilities,
            verifications=[],
            overall="none",
            judge_model=model,
            judged_at=judged_at,
            error=f"api_error: {exc}",
        )

    # Parsear la respuesta
    raw_text = ""
    try:
        raw_text = response.text or ""
        parsed = json.loads(raw_text)
    except (json.JSONDecodeError, AttributeError, ValueError) as exc:
        logger.warning(
            "judge_conversation: JSON parse error para %s: %s — raw: %r",
            persona_id,
            exc,
            raw_text[:200],
        )
        return eval_run_entity.JudgeVerdict(
            declared_capabilities=declared_capabilities,
            verifications=[],
            overall="none",
            judge_model=model,
            judged_at=judged_at,
            error=f"json_parse_error: {exc}",
        )

    # Mapear a entities
    try:
        raw_verifications_raw = parsed.get("verifications", [])
        if not isinstance(raw_verifications_raw, list):
            raise TypeError(
                f"expected list for 'verifications', got {type(raw_verifications_raw).__name__}"
            )
        raw_verifications: list[dict[str, object]] = raw_verifications_raw
        # Filtrar items mal formados Y caps que no estaban declaradas.
        # Lo segundo evita que el juez halucine caps inexistentes (ej.
        # "asks_about_dragons") y queden persistidas como evidencia falsa.
        declared_set = set(declared_capabilities)
        verifications = [
            eval_run_entity.CapabilityVerification(
                capability=str(v["capability"]),
                verified=bool(v["verified"]),
                evidence=str(v["evidence"]) if v.get("evidence") is not None else None,
                reasoning=str(v["reasoning"]) if v.get("reasoning") is not None else None,
            )
            for v in raw_verifications
            if "capability" in v and "verified" in v and str(v["capability"]) in declared_set
        ]
        raw_overall = parsed.get("overall", "none")
        overall: typing.Literal["all_verified", "partial", "none"]
        if raw_overall in ("all_verified", "partial", "none"):
            overall = raw_overall
        else:
            overall = _compute_overall(verifications)

    except (KeyError, TypeError, ValueError) as exc:
        logger.warning(
            "judge_conversation: schema mismatch para %s: %s — parsed: %r",
            persona_id,
            exc,
            str(parsed)[:200],
        )
        return eval_run_entity.JudgeVerdict(
            declared_capabilities=declared_capabilities,
            verifications=[],
            overall="none",
            judge_model=model,
            judged_at=judged_at,
            error=f"schema_mismatch: {exc}",
        )

    return eval_run_entity.JudgeVerdict(
        declared_capabilities=declared_capabilities,
        verifications=verifications,
        overall=overall,
        judge_model=model,
        judged_at=judged_at,
    )
