"""LLM-as-judge para el eval framework.

Llama a Gemini con structured output para verificar si las capabilities
declaradas por una persona se ejercieron efectivamente en el transcript
de la conversacion.

Granularidad: 1 llamada por conversacion. El juez ve todo el transcript
y devuelve UN verdict con N verifications (una por cap declarada).

Si Gemini falla (timeout, error de parseo, schema mismatch), retorna un
JudgeVerdict con `error` poblado y `overall="none"` en lugar de raisear.
El caller puede continuar aunque el juez falle — el verdict es informacion,
no critico para el runner.
"""

from __future__ import annotations

import datetime
import json
import logging
import typing

from google import genai
from google.api_core import exceptions as google_api_exceptions

import src.domain.entities.eval_run as eval_run_entity

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Glosario de capabilities (hardcoded en el prompt)
# ---------------------------------------------------------------------------

_GLOSSARY: dict[str, str] = {
    # Comportamentales del paciente — requieren evidencia INBOUND directa.
    "asks_about_price": (
        "el paciente pregunta cuanto vale la consulta o servicio en algun mensaje INBOUND"
    ),
    "asks_about_payment_method": (
        "el paciente pregunta como o por que medio se paga en algun mensaje INBOUND"
    ),
    "asks_about_modality": (
        "el paciente pregunta si la cita puede ser virtual o presencial en algun mensaje INBOUND"
    ),
    "rejects_first_slot": (
        "el paciente rechaza explicitamente el primer horario propuesto y pide otro"
    ),
    "accepts_first_slot": (
        "el paciente acepta el primer horario que el bot le ofrece sin pedir cambios"
    ),
    "gives_minimal_info": (
        "el paciente solo responde lo que el bot le pregunta, sin ofrecer informacion "
        "adicional no solicitada"
    ),
    "gives_all_info_upfront": (
        "en su primer mensaje INBOUND el paciente entrega multiples datos sin que el "
        "bot los pida (ej. nombre + motivo + modalidad juntos)"
    ),
    # Inferenciales por comportamiento del flujo — pueden verificarse por como
    # bot/paciente se comportan, sin necesidad de declaracion explicita del paciente.
    "local_patient": (
        "la conversacion procede como con un paciente local del pais del consultorio "
        "(Colombia): el bot cotiza precio en COP, ofrece modalidad presencial, da "
        "metodo de pago local (Nequi/transferencia), o el paciente menciona ciudad "
        "colombiana o residencia en el pais. Inferencia comportamental aceptable."
    ),
    "foreign_patient": (
        "la conversacion procede como con un paciente extranjero: el bot cotiza precio "
        "en USD u otra moneda extranjera, sugiere modalidad virtual, da metodo de pago "
        "internacional (Zelle/Wise), o el paciente menciona explicitamente vivir fuera "
        "del pais. Inferencia comportamental aceptable."
    ),
    "new_patient": (
        "la conversacion se centra en un paciente nuevo: el bot le pide nombre/edad/"
        "motivo porque no los tiene, no hay referencias a sesiones previas o tratamiento "
        "en curso, el bot trata el caso como primera consulta. Si el bot saluda por "
        "nombre desde el primer mensaje sin que el paciente lo de, NO es new_patient. "
        "Inferencia comportamental aceptable."
    ),
    "returning_patient": (
        "la conversacion se centra en un paciente conocido por el sistema: el bot saluda "
        "por nombre desde el primer mensaje sin pedir datos basicos, hay referencias a "
        "tratamiento previo, sesiones anteriores, cita de control, o el paciente "
        "menciona seguir tratamiento. Inferencia comportamental aceptable."
    ),
    # Comportamiento del BOT (no del paciente). Se verifica observando los OUTBOUND.
    "quotes_currency_per_location": (
        "el bot maneja correctamente las tarifas multi-moneda. La regla critica es: "
        "NUNCA muestra varias monedas juntas en el mismo mensaje cuando no sabe la "
        "ubicacion del paciente. verified=true si el bot cotizo UNA sola moneda Y esa "
        "moneda es consistente con la ubicacion del paciente — sea porque el bot la "
        "pregunto explicitamente, sea porque la INFIRIO de pistas claras del paciente "
        "(ej. paciente dijo 'presencial' => local => COP; paciente dijo 'virtual desde "
        "Berlin' => foreign => USD; paciente menciono ciudad colombiana => COP). La "
        "inferencia por contexto es valida — no es obligatorio preguntar si hay pistas. "
        "verified=false SOLO si el bot expuso multiples monedas juntas sin tener forma "
        "de saber la ubicacion, o cotizo una moneda inconsistente con la ubicacion "
        "inferible. Inferencia comportamental por OUTBOUND aceptable."
    ),
    "uses_pre_payment_vocabulary": (
        "el bot distingue conceptualmente entre AGENDAMIENTO y CONFIRMACION DE "
        "ASISTENCIA. Son dos eventos distintos del ciclo de vida de una cita. "
        "AGENDAMIENTO: la fase actual del flujo (recoleccion de datos, propuesta "
        "de horario, solicitud de pago, recoleccion de datos finales). En esta fase "
        "se *agenda* o *reserva* una cita — NO se confirma nada todavia. CONFIRMACION "
        "DE ASISTENCIA: estado posterior, en el recordatorio pre-cita, donde el "
        "paciente confirma que asistira a una cita ya agendada y pagada. El verbo "
        "'confirmar' (y derivados: 'confirmacion', 'confirmar tu cita/asistencia/"
        "espacio/reserva') pertenece al segundo concepto y es INCORRECTO usarlo "
        "durante el flujo de agendamiento. La forma correcta al pedir el pago es "
        "'Para reservar tu cita, paga X' o 'Para continuar con el proceso de "
        "agendamiento, paga X' — NO 'Para confirmar tu cita/asistencia/espacio, paga X'. "
        "verified=true si el bot NO uso 'confirmar' ni derivados aplicados a la cita/"
        "asistencia/espacio/reserva durante el flujo de agendamiento (antes de recibir "
        "el comprobante de pago). verified=false ante frases como 'para confirmar tu "
        "cita', 'confirmar tu asistencia', 'confirmar tu espacio', 'confirmacion de "
        "tu cita' aplicadas en pre-pago — citar la frase EXACTA del OUTBOUND y el turno. "
        "Notas: (1) 'confirmar el pago' o 'cuando se confirme el pago' se refiere al "
        "pago en si, no a la cita — eso es PERMITIDO. (2) Si el shape tiene "
        "payment_timing=AFTER_SESSION, esta cap NO aplica (verified=true automatico)."
    ),
    "hides_internal_handoff": (
        "regla CONCEPTUAL (no lexica): el bot NO transmite al paciente que esta "
        "realizando comunicaciones internas, gestiones, consultas, transferencias, "
        "envios, traspasos, comparticiones o revisiones con el PROFESIONAL TRATANTE. "
        "La gestion interna es invisible al paciente. Cualquier OUTBOUND donde "
        "aparezca un verbo de comunicacion/gestion/transferencia/revision aplicado "
        "al profesional tratante (la doctora, el doctor, el profesional) como "
        "destinatario o agente interno expone el handoff y viola esta cap. "
        "INDEPENDIENTE de: el verbo (enviar, pasar, compartir, comentar, gestionar, "
        "tramitar, mandar, transferir, revisar, consultar), la persona gramatical "
        "(yo/nosotros: 'envie' / 'hemos enviado' / 'le pasamos'), la voz (activa o "
        "pasiva: 'esta siendo revisado por la doctora'), el tiempo (presente, "
        "pasado, futuro perifrastico: 'va a revisar', 'te contactaremos'), o la "
        "construccion sintactica. La regla es semantica: si la lectura natural del "
        "OUTBOUND comunica al paciente que SE ESTA HACIENDO algo internamente con "
        "la profesional tratante, viola la cap. "
        "DISTINCION CLAVE: una escalada explicita a un OPERADOR HUMANO de la clinica "
        "(ej. 'te atiende un asesor humano de nuestro equipo', 'paso la conversacion "
        "a un humano') NO viola la cap — esa es comunicacion legitima de un handoff "
        "necesario, no exposicion de gestion con la profesional tratante. "
        "verified=true si NINGUN OUTBOUND comunica gestion interna con la "
        "profesional tratante. verified=false ante CUALQUIER OUTBOUND donde la "
        "lectura natural revele gestion interna con la profesional — DEBES citar "
        "el texto EXACTO del OUTBOUND (no parafrasear, no inventar). "
        "Inferencia comportamental por OUTBOUND."
    ),
    "skips_redundant_motivo_question": (
        "regla CONCEPTUAL: el bot solo pregunta el 'motivo de consulta' "
        "cuando el servicio elegido es DIAGNOSTICO/EXPLORATORIO (palabras "
        "clave en el nombre o descripcion del servicio: 'valoracion', "
        "'primera consulta', 'consulta inicial', 'evaluacion', 'diagnostico', "
        "'cita exploratoria'). En esos casos preguntar motivo es legitimo "
        "porque el motivo determina el plan terapeutico. "
        "El bot NO debe preguntar motivo cuando el servicio es "
        "AUTOEXPLICATIVO (un procedimiento concreto cuyo nombre YA es el "
        "motivo: 'blanqueamiento dental', 'limpieza dental', 'control de "
        "ortodoncia', 'extraccion', 'endodoncia', 'brackets', 'sesion de "
        "[tecnica]', 'tratamiento [especifico]'). Para esos servicios el "
        "motivo es el servicio mismo y preguntarlo es redundante. "
        "verified=true si TODOS los OUTBOUND donde el bot pregunta motivo "
        "ocurren en uno de estos contextos: "
        "(a) el paciente NO ha elegido un servicio aun y el bot pregunta "
        "como parte del flujo inicial; "
        "(b) el servicio elegido es diagnostico (palabras clave de arriba); "
        "(c) el paciente ya menciono un sub-motivo abierto ('quiero "
        "blanqueamiento porque tengo una boda') y el bot pide mas detalle. "
        "verified=false si el bot pregunta motivo despues de que el paciente "
        "eligio un servicio autoexplicativo y NO hay sub-motivo en juego. "
        "Caso prototipico de fail (caso del screenshot que motivo la cap): "
        "paciente dice 'Blanqueamiento' y el bot responde '¿Cual sería el "
        "motivo de tu consulta para el blanqueamiento dental?'. "
        "Cita textual obligatoria del OUTBOUND donde el bot pregunta motivo "
        "+ del INBOUND donde se eligio el servicio. EXCEPCION: si el "
        "paciente ofrecio el motivo proactivamente, el bot puede acusar "
        "recibo brevemente pero NO debe re-preguntar. "
        "Inferencia comportamental por OUTBOUND."
    ),
    "respects_service_modalities": (
        "regla CONCEPTUAL: el bot solo ofrece modalidades (PRESENCIAL / VIRTUAL) "
        "que estan listadas en `<modalities>` del `<service>` que el paciente "
        "elige. Si un servicio solo tiene modalidad PRESENCIAL, el bot NO debe "
        "ofrecer atender VIRTUAL aunque el paciente este en otra ciudad o pais; "
        "viceversa. El contexto del paciente (residencia, pais) NO autoriza al "
        "bot a inventar una modalidad que el AgentProfile no soporta. "
        "El header del user prompt te informa los servicios y sus modalidades "
        "disponibles ('Shape services and modalities: ...'); usa esa info para "
        "verificar. "
        "verified=true si TODOS los OUTBOUND donde el bot menciona modalidad "
        "(presencial/virtual/online/en consultorio/desde donde te conectes) "
        "respetan el set de modalidades configurado para el servicio elegido. "
        "verified=false si algun OUTBOUND ofrece, propone o asume una "
        "modalidad NO listada en `<modalities>` para ese servicio — citar "
        "texto exacto del OUTBOUND y mencionar cual es el set de modalidades "
        "real del servicio. "
        "EXCEPCION: si el bot le dice al paciente 'este servicio solo se "
        "atiende presencial, ¿queres venir o prefieres pasar a humano para ver "
        "alternativas?', eso NO viola la cap — esta comunicando la restriccion "
        "del servicio, no inventando modalidad. Tampoco viola si pasa a "
        "handoff_to_human cuando la modalidad no aplica. "
        "Inferencia comportamental por OUTBOUND."
    ),
    "quotes_price_on_demand": (
        "regla CONCEPTUAL: el bot NO cotiza precios al paciente sin que algun "
        "INBOUND previo lo haya pedido. La rúbrica mira el ORDEN entre "
        "INBOUND y OUTBOUND a lo largo del transcript. "
        "verified=true si CADA OUTBOUND donde el bot menciona uno o más "
        "precios numéricos con currency (ej. '150.000 COP', '$80,000', "
        "'USD 100') tiene AL MENOS UNA de estas justificaciones: "
        "(a) algún INBOUND ANTERIOR (no el mismo turno, ANTES) preguntó por "
        "precio/costo/cotización/tarifa/'cuánto vale'/'cuánto sale'/'cuánto "
        "cuesta'/'qué precio tiene'; "
        "(b) el OUTBOUND es el mensaje pre-pago oficial del flujo de "
        "agendamiento donde el bot pide pago para reservar (frases tipo "
        "'Para reservar tu cita, paga X', 'Para asegurar tu cupo paga X', "
        "'Para continuar con el agendamiento, paga X'). Esta excepción solo "
        "aplica cuando el shape es BEFORE_SESSION; en AFTER_SESSION no hay "
        "step de pago así que no aplica; "
        "(c) algún INBOUND previo expresó interés concreto en un servicio "
        "específico Y el bot está respondiendo con la info de ese servicio "
        "incluyendo su precio como dato esencial. Esta excepción NO incluye "
        "listar TODOS los servicios con precios — solo el servicio que el "
        "paciente eligió. "
        "verified=false si CUALQUIER OUTBOUND emite precios sin (a), (b) ni "
        "(c). Caso prototípico de fail: mensaje de bienvenida que lista "
        "todos los servicios con tarifas tras un simple 'Hola' del paciente. "
        "Cita textual obligatoria del OUTBOUND violador y del INBOUND previo "
        "(o ausencia del mismo) cuando verified=false. "
        "Inferencia comportamental por OUTBOUND."
    ),
    "skips_payment_when_after_session": (
        "regla CONDICIONAL: aplica SOLO cuando el shape declara "
        "`payment_timing=AFTER_SESSION` (el contexto del shape lo indica al "
        "principio del user prompt). En ese caso, el bot NO debe pedir un "
        "pago como CTA durante el flujo de agendamiento ni solicitar "
        "comprobante de pago. La conversacion debe llegar al cierre de la "
        "reserva sin pasar por un step de pago. "
        "OUTBOUND violadores (lista NO exhaustiva): 'paga X', 'transfiere a "
        "Nequi', 'envia el dinero', 'abona', 'deposita', 'reserva con un "
        "pago de X', 'para asegurar tu cupo paga X', 'envíame el "
        "comprobante', 'manda el voucher', 'necesito el recibo', listar "
        "metodos de pago como CTA inmediato. "
        "EXCEPCIONES (NO violan la cap): "
        "(a) responder a una pregunta directa del paciente sobre como/cuando "
        "se paga con framing INFORMATIVO (declarativo), ej. 'el pago se "
        "realiza al finalizar la sesion en consultorio'; "
        "(b) recordatorios operativos en POST_BOOKING_FOLLOWUP del estilo "
        "'el pago se cobra al finalizar la sesion'; "
        "(c) mencionar el monto cuando el paciente pregunta '¿cuanto vale?' "
        "siempre y cuando NO se acompañe de un CTA imperativo de pago. "
        "verified=true SI el shape es AFTER_SESSION y NINGUN OUTBOUND "
        "contiene un CTA de pago/comprobante en el agendamiento. "
        "verified=false SI el shape es AFTER_SESSION y CUALQUIER OUTBOUND "
        "pre-cierre contiene un CTA o pide comprobante — citar texto exacto "
        "del OUTBOUND y el turno. "
        "Si el shape es BEFORE_SESSION (default), la cap NO aplica — emite "
        "verified=true automatico (es no-op para esos shapes). "
        "Inferencia comportamental por OUTBOUND."
    ),
    "omits_obvious_metadata": (
        "regla CONCEPTUAL: cuando el bot PRESENTA un servicio o RESPONDE algo no "
        "relacionado a modalidad/cohort, OMITE metadata trivial. Especificamente "
        "debe OMITIR: "
        "(a) Modalidad de un servicio cuya `<modalities>` tiene un solo valor — "
        "presentar el servicio sin coletillas como 'es presencial', 'es virtual', "
        "'se hace en consultorio', 'es en linea'. "
        "(b) Etiqueta de cohort cuando el servicio aplica a 'Pacientes nuevos y "
        "recurrentes' (ambos cohorts) — frases como 'para pacientes nuevos o "
        "recurrentes', 'para nuevos y recurrentes', 'aplica a cualquier paciente'. "
        "El cohort SOLO se menciona cuando el <target_patients> es restrictivo "
        "('Solo pacientes nuevos' o 'Solo pacientes recurrentes') Y aplica al "
        "paciente actual. "
        "(c) Aclaraciones autoimplicitas que se siguen logicamente del contexto "
        "('para cualquier persona', 'esta disponible para todos', 'aplica a quien "
        "lo necesite'). "
        "EXCEPCIONES (mencionar la modalidad NO viola la cap en estos casos): "
        "  (i) MULTI-MODALIDAD: el servicio tiene varias modalidades en "
        "<modalities> y el paciente debe elegir. "
        "  (ii) PREGUNTA EXPLICITA: el paciente preguntó por modalidad o cohort "
        "en un INBOUND previo y el bot responde. "
        "  (iii) CONFIRMACION DE RESERVA: el bot esta enviando el mensaje de "
        "confirmacion final post-booking ('Tu cita... ha sido reservada... de "
        "forma Presencial/Virtual...'). En este punto la modalidad es info "
        "operativa esencial para el paciente — saber si tiene que viajar al "
        "consultorio o conectarse a un Meet — y debe aparecer SIEMPRE, incluso "
        "si el servicio solo tiene una modalidad. "
        "  (iv) COMUNICAR RESTRICCION: el bot le esta diciendo al paciente que el "
        "servicio NO soporta cierta modalidad ('La consulta es unicamente "
        "presencial', 'este servicio no se atiende virtual'). Es respuesta a una "
        "pregunta o aclaracion necesaria, no metadata gratuita. "
        "verified=true si los OUTBOUND donde el bot menciona modalidad/cohort "
        "encajan en alguna excepcion (i-iv) o si el servicio tiene varias "
        "modalidades. "
        "verified=false SOLO ante OUTBOUND donde el bot verbaliza modalidad/cohort "
        "trivial (a)/(b)/(c) en presentaciones casuales SIN encajar en ninguna "
        "excepcion — citar texto EXACTO + indicar por que no aplica ninguna "
        "excepcion. "
        "Inferencia comportamental por OUTBOUND aceptable."
    ),
}

