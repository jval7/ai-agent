import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.entities.patient as patient_entity
import src.services.agentic.prompts.professional_reference as professional_reference
import src.services.agentic.prompts.prompt_section as prompt_section
import src.services.agentic.state_models as agentic_state_models

# Runtime enforcement: data injected by the backend must be used verbatim.
# Lives here (not in style_rules_template) because it references internal
# runtime variable names that a professional would never see in the UI form.
_NEVER_INVENT_INJECTED_DATA = (
    "Si el contexto inyectado tiene `fecha_cita`, `nombre_paciente`, `modalidad_actual` u otro dato "
    "del paciente o de la cita, usalos EXACTAMENTE como aparecen. "
    "NUNCA inventes ni parafrasees fechas, horas, nombres ni datos del paciente."
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
                "  (c) Reprogramar o cancelar una cita previa — usa handoff_to_human "
                "(el bot no gestiona cambios de citas pasadas).",
                "Si el paciente quiere agendar (caso a):\n"
                "  - SOLO ofrece servicios marcados con `<target_patients>` que incluya "
                "'recurrentes' (Pacientes nuevos y recurrentes O Solo pacientes recurrentes). "
                "Ignora los servicios marcados solo para pacientes nuevos.\n"
                "  - Pregunta motivo (consultation_reason) y modalidad (si el servicio "
                "soporta ambas; si soporta una sola, asumela).\n"
                "  - Si la modalidad es VIRTUAL y no tienes patient_location del paciente "
                "conocido, preguntala.\n"
                "  - Cuando tengas los datos, llama submit_consultation_reason_for_review.",
                "Si el paciente solo tiene una pregunta (caso b), responde con la informacion "
                "del system prompt (precios, horarios, datos de pago, etc.). NO llames "
                "submit_consultation_reason_for_review si solo es una consulta.",
                "Si pide reprogramar/cancelar una cita previa (caso c), usa handoff_to_human "
                "directamente — no intentes gestionar el cambio.",
                "No llames confirm_selected_slot_and_create_event en este estado.",
            ]

        # Patient is brand new (no profile in the repository).
        return [
            "Flujo actual: inicio de agendamiento con un paciente NUEVO "
            "(no esta registrado, primera vez).",
            "Sigue esta secuencia conversacional, agrupando preguntas relacionadas en un mismo mensaje:\n"
            "  1. Si es el primer mensaje, presentate y pregunta el nombre del paciente.\n"
            "  2. Presenta los servicios disponibles. SOLO ofrece servicios marcados con "
            "`<target_patients>` que incluya 'nuevos' (Pacientes nuevos y recurrentes O "
            "Solo pacientes nuevos). Ignora los servicios marcados solo para pacientes "
            "recurrentes.\n"
            "  3. Pregunta el motivo (consultation_reason). En el mismo mensaje, pregunta la "
            "modalidad SOLO si el servicio elegido en el paso 2 soporta ambas (revisa "
            "`<modalities>` del `<service>` correspondiente). Si el servicio solo soporta una "
            "modalidad, asume esa automaticamente y no preguntes.\n"
            "  4. Si la modalidad resultante es VIRTUAL, pregunta ciudad o pais desde donde "
            "se conectara. Si es PRESENCIAL, omite este paso.",
            "Datos a recolectar antes de llamar submit_consultation_reason_for_review:\n"
            "  • Nombre del paciente\n"
            "  • Tipo de servicio (de la seccion <services>)\n"
            "  • consultation_reason (motivo breve)\n"
            "  • appointment_modality (PRESENCIAL o VIRTUAL — inferida del servicio si solo "
            "soporta una; preguntada al paciente si soporta ambas)\n"
            "  • patient_location (solo si modalidad es VIRTUAL)",
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
        if runtime_context.missing_confirmation_fields:
            missing_fields_bullet = "\n• ".join(runtime_context.missing_confirmation_fields)
            return [
                "Flujo actual: ya hay slot seleccionado, completa perfil para confirmar.",
                f"Campos faltantes para confirmar:\n• {missing_fields_bullet}",
                "Pide todos los campos faltantes en un solo mensaje. "
                "Cuando no falte ningun campo, llama confirm_selected_slot_and_create_event.",
            ]
        return [
            "Flujo actual: ya hay slot seleccionado y no faltan campos de perfil.",
            "Llama confirm_selected_slot_and_create_event para completar la reserva.",
        ]
    if runtime_context.state == "AWAITING_CONSULTATION_REVIEW":
        return [
            "Flujo actual: motivo de consulta enviado, esperando revision del profesional.",
            "Puedes responder preguntas del paciente usando solo la informacion que ya tienes: "
            "horarios, modalidades, direccion del consultorio o informacion general del profesional.",
            "No avances el flujo de agendamiento ni solicites datos adicionales.",
            "Si el paciente hace una pregunta que va mas alla de lo que puedes responder "
            "con la informacion disponible, usa handoff_to_human.",
        ]
    if runtime_context.state == "AWAITING_PAYMENT_CONFIRMATION":
        return [
            "Flujo actual: pago pendiente de aprobacion.",
            "Si el paciente avisa que ya pago o envia comprobante, responde solo 'Gracias, dame un momento'. "
            f"No menciones que alguien esta revisando el pago ni que {ref} lo va a confirmar.",
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
            "Si el paciente dice que NO puede asistir o pide reagendar/cancelar su cita, "
            "usa handoff_to_human — el bot no gestiona cambios de citas ya reservadas.",
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
                "La cita es PRESENCIAL. Incluye en la confirmacion la direccion del consultorio, "
                "las indicaciones de llegada y las notas de acceso tal como aparezcan en la seccion "
                "'Datos del consultorio' del contexto inyectado.",
                "Si la seccion 'Datos del consultorio' no existe o no tiene direccion, "
                "transfiere a humano en lugar de inventar datos.",
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
            "usa handoff_to_human.",
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
