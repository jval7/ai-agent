"""Single-turn prompt lab for fast iteration on the bot's system prompt.

Loads a shape, builds the COMPLETE system prompt the bot actually receives
(base XML + state instructions + runtime context with the same enabled tools
the runtime would set for the chosen state), then calls Gemini N times in
parallel with one user input (optionally preceded by a conversation history
that simulates earlier turns). Reports pattern hits + sample replies.

Use this to iterate on the prompt without the deploy + eval cycle.

Usage:
  GOOGLE_APPLICATION_CREDENTIALS=/path/to/adc.json \\
  GOOGLE_CLOUD_PROJECT=ai-agent-calendar-dev \\
  PYTHONPATH=. uv run python scripts/prompt_lab.py \\
      --shape shape_minimal \\
      --input "Cuanto vale la consulta?" \\
      --n 10

  # With conversation history (simulates a multi-turn flow):
  PYTHONPATH=. uv run python scripts/prompt_lab.py \\
      --shape shape_minimal \\
      --history '[
        {"role":"user","content":"Hola"},
        {"role":"model","content":"Soy Asistente. Tenemos Consulta inicial. Tu nombre?"}
      ]' \\
      --input "Soy Ana. Si, agendo esa cita."

Args:
  --shape NAME        : tests/fixtures/profiles/<NAME>.json (e.g. shape_minimal)
  --input "TEXT"      : last user message (latest INBOUND)
  --history JSON      : prior turns as JSON list of {"role":"user|model","content":...}
  --state STATE       : runtime state (default NO_ACTIVE_REQUEST)
  --n N               : how many Gemini calls (default 10)
  --pattern REGEX     : regex to count hits in responses (default \\bpresencial\\b)
  --temperature F     : Gemini temperature (default 0.3)
  --model NAME        : Gemini model (default gemini-3-flash-preview)
  --show              : print each reply (default: only first 3)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import pathlib
import re

from google import genai

import scripts.coverage as coverage_module
import src.services.agentic.prompt_builder as prompt_builder_module
import src.services.agentic.prompts.professional_profile_xml_renderer as xml_renderer
import src.services.agentic.runtime_context_resolver as resolver_module
import src.services.agentic.state_models as agentic_state_models

_PROFILES_DIR = pathlib.Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "profiles"
_GEMINI_MODEL = "gemini-3-flash-preview"
_GEMINI_LOCATION = "global"


def _build_system_prompt(shape: coverage_module.Shape, state: str) -> str:
    base = xml_renderer.render_system_prompt_xml(shape.agent_profile)
    builder = prompt_builder_module.RuntimePromptBuilder()
    runtime_ctx = agentic_state_models.RuntimePromptContext(
        state=state,  # type: ignore[arg-type]
        enabled_tool_names=resolver_module.enabled_tools_for_state(state),
    )
    runtime_prompt = builder.build_runtime_system_prompt(
        runtime_ctx,
        known_patient=None,
        agent_profile=shape.agent_profile,
    )
    return builder.compose_base_and_runtime_system_prompt(base, runtime_prompt)


def _build_contents(
    history: list[dict[str, str]] | None,
    user_input: str,
) -> list[genai.types.Content]:
    """Build the Gemini contents list: history (alternating user/model) + final user turn."""
    contents: list[genai.types.Content] = []
    for turn in history or []:
        role = turn["role"]
        if role not in ("user", "model"):
            raise ValueError(f"history role must be 'user' or 'model', got {role!r}")
        contents.append(
            genai.types.Content(role=role, parts=[genai.types.Part(text=turn["content"])])
        )
    contents.append(genai.types.Content(role="user", parts=[genai.types.Part(text=user_input)]))
    return contents


async def _ask_gemini(
    client: genai.Client,
    model: str,
    system_prompt: str,
    contents: list[genai.types.Content],
    temperature: float,
) -> str:
    def _sync_call() -> str:
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
            ),
        )
        return response.text or ""

    return await asyncio.to_thread(_sync_call)


async def _run(args: argparse.Namespace) -> int:
    shape_path = _PROFILES_DIR / f"{args.shape}.json"
    if not shape_path.exists():
        available = sorted(p.stem for p in _PROFILES_DIR.glob("*.json"))
        print(f"Shape not found: {args.shape}\nAvailable: {', '.join(available)}")
        return 1

    history: list[dict[str, str]] | None = None
    if args.history:
        try:
            history = json.loads(args.history)
        except json.JSONDecodeError as exc:
            print(f"--history is not valid JSON: {exc}")
            return 1

    shape = coverage_module.load_shape(shape_path)
    system_prompt = _build_system_prompt(shape, args.state)
    contents = _build_contents(history, args.input)
    pattern = re.compile(args.pattern, re.IGNORECASE)

    print("=" * 70)
    print(f"Shape:    {args.shape}")
    print(f"State:    {args.state}")
    print(f"Tools:    {resolver_module.enabled_tools_for_state(args.state)}")
    print(f"History:  {len(history or [])} turns")
    print(f"Input:    {args.input!r}")
    print(f"N:        {args.n}")
    print(f"Pattern:  {args.pattern!r}")
    print(f"Model:    {args.model}")
    print(f"Temp:     {args.temperature}")
    print(f"Prompt:   {len(system_prompt)} chars")
    print("=" * 70)

    project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("VERTEXAI_PROJECT")
    if not project:
        print("Set GOOGLE_CLOUD_PROJECT (e.g. ai-agent-calendar-dev)")
        return 1
    client = genai.Client(vertexai=True, location=_GEMINI_LOCATION, project=project)
    tasks = [
        _ask_gemini(client, args.model, system_prompt, contents, args.temperature)
        for _ in range(args.n)
    ]
    replies = await asyncio.gather(*tasks)

    hits = [r for r in replies if pattern.search(r)]
    rate = len(hits) / len(replies) * 100

    print(f"\nPattern hit rate: {len(hits)}/{len(replies)} = {rate:.0f}%")
    print()

    samples = replies if args.show else replies[:3]
    label = "all" if args.show else "first 3"
    print(f"--- {label} replies ---")
    for i, r in enumerate(samples, start=1):
        marker = "[HIT]" if pattern.search(r) else "[ok ]"
        print(f"\n{marker} [{i}]\n{r}")

    return 0 if rate < 10 else 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--shape", default="shape_minimal", help="shape name (default: shape_minimal)"
    )
    parser.add_argument("--input", default="Cuanto vale la consulta?", help="user message")
    parser.add_argument(
        "--history",
        default=None,
        help='prior turns JSON: \'[{"role":"user","content":"..."},{"role":"model","content":"..."}]\'',
    )
    parser.add_argument("--state", default="NO_ACTIVE_REQUEST", help="runtime state")
    parser.add_argument("--n", type=int, default=10, help="how many calls")
    parser.add_argument(
        "--pattern",
        default=r"\bpresencial\b",
        help="regex to count hits (default: \\bpresencial\\b)",
    )
    parser.add_argument(
        "--temperature", type=float, default=0.3, help="Gemini temperature (default 0.3)"
    )
    parser.add_argument(
        "--model", default=_GEMINI_MODEL, help=f"Gemini model (default {_GEMINI_MODEL})"
    )
    parser.add_argument("--show", action="store_true", help="print all replies")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    raise SystemExit(asyncio.run(_run(args)))
