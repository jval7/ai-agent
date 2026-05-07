# Publish Readiness Checklist

Checklist rapido para salir a produccion sin frenar iteracion.

## P0 Bloqueantes (antes de publicar)

- [ ] **Secretos en produccion**
  - [ ] Mover secretos a Secret Manager (nada sensible en `.env` de prod).
  - [ ] Rotar secretos que hayan estado en repo/maquina local.
- [ ] **Auth y sesiones**
  - [ ] Access token corto.
  - [ ] Refresh token rotado y revocable.
  - [ ] Logout invalida refresh token activo.
- [ ] **Webhook Meta seguro**
  - [ ] Validar `X-Hub-Signature-256`.
  - [ ] Mantener deduplicacion de eventos/mensajes.
  - [ ] Rechazar payloads invalidos y replay.
- [ ] **CORS de produccion**
  - [ ] Permitir solo dominios reales de frontend.
  - [ ] Eliminar localhost y comodines.
- [ ] **Observabilidad y alertas**
  - [ ] Alertas por `5xx` backend.
  - [ ] Alertas por fallos de webhook.
  - [ ] Alertas por fallos LLM (Gemini empty/timeout).
- [ ] **Deploy controlado**
  - [ ] WIF + Terraform state remoto habilitado.
  - [ ] Aprobacion manual para ambiente `prod` en GitHub.

## P1 Backend recomendado

- [ ] Rate limiting en auth y webhook.
- [ ] Smoke test post-deploy (health + flujo minimo).
- [ ] Limpieza/TTL de datos temporales (tokens/eventos expirados).
- [ ] Verificar indices de Firestore para queries criticas.
- [ ] Runbook de rollback (imagen/tag anterior).

## P1 Frontend recomendado

- [ ] Build de produccion y manejo de errores (error boundary/fallback).
- [ ] Guardas de sesion y expiracion de token.
- [ ] Config por ambiente (`API_BASE_URL`) validada.
- [ ] Evitar exponer datos sensibles en cliente.

## P2 Deseable

- [ ] CSP estricta + revisiones XSS.
- [ ] Auditoria de accesos y sesiones.
- [ ] Dashboard de metricas operativas (latencia, tasa error, retries LLM).

## Plan minimo para salir rapido (Top 3)

- [ ] **1. Secretos + rotacion**
- [ ] **2. Webhook seguro + auth endurecida**
- [ ] **3. Alertas + smoke test post deploy**

## Tracking rapido

- Owner:
- Fecha objetivo:
- Ambiente objetivo:
- Riesgo residual aceptado:
