# Next Steps Plan

## 1. Validar flujo E2E real en local
- Levantar backend: `uv run uvicorn src.entrypoints.web.main:app --reload`
- Exponer con `ngrok` o `cloudflared`
- Usar Meta Embedded Signup + webhook real
- Verificar que llegan mensajes y que aparecen en:
  - `GET /v1/conversations`
  - `GET /v1/conversations/{id}/messages`

## 2. Automatizar callback OAuth
- Estado actual: se completa signup con `POST /v1/whatsapp/embedded-signup/complete`
- Próxima mejora: crear `GET /oauth/meta/callback` para no copiar `code/state` manualmente

## 3. Cerrar seguridad mínima antes de exponer
- Validar firma de webhook (`X-Hub-Signature-256`)
- Desactivar `GET /v1/whatsapp/dev/verify-token` fuera de dev con flag de entorno (`ENABLE_DEV_ENDPOINTS`)

## 4. Preparar despliegue
- Mover `MEMORY_JSON_FILE_PATH` a un volumen persistente
- Configurar secretos reales: `JWT_SECRET`, `META_*`, `ANTHROPIC_API_KEY`