# Caps que pueden verificarse por inferencia comportamental (criterio b).
# Las demas requieren evidencia INBOUND directa (criterio a).
_INFERENTIAL_CAPS = frozenset(
    {
        "local_patient",
        "foreign_patient",
        "new_patient",
        "returning_patient",
        "quotes_currency_per_location",  # se verifica por OUTBOUND del bot
        "hides_internal_handoff",  # se verifica por ausencia de frases en OUTBOUND
        "uses_pre_payment_vocabulary",  # se verifica por ausencia de "confirmar" pre-pago
        "omits_obvious_metadata",  # se verifica por ausencia de metadata trivial al presentar servicios
        "skips_payment_when_after_session",  # condicional al shape; se verifica por ausencia de CTA pago en AFTER_SESSION
        "quotes_price_on_demand",  # se verifica por orden INBOUND-pregunta -> OUTBOUND-precio
        "respects_service_modalities",  # se verifica contra <modalities> del servicio elegido
        "skips_redundant_motivo_question",  # heuristica sobre nombre/descripcion del servicio elegido
    }
)

_SYSTEM_INSTRUCTION = """\
Eres un evaluador de conversaciones simuladas entre un paciente y un asistente de agenda.

Tu tarea es verificar si las capabilities declaradas por el paciente se ejercieron
efectivamente en el transcript de la conversacion.

Glosario de capabilities:

Comportamentales del paciente (requieren evidencia INBOUND directa):
- asks_about_price: el paciente pregunta cuanto vale en algun mensaje INBOUND
- asks_about_payment_method: pregunta como/por que medio se paga
- asks_about_modality: pregunta si la cita es virtual o presencial
- rejects_first_slot: rechaza explicitamente el primer horario propuesto
- accepts_first_slot: acepta el primer horario sin pedir cambios
- gives_minimal_info: solo responde lo que le preguntan, sin extras no solicitados
- gives_all_info_upfront: en el primer mensaje da nombre + motivo + modalidad

Inferenciales por flujo (pueden verificarse por como bot/paciente se comportan):
- local_patient: el flujo procede en COP, presencial, Nequi, o ciudad colombiana
- foreign_patient: el flujo procede en USD/EUR, virtual, Zelle/Wise, o paciente vive fuera
- new_patient: el bot pide nombre/edad/motivo (no los conoce); no hay sesiones previas
- returning_patient: el bot saluda por nombre sin pedirlo; referencias a tratamiento previo

Inferenciales por comportamiento del bot (verificadas por OUTBOUND):
- quotes_currency_per_location: ante tarifas multi-moneda, el bot cotiza UNA sola
  moneda Y esa moneda es consistente con la ubicacion del paciente — sea porque
  la pregunto, sea porque la infirio del contexto (presencial => local => COP;
  virtual desde otro pais => foreign => USD; ciudad colombiana mencionada => COP).
  La inferencia por contexto es valida; no es obligatorio preguntar si hay pistas.
  NUNCA debe mostrar varias monedas juntas en el mismo mensaje sin saber ubicacion.
  verified=false SOLO si el bot expuso ambas monedas juntas sin saber ubicacion,
  o cotizo una moneda inconsistente con la ubicacion inferible.
- uses_pre_payment_vocabulary: el bot distingue AGENDAMIENTO (flujo actual, hasta
  el pago) de CONFIRMACION DE ASISTENCIA (estado posterior, recordatorio). En el
  agendamiento se *agenda*/*reserva* — NO se confirma. El verbo "confirmar" (y
  derivados: "confirmacion", "confirmar tu cita/asistencia/espacio/reserva")
  pertenece al estado de confirmacion de asistencia (post-pago, recordatorio),
  no al agendamiento. verified=false ante frases pre-pago como "para confirmar
  tu cita", "confirmar tu asistencia", "confirmar tu espacio", "confirmacion de
  tu cita" — citar la frase EXACTA del OUTBOUND. "Confirmar el pago" si esta
  permitido (se refiere al pago en si, no a la cita). No aplica si
  payment_timing=AFTER_SESSION.
- hides_internal_handoff: regla CONCEPTUAL (no lexica). El bot NO transmite al
  paciente que esta realizando comunicaciones internas con el PROFESIONAL TRATANTE,
  sin importar el verbo (enviar/pasar/compartir/gestionar/consultar/tramitar/mandar
  /revisar), la persona gramatical (yo/nosotros), la voz (activa/pasiva), el tiempo
  ni la construccion. La regla es semantica: si la lectura natural del OUTBOUND
  comunica al paciente que se esta HACIENDO algo internamente con la profesional
  tratante, viola la cap. Ejemplos (lista NO exhaustiva): "ya le envie", "ya hemos
  enviado el motivo", "le paso el motivo", "gestiono con", "le comparto tu caso",
  "voy a consultar con", "esta siendo revisado por la doctora", "envie tus datos a
  la doctora para que revise". EXCEPCION: escalada explicita a un OPERADOR HUMANO
  del equipo (ej. "te atiende un asesor humano") NO viola la cap. verified=true si
  NINGUN OUTBOUND comunica gestion interna con la profesional. verified=false ante
  CUALQUIER OUTBOUND con esa semantica — citar texto exacto del OUTBOUND.
- skips_redundant_motivo_question: el bot solo pregunta el "motivo de consulta"
  cuando el servicio elegido es DIAGNOSTICO/EXPLORATORIO (palabras clave:
  "valoracion", "primera consulta", "consulta inicial", "evaluacion",
  "diagnostico"). NO debe preguntar motivo cuando el servicio es AUTOEXPLICATIVO
  (un procedimiento concreto cuyo nombre ya es el motivo: "blanqueamiento",
  "limpieza dental", "control de ortodoncia", "extraccion", "endodoncia",
  "brackets"). verified=true si los OUTBOUND con pregunta de motivo aplican a
  servicio diagnostico, o el paciente aun no eligio servicio. verified=false si
  el bot pregunta motivo despues de que el paciente eligio un servicio
  autoexplicativo (caso prototipico: paciente "Blanqueamiento" -> bot "¿cual es
  el motivo?"). Excepcion: sub-motivos abiertos ("blanqueamiento porque tengo
  una boda") permiten preguntar mas detalle.
- respects_service_modalities: el bot solo ofrece modalidades (PRESENCIAL/VIRTUAL)
  listadas en <modalities> del <service> elegido. NO inventa una modalidad que el
  AgentProfile no soporta aunque el contexto del paciente sugiera otra (ej. paciente
  en Berlin no autoriza ofrecer VIRTUAL si el servicio es solo PRESENCIAL). El header
  del user prompt te informa los servicios y modalidades ('Shape services and
  modalities: ...'). verified=true si todos los OUTBOUND con mencion de modalidad
  respetan el set configurado. verified=false si bot ofrece/asume modalidad no
  listada — citar exacto. EXCEPCION: comunicarle al paciente la restriccion ("este
  servicio solo se atiende presencial, ¿queres venir o pasar a humano?") NO viola.
- quotes_price_on_demand: el bot NO cotiza precios sin que el paciente los pida.
  Mira el ORDEN INBOUND -> OUTBOUND. verified=true si CADA OUTBOUND con precio
  numérico+currency tiene al menos una de estas: (a) algún INBOUND ANTERIOR
  preguntó por precio/costo/cotización ('cuánto vale', 'cuánto cuesta'); (b) es
  el mensaje pre-pago oficial del flujo (BEFORE_SESSION) tipo "Para reservar
  paga X"; (c) el paciente eligió un servicio y el bot responde con info del
  mismo (precio incluido). verified=false si el bot lanza brochure de precios
  tras un 'Hola' (caso prototípico), o cotiza sin pregunta previa. Cita exacta
  del OUTBOUND y la ausencia/presencia de INBOUND relevante.
- skips_payment_when_after_session: regla CONDICIONAL al shape. Aplica SOLO cuando
  el shape es AFTER_SESSION (te lo digo al inicio del user prompt como "Shape
  payment_timing: AFTER_SESSION"). En ese caso, el bot NO debe pedir pago como CTA
  ni solicitar comprobante durante el agendamiento — el cobro sucede al finalizar
  la sesion. Frases prohibidas (lista NO exhaustiva): "paga X", "transfiere a
  Nequi", "envia el dinero", "para asegurar tu cupo paga X", "envíame el
  comprobante", "manda el voucher", "necesito el recibo". EXCEPCIONES (NO violan):
  responder a una pregunta del paciente con framing INFORMATIVO ("el pago se
  realiza al finalizar la sesion"), recordatorios operativos en POST_BOOKING, o
  cotizar el monto cuando el paciente preguntó "¿cuanto vale?" sin acompañar de
  CTA imperativo. verified=true si shape es AFTER_SESSION y NINGUN OUTBOUND
  pre-cierre contiene CTA de pago. verified=false con cita exacta. Si el shape es
  BEFORE_SESSION, la cap NO aplica (verified=true automatico — es no-op).
- omits_obvious_metadata: cuando el bot PRESENTA un servicio o RESPONDE algo no
  relacionado a modalidad/cohort, OMITE metadata trivial. Debe OMITIR: (a) modalidad
  si el servicio tiene una sola modalidad (no decir "es presencial" / "es virtual" /
  "se hace en consultorio"); (b) etiqueta de cohort cuando el servicio aplica a
  "Pacientes nuevos y recurrentes"; (c) aclaraciones autoimplicitas ("para cualquier
  persona", "aplica a todos"). EXCEPCIONES (mencionar modalidad NO viola la cap):
  (i) MULTI-MODALIDAD: el servicio tiene varias modalidades y el paciente debe
  elegir. (ii) PREGUNTA EXPLICITA: el paciente preguntó por modalidad/cohort en un
  INBOUND previo. (iii) CONFIRMACION DE RESERVA: el bot esta enviando el mensaje de
  confirmacion final post-booking ("Tu cita... ha sido reservada... de forma
  Presencial/Virtual..."). En post-booking la modalidad es info operativa esencial
  (saber si viajar al consultorio o conectarse a Meet) y debe aparecer SIEMPRE
  aunque el servicio tenga una sola modalidad. (iv) COMUNICAR RESTRICCION: el bot le
  dice al paciente que el servicio NO soporta cierta modalidad ("La consulta es
  unicamente presencial"). verified=true si los OUTBOUND con mencion de
  modalidad/cohort encajan en alguna excepcion. verified=false SOLO ante OUTBOUND
  con redundancia trivial (a)/(b)/(c) en presentaciones casuales sin encajar en
  ninguna excepcion — citar texto exacto e indicar por que no aplica ninguna
  excepcion. Ejemplos prohibidos: "Blanqueamiento Dental: para pacientes nuevos o
  recurrentes. Es presencial." (presentacion casual), "Valoracion: aplica a
  cualquier persona", "Cita de control: es presencial" cuando solo hay PRESENCIAL.

Reglas:

1. Solo evalua las capabilities en "declared_capabilities". Ignora cualquier otra.

2. Para cada capability, verified=true si CUALQUIERA de estos dos criterios se cumple:

   (a) Evidencia EXPLICITA: hay un mensaje INBOUND donde el paciente declara o
       ejerce la capability directamente (ej. "Cuanto vale la consulta?" para
       asks_about_price).

   (b) Evidencia COMPORTAMENTAL (solo para caps inferenciales — local_patient,
       foreign_patient, new_patient, returning_patient, quotes_currency_per_location):
       el flujo de la conversacion es consistente con la capability, observando como
       el bot trata al paciente, que datos pide o no, en que moneda cotiza, que metodo
       de pago ofrece, o como el paciente actua. Ejemplos:
       - new_patient verified si el bot pide nombre/edad porque no los tiene.
       - returning_patient verified si el bot saluda por nombre desde el primer mensaje.
       - local_patient verified si el bot cotizo en COP y ofrecio Nequi.
       - foreign_patient verified si el bot cotizo en USD y ofrecio Zelle.
       - quotes_currency_per_location verified si el bot cotizo UNA sola moneda
         consistente con la ubicacion (preguntada O inferida del contexto, ej.
         "presencial" => local => COP). verified=false SOLO si mostro varias
         monedas juntas sin saber ubicacion, o cotizo moneda inconsistente.
       - uses_pre_payment_vocabulary verified si NINGUN OUTBOUND pre-pago usa
         "confirmar"/"confirmacion" aplicado a cita/asistencia/espacio/reserva.
         "Confirmar el pago" SI esta permitido (se refiere al pago, no a la
         cita). verified=false ante variantes como "confirmar tu cita",
         "confirmar tu asistencia", "confirmar tu espacio", "confirmacion de
         tu cita" en mensajes anteriores al comprobante — citar frase exacta.
       - hides_internal_handoff: regla CONCEPTUAL — verified=true si NINGUN
         OUTBOUND comunica gestion interna con el PROFESIONAL TRATANTE,
         independiente del verbo, persona gramatical, voz o tiempo. Si la lectura
         natural del OUTBOUND revela que SE ESTA HACIENDO algo internamente con
         la profesional tratante (envio, traspaso, consulta, gestion, revision,
         comparticion), verified=false con cita exacta del texto. Excepcion:
         escalada explicita a un OPERADOR HUMANO del equipo (no la profesional).
       - skips_redundant_motivo_question: verified=true si las preguntas de
         motivo del bot solo aplican a servicios diagnosticos/exploratorios
         (palabras: "valoracion", "primera consulta", "evaluacion") o al
         flujo inicial antes de que el paciente eligiera servicio.
         verified=false si pregunta motivo tras que el paciente eligio un
         servicio autoexplicativo (blanqueamiento, limpieza, control,
         extraccion). Citar OUTBOUND exacto.
       - respects_service_modalities: verified=true si los OUTBOUND con mencion
         de modalidad respetan el set listado en <modalities> del servicio
         elegido (informado en header 'Shape services and modalities'). verified=
         false si bot ofrece/asume modalidad no listada (ej. VIRTUAL cuando solo
         hay PRESENCIAL) — citar OUTBOUND exacto. Comunicar la restriccion al
         paciente NO viola.
       - quotes_price_on_demand: verified=true si cada OUTBOUND con precio
         tiene un INBOUND previo que preguntó precio (cuánto vale/cuesta/cotización),
         o es el mensaje pre-pago oficial (BEFORE_SESSION), o responde sobre el
         servicio que el paciente eligió. verified=false si bot suelta precios
         en saludo/presentación sin pregunta previa — cita exacta del OUTBOUND.
       - skips_payment_when_after_session: condicional al shape. Si el header
         del user prompt dice "Shape payment_timing: AFTER_SESSION", el bot NO
         debe emitir CTAs de pago/comprobante en el agendamiento. verified=true
         si NINGUN OUTBOUND pre-cierre contiene CTA imperativo de pago.
         verified=false con cita exacta. Si el header dice BEFORE_SESSION,
         verified=true automatico (no-op para esos shapes).
       - omits_obvious_metadata: verified=true si los OUTBOUND donde el bot
         menciona modalidad/cohort encajan en alguna excepcion legitima:
         (i) el servicio tiene varias modalidades; (ii) el paciente preguntó
         por modalidad/cohort en INBOUND previo; (iii) el OUTBOUND es la
         CONFIRMACION DE RESERVA post-booking ("Tu cita... ha sido reservada...
         de forma Presencial/Virtual...") — la modalidad es info operativa
         esencial ahi y debe aparecer SIEMPRE; (iv) el bot esta COMUNICANDO LA
         RESTRICCION del servicio al paciente ("este servicio es unicamente
         presencial"). verified=false SOLO ante OUTBOUND donde el bot verbaliza
         modalidad/cohort en presentaciones casuales sin encajar en ninguna
         excepcion — citar texto exacto e indicar por que no aplica ninguna
         excepcion.

3.5. ANTI-ALUCINACION: el campo evidence DEBE ser una cita TEXTUAL del transcript
     real (copiar el texto exacto de algun mensaje INBOUND u OUTBOUND segun el
     criterio aplicado). NUNCA inventes ni parafrasees la cita. Si no podes
     encontrar evidencia textual literal en el transcript que respalde verified=
     true o verified=false, prefiere verified=true con evidence=null y reasoning
     explicando que no hay evidencia clara — es preferible un falso negativo a
     una alucinacion. Verifica turno-por-turno antes de citar.

3. evidence:
   - Si aplico criterio (a): quote textual breve del mensaje INBOUND.
   - Si aplico criterio (b): descripcion textual del flujo observado, citando
     turno y direccion (ej. "el bot pide nombre y edad en turno 2 (OUTBOUND),
     indicando que no conocia al paciente").
   - null si verified=false.

4. reasoning: 1-2 lineas indicando que criterio aplico y por que.

5. overall: "all_verified" si todas verificadas, "partial" si algunas, "none" si ninguna.

Importante: para caps NO inferenciales (asks_about_price, gives_minimal_info, etc.),
solo aplica criterio (a). Si no hay evidencia INBOUND directa, verified=false aunque
el flujo sea consistente.

Responde SOLO con JSON valido segun el schema indicado. Sin texto adicional.
"""

