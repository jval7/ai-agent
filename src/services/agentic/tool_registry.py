import src.services.dto.llm_dto as llm_dto


class ToolDefinitionRegistry:
    def build_waiting_state_tool_definitions(self) -> list[llm_dto.FunctionDeclarationDTO]:
        return [
            llm_dto.FunctionDeclarationDTO(
                name="handoff_to_human",
                description=(
                    "Pasa la conversacion a modo humano solo cuando el paciente solicita "
                    "explicitamente la intervencion de una persona humana."
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string"},
                        "summary_for_professional": {"type": "string"},
                    },
                    "required": ["reason", "summary_for_professional"],
                    "additionalProperties": False,
                },
            ),
            llm_dto.FunctionDeclarationDTO(
                name="cancel_active_scheduling_request",
                description=(
                    "Cancela la solicitud de agendamiento activa solo cuando el paciente lo pide "
                    "explicitamente."
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string"},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            ),
        ]

    def build_tool_definitions(
        self,
        enabled_tool_names: list[str] | None = None,
    ) -> list[llm_dto.FunctionDeclarationDTO]:
        all_tool_definitions = [
            llm_dto.FunctionDeclarationDTO(
                name="submit_consultation_reason_for_review",
                description=(
                    "Envia el motivo de consulta y modalidad para revision del profesional. "
                    "Llama esta tool apenas tengas consultation_reason y appointment_modality; "
                    "no necesitas nombre, apellido, edad ni otros datos en este paso. "
                    "Si la modalidad es VIRTUAL debes incluir patient_location. "
                    "Si la modalidad es PRESENCIAL, patient_location se puede omitir."
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "request_id": {"type": "string"},
                        "consultation_reason": {"type": "string"},
                        "appointment_modality": {
                            "type": "string",
                            "enum": ["PRESENCIAL", "VIRTUAL"],
                        },
                        "patient_location": {"type": "string"},
                    },
                    "required": ["consultation_reason", "appointment_modality"],
                    "additionalProperties": False,
                },
            ),
            llm_dto.FunctionDeclarationDTO(
                name="confirm_selected_slot_and_create_event",
                description=(
                    "Confirma un horario elegido por el paciente y crea el evento en Google Calendar. "
                    "Si el perfil del paciente ya existe en contexto, reutilizalo y no repitas preguntas innecesarias. "
                    "Si el perfil no existe, pide TODOS los datos faltantes en UN SOLO mensaje "
                    "(patient_full_name, patient_email, patient_phone, patient_age). "
                    "patient_phone puede tomarse del numero de WhatsApp si ya esta disponible. "
                    "consultation_reason debe reutilizarse del motivo ya aprobado; no repreguntes el motivo salvo "
                    "que el profesional haya pedido mas informacion. "
                    "La eleccion del horario se hace por numero de opcion y el backend persiste esa seleccion. "
                    "Si slot_id no se incluye, el backend usara el slot ya seleccionado por el paciente."
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "request_id": {"type": "string"},
                        "slot_id": {"type": "string"},
                        "patient_full_name": {"type": "string"},
                        "patient_email": {"type": "string"},
                        "patient_phone": {"type": "string"},
                        "patient_age": {"type": ["integer", "string"]},
                        "consultation_reason": {"type": "string"},
                        "patient_location": {"type": "string"},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            ),
            llm_dto.FunctionDeclarationDTO(
                name="handoff_to_human",
                description=(
                    "Pasa la conversacion a modo humano solo cuando el paciente solicita "
                    "explicitamente la intervencion de una persona humana."
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string"},
                        "summary_for_professional": {"type": "string"},
                    },
                    "required": ["reason", "summary_for_professional"],
                    "additionalProperties": False,
                },
            ),
            llm_dto.FunctionDeclarationDTO(
                name="cancel_active_scheduling_request",
                description=(
                    "Cancela la solicitud de agendamiento activa solo cuando el paciente lo pide "
                    "explicitamente."
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string"},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            ),
        ]

        if enabled_tool_names is None:
            return all_tool_definitions

        enabled_tool_name_set = set(enabled_tool_names)
        filtered_tool_definitions: list[llm_dto.FunctionDeclarationDTO] = []
        for tool_definition in all_tool_definitions:
            if tool_definition.name in enabled_tool_name_set:
                filtered_tool_definitions.append(tool_definition)
        return filtered_tool_definitions
