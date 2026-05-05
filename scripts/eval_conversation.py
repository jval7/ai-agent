"""
Pipeline de evaluacion (LLM as a Judge): descarga la ultima subsession
de una conversacion desde Firestore y la evalua con Gemini.

Requiere:
    - ADC configurado (gcloud auth application-default login)
    - Credenciales en .secrets/make_credentials.env

Uso:
    uv run python scripts/eval_conversation.py <conversation_id>
"""

from __future__ import annotations

import argparse
import base64
import datetime
import json
import logging
import os
import pathlib
import sys

_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import google.cloud.firestore as google_cloud_firestore  # noqa: E402
import httpx  # noqa: E402
from google import genai  # noqa: E402

import src.domain.entities.conversation as conversation_entity  # noqa: E402
import src.domain.entities.message as message_entity  # noqa: E402

# ---------------------------------------------------------------------------
# Cargar .secrets/
# ---------------------------------------------------------------------------
_SECRETS_DIR = pathlib.Path(__file__).resolve().parent.parent / ".secrets"
_EVAL_RESULTS_DIR = pathlib.Path(__file__).resolve().parent / "eval_results"


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

GEMINI_MODEL = "gemini-3-flash-preview"
GEMINI_LOCATION = "global"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("eval")

# ---------------------------------------------------------------------------
# Rubric de evaluacion
# ---------------------------------------------------------------------------
EVALUATION_SYSTEM_PROMPT = """\
Eres un evaluador experto de conversaciones de un bot de WhatsApp para un \
consultorio de psicologia. Recibirás el transcript de una conversacion entre \
un paciente y el bot de agendamiento.

Evalúa SOLO el desempeño del BOT (no del paciente) en estas 6 dimensiones. \
Cada dimension se califica de 1 a 5:

1. **tono_y_empatia** (1-5): ¿El tono es profesional, calido y empatico? \
¿Transmite comprension y respeto? Un 1 es robotico/frio, un 5 es \
perfectamente empatico y humano.

2. **formato_whatsapp** (1-5): ¿Usa formato de WhatsApp correctamente? \
Mensajes cortos y estructurados, *negritas* para enfasis, bullet points (•) \
para listas. Un 1 usa parrafos largos sin formato, un 5 es formato WhatsApp perfecto.

3. **coherencia_del_flujo** (1-5): ¿La conversacion progresa logicamente \
hacia el agendamiento? No se repite, no salta pasos, no va en circulos. \
Un 1 es caotico, un 5 es flujo impecable.

4. **eficiencia_recoleccion_datos** (1-5): ¿El bot reutiliza datos ya \
proporcionados? ¿Pide los campos faltantes (nombre, email, telefono, edad) \
en UN solo mensaje? ¿No re-pregunta lo ya respondido? Un 1 re-pregunta todo, \
un 5 es perfectamente eficiente.

5. **precision_informacion** (1-5): ¿La informacion proporcionada es correcta? \
Modalidades (presencial en Cali, virtual), metodo de pago (solo Nequi), \
no inventa detalles. Un 1 da informacion falsa, un 5 es 100% preciso.

6. **calidad_general** (1-5): Evaluacion holistica. ¿La conversacion fue \
natural, eficiente y util? ¿Un paciente real estaria satisfecho? Un 1 es \
inaceptable, un 5 es excelente.

Responde EXCLUSIVAMENTE en JSON con esta estructura exacta:
{
  "dimensiones": {
    "tono_y_empatia": {"score": <1-5>, "aprobado": <true/false>, "razon": "<max 2 oraciones>"},
    "formato_whatsapp": {"score": <1-5>, "aprobado": <true/false>, "razon": "<max 2 oraciones>"},
    "coherencia_del_flujo": {"score": <1-5>, "aprobado": <true/false>, "razon": "<max 2 oraciones>"},
    "eficiencia_recoleccion_datos": {"score": <1-5>, "aprobado": <true/false>, "razon": "<max 2 oraciones>"},
    "precision_informacion": {"score": <1-5>, "aprobado": <true/false>, "razon": "<max 2 oraciones>"},
    "calidad_general": {"score": <1-5>, "aprobado": <true/false>, "razon": "<max 2 oraciones>"}
  },
  "score_general": <float promedio de los 6 scores>,
  "aprobado_general": <true si todos los scores >= 3>,
  "resumen": "<2-3 oraciones de evaluacion general>",
  "fortalezas": ["<fortaleza 1>", "<fortaleza 2>"],
  "mejoras": ["<area de mejora 1>", "<area de mejora 2>"]
}

Criterio de aprobado por dimension: score >= 3.
"""

