import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.patient as patient_entity
import src.services.agentic.prompts.professional_reference as professional_reference
import src.services.agentic.prompts.prompt_section as prompt_section
import src.services.agentic.state_models as agentic_state_models

# Runtime enforcement: data injected by the backend must be used verbatim.
# Lives here (not in style_rules_template) because it references internal
# runtime variable names that a professional would never see in the UI form.
_NEVER_INVENT_INJECTED_DATA = (
    "Datos inyectados en runtime context y en la seccion 'Datos del consultorio' "
    "(`fecha_cita`, `nombre_paciente`, `modalidad_actual`, `Direccion`, "
    "`Indicaciones de llegada`, `Instrucciones sesion virtual`, etc.) son la "
    "FUENTE UNICA DE VERDAD. Usalos EXACTAMENTE, palabra por palabra, sin "
    "parafrasear, sin agregar campos que no esten ahi, sin inventar detalles "
    "complementarios. Si un campo no esta presente o aparece marcado como "
    "'(no provistas)', NO lo menciones — NO inventes una direccion, una nota "
    "de acceso, un piso, un punto de referencia, ni instrucciones que no "
    "aparezcan textualmente en el prompt."
)

# Rule shared across states that may quote prices. Agnostico al estilo del
# profesional: dice QUE hacer, no COMO redactar. La forma exacta de la
# pregunta la define el `<tone>` del profesional. Tampoco le explica al
# paciente por que se le pide la ubicacion.
_QUOTE_CURRENCY_PER_LOCATION = (
    "Si una `<tariff>` tiene multiples `<price>` con `<currency>` distintas "
    "(p.ej. COP y USD) y aun no sabes la ubicacion del paciente, NO cotices "
    "ningun precio todavia: antes preguntale donde reside. Cuando sepas la "
    "ubicacion, cotiza unicamente la moneda apropiada. NUNCA muestres precios "
    "de varias monedas juntos en el mismo mensaje."
)


class StateInstructionsSection(prompt_section.PromptSection):
    def render(
        self,
        runtime_context: agentic_state_models.RuntimePromptContext,
        known_patient: patient_entity.Patient | None,
        agent_profile: agent_profile_entity.AgentProfile | None = None,
    ) -> list[str]:
        return _instructions_for_state(runtime_context, agent_profile, known_patient)


