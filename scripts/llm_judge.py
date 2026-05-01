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
    "asks_about_price": "el paciente pregunta cuanto vale la consulta o servicio",
    "asks_about_payment_method": "el paciente pregunta como o por que medio se paga",
    "asks_about_modality": "el paciente pregunta si la cita es virtual o presencial",
    "rejects_first_slot": "el paciente rechaza el primer horario propuesto",
    "accepts_first_slot": "el paciente acepta el primer horario sin pedir cambios",
    "gives_minimal_info": "el paciente solo responde lo que le preguntan, no ofrece extras",
    "gives_all_info_upfront": "en su primer mensaje el paciente da nombre + motivo + modalidad",
    "local_patient": "el paciente menciona o confirma residir en el pais del consultorio (Colombia)",
    "foreign_patient": "el paciente menciona residir fuera del pais",
    "new_patient": "primera consulta — el paciente no menciona haber sido paciente antes",
    "returning_patient": "el paciente menciona explicitamente haber sido paciente antes",
}

_SYSTEM_INSTRUCTION = """\
Eres un evaluador de conversaciones simuladas entre un paciente y un asistente de agenda.

Tu tarea es verificar si las capabilities declaradas por el paciente se ejercieron
efectivamente en el transcript de la conversacion.

Glosario de capabilities:
- asks_about_price: el paciente pregunta cuanto vale la consulta o servicio
- asks_about_payment_method: el paciente pregunta como o por que medio se paga
- asks_about_modality: el paciente pregunta si la cita es virtual o presencial
- rejects_first_slot: el paciente rechaza el primer horario propuesto
- accepts_first_slot: el paciente acepta el primer horario sin pedir cambios
- gives_minimal_info: el paciente solo responde lo que le preguntan, no ofrece extras
- gives_all_info_upfront: en su primer mensaje el paciente da nombre + motivo + modalidad
- local_patient: el paciente menciona o confirma residir en el pais del consultorio (Colombia)
- foreign_patient: el paciente menciona residir fuera del pais
- new_patient: primera consulta — el paciente no menciona haber sido paciente antes
- returning_patient: el paciente menciona explicitamente haber sido paciente antes

Reglas:
1. Solo evalua las capabilities que te indiquen en "declared_capabilities".
2. Para cada capability, determina si hay evidencia clara en algun mensaje INBOUND del transcript.
3. verified=true solo si hay evidencia explicita. En caso de duda, false.
4. evidence: cita textual breve del mensaje INBOUND donde se observa (null si verified=false).
5. reasoning: 1-2 lineas justificando la decision.
6. overall: "all_verified" si todas verificadas, "partial" si algunas, "none" si ninguna.

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
        verifications = [
            eval_run_entity.CapabilityVerification(
                capability=str(v["capability"]),
                verified=bool(v["verified"]),
                evidence=str(v["evidence"]) if v.get("evidence") is not None else None,
                reasoning=str(v["reasoning"]) if v.get("reasoning") is not None else None,
            )
            for v in raw_verifications
            if "capability" in v and "verified" in v
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