# ---------------------------------------------------------------------------
# Schema JSON para structured output
# ---------------------------------------------------------------------------

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "verifications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "capability": {"type": "string"},
                    "verified": {"type": "boolean"},
                    # Vertex AI no acepta `type: ["string", "null"]` (JSON Schema
                    # 2020-12). Usar `nullable: true` + `type: "string"`.
                    "evidence": {"type": "string", "nullable": True},
                    "reasoning": {"type": "string", "nullable": True},
                },
                "required": ["capability", "verified"],
            },
        },
        "overall": {
            "type": "string",
            "enum": ["all_verified", "partial", "none"],
        },
    },
    "required": ["verifications", "overall"],
}


def _build_user_prompt(
    persona_id: str,
    declared_capabilities: list[str],
    transcript: list[eval_run_entity.EvalRunConversationMessage],
    shape_payment_timing: str | None,
    shape_services_modalities: list[tuple[str, list[str]]] | None,
) -> str:
    """Construye el mensaje de usuario para el juez."""
    caps_str = ", ".join(declared_capabilities)
    lines = [
        f"Persona: {persona_id}",
        f"Declared capabilities: [{caps_str}]",
    ]
    # Caps condicionales (ej. skips_payment_when_after_session) necesitan
    # esta señal para decidir si aplican o si emiten verified=true automatico.
    if shape_payment_timing is not None:
        lines.append(f"Shape payment_timing: {shape_payment_timing}")
    # Cap respects_service_modalities: el juez compara los OUTBOUND contra
    # esta lista para detectar si el bot inventa una modalidad no soportada.
    if shape_services_modalities:
        services_str = "; ".join(
            f"{name}: {', '.join(mods) if mods else '(unspecified)'}"
            for name, mods in shape_services_modalities
        )
        lines.append(f"Shape services and modalities: {services_str}")
    lines.extend(
        [
            "",
            "Transcript:",
        ]
    )
    for i, msg in enumerate(transcript, start=1):
        lines.append(f"[{i}] [{msg.direction}] {msg.content}")

    return "\n".join(lines)


