# Agendachat — Contexto (Ligero)

> **Marca**: Agendachat (público). **Identidad técnica del repo/infra**: `ai-agent` (Cloud Run, buckets, secrets, IAM siguen así para no romper logs/alertas). Este doc usa "Agendachat" en copy y "ai-agent" cuando se refiere a recursos GCP concretos.

## Propósito
Este archivo es la guía global mínima para trabajar en este repositorio.
Los detalles específicos de backend/frontend viven en archivos de contexto dedicados.

## Navegación y Delegación

| Dominio | Agente | Context doc |
|---------|--------|-------------|
| Backend (services, ports, adapters, domain, tests) | `backend` | `docs/BACKEND_CONTEXT.md` |
| Frontend (UI, pages, hooks, React) | `frontend` | `docs/FRONTEND_PLAN.md` |
| Infra (Terraform, Docker, deploys, GCP) | `infra` | `docs/DEPLOYMENT.md` |
| Prompts (sp.txt, instrucciones de estado, reglas de estilo, tool descriptions) | `prompts` | `docs/PROMPTS_CONTEXT.md` |
| Contratos/endpoints (referencia) | — | `docs/API_ENDPOINTS.md` |
| Estado de la infra pausada | — | `docs/HIBERNATION.md` |
| Deuda técnica priorizada | — | `docs/TECH_DEBT.md` |

- Si una tarea cruza límites de dominio, coordinar desde la sesión principal.
- Cada agente lee su context doc antes de actuar.
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
- Siempre correr los tests (`uv run pytest tests/services -q`) después de cualquier cambio de código. Si hay tests rotos, corregirlos antes de hacer commit.
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
- Evaluación del bot: `make eval` (filtro: `make eval SHAPES="shape_minimal"`)
- Deploy backend: `make deploy-back ENV=dev|prod`
- Deploy frontend: `make deploy-front ENV=dev|prod`
- Deploy todo: `make deploy-all ENV=dev|prod`

`ENV` por defecto es `dev` en todos los targets de deploy y de secrets.

## Criterio de Hecho (Por Defecto)
- El código respeta reglas del contexto específico consultado (backend o frontend).
- Pasan checks relevantes (`make static-checks` y tests objetivo).
- Los cambios son consistentes con el archivo de contexto fuente de verdad correspondiente.
