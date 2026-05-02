"""
Load test script: simula pacientes concurrentes enviando mensajes
al backend via webhook (sin WhatsApp real).

Cada paciente es simulado por una LLM (Gemini) que genera respuestas
naturales basadas en un perfil/persona. El webhook es sincronico:
cuando retorna 200, el AI ya proceso y respondio. El script lee la
respuesta del AI y la alimenta al LLM-paciente para generar la
siguiente respuesta.

Modos de uso:
---------------------------------------------------------------------------

MODO LEGACY (--profile):
    Requiere:
        .secrets/make_credentials.env   → OWNER_EMAIL, OWNER_PASSWORD, PATIENT_EMAIL
        .secrets/make_api_base.env      → API_BASE

    Uso:
        uv run python scripts/load_test.py                         # default (psicologa, prod)
        uv run python scripts/load_test.py --profile ortodoncista  # pacientes de ortodoncia
        ENV=dev uv run python scripts/load_test.py                 # carga make_credentials_dev.env

MODO EVAL (--eval-mode):
    Requiere:
        .secrets/make_credentials_eval.env  → EVAL_API_BASE, EVAL_ADMIN_SECRET, PATIENT_EMAIL

    Donde:
        EVAL_API_BASE=https://dev-backend.run.app   # URL del backend dev
        EVAL_ADMIN_SECRET=<shared secret>            # match con backend EVAL_ADMIN_SECRET
        PATIENT_EMAIL=test@example.com               # email que el paciente simulado da al bot

    Uso:
        uv run python scripts/load_test.py --eval-mode
        uv run python scripts/load_test.py --eval-mode --shape shape_minimal
        uv run python scripts/load_test.py --eval-mode --no-cleanup

    El modo eval:
        - Carga shapes desde tests/fixtures/profiles/*.json.
        - Por cada shape, crea un tenant efimero via POST /v1/dev/eval-tenants.
        - Aplica el agent_profile del shape al tenant efimero.
        - Pre-seed Patients para personas con cap returning_patient.
        - Corre conversaciones reutilizando _run_patient.
        - Persiste reporte en Firestore (eval_runs/{run_id}_{shape_name}).
        - Borra el tenant efimero al terminar (salvo --no-cleanup).
        - Imprime un summary al final.
        - Exit code != 0 si alguna shape fue skipeada por gap de coverage.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import logging
import os
import pathlib
import sys
import time
import typing
import uuid
import zoneinfo

# Project root en sys.path para poder importar `scripts.personas` cuando este
# archivo se ejecuta directamente (`uv run python scripts/load_test.py`).
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import google.cloud.firestore as google_cloud_firestore  # noqa: E402
import httpx  # noqa: E402
from google import genai  # noqa: E402

import scripts.coverage as coverage  # noqa: E402
import scripts.llm_judge as llm_judge  # noqa: E402
import scripts.personas as personas_module  # noqa: E402
import src.adapters.outbound.firestore.paths as firestore_paths  # noqa: E402
import src.domain.entities.agent_profile as agent_profile_entity  # noqa: E402
import src.domain.entities.eval_run as eval_run_entity  # noqa: E402

# ---------------------------------------------------------------------------
# CLI parsing (antes de cargar .env para que --eval-mode sea conocido)
# ---------------------------------------------------------------------------
_arg_parser = argparse.ArgumentParser(description="Load test del bot WhatsApp")
_arg_parser.add_argument(
    "--profile",
    choices=["psicologa", "ortodoncista"],
    default=None,
    help="Tipo de profesional a simular (solo modo legacy, incompatible con --eval-mode).",
)
_arg_parser.add_argument(
    "--eval-mode",
    action="store_true",
    help="Corre evaluacion sistematica con shapes y personas anotadas.",
)
_arg_parser.add_argument(
    "--shape",
    action="append",
    default=None,
    help=(
        "Filtrar a uno o mas shapes especificos (solo con --eval-mode). "
        "Repetir el flag para varios: --shape A --shape B."
    ),
)
_arg_parser.add_argument(
    "--no-cleanup",
    action="store_true",
    help="No borrar tenants efimeros al finalizar (para inspeccion manual).",
)
_args, _ = _arg_parser.parse_known_args()

# Validaciones de exclusividad mutua
if _args.eval_mode and _args.profile is not None:
    sys.exit("Error: --eval-mode y --profile son incompatibles. Usa uno u otro.")
if _args.shape is not None and not _args.eval_mode:
    sys.exit("Error: --shape solo es valido junto a --eval-mode.")

EVAL_MODE: bool = _args.eval_mode
SHAPE_FILTERS: list[str] = list(_args.shape) if _args.shape else []
_NO_CLEANUP: bool = _args.no_cleanup

# Default legacy profile cuando no se pasa --profile en modo legacy
PROFILE_TYPE: str = _args.profile if _args.profile is not None else "psicologa"

# ---------------------------------------------------------------------------
# Cargar archivos de .secrets/ segun modo
# ---------------------------------------------------------------------------
_SECRETS_DIR = pathlib.Path(__file__).resolve().parent.parent / ".secrets"


def _load_env_file(path: pathlib.Path) -> None:
    """Carga un archivo KEY=VALUE en os.environ (no sobreescribe)."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        if key and key not in os.environ:
            os.environ[key] = value


if EVAL_MODE:
    # En eval-mode se usa exclusivamente make_credentials_eval.env
    _load_env_file(_SECRETS_DIR / "make_credentials_eval.env")
else:
    _ENV_SUFFIX = f"_{os.environ['ENV']}" if os.environ.get("ENV") else ""
    _load_env_file(_SECRETS_DIR / f"make_credentials{_ENV_SUFFIX}.env")
    _load_env_file(_SECRETS_DIR / f"make_api_base{_ENV_SUFFIX}.env")

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------
API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "")
OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "")
PATIENT_EMAIL = os.environ.get("PATIENT_EMAIL", "")

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_LOCATION = "us-central1"

NUM_PATIENTS = 3  # cuantos pacientes simular por batch (modo legacy)
RUN_ID = uuid.uuid4().hex[:8]  # ID unico por corrida (8 chars para eval; era 6 antes)
POLL_INTERVAL = 10  # segundos entre cada poll de scheduling requests
STAGGER_DELAY = 5  # segundos entre lanzamiento de cada paciente
MAX_TURNS = 20  # maximo de mensajes por paciente (evita loops infinitos)

_SHAPES_DIR = _PROJECT_ROOT / "tests" / "fixtures" / "profiles"

