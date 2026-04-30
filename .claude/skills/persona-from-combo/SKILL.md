---
name: persona-from-combo
description: Genera una persona simulada para cubrir un combo de capabilities no cubierto en algun shape de tests/fixtures/profiles/. Usalo cuando el usuario pida "agregar una persona para shape X", "cubrir el combo Y", "poblar el pool de personas" o similar; o cuando el usuario mencione `/persona-from-combo`. El skill valida combos contradictorios, asigna IDs/whatsapp_user_id sin colision, redacta persona_text hibrido (template + narrativa LLM) y modifica scripts/personas.py via Edit con confirmacion previa.
---

# /persona-from-combo

## Que hace

Genera una nueva `Persona` para `scripts/personas.py` que cubre algun combo de `required_combos` declarado en un shape (`tests/fixtures/profiles/*.json`) y que ningun persona del pool actual cubre todavia.

Es un acelerador de redacción para que cada persona del pool exista porque algun combo concreto la justifica, en lugar de escribirse a mano sin coverage explicito.

## Argumento

```
/persona-from-combo <shape_name> [<combo_index>]
```

- `<shape_name>`: el `metadata.name` del shape (ej. `shape_multicurrency`).
- `<combo_index>` (opcional): indice 0-based dentro de `required_combos`. Default: el primer combo no cubierto.

Si el usuario invoca sin shape_name, pedi cual quiere cubrir y mostrale los shapes disponibles con sus combos no cubiertos.

## Workflow

### 1. Cargar contexto

Usa la herramienta Read para leer estos archivos en paralelo:

- `scripts/personas.py` — extraer:
  - `CAPABILITY_VOCABULARY` (tags validos)
  - IDs ya usados (campo `id` de cada Persona)
  - `whatsapp_user_id` ya usados
  - Lista a la que vas a agregar (PSICOLOGA_PERSONAS o ORTODONCIA_PERSONAS)
- `tests/fixtures/profiles/<shape_name>.json` — extraer:
  - `metadata.required_combos`
  - `metadata.description` (contexto del shape)

### 2. Detectar combos no cubiertos

Calcula mentalmente la operacion de `coverage.detect_uncovered_combos`:

```
Para cada combo en metadata.required_combos:
    Si NINGUNA persona del pool tiene TODOS los caps del combo (subset),
    el combo esta uncovered.
```

Si **todos** los combos del shape ya estan cubiertos, decile al usuario y termina sin generar nada.

### 3. Elegir el combo a cubrir

- Si el usuario paso `<combo_index>`, usa ese combo (validar que sea uncovered).
- Si no, toma el primer combo uncovered (el orden de `required_combos` es la fuente de verdad).

### 4. Validar el combo

Caps deben estar en `CAPABILITY_VOCABULARY` (esto ya lo garantiza Pydantic al cargar el shape, pero re-chequea por las dudas).

**Pares contradictorios — abortar si el combo declara dos del mismo par**:

| Cap A | Cap B | Por que excluyente |
|---|---|---|
| `accepts_first_slot` | `rejects_first_slot` | Decision binaria opuesta |
| `gives_minimal_info` | `gives_all_info_upfront` | Estilos opuestos |
| `local_patient` | `foreign_patient` | Misma persona no es ambos |
| `new_patient` | `returning_patient` | Cohort excluyente |

Si detectas contradiccion, NO generes la persona — reporta el conflicto y termina.

### 5. Decidir profile_group (PSICOLOGA o ORTODONCIA)

Los shapes son profession-agnosticos, asi que el dev debe decidir donde va la persona.

Si el usuario lo paso explicitamente, usalo. Sino, pregunta:

> El shape `<name>` no especifica especialidad. ¿La persona la agrego a PSICOLOGA_PERSONAS o ORTODONCIA_PERSONAS?

Default razonable si no responde: `PSICOLOGA_PERSONAS` (es el rango con mas personas existentes en proyectos historicos).

### 6. Generar identidad

**`whatsapp_user_id`**: siguiente libre en el rango del profile.

| Profile | Rango | Formato |
|---|---|---|
| Psicologia | `573001110001`–`573001110099` | Incrementar el ultimo libre |
| Ortodoncia | `573002220001`–`573002220099` | Incrementar el ultimo libre |