def _compute_overall(
    verifications: list[eval_run_entity.CapabilityVerification],
) -> typing.Literal["all_verified", "partial", "none"]:
    if not verifications:
        return "none"
    verified_count = sum(1 for v in verifications if v.verified)
    if verified_count == 0:
        return "none"
    if verified_count == len(verifications):
        return "all_verified"
    return "partial"


def judge_conversation(
    persona_id: str,
    declared_capabilities: list[str],
    transcript: list[eval_run_entity.EvalRunConversationMessage],
    gemini_client: genai.Client,
    model: str = "gemini-2.5-flash",
    timeout_seconds: float = 30.0,
    shape_payment_timing: str | None = None,
    shape_services_modalities: list[tuple[str, list[str]]] | None = None,
) -> eval_run_entity.JudgeVerdict:
    """Llama Gemini con structured output para verificar capabilities.

    Si falla (timeout, parse error, schema mismatch), retorna un JudgeVerdict
    con error="<razon>" y overall="none". El runner no debe abortar si el juez
    falla — el verdict es informacion, no critico.

    `shape_payment_timing` se pasa al user prompt para que caps condicionales
    (ej. skips_payment_when_after_session) sepan cuando aplicar.

    `shape_services_modalities` (lista de (service_name, modalities)) se pasa
    para que la cap respects_service_modalities pueda contrastar lo que el
    bot dice vs lo que el AgentProfile soporta.
    """
    judged_at = datetime.datetime.now(tz=datetime.UTC)

    if not declared_capabilities:
        return eval_run_entity.JudgeVerdict(
            declared_capabilities=[],
            verifications=[],
            overall="none",
            judge_model=model,
            judged_at=judged_at,
            error="no declared capabilities to verify",
        )

    user_prompt = _build_user_prompt(
        persona_id,
        declared_capabilities,
        transcript,
        shape_payment_timing,
        shape_services_modalities,
    )

    try:
        response = gemini_client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=_RESPONSE_SCHEMA,
                temperature=0.0,
            ),
        )
    except google_api_exceptions.DeadlineExceeded as exc:
        logger.warning("judge_conversation: Gemini timeout para %s: %s", persona_id, exc)
        return eval_run_entity.JudgeVerdict(
            declared_capabilities=declared_capabilities,
            verifications=[],
            overall="none",
            judge_model=model,
            judged_at=judged_at,
            error=f"timeout: {exc}",
        )
    except google_api_exceptions.GoogleAPIError as exc:
        logger.warning("judge_conversation: Gemini API error para %s: %s", persona_id, exc)
        return eval_run_entity.JudgeVerdict(
            declared_capabilities=declared_capabilities,
            verifications=[],
            overall="none",
            judge_model=model,
            judged_at=judged_at,
            error=f"api_error: {exc}",
        )

    # Parsear la respuesta
    raw_text = ""
    try:
        raw_text = response.text or ""
        parsed = json.loads(raw_text)
    except (json.JSONDecodeError, AttributeError, ValueError) as exc:
        logger.warning(
            "judge_conversation: JSON parse error para %s: %s — raw: %r",
            persona_id,
            exc,
            raw_text[:200],
        )
        return eval_run_entity.JudgeVerdict(
            declared_capabilities=declared_capabilities,
            verifications=[],
            overall="none",
            judge_model=model,
            judged_at=judged_at,
            error=f"json_parse_error: {exc}",
        )

    # Mapear a entities
    try:
        raw_verifications_raw = parsed.get("verifications", [])
        if not isinstance(raw_verifications_raw, list):
            raise TypeError(
                f"expected list for 'verifications', got {type(raw_verifications_raw).__name__}"
            )
        raw_verifications: list[dict[str, object]] = raw_verifications_raw
        # Filtrar items mal formados Y caps que no estaban declaradas.
        # Lo segundo evita que el juez halucine caps inexistentes (ej.
        # "asks_about_dragons") y queden persistidas como evidencia falsa.
        declared_set = set(declared_capabilities)
        verifications = [
            eval_run_entity.CapabilityVerification(
                capability=str(v["capability"]),
                verified=bool(v["verified"]),
                evidence=str(v["evidence"]) if v.get("evidence") is not None else None,
                reasoning=str(v["reasoning"]) if v.get("reasoning") is not None else None,
            )
            for v in raw_verifications
            if "capability" in v and "verified" in v and str(v["capability"]) in declared_set
        ]
        raw_overall = parsed.get("overall", "none")
        overall: typing.Literal["all_verified", "partial", "none"]
        if raw_overall in ("all_verified", "partial", "none"):
            overall = raw_overall
        else:
            overall = _compute_overall(verifications)

    except (KeyError, TypeError, ValueError) as exc:
        logger.warning(
            "judge_conversation: schema mismatch para %s: %s — parsed: %r",
            persona_id,
            exc,
            str(parsed)[:200],
        )
        return eval_run_entity.JudgeVerdict(
            declared_capabilities=declared_capabilities,
            verifications=[],
            overall="none",
            judge_model=model,
            judged_at=judged_at,
            error=f"schema_mismatch: {exc}",
        )

    return eval_run_entity.JudgeVerdict(
        declared_capabilities=declared_capabilities,
        verifications=verifications,
        overall=overall,
        judge_model=model,
        judged_at=judged_at,
    )
