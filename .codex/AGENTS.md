# AI-Agent Contexto (Ligero)

## Propósito
Este archivo es la guía global mínima para trabajar en este repositorio.
Los detalles específicos de backend/frontend viven en archivos de contexto dedicados.

## Archivos Canónicos de Contexto
- Backend (fuente de verdad): `/Users/jhonvalderrama/Documents/repos/ai-agent/BACKEND_CONTEXT.md`
- Frontend (fuente de verdad): `/Users/jhonvalderrama/Documents/repos/ai-agent/FRONTEND_PLAN.md`
- Referencia de API: `/Users/jhonvalderrama/Documents/repos/ai-agent/API_ENDPOINTS.md`
- Despliegue (infra + codigo): `/Users/jhonvalderrama/Documents/repos/ai-agent/DEPLOYMENT.md`

## Cómo Navegar
- Si la tarea es de backend (arquitectura, casos de uso, providers, persistencia), leer `BACKEND_CONTEXT.md`.
- Si la tarea es de frontend (UI/UX, flujos, cambios visuales), leer `FRONTEND_PLAN.md`.
- Si la tarea es de contratos/endpoints, leer `API_ENDPOINTS.md`.
- Si la tarea es de despliegue (infraestructura o release de codigo), leer `DEPLOYMENT.md`.
- No duplicar reglas o detalles de backend/frontend en este archivo.

## Principios de Trabajo
- Validar supuestos en el código antes de editar.
- Para librerías terceras: inspeccionar implementación primero; si no alcanza, ir a documentación oficial.
- Para entradas de usuario en lenguaje libre (por ejemplo, elección de horarios), priorizar interpretación semántica con LLM en lugar de parseo rígido con strings o números quemados; usar lógica determinística solo para validar la salida estructural.
- Nunca usar `git commit --no-verify`. Si fallan hooks/pre-commit, corregir errores y luego hacer commit o `--amend`.
- Mantener este archivo corto y estable; poner detalles cambiantes en los archivos de contexto dedicados.

## Criterio de Hecho (Por Defecto)
- El código respeta reglas del contexto específico consultado (backend o frontend).
- Pasan checks relevantes (`make static-checks` y tests objetivo).
- Los cambios son consistentes con el archivo de contexto fuente de verdad correspondiente.