# ---------------------------------------------------------------------------
# Dimension labels para display
# ---------------------------------------------------------------------------
_DIMENSION_LABELS: dict[str, str] = {
    "tono_y_empatia": "Tono y empatia",
    "formato_whatsapp": "Formato WhatsApp",
    "coherencia_del_flujo": "Coherencia del flujo",
    "eficiencia_recoleccion_datos": "Eficiencia recoleccion datos",
    "precision_informacion": "Precision informacion",
    "calidad_general": "Calidad general",
}


# ---------------------------------------------------------------------------
# Login + tenant_id extraction
# ---------------------------------------------------------------------------
def _login_and_get_tenant_id() -> str:
    """Login via API y extrae tenant_id del JWT."""
    with httpx.Client(base_url=API_BASE, timeout=30.0) as client:
        resp = client.post(
            "/v1/auth/login",
            json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
        )
        resp.raise_for_status()
        access_token: str = resp.json()["access_token"]

    # Decode JWT payload (sin verificar firma — es dev tool)
    payload_b64 = access_token.split(".")[1]
    payload_b64 += "=" * (4 - len(payload_b64) % 4)
    claims = json.loads(base64.urlsafe_b64decode(payload_b64))
    tenant_id: str = claims["tenant_id"]
    logger.info("tenant_id: %s", tenant_id)
    return tenant_id


# ---------------------------------------------------------------------------
# Firestore: leer subsession messages
# ---------------------------------------------------------------------------
def _fetch_subsession_messages(
    tenant_id: str,
    conversation_id: str,
) -> list[conversation_entity.ConversationSubsession]:
    """Lee la conversacion de Firestore y retorna la lista de subsessions."""
    db = google_cloud_firestore.Client()
    doc_ref = db.document(f"tenants/{tenant_id}/conversations/{conversation_id}")
    snapshot = doc_ref.get()

    if not snapshot.exists:
        logger.error("Conversacion no encontrada: %s", conversation_id)
        sys.exit(1)

    raw_data = snapshot.to_dict()
    if raw_data is None:
        logger.error("Documento vacio: %s", conversation_id)
        sys.exit(1)

    conversation = conversation_entity.Conversation.model_validate(raw_data)

    if not conversation.subsessions:
        logger.error(
            "La conversacion %s no tiene subsessions. "
            "Solo se evaluan conversaciones con booking completado.",
            conversation_id,
        )
        sys.exit(1)

    return conversation.subsessions


# ---------------------------------------------------------------------------
# Formatear transcript
# ---------------------------------------------------------------------------
def _format_transcript(
    messages: list[message_entity.Message],
) -> str:
    """Formatea mensajes como transcript legible."""
    lines: list[str] = []
    for msg in sorted(messages, key=lambda m: m.created_at):
        timestamp = msg.created_at.strftime("%H:%M:%S")
        if msg.direction == "INBOUND":
            speaker = "PACIENTE"
        elif msg.role == "human_agent":
            speaker = "PROFESIONAL"
        elif msg.role == "system":
            speaker = "SISTEMA"
        else:
            speaker = "BOT"
        lines.append(f"[{timestamp}] {speaker}: {msg.content}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Evaluar con Gemini
# ---------------------------------------------------------------------------
def _evaluate_with_gemini(transcript: str) -> dict[str, object]:
    """Llama a Gemini como juez y retorna el resultado parseado."""
    client = genai.Client(vertexai=True, location=GEMINI_LOCATION)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[{"role": "user", "parts": [{"text": transcript}]}],
        config={
            "system_instruction": EVALUATION_SYSTEM_PROMPT,
            "response_mime_type": "application/json",
            "temperature": 0.2,
        },
    )

    raw_text: str = response.candidates[0].content.parts[0].text.strip()
    result: dict[str, object] = json.loads(raw_text)
    return result


