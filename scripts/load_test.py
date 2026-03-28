"""
Load test script: simula 10 pacientes concurrentes enviando mensajes
al backend via webhook (sin WhatsApp real).

Cada paciente es simulado por una LLM (Gemini) que genera respuestas
naturales basadas en un perfil/persona. El webhook es sincronico:
cuando retorna 200, el AI ya proceso y respondio. El script lee la
respuesta del AI y la alimenta al LLM-paciente para generar la
siguiente respuesta.

Requiere:
    - WHATSAPP_OUTBOUND_NOOP=true en el backend
    - ADC configurado (gcloud auth application-default login)

Uso:
    uv run python scripts/load_test.py                          # local
    API_BASE=https://tu-backend.run.app uv run python scripts/load_test.py  # GCP
"""

from __future__ import annotations

import asyncio
import logging
import os
import pathlib
import time
import typing
import uuid

import httpx
from google import genai

# ---------------------------------------------------------------------------
# Cargar .secrets/make_credentials.env y .secrets/make_api_base.env
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


_load_env_file(_SECRETS_DIR / "make_credentials.env")
_load_env_file(_SECRETS_DIR / "make_api_base.env")

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------
API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "")
OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "")

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_LOCATION = "us-central1"

NUM_PATIENTS = 3  # cuantos pacientes simular por batch
RUN_ID = uuid.uuid4().hex[:6]  # ID unico por corrida para evitar reutilizar conversaciones
POLL_INTERVAL = 10  # segundos entre cada poll de scheduling requests
STAGGER_DELAY = 5  # segundos entre lanzamiento de cada paciente
MAX_TURNS = 20  # maximo de mensajes por paciente (evita loops infinitos)

# ---------------------------------------------------------------------------
# System prompt para el LLM que simula pacientes
# ---------------------------------------------------------------------------
_PATIENT_SYSTEM_INSTRUCTION = """\
Eres {display_name}. Escribes por WhatsApp a un consultorio de psicologia.

{persona}

IMPORTANTE — como escribir:
- Eres una persona REAL, no un bot. Escribe como alguien normal por WhatsApp.
- Mensajes CORTOS. Maximo 1-2 oraciones. La gente real no escribe parrafos por WhatsApp.
- NO uses terminologia clinica ni del consultorio. No digas "consulta individual adultos" ni "terapia infantil". Di "una cita", "ver a la doctora", "una sesion para mi hijo".
- NO des toda tu informacion de una (a menos que tu comportamiento lo indique). La gente real responde lo que le preguntan.
- Primer mensaje: saluda y di lo MINIMO. Ejemplos reales: "Hola buenas tardes, quiero pedir una cita", "Hola, cuanto vale la consulta?", "Buenas, quiero agendar una sesion".
- Cuando te pidan datos (nombre, edad, correo, telefono), responde con datos coherentes con tu perfil.
- Responde SOLO con el mensaje de WhatsApp. Sin comillas, sin prefijos.
- Si te confirman la cita, agradece brevemente y despidete.
- NUNCA actues como el consultorio ni como la asistente. Tu SOLO eres el paciente. No ofrezcas horarios, precios ni informacion del consultorio. Si no sabes algo, PREGUNTA.
- Si te dicen "dame un momento" o similar, responde algo breve como "Dale", "Ok", "Listo" y espera.
- NUNCA actues como el consultorio ni como la asistente. Tu SOLO eres el paciente. No ofrezcas horarios, precios ni informacion del consultorio. Si no sabes algo, PREGUNTA.
- Si te dicen "dame un momento" o similar, responde algo breve como "Dale", "Ok", "Listo" y espera.
"""

