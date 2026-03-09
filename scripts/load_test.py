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
    uv run python scripts/load_test.py
"""

from __future__ import annotations

import asyncio
import logging
import time
import typing
import uuid

import httpx
from google import genai

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------
API_BASE = "http://localhost:8000"
OWNER_EMAIL = "owner@acme.com"
OWNER_PASSWORD = "supersecret"

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_LOCATION = "us-central1"

POLL_INTERVAL = 3  # segundos entre cada poll de scheduling requests
STAGGER_DELAY = 2  # segundos entre lanzamiento de cada paciente
MAX_TURNS = 20  # maximo de mensajes por paciente (evita loops infinitos)

# ---------------------------------------------------------------------------
# System prompt para el LLM que simula pacientes
# ---------------------------------------------------------------------------
PATIENT_SYSTEM_PROMPT = """\
Eres {display_name}, una persona real que escribe por WhatsApp a un \
consultorio de psicologia para agendar una cita.

Tu perfil:
{persona}

Reglas:
- Escribe como una persona real por WhatsApp: mensajes cortos, informales, en español colombiano.
- No uses emojis en exceso.
- Cuando te presenten opciones de horarios, elige una de manera natural \
(ej: "la primera me sirve", "prefiero la del miercoles", "me quedo con la segunda opcion").
- Cuando te pidan datos personales (nombre, edad, etc.), responde con los datos de tu perfil.
- No menciones que eres una simulacion ni que sigues instrucciones.
- Responde SOLO con el mensaje que enviarias por WhatsApp. Sin comillas, sin prefijos, sin formato extra.
- Si el profesional te confirma la cita, agradece brevemente y despidete.
"""

# ---------------------------------------------------------------------------
# 10 Pacientes (perfiles/personas en vez de mensajes fijos)
# ---------------------------------------------------------------------------
PATIENTS: list[dict[str, str]] = [
    {
        "whatsapp_user_id": "573001110001",
        "display_name": "Maria Lopez",
        "persona": (
            "Mujer, 32 anos. Lleva semanas con mucha ansiedad y no logra dormir bien. "
            "Quiere consulta virtual. Es amable y un poco timida. "
            "Vive en Bogota. Trabaja como contadora."
        ),
    },
    {
        "whatsapp_user_id": "573001110002",
        "display_name": "Carlos Ramirez",
        "persona": (
            "Hombre, 45 anos. Esta pasando por un duelo muy dificil, fallecio su mama "
            "hace un mes. Quiere cita presencial en Cali. Es reservado pero respetuoso. "
            "Trabaja como ingeniero civil."
        ),
    },
    {
        "whatsapp_user_id": "573001110003",
        "display_name": "Ana Martinez",
        "persona": (
            "Mujer, 28 anos. Tiene problemas de dependencia emocional con su pareja "
            "y quiere trabajar eso. Prefiere consulta virtual. Es expresiva y abierta. "
            "Vive en Barranquilla. Es disenadora grafica."
        ),
    },
    {
        "whatsapp_user_id": "573001110004",
        "display_name": "Diego Hernandez",
        "persona": (
            "Hombre, 38 anos. Muy estresado por el trabajo, siente que no puede mas. "
            "Necesita cita presencial en Cali. Es directo y practico. "
            "Es gerente de ventas en una empresa grande."
        ),
    },
    {
        "whatsapp_user_id": "573001110005",
        "display_name": "Laura Gomez",
        "persona": (
            "Mujer, 35 anos. Pasando por un proceso emocional dificil despues de su divorcio. "
            "Quiere consulta virtual. Es reflexiva y un poco melancolica. "
            "Vive en Pereira. Es profesora de colegio."
        ),
    },
    {
        "whatsapp_user_id": "573001110006",
        "display_name": "Andres Torres",
        "persona": (
            "Hombre, 40 anos. Padre preocupado. Su hijo Santiago de 8 anos tiene mucha "
            "ansiedad para ir al colegio y llora todas las mananas. Necesita orientacion. "
            "Quiere cita presencial en Cali. Es protector y atento."
        ),
    },
    {
        "whatsapp_user_id": "573001110007",
        "display_name": "Sofia Vargas",
        "persona": (
            "Mujer, 36 anos. Madre buscando psicologo para su hija Valentina de 10 anos. "
            "La nina tiene problemas emocionales desde que se separaron con el papa. "
            "Quiere consulta virtual. Es organizada y detallista."
        ),
    },
    {
        "whatsapp_user_id": "573001110008",
        "display_name": "Felipe Morales",
        "persona": (
            "Hombre, 30 anos. Tiene ataques de ansiedad frecuentes y le cuesta manejar "
            "sus emociones. Prefiere virtual ya que vive en Medellin. "
            "Es desarrollador de software. Es un poco ansioso al escribir."
        ),
    },
    {
        "whatsapp_user_id": "573001110009",
        "display_name": "Valentina Cruz",
        "persona": (
            "Mujer, 26 anos. Siente que depende mucho emocionalmente de sus relaciones "
            "y quiere aprender a estar bien sola. Quiere cita presencial en Cali. "
            "Es estudiante de derecho. Es curiosa y hace muchas preguntas."
        ),
    },
    {
        "whatsapp_user_id": "573001110010",
        "display_name": "Juan Pablo Rios",
        "persona": (
            "Hombre, 42 anos. Manejando mucho estres y necesita ayuda para procesar "
            "la muerte de su hermano menor. Quiere consulta virtual. "
            "Es comerciante. Es calmado pero se nota el dolor cuando habla del tema."
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

    system_instruction = PATIENT_SYSTEM_PROMPT.format(
        display_name=display_name,
        persona=persona,
    )

    # Mapear historial al formato Gemini:
    #   - mensajes del paciente -> role "model" (lo que Gemini ya "dijo")
    #   - mensajes del assistant -> role "user" (lo que el otro lado dijo)
    contents: list[dict[str, typing.Any]] = []

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
        for msg in conversation_history:
            gemini_role = "model" if msg["role"] == "patient" else "user"
            contents.append(
                {
                    "role": gemini_role,
                    "parts": [{"text": msg["content"]}],
                }
            )

    response = await asyncio.to_thread(
        client.models.generate_content,
        model=GEMINI_MODEL,
        contents=contents,
        config={
            "system_instruction": system_instruction,
            "max_output_tokens": 256,
            "temperature": 0.9,
        },
    )

    text: str = response.candidates[0].content.parts[0].text.strip()
    return text


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
    for msg in resp.json().get("items", []):
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
_TERMINAL_STATUSES = {"BOOKED", "CANCELLED", "REJECTED"}
_WAIT_FOR_OWNER_STATUSES = {"AWAITING_CONSULTATION_REVIEW", "AWAITING_PAYMENT_REVIEW"}


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
# Flujo por paciente (LLM-driven)
# ---------------------------------------------------------------------------
async def _run_patient(
    client: httpx.AsyncClient,
    access_token: str,
    phone_number_id: str,
    patient: dict[str, str],
    index: int,
) -> float:
    tag = f"Patient-{index + 1:02d}: {patient['display_name']}"
    start = time.monotonic()
    conversation_id: str | None = None

    for turn in range(1, MAX_TURNS + 1):
        # --- Obtener historial de conversacion ---
        history: list[dict[str, str]] = []
        if conversation_id is not None:
            history = await _get_messages(client, access_token, conversation_id)

        # --- Generar mensaje del paciente con LLM ---
        logger.info("[%s] Turno %d: Generando mensaje...", tag, turn)
        patient_message = await _generate_patient_message(
            display_name=patient["display_name"],
            persona=patient["persona"],
            conversation_history=history,
        )
        logger.info("[%s] Turno %d: Enviando: %s", tag, turn, patient_message[:80])

        # --- Enviar via webhook ---
        await _send_webhook(client, phone_number_id, patient, patient_message)

        # --- Obtener conversation_id si aun no lo tenemos ---
        if conversation_id is None:
            conversation_id = await _get_conversation_id(
                client, access_token, patient["whatsapp_user_id"]
            )

        # --- Verificar estado del scheduling request ---
        status = await _get_scheduling_status(client, access_token, patient["whatsapp_user_id"])

        if status in _TERMINAL_STATUSES:
            elapsed = time.monotonic() - start
            logger.info("[%s] Finalizado con status %s en %.1fs", tag, status, elapsed)
            return elapsed

        if status in _WAIT_FOR_OWNER_STATUSES:
            logger.info("[%s] Esperando accion del owner (status=%s)...", tag, status)
            new_status = await _wait_for_owner_action(
                client, access_token, patient["whatsapp_user_id"], tag, status
            )
            if new_status in _TERMINAL_STATUSES:
                elapsed = time.monotonic() - start
                logger.info("[%s] Finalizado con status %s en %.1fs", tag, new_status, elapsed)
                return elapsed
            # Owner actuo, el AI respondio con slots u otra cosa -> siguiente turno

    elapsed = time.monotonic() - start
    logger.info("[%s] Alcanzo MAX_TURNS (%d) en %.1fs", tag, MAX_TURNS, elapsed)
    return elapsed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    total_start = time.monotonic()
    logger.info("Iniciando load test con %d pacientes...", len(PATIENTS))

    async with httpx.AsyncClient(base_url=API_BASE, timeout=120.0) as client:
        access_token, phone_number_id = await _setup(client)

        async def _launch_patient(
            patient: dict[str, str], index: int
        ) -> tuple[str, float | Exception]:
            await asyncio.sleep(index * STAGGER_DELAY)
            try:
                elapsed = await _run_patient(client, access_token, phone_number_id, patient, index)
                return patient["display_name"], elapsed
            except Exception as exc:
                logger.error(
                    "[Patient-%02d: %s] FALLO: %s",
                    index + 1,
                    patient["display_name"],
                    exc,
                )
                return patient["display_name"], exc

        tasks = [_launch_patient(patient, i) for i, patient in enumerate(PATIENTS)]
        results = await asyncio.gather(*tasks)

    total_elapsed = time.monotonic() - total_start

    # Resumen
    ok_count = sum(1 for _, r in results if isinstance(r, float))
    fail_count = len(results) - ok_count
    total_min = int(total_elapsed // 60)
    total_sec = int(total_elapsed % 60)

    print()
    print("=" * 50)
    print("  LOAD TEST SUMMARY")
    print("=" * 50)
    print(f"  Total: {len(results)} | OK: {ok_count} | FAIL: {fail_count}")
    print(f"  Tiempo: {total_min}m {total_sec}s")
    print("-" * 50)
    for i, (name, result) in enumerate(results):
        if isinstance(result, float):
            print(f"  [OK]   Patient-{i + 1:02d} ({name})  {result:.1f}s")
        else:
            print(f"  [FAIL] Patient-{i + 1:02d} ({name})  {result}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
