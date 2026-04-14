import src.domain.entities.patient as patient_entity
import src.services.agentic.prompts.prompt_section as prompt_section
import src.services.agentic.state_models as agentic_state_models


class StateInstructionsSection(prompt_section.PromptSection):
    def render(
        self,
        runtime_context: agentic_state_models.RuntimePromptContext,
        known_patient: patient_entity.Patient | None,
    ) -> list[str]:
        del known_patient
        return _instructions_for_state(runtime_context)


def _instructions_for_state(
    runtime_context: agentic_state_models.RuntimePromptContext,
) -> list[str]:
    if runtime_context.state == "NO_ACTIVE_REQUEST":
        return [
            "Flujo actual: inicio de agendamiento. Sigue las instrucciones del system prompt para recoger los datos necesarios.",
            "Cuando tengas consultation_reason y appointment_modality (y patient_location si es VIRTUAL), "
            "llama submit_consultation_reason_for_review.",
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
            "No menciones que alguien esta revisando el pago ni que la Doc lo va a confirmar.",
            "Puedes responder preguntas del paciente usando solo la informacion que ya tienes: "
            "precios, datos de pago, horarios o informacion general del consultorio.",
            "No solicites el comprobante de nuevo ni avances el flujo de agendamiento.",
            "Sigue las reglas de medio de pago del system prompt. "
            "Solo usa handoff_to_human si el paciente dice explicitamente que NO puede pagar "
            "y necesita hablar con alguien para buscar una alternativa.",
        ]
    if runtime_context.state == "POST_BOOKING_FOLLOWUP":
        return [
            "Flujo actual: la cita fue reservada exitosamente. Sigue las instrucciones de post_booking del system prompt.",
            "Puedes responder preguntas generales del paciente: informacion del consultorio, "
            "horarios, direccion, preparacion para la cita u otros datos generales.",
            "NO inicies un nuevo proceso de agendamiento. Si el paciente quiere agendar otra cita, "
            "usa handoff_to_human.",
            "Cuando el paciente se despida o confirme que no necesita nada mas (ej: 'gracias', "
            "'no gracias', 'eso es todo', 'ya estoy bien', 'listo', 'ok'), "
            "DEBES llamar close_session obligatoriamente. No te despidas solo con texto; "
            "tu respuesta de despedida DEBE incluir la llamada a close_session.",
            "IMPORTANTE: tu UNICO objetivo en este estado es responder preguntas generales y "
            "cerrar la sesion cuando el paciente termine. No debes salir de este estado por "
            "ningun otro motivo.",
        ]
    return ["Mantente en flujo natural y sin mencionar procesos internos."]
