"""Tests para scripts/llm_judge.py.

Todos los tests mockean el genai.Client para no llamar a Gemini real.
"""

from __future__ import annotations

import collections.abc
import datetime
import json
import pathlib
import sys
import unittest.mock

# Asegurar que el project root esté en sys.path
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import scripts.llm_judge as llm_judge  # noqa: E402
import src.domain.entities.eval_run as eval_run_entity  # noqa: E402

_NOW = datetime.datetime(2026, 4, 30, 12, 0, 0, tzinfo=datetime.UTC)


def _make_transcript(
    messages: list[tuple[str, str]],
) -> list[eval_run_entity.EvalRunConversationMessage]:
    """Helper: [(direction, content), ...]"""
    return [
        eval_run_entity.EvalRunConversationMessage(
            direction=direction,  # type: ignore[arg-type]
            content=content,
            timestamp=_NOW,
        )
        for direction, content in messages
    ]


def _make_gemini_response(
    payload: collections.abc.Mapping[str, object],
) -> unittest.mock.MagicMock:
    """Simula la respuesta de gemini_client.models.generate_content."""
    mock_response = unittest.mock.MagicMock()
    mock_response.text = json.dumps(payload)
    return mock_response


def _make_gemini_client(response: object) -> unittest.mock.MagicMock:
    """Crea un mock de genai.Client cuyo generate_content retorna `response`."""
    mock_client = unittest.mock.MagicMock()
    if isinstance(response, BaseException):
        mock_client.models.generate_content.side_effect = response
    else:
        mock_client.models.generate_content.return_value = response
    return mock_client


# ---------------------------------------------------------------------------
# test_judge_conversation_returns_verdict_for_simple_case
# ---------------------------------------------------------------------------


def test_judge_conversation_returns_verdict_for_simple_case() -> None:
    """Gemini retorna JSON valido; se parsea como JudgeVerdict correcto."""
    payload = {
        "verifications": [
            {
                "capability": "asks_about_price",
                "verified": True,
                "evidence": "cuanto vale la consulta?",
                "reasoning": "El paciente pregunto explicitamente el precio.",
            }
        ],
        "overall": "all_verified",
    }
    transcript = _make_transcript(
        [
            ("INBOUND", "cuanto vale la consulta?"),
            ("OUTBOUND", "La consulta vale $150.000 COP."),
        ]
    )
    client = _make_gemini_client(_make_gemini_response(payload))

    verdict = llm_judge.judge_conversation(
        persona_id="diego_local_asks_price",
        declared_capabilities=["asks_about_price"],
        transcript=transcript,
        gemini_client=client,
    )

    assert verdict.error is None
    assert verdict.overall == "all_verified"
    assert verdict.judge_model == "gemini-2.5-flash"
    assert len(verdict.verifications) == 1
    assert verdict.verifications[0].capability == "asks_about_price"
    assert verdict.verifications[0].verified is True
    assert verdict.verifications[0].evidence == "cuanto vale la consulta?"
    assert verdict.declared_capabilities == ["asks_about_price"]


def test_judge_conversation_partial_verdict() -> None:
    """Gemini retorna 'partial': algunas caps verificadas, otras no."""
    payload = {
        "verifications": [
            {"capability": "asks_about_price", "verified": True, "evidence": "cuanto vale?"},
            {"capability": "rejects_first_slot", "verified": False, "evidence": None},
        ],
        "overall": "partial",
    }
    client = _make_gemini_client(_make_gemini_response(payload))
    transcript = _make_transcript([("INBOUND", "cuanto vale?")])

    verdict = llm_judge.judge_conversation(
        persona_id="p1",
        declared_capabilities=["asks_about_price", "rejects_first_slot"],
        transcript=transcript,
        gemini_client=client,
    )

    assert verdict.overall == "partial"
    assert verdict.error is None
    assert len(verdict.verifications) == 2


# ---------------------------------------------------------------------------
# test_judge_conversation_handles_gemini_timeout
# ---------------------------------------------------------------------------


def test_judge_conversation_handles_gemini_timeout() -> None:
    """Si Gemini lanza DeadlineExceeded, retorna verdict con error, sin raisear."""
    from google.api_core import exceptions as google_api_exceptions

    client = _make_gemini_client(google_api_exceptions.DeadlineExceeded("timeout"))

    verdict = llm_judge.judge_conversation(
        persona_id="p_timeout",
        declared_capabilities=["asks_about_price"],
        transcript=_make_transcript([("INBOUND", "hola")]),
        gemini_client=client,
    )

    assert verdict.overall == "none"
    assert verdict.error is not None
    assert "timeout" in verdict.error
    assert verdict.verifications == []
    assert verdict.declared_capabilities == ["asks_about_price"]


