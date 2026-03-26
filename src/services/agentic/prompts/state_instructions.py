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
            "Flujo actual: inicio de agendamiento.",
            "Si aun no conoces el nombre del paciente, pidelo antes de avanzar. No pidas mas datos en ese mensaje.",
            "Si ya tienes el nombre, pide lo que falte: motivo de consulta, modalidad (presencial o virtual).",
            "Si la modalidad es VIRTUAL, pregunta desde donde se conectaria (ciudad/pais).",
            "Pregunta de forma conversacional, como lo haria una persona por WhatsApp. No uses formatos de lista ni lenguaje formal para pedir estos datos.",
            "Apenas tengas consultation_reason y appointment_modality, llama submit_consultation_reason_for_review.",
            "No llames confirm_selected_slot_and_create_event en este estado.",
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
            "Flujo actual: hay horarios propuestos y se espera una seleccion numerica.",
            "Si el paciente aun no eligio, recuerda elegir solo con numero de opcion.",
            "No llames confirm_selected_slot_and_create_event hasta tener slot seleccionado.",
        ]
    if runtime_context.state == "COLLECTING_CONFIRMATION_DATA":
        if runtime_context.missing_confirmation_fields:
            missing_fields_bullet = "\n• ".join(runtime_context.missing_confirmation_fields)
            return [
                "Flujo actual: ya hay slot seleccionado, completa perfil para confirmar.",
                f"Campos faltantes para confirmar:\n• {missing_fields_bullet}",
                "Pide TODOS los campos faltantes en UN SOLO mensaje usando lista con bullet points (•).",
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
            "Flujo actual: pago pendiente de aprobacion por el profesional.",
            "Puedes responder preguntas del paciente usando solo la informacion que ya tienes: "
            "precios, datos de pago, horarios o informacion general del consultorio.",
            "No solicites el comprobante de nuevo ni avances el flujo de agendamiento.",
            "IMPORTANTE sobre medio de pago: el unico medio de pago disponible es transferencia a Nequi. "
            "No preguntes si el paciente puede pagar por ese medio. Solo indica las instrucciones de pago "
            "de forma directiva. Si el paciente pregunta por otros medios de pago (efectivo, tarjeta, etc.), "
            "responde que por el momento solo se acepta Nequi y repite las instrucciones de pago. "
            "Solo usa handoff_to_human si el paciente dice explicitamente que NO puede pagar por Nequi "
            "y necesita hablar con alguien para buscar una alternativa.",
            "Si el paciente hace una pregunta que va mas alla de lo que puedes responder "
            "con la informacion disponible, usa handoff_to_human.",
        ]
    if runtime_context.state == "POST_BOOKING_FOLLOWUP":
        return [
            "Flujo actual: la cita fue reservada exitosamente.",
            "Pregunta al paciente si necesita algo mas: '¿Hay algo mas en lo que pueda ayudarte?'",
            "Puedes responder preguntas generales del paciente: informacion del consultorio, "
            "horarios, direccion, preparacion para la cita u otros datos generales.",
            "NO inicies un nuevo proceso de agendamiento. Si el paciente quiere agendar otra cita, "
            "indicale que debe iniciar una nueva conversacion o usa handoff_to_human.",
            "Cuando el paciente confirme que no necesita nada mas (ej: 'no gracias', 'eso es todo', "
            "'ya estoy bien', 'listo'), despidete amablemente y llama close_session.",
            "IMPORTANTE: tu UNICO objetivo en este estado es responder preguntas generales y "
            "cerrar la sesion cuando el paciente termine. No debes salir de este estado por "
            "ningun otro motivo.",
        ]
    return ["Mantente en flujo natural y sin mencionar procesos internos."]