# ---------------------------------------------------------------------------
# System prompt para el LLM que simula pacientes
# ---------------------------------------------------------------------------
_PATIENT_SYSTEM_INSTRUCTION = """\
Eres {display_name}. Escribes por WhatsApp a un {practice_type}.

Hoy es {today_human}. Cualquier fecha posterior a hoy es FUTURA. No asumas
que estamos en otro año o mes — usa esta fecha como referencia absoluta.

{persona}

IMPORTANTE — como escribir:
- Eres una persona REAL, no un bot. Escribe como alguien normal por WhatsApp.
- Mensajes CORTOS. Maximo 1-2 oraciones. La gente real no escribe parrafos por WhatsApp.
- NO uses terminologia clinica ni del consultorio. Di cosas naturales como "una cita", "ver a la doctora", "una valoracion", "una sesion para mi hijo" — no nombres tecnicos del servicio.
- TU motivo de consulta DEBE ser coherente con el {practice_type}. NO inventes problemas que no aplican a esta especialidad (ej. si es ortodoncia, no hables de ansiedad ni terapia psicologica; si es psicologia, no hables de brackets ni dientes).
- NO des toda tu informacion de una (a menos que tu comportamiento lo indique). La gente real responde lo que le preguntan.
- Primer mensaje: saluda y di lo MINIMO. Ejemplos reales: "Hola buenas tardes, quiero pedir una cita", "Hola, cuanto vale la consulta?", "Buenas, quiero agendar una sesion".
- Cuando te pidan datos (nombre, edad, telefono), responde con datos coherentes con tu perfil.
- Cuando te pidan correo electronico, SIEMPRE responde: {patient_email} — sin importar tu persona.
- Responde SOLO con el mensaje de WhatsApp. Sin comillas, sin prefijos.
- Si te confirman la cita, agradece brevemente y despidete.
- NUNCA actues como el consultorio ni como la asistente. Tu SOLO eres el paciente. No ofrezcas horarios, precios ni informacion del consultorio. Si no sabes algo, PREGUNTA.
- Si te dicen "dame un momento" o similar, responde algo breve como "Dale", "Ok", "Listo" y espera.
- NUNCA actues como el consultorio ni como la asistente. Tu SOLO eres el paciente. No ofrezcas horarios, precios ni informacion del consultorio. Si no sabes algo, PREGUNTA.
- Si te dicen "dame un momento" o similar, responde algo breve como "Dale", "Ok", "Listo" y espera.
"""

# ---------------------------------------------------------------------------
# Pacientes por tipo de profesional (modo legacy)
# ---------------------------------------------------------------------------
# Las personas viven en `scripts/personas.py` (anotadas con capabilities). El
# pool inicial está VACÍO por diseño — el skill `/persona-from-combo` (Fase 2
# del plan eval) lo va poblando a medida que los shapes lo demanden.
#
# Mientras el pool esté vacío, `--profile` aborta con mensaje claro. El runner
# mantiene la flag para retro-compat: cuando haya personas, vuelve a funcionar
# sin cambios.
# ---------------------------------------------------------------------------


def _persona_to_dict(persona: personas_module.Persona) -> dict[str, str]:
    """Bridge: convierte una Persona dataclass al dict que espera el resto
    del runner. Mantiene la API interna estable hasta que migremos
    completamente a Persona en el refactor de Fase 4.
    """
    return {
        "whatsapp_user_id": persona.whatsapp_user_id,
        "display_name": persona.display_name,
        "persona": persona.persona_text,
    }


PATIENTS: list[dict[str, str]] = (
    []
    if EVAL_MODE
    else [_persona_to_dict(p) for p in personas_module.get_personas_by_profile(PROFILE_TYPE)]
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("load_test")

# ---------------------------------------------------------------------------
# Gemini client (singleton)
# ---------------------------------------------------------------------------
_gemini_client: genai.Client | None = None


def _get_gemini_client() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(
            vertexai=True,
            location=GEMINI_LOCATION,
        )
    return _gemini_client


# ---------------------------------------------------------------------------
# LLM: generar mensaje del paciente
# ---------------------------------------------------------------------------
async def _generate_patient_message(
    display_name: str,
    persona: str,
    conversation_history: list[dict[str, str]],
    practice_type: str = "consultorio de psicologia",
) -> str:
    """Genera el siguiente mensaje del paciente usando Gemini.

    conversation_history: lista de {"role": "patient"|"assistant", "content": "..."}
    """
    client = _get_gemini_client()

    today_human = _format_today_human()
    system_instruction = _PATIENT_SYSTEM_INSTRUCTION.format(
        display_name=display_name,
        persona=persona,
        patient_email=PATIENT_EMAIL,
        today_human=today_human,
        practice_type=practice_type,
    )

    # Mapear historial al formato Gemini:
    #   - mensajes del paciente -> role "model" (lo que Gemini ya "dijo")
    #   - mensajes del assistant -> role "user" (lo que el otro lado dijo)
    contents: list[dict[str, typing.Any]] = []

    # Filtrar mensajes vacios del historial
    conversation_history = [m for m in conversation_history if m["content"].strip()]

    if not conversation_history:
        # Primer mensaje: trigger para que genere el saludo
        contents.append(
            {
                "role": "user",
                "parts": [
                    {"text": "Inicia la conversacion enviando tu primer mensaje de WhatsApp."}
                ],
            }
        )
    else:
        # Gemini requiere que el primer mensaje sea role "user".
        # Si el historial empieza con un mensaje del paciente (model),
        # anteponemos el trigger inicial.
        first_role = "model" if conversation_history[0]["role"] == "patient" else "user"
        if first_role == "model":
            contents.append(
                {
                    "role": "user",
                    "parts": [
                        {"text": "Inicia la conversacion enviando tu primer mensaje de WhatsApp."}
                    ],
                }
            )

        for msg in conversation_history:
            gemini_role = "model" if msg["role"] == "patient" else "user"
            # Gemini requiere alternancia estricta user/model.
            # Si hay dos consecutivos del mismo rol, fusionar en el ultimo.
            if contents and contents[-1]["role"] == gemini_role:
                contents[-1]["parts"][0]["text"] += "\n" + msg["content"]
            else:
                contents.append(
                    {
                        "role": gemini_role,
                        "parts": [{"text": msg["content"]}],
                    }
                )

        # Gemini necesita que el ultimo mensaje sea "user" para generar "model"
        if contents[-1]["role"] == "model":
            contents.append(
                {
                    "role": "user",
                    "parts": [{"text": "Responde al ultimo mensaje como lo haria tu personaje."}],
                }
            )

    logger.info("Gemini contents (%d msgs): roles=%s", len(contents), [c["role"] for c in contents])
    for i, c in enumerate(contents):
        logger.info("  [%d] %s: %s", i, c["role"], c["parts"][0]["text"][:100])

    max_retries = 3
    gemini_timeout_seconds = 30.0
    for attempt in range(max_retries):
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.models.generate_content,
                    model=GEMINI_MODEL,
                    contents=contents,
                    config={
                        "system_instruction": system_instruction,
                        "max_output_tokens": 1024,
                        "temperature": 0.9,
                    },
                ),
                timeout=gemini_timeout_seconds,
            )
            break
        except TimeoutError:
            if attempt < max_retries - 1:
                logger.warning(
                    "Gemini timeout tras %.0fs, reintentando (attempt %d/%d)...",
                    gemini_timeout_seconds,
                    attempt + 1,
                    max_retries,
                )
                continue
            raise RuntimeError(
                f"Gemini timeout tras {gemini_timeout_seconds:.0f}s en {max_retries} intentos"
            ) from None
        except Exception as exc:
            if "429" in str(exc) and attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                logger.warning("Gemini 429, reintentando en %ds...", wait)
                await asyncio.sleep(wait)
            else:
                raise

    # Log raw response for debugging
    if not response.candidates:
        prompt_feedback = getattr(response, "prompt_feedback", None)
        raise RuntimeError(f"Gemini returned no candidates (prompt_feedback={prompt_feedback})")
    candidate = response.candidates[0]
    parts = candidate.content.parts if candidate.content and candidate.content.parts else []
    logger.info("Gemini finish_reason=%s, parts=%d", candidate.finish_reason, len(parts))
    for i, part in enumerate(parts):
        logger.info("  part[%d].text=%r", i, part.text[:200] if part.text else part.text)

    # Extraer texto de la primera part que tenga contenido
    for part in parts:
        text: str = part.text or ""
        if text.strip():
            return text.strip()
    return ""