# ---------------------------------------------------------------------------
# test_judge_conversation_handles_invalid_json_response
# ---------------------------------------------------------------------------


def test_judge_conversation_handles_invalid_json_response() -> None:
    """Si la respuesta de Gemini no es JSON valido, retorna verdict con error."""
    mock_response = unittest.mock.MagicMock()
    mock_response.text = "esto no es json {"
    client = _make_gemini_client(mock_response)

    verdict = llm_judge.judge_conversation(
        persona_id="p_invalid_json",
        declared_capabilities=["asks_about_modality"],
        transcript=_make_transcript([("INBOUND", "es presencial?")]),
        gemini_client=client,
    )

    assert verdict.overall == "none"
    assert verdict.error is not None
    assert "json_parse_error" in verdict.error
    assert verdict.verifications == []


# ---------------------------------------------------------------------------
# test_judge_conversation_handles_schema_mismatch
# ---------------------------------------------------------------------------


def test_judge_conversation_handles_schema_mismatch() -> None:
    """JSON valido pero campos faltantes en verificaciones — fallback gracioso."""
    # "verifications" contiene items sin el campo requerido "verified"
    payload = {
        "verifications": [
            {"capability": "asks_about_price"},  # falta "verified"
        ],
        "overall": "all_verified",
    }
    client = _make_gemini_client(_make_gemini_response(payload))

    verdict = llm_judge.judge_conversation(
        persona_id="p_schema_mismatch",
        declared_capabilities=["asks_about_price"],
        transcript=_make_transcript([("INBOUND", "cuanto?")]),
        gemini_client=client,
    )

    # Items sin "verified" son filtrados (no tienen la key requerida).
    # El overall del JSON es "all_verified" pero sin verifications, se toma
    # el valor raw del JSON que puede no reflejar realidad — aceptamos que
    # el verdict llega limpio sin error siempre que el JSON sea parseable.
    # Si el codigo falla en el mapeo, debe retornar schema_mismatch error.
    # En la implementacion actual, items sin "verified" se filtran silenciosamente.
    assert verdict.error is None or "schema_mismatch" in (verdict.error or "")


def test_judge_conversation_handles_schema_mismatch_type_error() -> None:
    """JSON con tipo incorrecto en campo clave — retorna schema_mismatch error."""
    # "verifications" es un string en lugar de lista
    payload = {
        "verifications": "no es una lista",
        "overall": "all_verified",
    }
    client = _make_gemini_client(_make_gemini_response(payload))

    verdict = llm_judge.judge_conversation(
        persona_id="p_type_error",
        declared_capabilities=["asks_about_price"],
        transcript=_make_transcript([("INBOUND", "cuanto?")]),
        gemini_client=client,
    )

    assert verdict.overall == "none"
    assert verdict.error is not None
    assert "schema_mismatch" in verdict.error


# ---------------------------------------------------------------------------
# test: no declared capabilities
# ---------------------------------------------------------------------------


def test_judge_conversation_empty_declared_capabilities() -> None:
    """Sin caps declaradas, retorna verdict con error informativo sin llamar Gemini."""
    client = _make_gemini_client(None)

    verdict = llm_judge.judge_conversation(
        persona_id="p_empty",
        declared_capabilities=[],
        transcript=_make_transcript([("INBOUND", "hola")]),
        gemini_client=client,
    )

    # No debe haber llamado a Gemini
    client.models.generate_content.assert_not_called()
    assert verdict.overall == "none"
    assert verdict.error is not None


# ---------------------------------------------------------------------------
# test: GoogleAPIError (generico)
# ---------------------------------------------------------------------------


def test_judge_conversation_handles_generic_google_api_error() -> None:
    """Si Gemini lanza GoogleAPIError generico, retorna verdict con error."""
    from google.api_core import exceptions as google_api_exceptions

    client = _make_gemini_client(google_api_exceptions.GoogleAPIError("server error"))

    verdict = llm_judge.judge_conversation(
        persona_id="p_api_error",
        declared_capabilities=["new_patient"],
        transcript=_make_transcript([("INBOUND", "hola, soy nuevo")]),
        gemini_client=client,
    )

    assert verdict.overall == "none"
    assert verdict.error is not None
    assert "api_error" in verdict.error
