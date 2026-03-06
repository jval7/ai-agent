# AI-Agent Contexto (Ligero)

## Propósito
Este archivo es la guía global mínima para trabajar en este repositorio.
Los detalles específicos de backend/frontend viven en archivos de contexto dedicados.

## Archivos Canónicos de Contexto
- Backend (fuente de verdad): `BACKEND_CONTEXT.md`
- Frontend (fuente de verdad): `FRONTEND_PLAN.md`
- Referencia de API: `API_ENDPOINTS.md`
- Despliegue (infra + codigo): `DEPLOYMENT.md`

## Cómo Navegar
- Si la tarea es de backend (arquitectura, casos de uso, providers, persistencia), leer `BACKEND_CONTEXT.md`.
- Si la tarea es de frontend (UI/UX, flujos, cambios visuales), leer `FRONTEND_PLAN.md`.
- Si la tarea es de contratos/endpoints, leer `API_ENDPOINTS.md`.
- Si la tarea es de despliegue (infraestructura o release de codigo), leer `DEPLOYMENT.md`.
- No duplicar reglas o detalles de backend/frontend en este archivo.

## Stack
- Backend: FastAPI + arquitectura hexagonal + Firestore + Gemini (Vertex AI).
- Orquestación agéntica: LangGraph en `src/services/agentic/`.
- Frontend: React + Vite + TypeScript + Tailwind + TanStack Query.
- Infra: GCP (Cloud Run, Artifact Registry, Secret Manager, CDN).

## Estructura de capas (backend)
- `src/entrypoints/web`: capa HTTP (routers, handlers, auth).
- `src/services`: casos de uso y DTOs.
- `src/services/agentic`: grafos LangGraph y engine de orquestación.
- `src/ports`: contratos/interfaces para adapters.
- `src/adapters/outbound`: implementaciones concretas.
- `src/domain`: entidades Pydantic.
- `src/infra`: settings + wiring en `container.py`.
- Flujo de dependencias: `entrypoints -> services -> ports <- adapters`.

## Principios de Trabajo
- Validar supuestos en el código antes de editar.
- Para librerías terceras: inspeccionar implementación primero; si no alcanza, ir a documentación oficial.
- Para entradas de usuario en lenguaje libre (por ejemplo, elección de horarios), priorizar interpretación semántica con LLM en lugar de parseo rígido con strings o números quemados; usar lógica determinística solo para validar la salida estructural.
- Nunca usar `git commit --no-verify`. Si fallan hooks/pre-commit, corregir errores y luego hacer commit o `--amend`.
- Mantener este archivo corto y estable; poner detalles cambiantes en los archivos de contexto dedicados.

## Reglas de Ingeniería Backend
1. No usar `hasattr()` / `getattr()` ni reflexión similar.
2. Importar módulos, no objetos directamente.
3. Respetar arquitectura hexagonal y límites limpios.
4. No usar `global`.
5. Usar sintaxis de unión con `|` (`str | None`), no `Optional[str]`.
6. Mantener imports al inicio del archivo.
7. Usar Pydantic para modelos de datos.
8. Capturar excepciones específicas (evitar `Exception` genérica).
9. Seguir el Zen de Python.

## Comandos útiles
- Setup: `uv sync --group dev && uv run pre-commit install`
- Run API: `uv run uvicorn src.entrypoints.web.main:app --reload`
- Static checks: `make static-checks`
- Tests backend: `uv run pytest tests/services -q`
- Frontend dev: `make fe-dev`
- Frontend checks: `make fe-checks`
- All checks: `make checks`
- Deploy backend: `make deploy-back`
- Deploy frontend: `make deploy-front`
- Deploy todo: `make deploy-all`

## Criterio de Hecho (Por Defecto)
- El código respeta reglas del contexto específico consultado (backend o frontend).
- Pasan checks relevantes (`make static-checks` y tests objetivo).
- Los cambios son consistentes con el archivo de contexto fuente de verdad correspondiente.