Si la lista esta vacia, empiezan en `xxx0001`.

**`id`**: snake_case derivado del cap mas distintivo del combo. Patron:

```
<nombre_corto>_<cap_distintivo>
```

Ejemplos:
- combo `[foreign_patient, asks_about_price]` → `bruno_foreign_asks_price`
- combo `[returning_patient]` → `patricia_returning`
- combo `[local_patient, asks_about_modality]` → `daniel_local_asks_modality`

Si chocas con un id existente, sufija `_2`, `_3`, etc.

**`display_name`**: nombre realista. Genera con LLM segun los caps:

| Cap presente | Region/contexto |
|---|---|
| `local_patient` | Colombia (Cali, Bogotá, Medellín, Cartagena, Barranquilla) |
| `foreign_patient` | Latam (Lima, CDMX, Buenos Aires, Santiago) o Europa (Madrid, Berlín, Barcelona) |

### 7. Redactar `persona_text` (hibrido: template + narrativa)

#### Parte A — Narrativa (genera con LLM)

2-3 oraciones que situen al paciente: edad, ciudad, motivo de consulta, contexto. Tono coherente con personas existentes del pool (`scripts/personas.py`).

Importante:
- Si `local_patient`: motivo de consulta + ciudad colombiana + opcional preferencia presencial/virtual.
- Si `foreign_patient`: motivo de consulta + ciudad fuera de Colombia + virtual obviamente.
- Si `returning_patient`: mencion de "ya tuviste valoracion antes" o equivalente.
- Profession-agnostico: si el shape se va a usar con psicologia, motivos psicologicos; si con ortodoncia, motivos dentales. Si no esta claro, usa motivos genericos (consulta, valoracion).

#### Parte B — Seccion "Comportamiento:" (template determinista)

Una frase canonica por cada cap presente. Usa esta tabla literalmente:

| Capability | Frase canonica |
|---|---|
| `asks_about_price` | "Lo primero que preguntas es cuanto vale." |
| `asks_about_payment_method` | "Preguntas como y por que medio se paga." |
| `asks_about_modality` | "Preguntas si la cita puede ser virtual o presencial." |
| `rejects_first_slot` | "Cuando te den horarios, dices que el primero no te sirve. Si te ofrecen otro, lo aceptas." |
| `accepts_first_slot` | "Tomas el primer horario que te ofrezcan sin pedir cambios." |
| `gives_minimal_info` | "Respondes solo lo que te preguntan, no ofreces extras." |
| `gives_all_info_upfront` | "En tu primer mensaje das todo: nombre, motivo, modalidad." |

Caps que **no** generan frase de Comportamiento (son parte de la identidad, no de la conducta): `local_patient`, `foreign_patient`, `new_patient`, `returning_patient`.

#### Estructura final del `persona_text`

```
<narrativa de 2-3 oraciones>. Comportamiento: <frases canonicas concatenadas>.
```

### 8. Mostrar preview y pedir aprobacion

Imprime al usuario el bloque Python listo para pegar:

```python
Persona(
    id="<id_generado>",
    display_name="<display_name>",
    whatsapp_user_id="<wa_id>",
    persona_text=(
        "<narrativa>. "
        "Comportamiento: <frases canonicas>."
    ),
    capabilities=[<lista en orden de declaracion del combo + caps adicionales si aplican>],
),
```

Y pregunta:

> ¿Aplicar este cambio a `scripts/personas.py:<PROFILE>_PERSONAS`? (responde "si" o sugeri ajustes)

**No edites el archivo hasta que el usuario apruebe.**

### 9. Aplicar el Edit

Si el usuario aprueba:

1. Re-leer `scripts/personas.py` para tener el contenido actual exacto (puede haber cambiado entre la lectura inicial y ahora).
2. Localiza la lista correcta. El patron de cierre es:

   ```python
   PSICOLOGA_PERSONAS: list[Persona] = [
       ...existing personas...
   ]
   ```

3. Si la lista esta vacia (`PSICOLOGA_PERSONAS: list[Persona] = []`), reemplaza por:

   ```python
   PSICOLOGA_PERSONAS: list[Persona] = [
       Persona(
           ...nueva persona...
       ),
   ]
   ```