# ---------------------------------------------------------------------------
# 7 Pacientes composicionales
# ---------------------------------------------------------------------------
PATIENTS: list[dict[str, str]] = [
    # --- 2 Nacionales presencial (Cali) ---
    {
        "whatsapp_user_id": "573001110001",
        "display_name": "Carlos Ramirez",
        "persona": (
            "Tienes 45 años, vives en Cali. Quieres ir presencial al consultorio. "
            "Tu mamá falleció hace un mes y no sabes cómo manejarlo. "
            "Comportamiento: coopera sin complicaciones, responde lo que te pregunten."
        ),
    },
    {
        "whatsapp_user_id": "573001110002",
        "display_name": "Andres Torres",
        "persona": (
            "Tienes 40 años, vives en Cali. Tu hijo Santiago de 8 años tiene mucha ansiedad "
            "y no quiere ir al colegio. Quieres llevarlo presencial. "
            "Comportamiento: lo primero que preguntas es cuánto cuesta. No das más datos "
            "hasta que te digan el precio. Insiste si no te lo dicen."
        ),
    },
    # --- 2 Nacionales virtual ---
    {
        "whatsapp_user_id": "573001110003",
        "display_name": "Ana Martinez",
        "persona": (
            "Tienes 28 años, vives en Barranquilla. Prefieres virtual porque no estás en Cali. "
            "Estás en una relación que te hace daño pero no puedes dejarla. "
            "Comportamiento: cuando te den horarios, di que el primero no te sirve. "
            "Si te ofrecen otro, acepta."
        ),
    },
    {
        "whatsapp_user_id": "573001110004",
        "display_name": "Sofia Vargas",
        "persona": (
            "Tienes 36 años, vives en Medellín. Tu hija Valentina de 10 años tiene cambios "
            "de ánimo fuertes desde que te separaste. Quieres que la vea virtual. "
            "Comportamiento: antes de agendar, pregunta qué enfoque usa la doctora "
            "y si tiene experiencia con niños."
        ),
    },
    # --- 3 Extranjeros virtual ---
    {
        "whatsapp_user_id": "573001110005",
        "display_name": "Laura Gomez",
        "persona": (
            "Tienes 35 años, vives en Madrid, España. Te separaste hace poco y la estás "
            "pasando muy mal. Necesitas hablar con alguien, virtual obviamente. "
            "Comportamiento: cuando te digan que pagues por Nequi, pregunta si se puede "
            "pagar con tarjeta o transferencia porque no conoces Nequi."
        ),
    },
    {
        "whatsapp_user_id": "573001110006",
        "display_name": "Felipe Morales",
        "persona": (
            "Tienes 30 años, vives en Lima, Perú. Llevas semanas con ataques de ansiedad. "
            "Comportamiento: en tu primer mensaje da todo de una — tu nombre, que quieres "
            "una cita virtual, que estás en Lima, y tu motivo. Eres directo."
        ),
    },
    {
        "whatsapp_user_id": "573001110007",
        "display_name": "Isabella Chen",
        "persona": (
            "Tienes 33 años, vives en Ciudad de México. Tu pareja y tú tienen muchos problemas "
            "y quieren terapia de pareja (esto NO lo trata la doctora). "
            "Comportamiento: coopera normalmente. Si te dicen que no tratan tu caso, "
            "pregunta si pueden recomendar a alguien."
        ),
    },
]

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
) -> str:
    """Genera el siguiente mensaje del paciente usando Gemini.

    conversation_history: lista de {"role": "patient"|"assistant", "content": "..."}
    """
    client = _get_gemini_client()

    system_instruction = _PATIENT_SYSTEM_INSTRUCTION.format(
        display_name=display_name,
        persona=persona,
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
    for attempt in range(max_retries):
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=GEMINI_MODEL,
                contents=contents,
                config={
                    "system_instruction": system_instruction,
                    "max_output_tokens": 1024,
                    "temperature": 0.9,
                },
            )
            break
        except Exception as exc:
            if "429" in str(exc) and attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                logger.warning("Gemini 429, reintentando en %ds...", wait)
                await asyncio.sleep(wait)
            else:
                raise

    # Log raw response for debugging
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
# Setup: login + phone_number_id
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


async def _get_scheduling_status(
    client: httpx.AsyncClient,
    access_token: str,
    whatsapp_user_id: str,
) -> str | None:
    """Retorna el status del scheduling request mas reciente para este paciente, o None."""
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = await client.get("/v1/scheduling-requests", headers=headers)
    resp.raise_for_status()
    items: list[dict[str, object]] = resp.json().get("items", [])

    for item in items:
        if item.get("whatsapp_user_id") == whatsapp_user_id:
            return typing.cast(str, item.get("status"))
    return None


async def _wait_for_owner_action(
    client: httpx.AsyncClient,
    access_token: str,
    whatsapp_user_id: str,
    tag: str,
    current_status: str,
) -> str:
    """Polling hasta que el status cambie de current_status. Retorna el nuevo status."""
    elapsed = 0.0

    while True:
        status = await _get_scheduling_status(client, access_token, whatsapp_user_id)
        if status is not None and status != current_status:
            logger.info("[%s] Status cambio a %s tras %.0fs", tag, status, elapsed)
            return status

        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        if int(elapsed) % 30 == 0:
            logger.info("[%s] Esperando accion del owner... (%.0fs)", tag, elapsed)


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
                # Owner actuo -> esperar mensajes nuevos del AI
                if conversation_id is not None:
                    await _sync_new_assistant_messages(
                        client,
                        access_token,
                        conversation_id,
                        local_history,
                        tag,
                        "Post-owner",
                        max_wait=60.0,
                    )
            # Continuar al siguiente turno para que el paciente responda al nuevo mensaje
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
                max_wait=60.0,
            )
            if not got_response:
                raise RuntimeError(f"AI no respondio tras 60s en turno {turn}")

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
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    all_patients = PATIENTS
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
                        "[Patient-%02d: %s] FALLO: %s",
                        index + 1,
                        patient["display_name"],
                        exc,
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
    asyncio.run(main())
