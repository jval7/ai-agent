# Deuda Técnica

## 1. Mensaje de pago hardcodeado en guards (precios acoplados al código)

**Archivo:** `src/services/agentic/guards/helpers.py` → `build_payment_instructions_message()`
**Callers:** `numeric_slot_selection_guard.py`, `waiting_patient_choice_guard.py`

**Problema:**
Cuando el paciente selecciona un horario, el guard genera un mensaje de pago con precios hardcodeados en Python (COP). No considera ubicación del paciente (USD para extranjeros) ni permite que el owner cambie precios sin tocar código. Cada nuevo cliente de la plataforma requeriría modificar este archivo.

**Solución propuesta:**
El guard debe hacer el side effect (seleccionar slot) pero retornar `None` para que el LLM genere el mensaje de pago usando:
- Los precios del `<pricing>` en el system prompt (editable por el owner)
- La ubicación del paciente (`patient_location`) del runtime context
- Las reglas de `<pricing_logic>` del system prompt

Esto requiere:
- Verificar que el estado del scheduling request ya refleja `AWAITING_PAYMENT_CONFIRMATION` cuando el LLM genera
- Agregar un state_instruction para ese estado que le diga al LLM: "Presenta los precios según ubicación y reglas del system prompt"
- Asegurar que el runtime context incluye `patient_location` para la decisión COP/USD
- Puede requerir refactor del flujo LangGraph si el estado no se actualiza antes de la generación

**Impacto:** Medio. Funciona para un solo cliente (Aleja) con precios fijos en COP. Bloquea multi-tenant y precios USD para extranjeros.

---

## 2. Cierre automático de sesiones inactivas

**Problema:**
Después de `BOOKED`, si el paciente no responde al "¿algo más?", la sesión queda abierta indefinidamente. No hay mecanismo para cerrarla automáticamente.

**Solución propuesta:**
Implementar un cronjob (Cloud Scheduler + endpoint) que cierre sesiones en `POST_BOOKING_FOLLOWUP` sin actividad por más de 5 minutos.

**Impacto:** Bajo. Las sesiones se acumulan pero no afectan funcionalidad.

---

## 3. Terraform sobreescribe secret con versión bootstrap

**Problema:**
`make deploy-back` puede crear una versión vacía del secret `AI_AGENT_APP_CONFIG_JSON` via el recurso `google_secret_manager_secret_version.app_config_json_bootstrap`, sobreescribiendo la versión actual con las credenciales reales.

**Solución propuesta:**
Usar `lifecycle { ignore_changes }` en el recurso bootstrap o eliminar el recurso y gestionar el secret solo via `gcloud`.

**Impacto:** Alto cuando ocurre (CORS falla, backend no arranca). Ya ocurrió una vez.