4. Si la lista ya tiene personas, agrega la nueva como ULTIMA entrada (preserva orden de creacion historico).

5. Usa la herramienta Edit con `old_string` lo suficientemente especifico (incluye el `]` de cierre o la coma de la persona previa para ser unico).

### 10. Verificar cobertura post-edit

Corre con la herramienta Bash:

```bash
uv run python -c "
import pathlib
import scripts.coverage as coverage
import scripts.personas as personas

shape = coverage.load_shape(pathlib.Path('tests/fixtures/profiles/<shape_name>.json'))
uncovered = coverage.detect_uncovered_combos(shape, personas.ALL_PERSONAS)
print('Combos no cubiertos:', uncovered)
print('Total personas en pool:', len(personas.ALL_PERSONAS))
"
```

Reporta el resultado al usuario:

- Si el combo elegido ya **no** aparece en `uncovered` → exito.
- Si todavia aparece, hay un bug en la generacion (caps mal asignados). Reporta y revertis manualmente.

Sugiri al usuario correr `uv run pytest tests/scripts/test_coverage.py -q` para validar que nada se rompio.

## Pool ranges (referencia rapida)

```
PSICOLOGA_PERSONAS:  whatsapp_user_id en 573001110001-573001110099
ORTODONCIA_PERSONAS: whatsapp_user_id en 573002220001-573002220099
```

## Que NO hace este skill

- **No genera el `agent_profile` de un shape**. Eso es trabajo manual.
- **No corre el load_test**. Solo modifica `personas.py`.
- **No agrega al `--no-cleanup` ni Firestore**. Es generacion estatica de personas.
- **No agrega capabilities nuevas a `CAPABILITY_VOCABULARY`**. Si el combo necesita un cap inexistente, el skill aborta y le pide al usuario que primero edite el Literal en `personas.py`.
- **No agrega varias personas en una sola invocacion**. Una invocacion = una persona. Si necesitas N, invoca N veces.

## Ejemplo end-to-end

**Usuario**: `/persona-from-combo shape_multicurrency`

**Skill**:
1. Lee `scripts/personas.py` (vacio post-Fase 0) y `shape_multicurrency.json`.
2. Detecta combos uncovered:
   - `[local_patient, asks_about_price]`
   - `[foreign_patient, asks_about_price]`
3. Toma el primero: `[local_patient, asks_about_price]`.
4. Pregunta al usuario el profile → usuario responde `psicologa`.
5. Genera:
   ```python
   Persona(
       id="andres_local_asks_price",
       display_name="Andres Torres",
       whatsapp_user_id="573001110001",
       persona_text=(
           "Tienes 40 anios, vives en Cali. Tu hijo tiene mucha ansiedad y "
           "no quiere ir al colegio. Quieres llevarlo al consultorio. "
           "Comportamiento: Lo primero que preguntas es cuanto vale. "
           "Respondes solo lo que te preguntan, no ofreces extras."
       ),
       capabilities=["local_patient", "new_patient", "asks_about_price", "gives_minimal_info"],
   ),
   ```
   (Nota: el skill agrego `new_patient` como cap base implicito porque la persona es nueva por defecto si no es returning, y agrego `gives_minimal_info` como detalle de comportamiento que matchea la narrativa. Estos caps adicionales son OK siempre que no contradigan los del combo.)
6. Muestra preview, pide aprobacion.
7. Usuario aprueba → Edit en `scripts/personas.py:PSICOLOGA_PERSONAS`.
8. Smoke check: combo `[local_patient, asks_about_price]` ya no aparece en uncovered. Combo `[foreign_patient, asks_about_price]` sigue uncovered. Sugiere correr `/persona-from-combo shape_multicurrency` de nuevo para cubrirlo.

## Caps base implicitos

Si el combo no menciona ni `new_patient` ni `returning_patient`, el skill asume `new_patient` por default y lo agrega a las capabilities (porque toda persona simulada esta en uno de los dos cohorts). Lo registra explicitamente para que el matcher lo vea.

Si el combo no menciona ni `local_patient` ni `foreign_patient`, el skill agrega uno de los dos basado en el `display_name`/region elegidos. Tiene que ser explicito porque es identidad.