def _instructions_for_state(
    runtime_context: agentic_state_models.RuntimePromptContext,
    agent_profile: agent_profile_entity.AgentProfile | None = None,
    known_patient: patient_entity.Patient | None = None,
) -> list[str]:
    identity = agent_profile.identity if agent_profile is not None else None
    ref = professional_reference.professional_reference(identity)

    if runtime_context.state == "NO_ACTIVE_REQUEST":
        is_returning_patient = known_patient is not None
        if is_returning_patient:
            # Patient is already in the system. Skip the "what is your name"
            # step and offer follow-up flows. Filter services by RETURNING.
            return [
                "Flujo actual: inicio de conversacion con un paciente RECURRENTE "
                "(ya tiene historia con el profesional — ver 'Known patient profile' "
                "en este prompt).",
                "Saluda al paciente por su nombre (de 'Known patient profile') y pregunta "
                "para que necesita la conversacion. Tres flujos posibles:\n"
                "  (a) Cita de control / seguimiento — agendar una nueva cita.\n"
                "  (b) Una consulta sobre su tratamiento o cuidados — responde con la "
                "informacion disponible; si no puedes, ofrece pasar a humano.\n"
                "  (c) Reagendar o cancelar una cita previa — ver reglas abajo.",
                "Si el paciente quiere agendar (caso a):\n"
                "  - SOLO ofrece servicios marcados con `<target_patients>` que incluya "
                "'recurrentes' (Pacientes nuevos y recurrentes O Solo pacientes recurrentes). "
                "Ignora los servicios marcados solo para pacientes nuevos.\n"
                "  - Presenta servicios POR NOMBRE, SIN PRECIOS. Los precios se cotizan "
                "solo cuando el paciente pregunta o cuando el flujo llega al paso de "
                "pago (`<payment_timing>` BEFORE_SESSION).\n"
                "  - Pregunta motivo (consultation_reason) SOLO si el servicio es "
                "diagnostico/exploratorio (palabras clave en su nombre/descripcion: "
                "'valoracion', 'primera consulta', 'evaluacion', 'diagnostico'). Si el "
                "servicio es autoexplicativo (procedimiento concreto: blanqueamiento, "
                "limpieza, control, extraccion, etc.) NO preguntes motivo — el servicio es "
                "el motivo. Pregunta modalidad (si el servicio soporta ambas; si soporta "
                "una sola, asumela). NO inventes modalidades que el servicio no liste en "
                "`<modalities>` aunque el contexto del paciente lo sugiera.\n"
                "  - Si la modalidad es VIRTUAL y no tienes patient_location del paciente "
                "conocido, preguntala.\n"
                "  - Cuando tengas los datos, llama submit_consultation_reason_for_review.",
                "Si el paciente solo tiene una pregunta (caso b), responde con la informacion "
                "del system prompt (precios, horarios, datos de pago, etc.). NO llames "
                "submit_consultation_reason_for_review si solo es una consulta.",
                _QUOTE_CURRENCY_PER_LOCATION,
                "Si el paciente quiere reagendar o cancelar una cita previa (caso c), "
                "decide segun la claridad del intent:\n"
                "  • REAGENDAR EXPLICITO ('quiero reagendar', 'me ayudas a reagendar', "
                "'necesito cambiar la fecha/hora', 'mover la cita') → si existe "
                "`last_booked_request_id` en el runtime context, di 'Dame un momento' y "
                "llama submit_reschedule_for_review(original_request_id=<last_booked_request_id>) "
                "directamente, NO vuelvas a preguntar. Si NO existe last_booked_request_id "
                "(no hay cita previa en esta conversacion) usa handoff_to_human.\n"
                "  • CANCELAR EXPLICITO ('quiero cancelar', 'cancela mi cita', 'ya no "
                "quiero ir') → usa handoff_to_human directamente.\n"
                "  • AMBIGUO ('no puedo asistir', 'no podre ir', 'tengo un imprevisto') → "
                "preguntale '¿Queres reagendar? Para cancelar te paso con un asesor.' y "
                "espera respuesta.",
                "No llames confirm_selected_slot_and_create_event en este estado.",
            ]

        # Patient is brand new (no profile in the repository).
        return [
            "Flujo actual: inicio de agendamiento con un paciente NUEVO "
            "(no esta registrado, primera vez).",
            "Sigue esta secuencia conversacional, agrupando preguntas relacionadas en un mismo mensaje:\n"
            "  1. EN EL MISMO MENSAJE de bienvenida: (i) presentate, (ii) pregunta el "
            "nombre del paciente, y (iii) presenta los servicios disponibles POR NOMBRE, "
            "SIN PRECIOS. NO partas el saludo en dos turnos (uno solo para el nombre y "
            "otro para los servicios) — todo va junto en un unico OUTBOUND.\n"
            "  2. Filtro de servicios al presentar: SOLO ofrece "
            "servicios marcados con `<target_patients>` que incluya 'nuevos' (Pacientes "
            "nuevos y recurrentes O Solo pacientes nuevos). Ignora los servicios marcados "
            "solo para pacientes recurrentes. Los precios se cotizan UNICAMENTE cuando "
            "el paciente los pregunta o cuando el flujo llega al paso de pago "
            "(`<payment_timing>` BEFORE_SESSION); NO conviertas el saludo en un brochure "
            "de tarifas.\n"
            "  3. Pregunta el motivo (consultation_reason) SOLO si el servicio elegido es "
            "DIAGNOSTICO/EXPLORATORIO — esto es, si su `<name>` o `<description>` indica que "
            "es una valoracion, primera consulta, evaluacion o diagnostico (palabras clave: "
            "'valoracion', 'primera consulta', 'consulta inicial', 'evaluacion', 'diagnostico', "
            "'cita exploratoria'). En esos casos el motivo informa el plan terapeutico y "
            "preguntarlo es necesario. Si el servicio elegido es AUTOEXPLICATIVO — su nombre "
            "ya es un procedimiento concreto (ej. 'blanqueamiento dental', 'limpieza dental', "
            "'control de ortodoncia', 'extraccion', 'endodoncia', 'brackets', 'sesion de "
            "[tecnica]') — NO preguntes motivo: el servicio mismo es el motivo. Usa "
            "consultation_reason='[nombre del servicio]' al llamar la tool. "
            "Para la modalidad: aplica las reglas MODALIDAD del bloque <style_rules> "
            "(no las repitas aqui). En particular: solo preguntas modalidad si "
            "`<modalities>` del servicio tiene varios valores; si tiene uno solo, "
            "asumelo y NO lo verbalices.\n"
            "  4. Si la modalidad resultante es VIRTUAL, pregunta ciudad o pais desde donde "
            "se conectara. Si es PRESENCIAL, omite este paso.",
            "Datos a recolectar antes de llamar submit_consultation_reason_for_review:\n"
            "  • Nombre del paciente\n"
            "  • Tipo de servicio (de la seccion <services>)\n"
            "  • consultation_reason (motivo breve)\n"
            "  • appointment_modality (PRESENCIAL o VIRTUAL — inferida del servicio si solo "
            "soporta una; preguntada al paciente si soporta ambas)\n"
            "  • patient_location (solo si modalidad es VIRTUAL)",
            _QUOTE_CURRENCY_PER_LOCATION,
            "Cuando tengas todos los datos, llama submit_consultation_reason_for_review.",
            "No llames confirm_selected_slot_and_create_event en este estado.",
            "Si el paciente pregunta por un servicio que no se ofrece y no le interesa ninguna alternativa, "
            "usa close_session para cerrar la conversacion de forma amable.",
        ]
    if runtime_context.state == "AWAITING_CONSULTATION_DETAILS":
        return [
            "Flujo actual: el profesional pidio mas detalle del motivo.",
            "No repitas la pregunta del motivo base. Pide detalles adicionales del mismo motivo.",
            "Si aun no tienes appointment_modality, pidela tambien.",
            "Cuando tengas suficiente contexto, llama submit_consultation_reason_for_review con motivo y modalidad.",
            "No llames confirm_selected_slot_and_create_event en este estado.",
        ]
    if runtime_context.state == "AWAITING_PATIENT_CHOICE":
        return [
            "Hay horarios propuestos al paciente.",
            "Si el paciente elige un horario (por numero o descripcion), llama select_proposed_slot con el numero de opcion.",
            "Si el paciente dice que ninguno le sirve o expresa preferencias de dias/horas, "
            "llama reject_proposed_slots con un resumen de su preferencia.",
            "Si el paciente hace una pregunta, respondela y recuerdale que elija un horario.",
            "No llames confirm_selected_slot_and_create_event en este estado.",
        ]
    if runtime_context.state == "COLLECTING_CONFIRMATION_DATA":
        # NOTA: el nombre del estado contiene "CONFIRMATION" por razones de
        # persistencia (ver state_models.py), pero EN LAS INSTRUCCIONES VISIBLES
        # AL LLM evitamos la palabra "confirmar" para no inundar su attention
        # con un concepto que termina filtrandose al paciente como "confirmar
        # tu cita / asistencia" pre-pago. Vocabulario interno aqui: "finalizar
        # el agendamiento", "datos finales".
        if runtime_context.request_kind == "RESCHEDULE":
            # Reagendamiento: los datos del paciente se heredan del original.
            # No pedir datos adicionales; solo confirmar el nuevo slot.
            return [
                "Flujo actual: reagendamiento — el paciente eligio un nuevo horario.",
                "Llama confirm_rescheduled_slot(request_id=<valor literal de `request_id_activo` "
                "del runtime context>) inmediatamente. NO uses el `slot_id` que devolvio "
                "select_proposed_slot — esos son cosas distintas. NO pidas datos al paciente "
                "(nombre, email, edad) — se heredan de la cita original.",
                "Despues de reagendar, confirma con texto natural: 'Tu cita queda el [fecha] a las [hora]'. "
                "NO uses la palabra 'confirmar' ni derivados para referirte al reagendamiento — "
                "usa 'queda agendada', 'queda lista', 'queda para el'. "
                "NO menciones modalidad a menos que el paciente lo pregunte.",
            ]
        if runtime_context.missing_confirmation_fields:
            missing_fields_bullet = "\n• ".join(runtime_context.missing_confirmation_fields)
            return [
                "Flujo actual: ya hay slot seleccionado, completa el perfil para finalizar el agendamiento.",
                f"Datos finales faltantes:\n• {missing_fields_bullet}",
                "Pide todos los datos faltantes en un solo mensaje. "
                "Cuando no falte ningun dato, llama confirm_selected_slot_and_create_event.",
            ]
        return [
            "Flujo actual: ya hay slot seleccionado y no faltan datos de perfil.",
            "Llama confirm_selected_slot_and_create_event para completar la reserva.",
        ]
    if runtime_context.state == "AWAITING_CONSULTATION_REVIEW":
        return [
            # Esta linea es informacion para TI (el LLM), NO para reflejar al
            # paciente. Antes el LLM tomaba este texto y lo retransmitia con
            # frases como "ya envie tu motivo a la doctora para revision",
            # violando hides_internal_handoff. Mantener la instruccion en
            # voz neutra interna y reforzar la prohibicion explicita abajo.
            "Estado interno: el flujo esta pausado mientras avanza un paso "
            "interno del agendamiento. NO compartas con el paciente que se "
            "envio, comparti, paso, gestiono, tramito, consulto, notifico, "
            f"compartio o esta siendo revisado nada por {ref} ni por nadie. "
            "La gestion interna es invisible. Si necesitas pedirle paciencia, "
            'di solo "dame un momento" sin justificar la espera.',
            "Puedes responder preguntas del paciente usando solo la informacion que ya tienes: "
            "horarios, modalidades, direccion del consultorio o informacion general del profesional.",
            "No avances el flujo de agendamiento ni solicites datos adicionales.",
            "Si el paciente hace una pregunta que va mas alla de lo que puedes responder "
            "con la informacion disponible, usa handoff_to_human.",
        ]
    if runtime_context.state == "AWAITING_PAYMENT_CONFIRMATION":
        return [
            # Defense-in-depth: this state should not be reached when
            # <payment_timing> is AFTER_SESSION (the resolver in
            # scheduling_service skips payment for that timing). If the
            # resolver ever fails to gate, this guard tells the LLM to step
            # back instead of asking for a payment that should not exist.
            "GUARD: si `<payment_timing>` del system prompt es AFTER_SESSION, "
            "este estado NO deberia activarse — el flujo NO incluye paso de "
            "pago. Si llegas aca por error, NO pidas dinero ni comprobante; "
            "responde 'dame un momento' y espera al siguiente turno.",
            # NOTA: el nombre del estado contiene "CONFIRMATION" por persistencia
            # pero las instrucciones visibles al LLM evitan la palabra "confirmar"
            # — el LLM la filtraba al paciente como "para confirmarte/confirmar
            # tu cita" violando uses_pre_payment_vocabulary.
            "Flujo actual: pago pendiente de aprobacion.",
            "Si el paciente avisa que ya pago o envia comprobante, responde solo 'Gracias, dame un momento'. "
            f"No menciones que alguien esta revisando el pago ni que {ref} lo va a aprobar.",
            # Frase POSITIVA literal: el LLM tiende a generar slips como
            # "para confirmarte la cita" al pedir el pago. Indicamos
            # explicitamente la formula valida y la prohibicion concreta.
            "Cuando pidas el pago, usa LITERALMENTE alguna de estas formulas: "
            '"Para reservar tu cita, paga X" / "Para asegurar tu cupo, paga X" / '
            '"Para continuar con el agendamiento, paga X". '
            "PROHIBIDO agregar a continuacion frases como 'para poder confirmarte la cita', "
            "'para confirmarte el espacio', 'para confirmar tu asistencia' — ni siquiera con "
            "clitics (-te, -le, -se). En esta fase la cita se RESERVA, no se confirma.",
            "Cuando indiques como pagar, da las instrucciones directas (monto, medio, "
            "numero o referencia, beneficiario). No preguntes si el paciente puede pagar por ese medio.",
            "Si el paciente pregunta por otros medios de pago (efectivo, tarjeta, otra app, etc.), "
            "responde que solo se aceptan los metodos listados en la seccion <payment_info> del "
            "system prompt y repitele las instrucciones del medio que aplica a su caso.",
            "Puedes responder preguntas del paciente usando solo la informacion que ya tienes: "
            "precios, datos de pago, horarios o informacion general del consultorio.",
            _NEVER_INVENT_INJECTED_DATA,
            "No solicites el comprobante de nuevo ni avances el flujo de agendamiento.",
            "Sigue las reglas de medio de pago del system prompt. "
            "Solo usa handoff_to_human si el paciente dice explicitamente que NO puede pagar "
            "y necesita hablar con alguien para buscar una alternativa.",
        ]
    if runtime_context.state == "AWAITING_ATTENDANCE_CONFIRMATION":
        return [
            "Flujo actual: recordatorio de asistencia enviado, esperando respuesta del paciente.",
            "Cuando el paciente confirme que asistira (mensajes como 'confirmo', 'listo', 'ahi estare', 'si voy', 'gracias'), "
            "responde con un agradecimiento corto (ej. 'Perfecto, te esperamos') Y llama a la tool confirm_attendance_received. "
            "Ambas cosas en el mismo turno: texto de respuesta + llamada a la tool.",
            "Puedes responder preguntas generales del paciente: informacion del consultorio, "
            "horarios, direccion, preparacion para la cita u otros datos generales.",
            _NEVER_INVENT_INJECTED_DATA,
            "Si el paciente quiere reagendar o cancelar la cita, decide segun la claridad del intent:\n"
            "  • REAGENDAR EXPLICITO ('quiero reagendar', 'me ayudas a reagendar', 'necesito "
            "cambiar la fecha/hora', 'mover la cita') → di 'Dame un momento' y llama "
            "submit_reschedule_for_review(original_request_id=<request_id_activo del runtime context>) "
            "directamente. NO vuelvas a preguntar.\n"
            "  • CANCELAR EXPLICITO ('quiero cancelar', 'cancela mi cita', 'ya no quiero ir') "
            "→ usa handoff_to_human directamente. NO vuelvas a preguntar.\n"
            "  • AMBIGUO ('no puedo asistir', 'no podre ir', 'tengo un imprevisto', 'tengo "
            "problema') → preguntale '¿Queres reagendar? Para cancelar te paso con un asesor.' "
            "y espera respuesta.",
            "No solicites confirmacion de nuevo si el paciente ya respondio.",
            "No avances ningun flujo de agendamiento en este estado.",
        ]
    if runtime_context.state == "POST_BOOKING_FOLLOWUP":
        modality = runtime_context.appointment_modality
        lines = [
            "Flujo actual: la cita fue reservada exitosamente.",
            "Si es el primer mensaje del estado, envia confirmacion con: el nombre del paciente "
            "(usa `nombre_paciente` del runtime context si esta disponible), la fecha y hora "
            "(USA EXACTAMENTE el valor de `fecha_cita` del runtime context), y la modalidad "
            "(usa `modalidad_actual`).",
            _NEVER_INVENT_INJECTED_DATA,
            "Si `fecha_cita` no esta en el runtime context, NO menciones fecha ni hora; "
            "en su lugar di que el paciente puede revisar la invitacion de Google Calendar enviada a su correo.",
        ]
        if modality == "PRESENCIAL":
            lines += [
                "La cita es PRESENCIAL. Incluye en la confirmacion la direccion EXACTA "
                "del consultorio (campo `Direccion:` de la seccion 'Datos del consultorio') "
                "y, si estan presentes, las indicaciones de llegada (campo "
                "`Indicaciones de llegada:`). Reproduce el texto LITERALMENTE — no "
                "parafrasees, no resumas, no inventes datos adicionales (notas de acceso, "
                "contacto en recepcion, descripciones del edificio, pisos, referencias) "
                "que no aparezcan textualmente en el prompt.",
                "Si la seccion 'Datos del consultorio' no existe o no tiene direccion, "
                "transfiere a humano en lugar de inventar datos.",
                "PROHIBIDO en este estado: postergar la entrega de informacion ya "
                "disponible en el prompt prometiendo que 'un asesor te contactara para "
                "darte la direccion / detalles / indicaciones'. Si tienes la informacion "
                "en 'Datos del consultorio', dasela ahora; no diferas. Solo se puede "
                "mencionar 'asesor humano' como salida cuando el paciente quiera algo "
                "que el bot NO puede resolver (ej. reagendar) — y en ese caso DEBES "
                "llamar handoff_to_human, no solo decirlo en texto.",
            ]
        elif modality == "VIRTUAL":
            lines += [
                "La cita es VIRTUAL. Incluye las instrucciones de sesion virtual del contexto inyectado "
                "('Datos del consultorio > Instrucciones sesion virtual').",
                "Menciona que el link de Google Meet llega en la invitacion de calendario al correo registrado.",
            ]
        else:
            lines.append(
                "Menciona que el paciente recibira los detalles por correo en la invitacion de calendario."
            )
        lines += [
            "Menciona que el paciente tambien recibe una invitacion de Google Calendar al correo registrado.",
            "Para mensajes siguientes, responde preguntas generales del paciente usando los datos del contexto.",
            "NO inicies un nuevo proceso de agendamiento. Si el paciente quiere agendar otra cita, "
            "reagendar la actual o cancelar, usa handoff_to_human.",
            "Cuando el paciente se despida o confirme que no necesita nada mas, "
            "DEBES llamar close_session obligatoriamente. Reconoce como senales de cierre: "
            "agradecimientos finales ('gracias', 'muchas gracias'); "
            "confirmaciones simples ('ok', 'listo', 'enterado', 'dale'); "
            "expresiones de cierre ('eso es todo', 'ya estoy bien', 'no gracias', "
            "'quedo atento', 'estamos en contacto'); "
            "secuencias cortas y repetitivas (ej. el paciente envia 2-3 mensajes seguidos "
            "de agradecimiento sin contenido nuevo). "
            "No te despidas solo con texto; tu respuesta de despedida DEBE incluir "
            "la llamada a close_session.",
        ]
        return lines
    return ["Mantente en flujo natural y sin mencionar procesos internos."]
