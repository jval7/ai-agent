import src.services.dto.llm_dto as llm_dto


class ToolDefinitionRegistry:
    def _build_set_contact_name_definition(self) -> llm_dto.FunctionDeclarationDTO:
        return llm_dto.FunctionDeclarationDTO(
            name="set_contact_name",
            description=(
                "Registra el nombre de la persona que esta hablando (quien escribe por WhatsApp). "
                "Llama esta tool en cuanto sepas su nombre; puede ser diferente al del paciente "
                "si es un padre, madre o tutor agendando para otra persona."
            ),
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "contact_name": {"type": "string"},
                },
                "required": ["contact_name"],
                "additionalProperties": False,
            },
        )

    def build_waiting_state_tool_definitions(self) -> list[llm_dto.FunctionDeclarationDTO]:
        return [
            self._build_set_contact_name_definition(),
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
            self._build_set_contact_name_definition(),
            llm_dto.FunctionDeclarationDTO(
                name="select_proposed_slot",
                description=(
                    "Selecciona uno de los horarios propuestos al paciente. "
                    "Usa cuando el paciente indique cual horario prefiere, "
                    "ya sea por numero o describiendo el horario."
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "slot_option_number": {
                            "type": "string",
                            "description": "Numero de opcion elegido por el paciente (ej: '1', '2')",
                        },
                    },
                    "required": ["slot_option_number"],
                    "additionalProperties": False,
                },
            ),
            llm_dto.FunctionDeclarationDTO(
                name="reject_proposed_slots",
                description=(
                    "Rechaza todos los horarios propuestos porque ninguno le sirve al paciente. "
                    "El profesional propondra nuevos horarios."
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "patient_preference": {
                            "type": "string",
                            "description": (
                                "Resumen de la preferencia o restriccion del paciente "
                                "(ej: 'prefiere lunes en la tarde', 'no puede antes de las 5pm')"
                            ),
                        },
                    },
                    "required": ["patient_preference"],
                    "additionalProperties": False,
                },
            ),
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
                    # NOTA: el nombre del tool empieza con `confirm_*` por compatibilidad
                    # con el orchestrator existente. La descripcion EVITA el verbo
                    # "confirmar" porque el LLM lo reflejaba al paciente como
                    # "confirmar tu cita / asistencia" en pre-pago, violando la regla
                    # uses_pre_payment_vocabulary. Aqui el verbo correcto es agendar /
                    # crear el evento.
                    "Agenda definitivamente la cita: crea el evento en Google Calendar "
                    "para el horario que el paciente eligio y persiste el agendamiento "
                    "en Firestore. "
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
            llm_dto.FunctionDeclarationDTO(
                name="close_session",
                description=(
                    "Cierra la sesion actual y archiva la conversacion. "
                    "Llama esta tool UNICAMENTE cuando el paciente confirme que no necesita nada mas "
                    "despues de una reserva exitosa."
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "farewell_message": {"type": "string"},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            ),
            llm_dto.FunctionDeclarationDTO(
                name="confirm_attendance_received",
                description=(
                    "Llama esta tool cuando el paciente confirma que asistira a su cita "
                    "(mensajes como 'confirmo', 'listo', 'ahi estare', 'si voy', 'gracias'). "
                    "Cierra la sesion de inmediato."
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {},
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
