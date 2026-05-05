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
    # Comportamiento del BOT (no del paciente). Se verifica observando los OUTBOUND.
    "quotes_currency_per_location": (
        "el bot maneja correctamente las tarifas multi-moneda. La regla critica es: "
        "NUNCA muestra varias monedas juntas en el mismo mensaje cuando no sabe la "
        "ubicacion del paciente. verified=true si el bot cotizo UNA sola moneda Y esa "
        "moneda es consistente con la ubicacion del paciente — sea porque el bot la "
        "pregunto explicitamente, sea porque la INFIRIO de pistas claras del paciente "
        "(ej. paciente dijo 'presencial' => local => COP; paciente dijo 'virtual desde "
        "Berlin' => foreign => USD; paciente menciono ciudad colombiana => COP). La "
        "inferencia por contexto es valida — no es obligatorio preguntar si hay pistas. "
        "verified=false SOLO si el bot expuso multiples monedas juntas sin tener forma "
        "de saber la ubicacion, o cotizo una moneda inconsistente con la ubicacion "
        "inferible. Inferencia comportamental por OUTBOUND aceptable."
    ),
    "uses_pre_payment_vocabulary": (
        "el bot distingue conceptualmente entre AGENDAMIENTO y CONFIRMACION DE "
        "ASISTENCIA. Son dos eventos distintos del ciclo de vida de una cita. "
        "AGENDAMIENTO: la fase actual del flujo (recoleccion de datos, propuesta "
        "de horario, solicitud de pago, recoleccion de datos finales). En esta fase "
        "se *agenda* o *reserva* una cita — NO se confirma nada todavia. CONFIRMACION "
        "DE ASISTENCIA: estado posterior, en el recordatorio pre-cita, donde el "
        "paciente confirma que asistira a una cita ya agendada y pagada. El verbo "
        "'confirmar' (y derivados: 'confirmacion', 'confirmar tu cita/asistencia/"
        "espacio/reserva') pertenece al segundo concepto y es INCORRECTO usarlo "
        "durante el flujo de agendamiento. La forma correcta al pedir el pago es "
        "'Para reservar tu cita, paga X' o 'Para continuar con el proceso de "
        "agendamiento, paga X' — NO 'Para confirmar tu cita/asistencia/espacio, paga X'. "
        "verified=true si el bot NO uso 'confirmar' ni derivados aplicados a la cita/"
        "asistencia/espacio/reserva durante el flujo de agendamiento (antes de recibir "
        "el comprobante de pago). verified=false ante frases como 'para confirmar tu "
        "cita', 'confirmar tu asistencia', 'confirmar tu espacio', 'confirmacion de "
        "tu cita' aplicadas en pre-pago — citar la frase EXACTA del OUTBOUND y el turno. "
        "Notas: (1) 'confirmar el pago' o 'cuando se confirme el pago' se refiere al "
        "pago en si, no a la cita — eso es PERMITIDO. (2) Si el shape tiene "
        "payment_timing=AFTER_SESSION, esta cap NO aplica (verified=true automatico)."
    ),
    "hides_internal_handoff": (
        "regla CONCEPTUAL (no lexica): el bot NO transmite al paciente que esta "
        "realizando comunicaciones internas, gestiones, consultas, transferencias, "
        "envios, traspasos, comparticiones o revisiones con el PROFESIONAL TRATANTE. "
        "La gestion interna es invisible al paciente. Cualquier OUTBOUND donde "
        "aparezca un verbo de comunicacion/gestion/transferencia/revision aplicado "
        "al profesional tratante (la doctora, el doctor, el profesional) como "
        "destinatario o agente interno expone el handoff y viola esta cap. "
        "INDEPENDIENTE de: el verbo (enviar, pasar, compartir, comentar, gestionar, "
        "tramitar, mandar, transferir, revisar, consultar), la persona gramatical "
        "(yo/nosotros: 'envie' / 'hemos enviado' / 'le pasamos'), la voz (activa o "
        "pasiva: 'esta siendo revisado por la doctora'), el tiempo (presente, "
        "pasado, futuro perifrastico: 'va a revisar', 'te contactaremos'), o la "
        "construccion sintactica. La regla es semantica: si la lectura natural del "
        "OUTBOUND comunica al paciente que SE ESTA HACIENDO algo internamente con "
        "la profesional tratante, viola la cap. "
        "DISTINCION CLAVE: una escalada explicita a un OPERADOR HUMANO de la clinica "
        "(ej. 'te atiende un asesor humano de nuestro equipo', 'paso la conversacion "
        "a un humano') NO viola la cap — esa es comunicacion legitima de un handoff "
        "necesario, no exposicion de gestion con la profesional tratante. "
        "verified=true si NINGUN OUTBOUND comunica gestion interna con la "
        "profesional tratante. verified=false ante CUALQUIER OUTBOUND donde la "
        "lectura natural revele gestion interna con la profesional — DEBES citar "
        "el texto EXACTO del OUTBOUND (no parafrasear, no inventar). "
        "Inferencia comportamental por OUTBOUND."
    ),
    "omits_internal_categorization": (
        "El bot NO expone al paciente la metadata interna del sistema. "
        "Específicamente, NO debe decir frases como 'para pacientes nuevos', "
        "'para pacientes recurrentes', 'para pacientes nuevos o recurrentes' "
        "ni nada que traduzca los codigos internos NEW_ONLY/RETURNING_ONLY/"
        "BOTH_NEW_AND_RETURNING.\n"
        "Verifica AUSENCIA de esas frases en cualquier mensaje OUTBOUND del "
        "bot. Si todos los OUTBOUND están limpios → verified=true. Si "
        "encuentras una frase que regurgita la categorización → verified=false "
        "con la cita literal como evidence."
    ),
}

# Caps que pueden verificarse por inferencia comportamental (criterio b).
# Las demas requieren evidencia INBOUND directa (criterio a).
_INFERENTIAL_CAPS = frozenset(
    {
        "local_patient",
        "foreign_patient",
        "new_patient",
        "returning_patient",
        "quotes_currency_per_location",  # se verifica por OUTBOUND del bot
        "hides_internal_handoff",  # se verifica por ausencia de frases en OUTBOUND
        "uses_pre_payment_vocabulary",  # se verifica por ausencia de "confirmar" pre-pago
        "omits_internal_categorization",  # se verifica por ausencia de categorizacion en OUTBOUND
    }
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

Inferenciales por comportamiento del bot (verificadas por OUTBOUND):
- quotes_currency_per_location: ante tarifas multi-moneda, el bot cotiza UNA sola
  moneda Y esa moneda es consistente con la ubicacion del paciente — sea porque
  la pregunto, sea porque la infirio del contexto (presencial => local => COP;
  virtual desde otro pais => foreign => USD; ciudad colombiana mencionada => COP).
  La inferencia por contexto es valida; no es obligatorio preguntar si hay pistas.
  NUNCA debe mostrar varias monedas juntas en el mismo mensaje sin saber ubicacion.
  verified=false SOLO si el bot expuso ambas monedas juntas sin saber ubicacion,
  o cotizo una moneda inconsistente con la ubicacion inferible.
- uses_pre_payment_vocabulary: el bot distingue AGENDAMIENTO (flujo actual, hasta
  el pago) de CONFIRMACION DE ASISTENCIA (estado posterior, recordatorio). En el
  agendamiento se *agenda*/*reserva* — NO se confirma. El verbo "confirmar" (y
  derivados: "confirmacion", "confirmar tu cita/asistencia/espacio/reserva")
  pertenece al estado de confirmacion de asistencia (post-pago, recordatorio),
  no al agendamiento. verified=false ante frases pre-pago como "para confirmar
  tu cita", "confirmar tu asistencia", "confirmar tu espacio", "confirmacion de
  tu cita" — citar la frase EXACTA del OUTBOUND. "Confirmar el pago" si esta
  permitido (se refiere al pago en si, no a la cita). No aplica si
  payment_timing=AFTER_SESSION.
- hides_internal_handoff: regla CONCEPTUAL (no lexica). El bot NO transmite al
  paciente que esta realizando comunicaciones internas con el PROFESIONAL TRATANTE,
  sin importar el verbo (enviar/pasar/compartir/gestionar/consultar/tramitar/mandar
  /revisar), la persona gramatical (yo/nosotros), la voz (activa/pasiva), el tiempo
  ni la construccion. La regla es semantica: si la lectura natural del OUTBOUND
  comunica al paciente que se esta HACIENDO algo internamente con la profesional
  tratante, viola la cap. Ejemplos (lista NO exhaustiva): "ya le envie", "ya hemos
  enviado el motivo", "le paso el motivo", "gestiono con", "le comparto tu caso",
  "voy a consultar con", "esta siendo revisado por la doctora", "envie tus datos a
  la doctora para que revise". EXCEPCION: escalada explicita a un OPERADOR HUMANO
  del equipo (ej. "te atiende un asesor humano") NO viola la cap. verified=true si
  NINGUN OUTBOUND comunica gestion interna con la profesional. verified=false ante
  CUALQUIER OUTBOUND con esa semantica — citar texto exacto del OUTBOUND.
- omits_internal_categorization: el bot NO expone al paciente la metadata interna
  de filtrado de cohort. Verifica AUSENCIA de frases como "para pacientes nuevos",
  "para pacientes recurrentes", "para pacientes nuevos o recurrentes" o cualquier
  traduccion de los codigos internos NEW_ONLY/RETURNING_ONLY/BOTH_NEW_AND_RETURNING
  en los mensajes OUTBOUND. verified=true si todos los OUTBOUND estan limpios de
  esas frases. verified=false si encuentras alguna — citar la frase EXACTA del
  OUTBOUND como evidence.

Reglas:

1. Solo evalua las capabilities en "declared_capabilities". Ignora cualquier otra.

2. Para cada capability, verified=true si CUALQUIERA de estos dos criterios se cumple:

   (a) Evidencia EXPLICITA: hay un mensaje INBOUND donde el paciente declara o
       ejerce la capability directamente (ej. "Cuanto vale la consulta?" para
       asks_about_price).

   (b) Evidencia COMPORTAMENTAL (solo para caps inferenciales — local_patient,
       foreign_patient, new_patient, returning_patient, quotes_currency_per_location,
       uses_pre_payment_vocabulary, hides_internal_handoff, omits_internal_categorization):
       el flujo de la conversacion es consistente con la capability, observando como
       el bot trata al paciente, que datos pide o no, en que moneda cotiza, que metodo
       de pago ofrece, o como el paciente actua. Ejemplos:
       - new_patient verified si el bot pide nombre/edad porque no los tiene.
       - returning_patient verified si el bot saluda por nombre desde el primer mensaje.
       - local_patient verified si el bot cotizo en COP y ofrecio Nequi.
       - foreign_patient verified si el bot cotizo en USD y ofrecio Zelle.
       - quotes_currency_per_location verified si el bot cotizo UNA sola moneda
         consistente con la ubicacion (preguntada O inferida del contexto, ej.
         "presencial" => local => COP). verified=false SOLO si mostro varias
         monedas juntas sin saber ubicacion, o cotizo moneda inconsistente.
       - uses_pre_payment_vocabulary verified si NINGUN OUTBOUND pre-pago usa
         "confirmar"/"confirmacion" aplicado a cita/asistencia/espacio/reserva.
         "Confirmar el pago" SI esta permitido (se refiere al pago, no a la
         cita). verified=false ante variantes como "confirmar tu cita",
         "confirmar tu asistencia", "confirmar tu espacio", "confirmacion de
         tu cita" en mensajes anteriores al comprobante — citar frase exacta.
       - hides_internal_handoff: regla CONCEPTUAL — verified=true si NINGUN
         OUTBOUND comunica gestion interna con el PROFESIONAL TRATANTE,
         independiente del verbo, persona gramatical, voz o tiempo. Si la lectura
         natural del OUTBOUND revela que SE ESTA HACIENDO algo internamente con
         la profesional tratante (envio, traspaso, consulta, gestion, revision,
         comparticion), verified=false con cita exacta del texto. Excepcion:
         escalada explicita a un OPERADOR HUMANO del equipo (no la profesional).
       - omits_internal_categorization: verified=true si NINGUN OUTBOUND contiene
         frases como "para pacientes nuevos", "para pacientes recurrentes", "para
         pacientes nuevos o recurrentes" o cualquier traduccion de los codigos
         NEW_ONLY/RETURNING_ONLY/BOTH_NEW_AND_RETURNING. verified=false si
         encuentras alguna — citar la frase EXACTA del OUTBOUND como evidence.

3.5. ANTI-ALUCINACION: el campo evidence DEBE ser una cita TEXTUAL del transcript
     real (copiar el texto exacto de algun mensaje INBOUND u OUTBOUND segun el
     criterio aplicado). NUNCA inventes ni parafrasees la cita. Si no podes
     encontrar evidencia textual literal en el transcript que respalde verified=
     true o verified=false, prefiere verified=true con evidence=null y reasoning
     explicando que no hay evidencia clara — es preferible un falso negativo a
     una alucinacion. Verifica turno-por-turno antes de citar.

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
