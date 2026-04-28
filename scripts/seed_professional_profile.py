"""Seed the professional profile structured fields for the active tenant.

This is a one-shot migration: given an existing legacy `system_prompt` XML
in Firestore, this script populates the new structured fields (`identity`,
`professional_context`, `services`, `presencial_schedule`, `virtual_schedule`,
`payment_methods`) by hitting `PUT /v1/agent/professional-profile`.

The data is hardcoded from `docs/sp.txt` (the source-of-truth XML for the
single active professional). After running this, the professional will see
the form already filled in when they open Configuraciones → Agente.

The backend will regenerate the `system_prompt` XML from these fields and
overwrite the legacy XML, so the LLM behavior is preserved.

Requires:
    - .secrets/make_credentials.env with OWNER_EMAIL and OWNER_PASSWORD
    - API_BASE env var (defaults to http://localhost:8000)

Usage:
    uv run python scripts/seed_professional_profile.py
    API_BASE=https://prod.example.com uv run python scripts/seed_professional_profile.py

DELETE THIS FILE after running it in the target environment.
"""

from __future__ import annotations

import os
import pathlib
import sys
import typing

import httpx

# ---------------------------------------------------------------------------
# Load .secrets/make_credentials.env
# ---------------------------------------------------------------------------
_SECRETS_DIR = pathlib.Path(__file__).resolve().parent.parent / ".secrets"


def _load_env_file(path: pathlib.Path) -> None:
    """Load KEY=VALUE lines into os.environ (does not overwrite existing vars)."""
    if not path.is_file():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file(_SECRETS_DIR / "make_credentials.env")
_load_env_file(_SECRETS_DIR / "make_api_base.env")

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "")
OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "")


# ---------------------------------------------------------------------------
# Hardcoded payload derived from docs/sp.txt for Aleja Escobar.
# ---------------------------------------------------------------------------
_PAYLOAD: dict[str, object] = {
    "identity": {
        "assistant_name": "Claudia",
        "professional_title": "Psicóloga Aleja Escobar",
        "professional_address_term": "la Doc",
        "main_city": "Cali",
        "tone": (
            "Profesional y cálida, transmite calma y confianza. Concisa para lo "
            "operativo, pero empática y presente cuando el paciente lo necesita. "
            "Español neutro con toque colombiano natural."
        ),
        "languages": ["español"],
    },
    "professional_context": {
        "approach": "Enfoque humanista e integral del bienestar emocional.",
        "common_topics": [
            "ansiedad",
            "estrés",
            "dependencia emocional",
            "duelo",
            "orientación a padres",
            "procesos emocionales",
        ],
        "services_not_offered": ["terapia de pareja", "terapia grupal"],
        "coverage_notes": (
            "Atiende presencial en Cali y consulta en línea para Colombia y exterior."
        ),
    },
    "services": [
        {
            "name": "Consulta Individual Adultos",
            "description": None,
            "audience": "Adultos",
            "modalities": ["PRESENCIAL", "VIRTUAL"],
            "tariffs_local": [
                {
                    "label": "Sesión individual",
                    "amount": 130000,
                    "currency": "COP",
                    "discount_percent": None,
                },
                {
                    "label": "Paquete 3 sesiones",
                    "amount": 370500,
                    "currency": "COP",
                    "discount_percent": 5,
                },
                {
                    "label": "Paquete 4 sesiones",
                    "amount": 478400,
                    "currency": "COP",
                    "discount_percent": 8,
                },
            ],
            "tariffs_foreign": [
                {
                    "label": "Sesión individual",
                    "amount": 90,
                    "currency": "USD",
                    "discount_percent": None,
                },
                {
                    "label": "Paquete 3 sesiones",
                    "amount": 257,
                    "currency": "USD",
                    "discount_percent": 5,
                },
                {
                    "label": "Paquete 4 sesiones",
                    "amount": 332,
                    "currency": "USD",
                    "discount_percent": 8,
                },
            ],
        },
        {
            "name": "Psicología Infantil",
            "description": None,
            "audience": "Niños en edad escolar",
            "modalities": ["PRESENCIAL", "VIRTUAL"],
            "tariffs_local": [
                {
                    "label": "Sesión individual",
                    "amount": 150000,
                    "currency": "COP",
                    "discount_percent": None,
                },
                {
                    "label": "Paquete 3 sesiones",
                    "amount": 427500,
                    "currency": "COP",
                    "discount_percent": 5,
                },
                {
                    "label": "Paquete 4 sesiones",
                    "amount": 552000,
                    "currency": "COP",
                    "discount_percent": 8,
                },
            ],
            "tariffs_foreign": [],
        },
    ],
    "presencial_schedule": [
        {
            "weekday_from": "WED",
            "weekday_to": "FRI",
            "start_time": "08:00",
            "end_time": "16:00",
        },
        {
            "weekday_from": "SAT",
            "weekday_to": None,
            "start_time": "08:00",
            "end_time": "12:00",
        },
    ],
    "virtual_schedule": [
        {
            "weekday_from": "MON",
            "weekday_to": "FRI",
            "start_time": "08:00",
            "end_time": "18:00",
        },
        {
            "weekday_from": "SAT",
            "weekday_to": None,
            "start_time": "08:00",
            "end_time": "12:00",
        },
    ],
    "payment_methods": [
        {
            "currency": "COP",
            "method_name": "Nequi",
            "holder": "Alejandra Escobar",
            "instructions": "318 732 6409",
            "applies_when": "Colombia (COP)",
        },
        {
            "currency": "USD",
            "method_name": "Zelle",
            "holder": "Nelson",
            "instructions": "7867673701",
            "applies_when": "Extranjeros (USD)",
        },
    ],
}


def _login(base_url: str, email: str, password: str) -> str:
    """Login to the backend and return the access token."""
    response = httpx.post(
        f"{base_url}/v1/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    token: str = response.json()["access_token"]
    return token


def _put_professional_profile(base_url: str, token: str, payload: dict[str, object]) -> typing.Any:
    response = httpx.put(
        f"{base_url}/v1/agent/professional-profile",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def main() -> int:
    if not OWNER_EMAIL or not OWNER_PASSWORD:
        print(
            "ERROR: OWNER_EMAIL / OWNER_PASSWORD missing. "
            "Set them via .secrets/make_credentials.env or env vars.",
            file=sys.stderr,
        )
        return 1

    print(f"API_BASE = {API_BASE}")
    print(f"Logging in as {OWNER_EMAIL}...")
    token = _login(API_BASE, OWNER_EMAIL, OWNER_PASSWORD)

    print("Sending professional profile payload...")
    result = _put_professional_profile(API_BASE, token, _PAYLOAD)

    print("Seed completed successfully. Tenant id:", result.get("tenant_id"))
    print("Identity assistant_name:", (result.get("identity") or {}).get("assistant_name"))
    print("Services count:", len(result.get("services") or []))
    print("Payment methods count:", len(result.get("payment_methods") or []))
    print()
    print("Backend regenerated the system_prompt XML from these fields and saved it.")
    print("The professional can now open Configuraciones → Agente and see the form pre-filled.")
    print()
    print("REMEMBER: delete this script after running it in the target environment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