# ---------------------------------------------------------------------------
# Helpers: webhook + message retrieval
# ---------------------------------------------------------------------------
def _generate_message_id() -> str:
    return f"wamid.mock.{int(time.time() * 1000)}.{uuid.uuid4().hex[:8]}"


def _build_webhook_payload(
    phone_number_id: str,
    whatsapp_user_id: str,
    display_name: str,
    message_text: str,
) -> dict[str, object]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "mock_entry",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": phone_number_id},
                            "contacts": [
                                {
                                    "wa_id": whatsapp_user_id,
                                    "profile": {"name": display_name},
                                }
                            ],
                            "messages": [
                                {
                                    "from": whatsapp_user_id,
                                    "id": _generate_message_id(),
                                    "type": "text",
                                    "text": {"body": message_text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


async def _send_webhook(
    client: httpx.AsyncClient,
    phone_number_id: str,
    patient: dict[str, str],
    message_text: str,
) -> None:
    payload = _build_webhook_payload(
        phone_number_id=phone_number_id,
        whatsapp_user_id=patient["whatsapp_user_id"],
        display_name=patient["display_name"],
        message_text=message_text,
    )
    response = await client.post("/v1/webhooks/whatsapp", json=payload)
    response.raise_for_status()


async def _get_conversation_id(
    client: httpx.AsyncClient,
    access_token: str,
    whatsapp_user_id: str,
) -> str | None:
    """Busca el conversation_id para un whatsapp_user_id."""
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = await client.get("/v1/conversations", headers=headers)
    resp.raise_for_status()
    for conv in resp.json().get("items", []):
        if conv.get("whatsapp_user_id") == whatsapp_user_id:
            conversation_id: str = conv["conversation_id"]
            return conversation_id
    return None


async def _get_messages(
    client: httpx.AsyncClient,
    access_token: str,
    conversation_id: str,
) -> list[dict[str, str]]:
    """Retorna historial de mensajes como lista de {role, content}.

    role: "patient" (inbound) | "assistant" (outbound)
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = await client.get(
        f"/v1/conversations/{conversation_id}/messages",
        headers=headers,
    )
    resp.raise_for_status()

    history: list[dict[str, str]] = []
    items = resp.json().get("items", [])
    logger.info("Raw messages (%d): directions=%s", len(items), [m.get("direction") for m in items])
    for msg in items:
        role = "patient" if msg.get("direction") == "INBOUND" else "assistant"
        history.append({"role": role, "content": msg.get("content", "")})
    return history


# ---------------------------------------------------------------------------
# Setup: login + phone_number_id (modo legacy)
# ---------------------------------------------------------------------------
async def _setup(client: httpx.AsyncClient) -> tuple[str, str]:
    """Login y obtener phone_number_id. Retorna (access_token, phone_number_id)."""
    login_resp = await client.post(
        "/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    login_resp.raise_for_status()
    access_token: str = login_resp.json()["access_token"]

    conn_resp = await client.get(
        "/v1/whatsapp/connection",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    conn_resp.raise_for_status()
    conn_data = conn_resp.json()

    if conn_data.get("status") != "CONNECTED":
        raise RuntimeError(
            f"WhatsApp no esta conectado (status={conn_data.get('status')}). "
            "Ejecuta el flujo OAuth primero."
        )

    phone_number_id: str = conn_data["phone_number_id"]
    logger.info("phone_number_id: %s", phone_number_id)
    return access_token, phone_number_id


# ---------------------------------------------------------------------------
# Polling: estado del scheduling request
# ---------------------------------------------------------------------------
_TERMINAL_STATUSES = {"SESSION_CLOSED", "CANCELLED", "CONSULTATION_REJECTED", "HUMAN_HANDOFF"}
_WAIT_FOR_OWNER_STATUSES = {"AWAITING_CONSULTATION_REVIEW", "AWAITING_PAYMENT_CONFIRMATION"}


_BOGOTA_TZ = zoneinfo.ZoneInfo("America/Bogota")
_DEFAULT_PAYMENT_AMOUNT_COP = 130000


async def _get_scheduling_request(
    client: httpx.AsyncClient,
    access_token: str,
    whatsapp_user_id: str,
) -> dict[str, typing.Any] | None:
    """Retorna el scheduling request mas reciente para este paciente, o None."""
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = await client.get("/v1/scheduling-requests", headers=headers)
    resp.raise_for_status()
    items: list[dict[str, typing.Any]] = resp.json().get("items", [])
    for item in items:
        if item.get("whatsapp_user_id") == whatsapp_user_id:
            return item
    return None


async def _get_scheduling_status(
    client: httpx.AsyncClient,
    access_token: str,
    whatsapp_user_id: str,
) -> str | None:
    """Retorna el status del scheduling request mas reciente para este paciente, o None."""
    request = await _get_scheduling_request(client, access_token, whatsapp_user_id)
    if request is None:
        return None
    return typing.cast(str, request.get("status"))


_SPANISH_DAYS = {
    0: "lunes",
    1: "martes",
    2: "miércoles",
    3: "jueves",
    4: "viernes",
    5: "sábado",
    6: "domingo",
}
_SPANISH_MONTHS = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


def _format_today_human() -> str:
    """Return today's date in Spanish, e.g. 'miércoles 29 de abril de 2026'."""
    now = datetime.datetime.now(tz=_BOGOTA_TZ)
    return f"{_SPANISH_DAYS[now.weekday()]} {now.day} de {_SPANISH_MONTHS[now.month]} de {now.year}"


# Module-level state so successive calls during the same load test propose
# different slot windows (avoids the infinite "same slot" loop when the patient
# rejects the first proposal).
_slot_call_counter = 0


def _build_future_slots(num_slots: int) -> list[dict[str, str]]:
    """Genera N slots futuros en horario habil del consultorio.

    Reglas:
      - Empieza al menos 2 semanas en el futuro (evita confusion del paciente
        cuando un LLM piensa que la fecha es 'ayer').
      - Solo miercoles/jueves/viernes (interseccion de horarios presencial y
        virtual del consultorio).
      - Horas variadas: 9, 10, 11, 14, 15.
      - Cada llamada arranca un poco mas adelante para dar variedad si la
        misma cita pasa por varias rondas de propuesta.
    """
    global _slot_call_counter
    call_index = _slot_call_counter
    _slot_call_counter += 1

    now_bogota = datetime.datetime.now(tz=_BOGOTA_TZ)
    base_offset_days = 14 + call_index * 7  # 2 semanas + 1 semana extra por ronda
    cursor = now_bogota.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(
        days=base_offset_days
    )
    slot_hours = [9, 10, 11, 14, 15]
    # Rotar el orden de horas por ronda para que las propuestas no se vean
    # identicas si la misma request pasa por varias rondas.
    rotated_hours = (
        slot_hours[call_index % len(slot_hours) :] + slot_hours[: call_index % len(slot_hours)]
    )

    candidates: list[datetime.datetime] = []
    while len(candidates) < num_slots:
        # Miercoles=2, Jueves=3, Viernes=4
        if cursor.weekday() in {2, 3, 4}:
            for hour in rotated_hours:
                slot_start = cursor.replace(hour=hour)
                if slot_start > now_bogota and len(candidates) < num_slots:
                    candidates.append(slot_start)
        cursor += datetime.timedelta(days=1)

    slots: list[dict[str, str]] = []
    for start in candidates:
        end = start + datetime.timedelta(hours=1)
        slots.append(
            {
                "slot_id": uuid.uuid4().hex,
                "start_at": start.isoformat(),
                "end_at": end.isoformat(),
                "timezone": "America/Bogota",
            }
        )
    return slots


async def _act_as_owner(
    client: httpx.AsyncClient,
    access_token: str,
    request: dict[str, typing.Any],
    tag: str,
) -> None:
    """Ejecuta la accion del profesional segun el estado del scheduling request."""
    status = request.get("status")
    request_id = typing.cast(str, request["request_id"])
    conversation_id = typing.cast(str, request["conversation_id"])
    headers = {"Authorization": f"Bearer {access_token}"}

    if status == "AWAITING_CONSULTATION_REVIEW":
        slots = _build_future_slots(2)
        payload = {
            "slots": slots,
            "professional_note": "[load_test] auto-aprobado por owner-bot",
        }
        resp = await client.post(
            f"/v1/conversations/{conversation_id}/scheduling/requests/{request_id}/professional-slots",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        logger.info(
            "[%s] Owner-bot: 2 slots propuestos (%s, %s)",
            tag,
            slots[0]["start_at"],
            slots[1]["start_at"],
        )
        return

    if status == "AWAITING_PAYMENT_CONFIRMATION":
        payment_amount = request.get("payment_amount_cop") or _DEFAULT_PAYMENT_AMOUNT_COP
        payment_payload: dict[str, typing.Any] = {
            "decision": "APPROVE",
            "professional_note": "[load_test] pago auto-aprobado por owner-bot",
            "payment_amount_cop": int(typing.cast(int, payment_amount)),
            "payment_currency": "COP",
        }
        resp = await client.post(
            f"/v1/conversations/{conversation_id}/scheduling/requests/{request_id}/payment-review",
            headers=headers,
            json=payment_payload,
        )
        resp.raise_for_status()
        logger.info("[%s] Owner-bot: pago aprobado por %d COP", tag, payment_amount)
        return

    logger.warning("[%s] Owner-bot: estado %s no manejado", tag, status)


_OWNER_ACTION_TIMEOUT_SECONDS = 180.0


async def _wait_for_owner_action(
    client: httpx.AsyncClient,
    access_token: str,
    whatsapp_user_id: str,
    tag: str,
    current_status: str,
) -> str:
    """Actua como el profesional segun el estado, luego polea hasta que cambie.

    Si el owner-bot falla (HTTP error) o el status no cambia tras
    `_OWNER_ACTION_TIMEOUT_SECONDS`, raisea RuntimeError. Esto evita loops
    infinitos cuando el backend rechaza la accion (ej. tenants eval donde
    Calendar no esta conectado y el endpoint que llamamos no skipea).
    """
    request = await _get_scheduling_request(client, access_token, whatsapp_user_id)
    owner_action_failed = False
    if request is not None and request.get("status") == current_status:
        try:
            await _act_as_owner(client, access_token, request, tag)
        except httpx.HTTPStatusError as exc:
            owner_action_failed = True
            logger.warning(
                "[%s] Owner-bot fallo (%s): %s",
                tag,
                exc.response.status_code,
                exc.response.text[:200],
            )

    if owner_action_failed:
        raise RuntimeError(
            f"[{tag}] Owner-bot rechazado por backend (status={current_status}); "
            "abortando conversacion para no quedar en loop infinito."
        )

    elapsed = 0.0
    while elapsed < _OWNER_ACTION_TIMEOUT_SECONDS:
        status = await _get_scheduling_status(client, access_token, whatsapp_user_id)
        if status is not None and status != current_status:
            logger.info("[%s] Status cambio a %s tras %.0fs", tag, status, elapsed)
            return status

        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        if int(elapsed) % 30 == 0:
            logger.info("[%s] Esperando que el bot procese la accion... (%.0fs)", tag, elapsed)

    raise RuntimeError(
        f"[{tag}] Timeout esperando cambio de status desde {current_status} tras "
        f"{_OWNER_ACTION_TIMEOUT_SECONDS:.0f}s"
    )


# ---------------------------------------------------------------------------
# Helper: sincronizar mensajes nuevos del AI al historial local
# ---------------------------------------------------------------------------
async def _sync_new_assistant_messages(
    client: httpx.AsyncClient,
    access_token: str,
    conversation_id: str,
    local_history: list[dict[str, str]],
    tag: str,
    label: str,
    max_wait: float = 30.0,
) -> bool:
    """Polling hasta que aparezca un OUTBOUND nuevo. Retorna True si encontro respuesta."""
    known_assistant_count = sum(1 for m in local_history if m["role"] == "assistant")
    elapsed = 0.0
    poll = 2.0

    while elapsed < max_wait:
        all_messages = await _get_messages(client, access_token, conversation_id)
        assistant_msgs = [
            m for m in all_messages if m["role"] == "assistant" and m["content"].strip()
        ]

        if len(assistant_msgs) > known_assistant_count:
            last_assistant = assistant_msgs[-1]
            if (
                not local_history
                or local_history[-1].get("role") != "assistant"
                or local_history[-1]["content"] != last_assistant["content"]
            ):
                local_history.append({"role": "assistant", "content": last_assistant["content"]})
                logger.info("[%s] %s AI respondio: %s", tag, label, last_assistant["content"][:80])
            return True

        await asyncio.sleep(poll)
        elapsed += poll

    logger.warning("[%s] %s: No llego respuesta OUTBOUND tras %.0fs", tag, label, max_wait)
    return False


# ---------------------------------------------------------------------------
# Flujo por paciente (LLM-driven)
# ---------------------------------------------------------------------------
async def _run_patient(
    client: httpx.AsyncClient,
    access_token: str,
    phone_number_id: str,
    patient: dict[str, str],
    index: int,
    practice_type: str = "consultorio de psicologia",
) -> float:
    # Generar whatsapp_user_id unico por corrida para crear conversacion limpia
    patient = {**patient, "whatsapp_user_id": f"{patient['whatsapp_user_id']}{RUN_ID}"}
    tag = f"Patient-{index + 1:02d}: {patient['display_name']}"
    logger.info("[%s] whatsapp_user_id=%s", tag, patient["whatsapp_user_id"])
    logger.info("[%s] Persona: %s", tag, patient["persona"][:120])
    start = time.monotonic()
    conversation_id: str | None = None
    local_history: list[dict[str, str]] = []
    # Cuando vemos un wait status por primera vez, dejamos que el paciente
    # responda al AI antes de bloquear. En el siguiente turno, bloqueamos.
    pending_wait_status: str | None = None

    for turn in range(1, MAX_TURNS + 1):
        # --- Generar mensaje del paciente con LLM ---
        logger.info("[%s] Turno %d: Generando mensaje...", tag, turn)
        patient_message = await _generate_patient_message(
            display_name=patient["display_name"],
            persona=patient["persona"],
            conversation_history=local_history,
            practice_type=practice_type,
        )
        if not patient_message:
            logger.warning(
                "[%s] Turno %d: Gemini devolvio mensaje vacio, reintentando...", tag, turn
            )
            continue

        logger.info("[%s] Turno %d: Enviando: %s", tag, turn, patient_message[:80])

        # --- Enviar via webhook ---
        await _send_webhook(client, phone_number_id, patient, patient_message)
        local_history.append({"role": "patient", "content": patient_message})

        # --- Obtener conversation_id si aun no lo tenemos ---
        if conversation_id is None:
            conversation_id = await _get_conversation_id(
                client, access_token, patient["whatsapp_user_id"]
            )

        # --- Si hay un wait pendiente, el paciente ya respondio -> ahora bloquear ---
        if pending_wait_status is not None:
            pending_wait_status = None
            current = await _get_scheduling_status(
                client, access_token, patient["whatsapp_user_id"]
            )
            if current in _TERMINAL_STATUSES:
                elapsed = time.monotonic() - start
                logger.info("[%s] Finalizado con status %s en %.1fs", tag, current, elapsed)
                return elapsed
            if current in _WAIT_FOR_OWNER_STATUSES:
                logger.info("[%s] Esperando accion del owner (status=%s)...", tag, current)
                new_status = await _wait_for_owner_action(
                    client, access_token, patient["whatsapp_user_id"], tag, current
                )
                if new_status in _TERMINAL_STATUSES:
                    elapsed = time.monotonic() - start
                    logger.info("[%s] Finalizado con status %s en %.1fs", tag, new_status, elapsed)
                    return elapsed
            # Esperar respuesta del bot antes de pasar al siguiente turno (evita
            # que el LLM-paciente reenvie mensajes duplicados mientras el bot
            # todavia esta procesando).
            if conversation_id is not None:
                got_response = await _sync_new_assistant_messages(
                    client,
                    access_token,
                    conversation_id,
                    local_history,
                    tag,
                    f"Turno {turn} (post-pending)",
                    max_wait=120.0,
                )
                if not got_response:
                    raise RuntimeError(f"AI no respondio tras 120s en turno {turn} (post-pending)")
            continue

        # --- Esperar respuesta del AI desde el backend ---
        if conversation_id is not None:
            got_response = await _sync_new_assistant_messages(
                client,
                access_token,
                conversation_id,
                local_history,
                tag,
                f"Turno {turn}",
                max_wait=120.0,
            )
            if not got_response:
                raise RuntimeError(f"AI no respondio tras 120s en turno {turn}")

        # --- Verificar estado del scheduling request ---
        status = await _get_scheduling_status(client, access_token, patient["whatsapp_user_id"])

        if status in _TERMINAL_STATUSES:
            elapsed = time.monotonic() - start
            logger.info("[%s] Finalizado con status %s en %.1fs", tag, status, elapsed)
            return elapsed

        if status in _WAIT_FOR_OWNER_STATUSES:
            # No bloquear aun: dejar que el paciente responda al mensaje
            # del AI (ej: info de pago) en el siguiente turno, y DESPUES bloquear.
            logger.info(
                "[%s] Status=%s, paciente respondera primero antes de esperar al owner",
                tag,
                status,
            )
            pending_wait_status = status

    elapsed = time.monotonic() - start
    logger.info("[%s] Alcanzo MAX_TURNS (%d) en %.1fs", tag, MAX_TURNS, elapsed)
    return elapsed


# ---------------------------------------------------------------------------
# EVAL MODE — helpers
# ---------------------------------------------------------------------------


async def _apply_shape_agent_profile(
    client: httpx.AsyncClient,
    access_token: str,
    agent_profile: object,
) -> None:
    """Aplica el agent_profile del shape al tenant efimero via
    PUT /v1/agent/professional-profile.

    El shape JSON ya esta en formato compatible con UpdateProfessionalProfileDTO:
    los campos identity, services, presencial_schedule, virtual_schedule,
    payment_methods son exactamente los que acepta el endpoint.
    """
    # agent_profile viene deserializado como AgentProfile desde el shape JSON.
    # Lo convertimos a dict (mode="json" para que sea JSON-serializable) y
    # enviamos directamente. Los campos extra (tenant_id, updated_at) son
    # ignorados por el endpoint dado que UpdateProfessionalProfileDTO no los declara.
    profile = typing.cast(agent_profile_entity.AgentProfile, agent_profile)
    body = profile.model_dump(mode="json")
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = await client.put("/v1/agent/professional-profile", headers=headers, json=body)
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "_apply_shape_agent_profile HTTP %s: %s",
            exc.response.status_code,
            exc.response.text[:400],
        )
        raise


async def _pre_seed_patient(
    client: httpx.AsyncClient,
    access_token: str,
    persona: personas_module.Persona,
    run_id: str,
) -> None:
    """Crea o actualiza el Patient para una persona con cap returning_patient.

    El whatsapp_user_id se sufija con el run_id para coincidir con el que
    _run_patient usa al crear la conversacion. Si el patient ya existe (409),
    se ignora (idempotente). Otros 4xx (ej. 422 schema mismatch) se loguean
    pero no abortan el shape — la conversacion igual se ejecuta, simplemente
    no entra en el branch RETURNING.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    parts = [p for p in persona.display_name.split() if p]
    first_name = parts[0] if parts else "Test"
    last_name = parts[-1] if len(parts) > 1 else "Test"
    payload: dict[str, object] = {
        "whatsapp_user_id": persona.whatsapp_user_id + run_id,
        "first_name": first_name,
        "last_name": last_name,
        "email": PATIENT_EMAIL,
        "age": 35,
        "location": "Cali",
        "phone": "+57 300 000 0000",
    }
    resp = await client.post("/v1/patients", headers=headers, json=payload)
    if resp.status_code == 409:
        logger.info("_pre_seed_patient: patient ya existe para %s, continuando", persona.id)
        return
    if 400 <= resp.status_code < 500:
        # Cualquier 4xx (422 validation, 401, 403, etc.) lo logueamos y seguimos.
        # La persona returning va a fallar el branch RETURNING en runtime,
        # pero el shape no se interrumpe entero por esto.
        logger.warning(
            "_pre_seed_patient HTTP %s para %s: %s — sigo sin pre-seed",
            resp.status_code,
            persona.id,
            resp.text[:200],
        )
        return
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # 5xx = error del backend, no del input. Si esto pasa hay algo grave.
        logger.error(
            "_pre_seed_patient HTTP %s (server error) para %s: %s",
            exc.response.status_code,
            persona.id,
            exc.response.text[:200],
        )
        raise


async def _capture_conversation_snapshot(
    client: httpx.AsyncClient,
    access_token: str,
    persona: personas_module.Persona,
    shape: coverage.Shape,
    run_id: str,
    elapsed: float,
    status: typing.Literal["ok", "fail", "skipped"],
    error: str | None = None,
) -> eval_run_entity.EvalRunConversationSnapshot:
    """Captura el estado final de la conversacion del persona y lo empaqueta
    como EvalRunConversationSnapshot.

    Aun cuando status='fail', intentamos capturar transcript + scheduling state
    porque eso da evidencia para debug (que mensajes vio el bot antes de fallar).
    Si los GETs HTTP fallan (ej. tenant ya borrado, conversation_id no existe),
    los wraps de try/except dejan los campos vacios sin propagar excepcion.
    """
    # Combos que esta persona satisface para este shape.
    # Cast a list[list[str]] porque EvalRunConversationSnapshot.combos_satisfied
    # es list[list[str]] (vocabulario abierto en la entity); aca recibimos
    # list[list[Capability]] (Literal cerrado).
    combos_satisfied: list[list[str]] = [
        [str(cap) for cap in combo]
        for combo in shape.metadata.required_combos
        if set(combo).issubset(set(persona.capabilities))
    ]

    whatsapp_user_id_with_run = persona.whatsapp_user_id + run_id

    # --- Buscar conversation_id ---
    conversation_id: str | None = None
    try:
        conversation_id = await _get_conversation_id(
            client, access_token, whatsapp_user_id_with_run
        )
    except httpx.HTTPStatusError as exc:
        logger.warning("_capture_conversation_snapshot: no pudo obtener conv_id: %s", exc)

    # --- Obtener mensajes del transcript ---
    transcript: list[eval_run_entity.EvalRunConversationMessage] = []
    if conversation_id is not None:
        try:
            raw_messages = await _get_messages(client, access_token, conversation_id)
            for msg in raw_messages:
                direction: typing.Literal["INBOUND", "OUTBOUND"] = (
                    "INBOUND" if msg["role"] == "patient" else "OUTBOUND"
                )
                transcript.append(
                    eval_run_entity.EvalRunConversationMessage(
                        direction=direction,
                        content=msg["content"],
                        timestamp=datetime.datetime.now(tz=datetime.UTC),
                    )
                )
        except httpx.HTTPStatusError as exc:
            logger.warning("_capture_conversation_snapshot: no pudo obtener mensajes: %s", exc)

    # --- Buscar scheduling request ---
    scheduling_request_id: str | None = None
    final_status: str | None = None
    effective_status: typing.Literal["ok", "fail", "skipped"] = status
    try:
        sr = await _get_scheduling_request(client, access_token, whatsapp_user_id_with_run)
        if sr is not None:
            scheduling_request_id = typing.cast(str | None, sr.get("request_id"))
            final_status = typing.cast(str | None, sr.get("status"))
            # Si el scheduling request existe pero termino en un estado de fallo, marcar fail
            if final_status in {"CANCELLED", "CONSULTATION_REJECTED", "HUMAN_HANDOFF"}:
                effective_status = "fail"
            elif final_status == "SESSION_CLOSED":
                effective_status = "ok"
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "_capture_conversation_snapshot: no pudo obtener scheduling request: %s", exc
        )

    snapshot = eval_run_entity.EvalRunConversationSnapshot(
        persona_id=persona.id,
        combos_satisfied=combos_satisfied,
        status=effective_status,
        elapsed_seconds=elapsed,
        conversation_id=conversation_id,
        scheduling_request_id=scheduling_request_id,
        final_status=final_status,
        transcript=transcript,
        error=error,
    )

    # Llamar al juez si la conversacion tiene transcript y combos satisfechos.
    # judge_conversation es sync (Gemini SDK no expone async); usamos
    # asyncio.to_thread para no bloquear el event loop ~5s por persona.
    if snapshot.transcript and snapshot.combos_satisfied:
        declared_caps = list({cap for combo in snapshot.combos_satisfied for cap in combo})
        snapshot.judge_verdict = await asyncio.to_thread(
            llm_judge.judge_conversation,
            persona_id=persona.id,
            declared_capabilities=declared_caps,
            transcript=snapshot.transcript,
            gemini_client=_get_gemini_client(),
        )

    return snapshot


def _persist_eval_run(
    run_id: str,
    shape: coverage.Shape,
    conversation_results: list[eval_run_entity.EvalRunConversationSnapshot],
    started_at: datetime.datetime,
    finished_at: datetime.datetime,
    eval_tenant_id: str,
    skipped: bool = False,
    uncovered_combos: list[list[str]] | None = None,
) -> None:
    """Persiste el reporte del run en Firestore directamente con el SDK.

    Decision de document path: usamos `{run_id}_{shape_name}` en lugar de
    solo `run_id`. Razon: un run cubre N shapes — con solo run_id el documento
    se sobreescribiria con merge=True y solo quedaria el ultimo shape.
    Con el sufijo `_{shape_name}`, cada shape tiene su propio doc, el dashboard
    puede listar todos los shapes de un run filtrando por prefijo `run_id_`, y
    el historial es completo y auditable por shape.
    """
    doc_run_id = f"{run_id}_{shape.metadata.name}"
    # Forzar el project del Firestore client cuando este seteado en env
    # (.secrets/make_credentials_eval.env). Sin esto, el ADC personal
    # apunta por default al quota_project_id de prod aunque el script este
    # corriendo contra el backend dev.
    firestore_project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get(
        "EVAL_FIRESTORE_PROJECT"
    )
    firestore_client = (
        google_cloud_firestore.Client(project=firestore_project)
        if firestore_project
        else google_cloud_firestore.Client()
    )

    eval_run = eval_run_entity.EvalRun(
        run_id=run_id,
        shape_name=shape.metadata.name,
        started_at=started_at,
        finished_at=finished_at,
        total_personas=len(conversation_results),
        ok=sum(1 for s in conversation_results if s.status == "ok"),
        fail=sum(1 for s in conversation_results if s.status == "fail"),
        skipped=skipped,
        uncovered_combos=uncovered_combos or [],
        eval_tenant_id=eval_tenant_id,
    )

    run_doc_path = firestore_paths.eval_run_document(doc_run_id)
    firestore_client.document(run_doc_path).set(
        _flatten_nested_arrays(eval_run.model_dump(mode="json"), ["uncovered_combos"]),
        merge=True,
    )
    logger.info("Eval run persistido: %s", run_doc_path)

    for snapshot in conversation_results:
        conv_doc_path = firestore_paths.eval_run_conversation_document(
            doc_run_id, snapshot.persona_id
        )
        firestore_client.document(conv_doc_path).set(
            _flatten_nested_arrays(snapshot.model_dump(mode="json"), ["combos_satisfied"]),
            merge=True,
        )
        logger.info("Conversation snapshot persistido: %s", conv_doc_path)


def _flatten_nested_arrays(data: dict[str, typing.Any], keys: list[str]) -> dict[str, typing.Any]:
    """Firestore no permite arrays anidados (list[list[X]]). Aplana cada
    sublista a un string JSON-encoded para que persista como list[str].
    El adapter Firestore (lectura) hace la operacion inversa antes de
    devolver la entity.
    """
    out = dict(data)
    for key in keys:
        value = out.get(key)
        if isinstance(value, list):
            out[key] = [json.dumps(item) if isinstance(item, list) else item for item in value]
    return out


def _persist_skipped_run(
    run_id: str,
    shape: coverage.Shape,
    exc: coverage.CoverageGapError,
) -> None:
    """Persiste un eval run marcado como skipped cuando hay un gap de coverage."""
    now = datetime.datetime.now(tz=datetime.UTC)
    uncovered: list[list[str]] = [
        list(combo)
        for combo in coverage.detect_uncovered_combos(shape, personas_module.ALL_PERSONAS)
    ]
    _persist_eval_run(
        run_id=run_id,
        shape=shape,
        conversation_results=[],
        started_at=now,
        finished_at=now,
        eval_tenant_id="",
        skipped=True,
        uncovered_combos=uncovered,
    )
    logger.warning("Shape %r skipeada por gap de coverage: %s", shape.metadata.name, exc)


# ---------------------------------------------------------------------------
# EVAL MODE — lifecycle por shape
# ---------------------------------------------------------------------------


class _ShapeSummary(typing.TypedDict):
    """Resumen por shape que usa main_eval() para el reporte final de consola."""

    shape_name: str
    skipped: bool
    uncovered_combos: list[list[str]]
    conversation_results: list[eval_run_entity.EvalRunConversationSnapshot]


async def _run_eval_shape(
    client: httpx.AsyncClient,
    shape: coverage.Shape,
    run_id: str,
    admin_secret: str,
    eval_api_base: str,
) -> _ShapeSummary:
    """Lifecycle completo de evaluacion para un shape:
    coverage check → tenant efimero → aplicar profile → pre-seed → conversaciones
    → capturar snapshots → persistir → cleanup.

    Retorna un _ShapeSummary para el reporte final de consola.
    """
    shape_name = shape.metadata.name

    # 1. Validar coverage
    try:
        coverage.assert_combos_covered(shape, personas_module.ALL_PERSONAS)
    except coverage.CoverageGapError as exc:
        _persist_skipped_run(run_id, shape, exc)
        uncovered: list[list[str]] = [
            [str(cap) for cap in combo]
            for combo in coverage.detect_uncovered_combos(shape, personas_module.ALL_PERSONAS)
        ]
        return _ShapeSummary(
            shape_name=shape_name,
            skipped=True,
            uncovered_combos=uncovered,
            conversation_results=[],
        )

    # 2. Crear tenant efimero — si falla, no abortamos todo el run; persistimos
    #    skipped y seguimos con el siguiente shape.
    started_at = datetime.datetime.now(tz=datetime.UTC)
    create_resp = await client.post(
        "/v1/dev/eval-tenants",
        headers={"X-Eval-Admin-Secret": admin_secret},
        json={"run_id": run_id, "shape_name": shape_name},
    )
    try:
        create_resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "No se pudo crear eval tenant para shape %r: HTTP %s — %s",
            shape_name,
            exc.response.status_code,
            exc.response.text[:400],
        )
        try:
            _persist_skipped_run(
                run_id,
                shape,
                coverage.CoverageGapError(
                    f"create_eval_tenant failed: HTTP {exc.response.status_code}"
                ),
            )
        except Exception:
            logger.exception("Persistir skipped run fallo")
        return _ShapeSummary(
            shape_name=shape_name,
            skipped=True,
            uncovered_combos=[],
            conversation_results=[],
        )

    eval_tenant: dict[str, str] = create_resp.json()
    tenant_token: str = eval_tenant["access_token"]
    phone_number_id: str = eval_tenant["phone_number_id"]
    tenant_id: str = eval_tenant["tenant_id"]

    conversation_results: list[eval_run_entity.EvalRunConversationSnapshot] = []
    apply_profile_failed = False

    try:
        # 3. Aplicar agent_profile del shape al tenant efimero. Si falla, no
        #    queremos un reporte que pretenda ok=0,fail=0,skipped=False (engañoso).
        try:
            await _apply_shape_agent_profile(client, tenant_token, shape.agent_profile)
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            apply_profile_failed = True
            logger.error(
                "[Shape %r] _apply_shape_agent_profile fallo: %s — saltando conversaciones",
                shape_name,
                exc,
            )

        # 4-6. Solo correr conversaciones si el profile se aplico OK.
        if not apply_profile_failed:
            personas = coverage.select_personas_for_shape(shape, personas_module.ALL_PERSONAS)
            logger.info(
                "Shape %r: %d personas seleccionadas: %s",
                shape_name,
                len(personas),
                [p.id for p in personas],
            )

            # Pre-seed Patients para personas con returning_patient
            for persona in personas:
                if "returning_patient" in persona.capabilities:
                    await _pre_seed_patient(client, tenant_token, persona, run_id)
        else:
            personas = []

        # Correr conversaciones secuencialmente (cada shape es su propio tenant;
        # no hay valor en paralelizarlas dentro de un mismo tenant efimero dado
        # que el bot tiene estado compartido por conversacion).
        for i, persona in enumerate(personas):
            patient_dict = _persona_to_dict(persona)
            elapsed = 0.0
            snap_error: str | None = None
            snap_status: typing.Literal["ok", "fail", "skipped"] = "ok"
            shape_identity = shape.agent_profile.identity
            shape_practice_type = (
                shape_identity.professional_title
                if shape_identity is not None and shape_identity.professional_title
                else "consultorio"
            )
            try:
                elapsed = await _run_patient(
                    client,
                    tenant_token,
                    phone_number_id,
                    patient_dict,
                    i,
                    practice_type=shape_practice_type,
                )
            except (RuntimeError, httpx.HTTPStatusError) as exc:
                snap_error = f"{type(exc).__name__}: {exc}"
                snap_status = "fail"
                logger.error(
                    "[Shape %r / %s] conversacion fallo: %s", shape_name, persona.id, snap_error
                )

            # 7. Capturar transcript + estado final
            snapshot = await _capture_conversation_snapshot(
                client,
                tenant_token,
                persona,
                shape,
                run_id,
                elapsed=elapsed,
                status=snap_status,
                error=snap_error,
            )
            conversation_results.append(snapshot)

    finally:
        finished_at = datetime.datetime.now(tz=datetime.UTC)

        # 8. Persistir reporte a Firestore. Si falla (network, perms, schema),
        #    seguimos al cleanup del tenant — no queremos tenants huerfanos
        #    porque Firestore tuvo un hipo.
        try:
            _persist_eval_run(
                run_id=run_id,
                shape=shape,
                conversation_results=conversation_results,
                started_at=started_at,
                finished_at=finished_at,
                eval_tenant_id=tenant_id,
            )
        except Exception:
            logger.exception(
                "[Shape %r] _persist_eval_run fallo — sigo al cleanup del tenant",
                shape_name,
            )

        # 9. Cleanup tenant efimero (salvo --no-cleanup)
        if not _NO_CLEANUP:
            try:
                del_resp = await client.delete(
                    f"/v1/dev/eval-tenants/{tenant_id}",
                    headers={"X-Eval-Admin-Secret": admin_secret},
                )
                del_resp.raise_for_status()
                logger.info("Tenant efimero %s eliminado", tenant_id)
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "No se pudo eliminar tenant efimero %s: HTTP %s — %s",
                    tenant_id,
                    exc.response.status_code,
                    exc.response.text[:200],
                )
        else:
            logger.info("--no-cleanup: tenant efimero %s conservado", tenant_id)

    return _ShapeSummary(
        shape_name=shape_name,
        skipped=apply_profile_failed,
        uncovered_combos=[],
        conversation_results=conversation_results,
    )


# ---------------------------------------------------------------------------
# EVAL MODE — main
# ---------------------------------------------------------------------------
async def main_eval() -> int:
    """Punto de entrada del modo eval. Retorna exit code (0=ok, 1=skips)."""
    eval_api_base = os.environ.get("EVAL_API_BASE", "")
    eval_admin_secret = os.environ.get("EVAL_ADMIN_SECRET", "")
    if not eval_api_base:
        raise SystemExit(
            "EVAL_API_BASE no esta configurado. Agregalo a .secrets/make_credentials_eval.env."
        )
    if not eval_admin_secret:
        raise SystemExit(
            "EVAL_ADMIN_SECRET no esta configurado. Agregalo a .secrets/make_credentials_eval.env."
        )
    if not PATIENT_EMAIL:
        raise SystemExit(
            "PATIENT_EMAIL no esta configurado. Agregalo a .secrets/make_credentials_eval.env."
        )

    # Cargar shapes
    shapes = coverage.load_shapes_from_dir(_SHAPES_DIR)
    if SHAPE_FILTERS:
        wanted = set(SHAPE_FILTERS)
        available = {s.metadata.name for s in shapes}
        missing = wanted - available
        if missing:
            raise SystemExit(
                f"Shape(s) no encontrado(s) en {_SHAPES_DIR}: {sorted(missing)}. "
                f"Disponibles: {sorted(available)}"
            )
        shapes = [s for s in shapes if s.metadata.name in wanted]

    logger.info(
        "Eval mode: run_id=%s, %d shape(s) a evaluar%s",
        RUN_ID,
        len(shapes),
        f" (filtrado a {SHAPE_FILTERS!r})" if SHAPE_FILTERS else "",
    )

    total_start = time.monotonic()
    had_skips = False
    shape_summaries: list[_ShapeSummary] = []

    async with httpx.AsyncClient(base_url=eval_api_base, timeout=120.0) as client:
        for shape in shapes:
            summary = await _run_eval_shape(
                client,
                shape,
                RUN_ID,
                eval_admin_secret,
                eval_api_base,
            )
            shape_summaries.append(summary)
            if summary["skipped"]:
                had_skips = True

    total_elapsed = time.monotonic() - total_start
    total_min = int(total_elapsed // 60)
    total_sec = int(total_elapsed % 60)

    # Reporte de consola
    print()
    print(f"=== EVAL REPORT (run_id={RUN_ID}) ===")
    print()
    for summary in shape_summaries:
        sname = summary["shape_name"]
        if summary["skipped"]:
            missing_str = summary["uncovered_combos"]
            print(f"{sname:<30}  SKIPPED   combos faltantes: {missing_str}")
            print("  → SKIPPED   ninguna persona cubre los combos requeridos")
        else:
            results = summary["conversation_results"]
            ok_count = sum(1 for r in results if r.status == "ok")
            fail_count = sum(1 for r in results if r.status == "fail")
            shape_status = "OK" if fail_count == 0 else "FAIL"
            print(f"{sname:<30}  {shape_status:<6}  ok={ok_count} fail={fail_count}")
            for result in results:
                fs = result.final_status or "N/A"
                status_label = "OK" if result.status == "ok" else "FAIL"
                print(
                    f"  → {result.persona_id:<28}  {status_label:<4}  "
                    f"{fs}  ({result.elapsed_seconds:.1f}s)"
                )
        print()

    print(
        f"Pool: {len(personas_module.ALL_PERSONAS)} personas | Tiempo total: {total_min}m {total_sec}s"
    )
    if had_skips:
        print()
        print("ADVERTENCIA: hubo shapes skipeadas por gaps de coverage. Exit code = 1.")

    return 1 if had_skips else 0


# ---------------------------------------------------------------------------
# Main legacy
# ---------------------------------------------------------------------------
async def main() -> None:
    if not PATIENT_EMAIL:
        raise RuntimeError(
            "PATIENT_EMAIL not set. Add it to .secrets/make_credentials.env or export it."
        )
    if not PATIENTS:
        raise RuntimeError(
            f"No hay personas registradas para el perfil {PROFILE_TYPE!r}. "
            "El pool de scripts/personas.py está vacío hasta que el skill "
            "`/persona-from-combo` lo pueble (Fase 3 del plan eval). "
            "Ejecutá el skill iterativamente sobre los shapes en "
            "tests/fixtures/profiles/ y reintentá."
        )
    all_patients = PATIENTS[:NUM_PATIENTS]
    batch_size = NUM_PATIENTS
    total_start = time.monotonic()
    logger.info(
        "Iniciando load test con %d pacientes (batches de %d)...", len(all_patients), batch_size
    )

    all_results: list[tuple[str, float | Exception]] = []

    async with httpx.AsyncClient(base_url=API_BASE, timeout=120.0) as client:
        access_token, phone_number_id = await _setup(client)

        for batch_start in range(0, len(all_patients), batch_size):
            batch = all_patients[batch_start : batch_start + batch_size]
            batch_num = batch_start // batch_size + 1
            logger.info("--- Batch %d: %d pacientes ---", batch_num, len(batch))

            async def _launch_patient(
                patient: dict[str, str], index: int, stagger_offset: int = 0
            ) -> tuple[str, float | Exception]:
                await asyncio.sleep(stagger_offset * STAGGER_DELAY)
                try:
                    elapsed = await _run_patient(
                        client, access_token, phone_number_id, patient, index
                    )
                    return patient["display_name"], elapsed
                except Exception as exc:
                    logger.error(
                        "[Patient-%02d: %s] FALLO: %s: %s",
                        index + 1,
                        patient["display_name"],
                        type(exc).__name__,
                        str(exc) or "(no message)",
                        exc_info=True,
                    )
                    return patient["display_name"], exc

            tasks = [
                _launch_patient(patient, batch_start + i, stagger_offset=i)
                for i, patient in enumerate(batch)
            ]
            batch_results = await asyncio.gather(*tasks)
            all_results.extend(batch_results)

    total_elapsed = time.monotonic() - total_start

    # Summary
    ok_count = sum(1 for _, r in all_results if isinstance(r, float))
    fail_count = len(all_results) - ok_count
    total_min = int(total_elapsed // 60)
    total_sec = int(total_elapsed % 60)

    print()
    print("=" * 50)
    print("  LOAD TEST SUMMARY")
    print("=" * 50)
    print(f"  Total: {len(all_results)} | OK: {ok_count} | FAIL: {fail_count}")
    print(f"  Tiempo: {total_min}m {total_sec}s")
    print("-" * 50)
    for i, (name, result) in enumerate(all_results):
        if isinstance(result, float):
            print(f"  [OK]   Patient-{i + 1:02d} ({name})  {result:.1f}s")
        else:
            print(f"  [FAIL] Patient-{i + 1:02d} ({name})  {result}")
    print("=" * 50)


if __name__ == "__main__":
    if EVAL_MODE:
        exit_code = asyncio.run(main_eval())
        sys.exit(exit_code)
    else:
        asyncio.run(main())
