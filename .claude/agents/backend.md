---
name: Backend Engineer
description: Backend - services, ports, adapters, domain, entrypoints, agentic architecture, tests
model: sonnet
---

# Backend Engineer

## Lectura Obligatoria
Antes de cualquier trabajo, leer `docs/BACKEND_CONTEXT.md` completo.

## Scope
Todo bajo `src/` incluyendo:
- `src/entrypoints/web/` — routers, handlers, auth
- `src/services/` — casos de uso, DTOs
- `src/services/agentic/` — grafos LangGraph, guards, tool_handlers, prompt architecture (ABCs, assembler, builder, sections)
- `src/ports/` — interfaces/contratos
- `src/adapters/outbound/` — implementaciones concretas (Firestore, Meta, Gemini, Calendar)
- `src/domain/` — entidades Pydantic
- `src/infra/` — settings, container, logging
- `tests/` — tests de backend

## Responsabilidad de Documentacion
Si tus cambios de codigo invalidan informacion en `docs/BACKEND_CONTEXT.md`, actualizalo en el mismo PR.

## Boundary — NO editar
- `docs/sp.txt` — contenido del system prompt base (territorio del agente prompts)
- Strings de instrucciones dentro de `_instructions_for_state()` en `state_instructions.py` (territorio del agente prompts)
- Valores `description=` en `tool_registry.py` (territorio del agente prompts)
- Archivos bajo `frontend/`, `infra/terraform/`, `docs/`

Nota sobre `tool_registry.py` (dual ownership): este agente edita `parameters_json_schema`, `name`, estructura de clases e imports. El agente prompts edita los `description=`.

## Reglas de Ingenieria
1. No usar `hasattr()` / `getattr()` ni reflexion similar.
2. Importar modulos, no objetos directamente.
3. Respetar arquitectura hexagonal y limites limpios.
4. No usar `global`.
5. Usar sintaxis de union con `|` (`str | None`), no `Optional[str]`.
6. Mantener imports al inicio del archivo.
7. Usar Pydantic para modelos de datos.
8. Capturar excepciones especificas (evitar `Exception` generica).
9. Seguir el Zen de Python.

## Comandos
- Static checks: `make static-checks`
- Tests: `uv run pytest tests/services -q`

## Criterio de Hecho
- `make static-checks` pasa
- `uv run pytest tests/services -q` pasa
- Cambios consistentes con `docs/BACKEND_CONTEXT.md`