# ---------------------------------------------------------------------------
# Imprimir resultados por consola
# ---------------------------------------------------------------------------
def _print_results(
    conversation_id: str,
    result: dict[str, object],
    num_messages: int,
) -> None:
    dimensiones = result.get("dimensiones", {})
    score_general = result.get("score_general", 0.0)
    aprobado = result.get("aprobado_general", False)
    verdict = "APROBADO" if aprobado else "REPROBADO"

    print()
    print("=" * 60)
    print("  REPORTE DE EVALUACION")
    print("=" * 60)
    print(f"  Conversation ID : {conversation_id}")
    print(f"  Mensajes        : {num_messages}")
    print(f"  Score General   : {score_general}/5.0")
    print(f"  Resultado       : {verdict}")
    print("-" * 60)

    if isinstance(dimensiones, dict):
        for key, label in _DIMENSION_LABELS.items():
            dim = dimensiones.get(key, {})
            if isinstance(dim, dict):
                score = dim.get("score", "?")
                passed = "OK" if dim.get("aprobado") else "FALLO"
                reason = dim.get("razon", "")
                print(f"  {label:<32} {score}/5  {passed:<6}  {reason}")

    print("-" * 60)

    fortalezas = result.get("fortalezas", [])
    if isinstance(fortalezas, list) and fortalezas:
        print("  Fortalezas:")
        for f in fortalezas:
            print(f"    - {f}")

    mejoras = result.get("mejoras", [])
    if isinstance(mejoras, list) and mejoras:
        print("  Areas de mejora:")
        for m in mejoras:
            print(f"    - {m}")

    resumen = result.get("resumen", "")
    if resumen:
        print(f"\n  Resumen: {resumen}")

    print("=" * 60)


# ---------------------------------------------------------------------------
# Guardar reporte .md
# ---------------------------------------------------------------------------
def _save_report(
    conversation_id: str,
    result: dict[str, object],
    transcript: str,
    num_messages: int,
) -> pathlib.Path:
    """Guarda el reporte como .md y retorna la ruta."""
    _EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"eval_{conversation_id}_{now_str}.md"
    filepath = _EVAL_RESULTS_DIR / filename

    dimensiones = result.get("dimensiones", {})
    score_general = result.get("score_general", 0.0)
    aprobado = result.get("aprobado_general", False)
    verdict = "APROBADO" if aprobado else "REPROBADO"

    lines: list[str] = [
        "# Reporte de Evaluacion",
        "",
        f"- **Conversation ID**: `{conversation_id}`",
        f"- **Evaluado**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Mensajes**: {num_messages}",
        f"- **Score General**: {score_general}/5.0",
        f"- **Resultado**: {verdict}",
        "",
        "## Scores por Dimension",
        "",
        "| Dimension | Score | Resultado | Razon |",
        "|---|---|---|---|",
    ]

    if isinstance(dimensiones, dict):
        for key, label in _DIMENSION_LABELS.items():
            dim = dimensiones.get(key, {})
            if isinstance(dim, dict):
                score = dim.get("score", "?")
                passed = "OK" if dim.get("aprobado") else "FALLO"
                reason = dim.get("razon", "")
                lines.append(f"| {label} | {score}/5 | {passed} | {reason} |")

    fortalezas = result.get("fortalezas", [])
    if isinstance(fortalezas, list) and fortalezas:
        lines.extend(["", "## Fortalezas", ""])
        for f in fortalezas:
            lines.append(f"- {f}")

    mejoras = result.get("mejoras", [])
    if isinstance(mejoras, list) and mejoras:
        lines.extend(["", "## Areas de Mejora", ""])
        for m in mejoras:
            lines.append(f"- {m}")

    resumen = result.get("resumen", "")
    if resumen:
        lines.extend(["", "## Resumen", "", str(resumen)])

    lines.extend(["", "## Transcript", "", "```", transcript, "```", ""])

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evalua la ultima subsession de una conversacion con LLM as a Judge."
    )
    parser.add_argument("conversation_id", help="ID de la conversacion en Firestore")
    args = parser.parse_args()
    conversation_id: str = args.conversation_id

    logger.info("Evaluando conversacion: %s", conversation_id)

    # 1. Login y obtener tenant_id
    tenant_id = _login_and_get_tenant_id()

    # 2. Leer subsession de Firestore
    subsessions = _fetch_subsession_messages(tenant_id, conversation_id)
    latest_subsession = subsessions[-1]
    messages = latest_subsession.messages
    logger.info(
        "Subsession encontrada: %d mensajes, archivada el %s",
        len(messages),
        latest_subsession.archived_at.strftime("%Y-%m-%d %H:%M"),
    )

    # 3. Formatear transcript
    transcript = _format_transcript(messages)

    # 4. Evaluar con Gemini
    logger.info("Enviando transcript a Gemini para evaluacion...")
    result = _evaluate_with_gemini(transcript)

    # 5. Imprimir resultados
    _print_results(conversation_id, result, len(messages))

    # 6. Guardar reporte
    filepath = _save_report(conversation_id, result, transcript, len(messages))
    logger.info("Reporte guardado en: %s", filepath)


if __name__ == "__main__":
    main()
