import datetime

import src.domain.entities.patient as patient_entity
import src.services.agentic.prompt_builder as prompt_builder
import src.services.agentic.state_models as agentic_state_models


def _build_builder() -> prompt_builder.RuntimePromptBuilder:
    return prompt_builder.RuntimePromptBuilder()


def _build_patient() -> patient_entity.Patient:
    return patient_entity.Patient(
        tenant_id="t-1",
        whatsapp_user_id="wu-1",
        first_name="Maria",
        last_name="Garcia",
        email="maria@test.com",
        age=30,
        location="Bogota",
        phone="+573001234567",
        created_at=datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC),
    )


class TestPromptAssemblerOutputParity:
    def test_no_active_request_without_patient(self) -> None:
        builder = _build_builder()
        ctx = agentic_state_models.RuntimePromptContext(
            state="NO_ACTIVE_REQUEST",
            enabled_tool_names=["submit_consultation_reason_for_review", "set_contact_name"],
        )
        result = builder.build_runtime_system_prompt(ctx, known_patient=None)
        assert "INSTRUCCIONES RUNTIME (PRIORIDAD ALTA):" in result
        assert "- estado_conversacion: NO_ACTIVE_REQUEST" in result
        assert "- Known patient profile: not found" in result
        # New patient flow: explicit "primera vez" branch.
        assert "paciente NUEVO" in result
        assert "submit_consultation_reason_for_review, set_contact_name" in result

    def test_no_active_request_with_patient(self) -> None:
        builder = _build_builder()
        ctx = agentic_state_models.RuntimePromptContext(
            state="NO_ACTIVE_REQUEST",
            enabled_tool_names=["submit_consultation_reason_for_review"],
        )
        patient = _build_patient()
        result = builder.build_runtime_system_prompt(ctx, known_patient=patient)
        assert "Known patient profile (reuse this context" in result
        assert "- patient_full_name: Maria Garcia" in result
        assert "- patient_email: maria@test.com" in result
        assert "- patient_age: 30" in result
        # Returning patient flow: NO_ACTIVE_REQUEST instructions branch on
        # known_patient. The bot should offer follow-up flows (cita de
        # control, consulta, reprogramar) instead of the new-patient sequence.
        assert "paciente RECURRENTE" in result
        assert "Cita de control" in result

    def test_awaiting_consultation_details(self) -> None:
        builder = _build_builder()
        ctx = agentic_state_models.RuntimePromptContext(
            state="AWAITING_CONSULTATION_DETAILS",
            request_id="req-1",
            request_status="AWAITING_CONSULTATION_DETAILS",
            professional_note="Necesito mas detalle",
            enabled_tool_names=["submit_consultation_reason_for_review"],
        )
        result = builder.build_runtime_system_prompt(ctx, known_patient=None)
        assert "- request_id_activo: req-1" in result
        assert "Notas del profesional" in result
        assert "Necesito mas detalle" in result
        assert "Flujo actual: el profesional pidio mas detalle" in result

    def test_awaiting_patient_choice(self) -> None:
        builder = _build_builder()
        ctx = agentic_state_models.RuntimePromptContext(
            state="AWAITING_PATIENT_CHOICE",
            request_id="req-1",
            request_status="AWAITING_PATIENT_CHOICE",
            appointment_modality="PRESENCIAL",
            enabled_tool_names=[
                "select_proposed_slot",
                "reject_proposed_slots",
                "handoff_to_human",
            ],
        )
        result = builder.build_runtime_system_prompt(ctx, known_patient=None)
        assert "- modalidad_actual: PRESENCIAL" in result
        assert "select_proposed_slot" in result

    def test_collecting_confirmation_with_missing_fields(self) -> None:
        builder = _build_builder()
        ctx = agentic_state_models.RuntimePromptContext(
            state="COLLECTING_CONFIRMATION_DATA",
            request_id="req-1",
            request_status="AWAITING_PATIENT_CHOICE",
            selected_slot_id="slot-1",
            missing_confirmation_fields=["email", "age"],
            enabled_tool_names=["confirm_selected_slot_and_create_event"],
        )
        result = builder.build_runtime_system_prompt(ctx, known_patient=None)
        assert "- slot_seleccionado_actual: slot-1" in result
        # Avoid asserting on the verb "confirmar" because the state instruction
        # was deliberately rephrased to "Datos finales faltantes" to keep the
        # word "confirmar" out of the LLM's attention. See the comment in
        # state_instructions.py for the rationale (uses_pre_payment_vocabulary).
        assert "Datos finales faltantes:" in result
        assert "email" in result
        assert "age" in result

    def test_collecting_confirmation_no_missing_fields(self) -> None:
        builder = _build_builder()
        ctx = agentic_state_models.RuntimePromptContext(
            state="COLLECTING_CONFIRMATION_DATA",
            request_id="req-1",
            request_status="AWAITING_PATIENT_CHOICE",
            selected_slot_id="slot-1",
            enabled_tool_names=["confirm_selected_slot_and_create_event"],
        )
        result = builder.build_runtime_system_prompt(ctx, known_patient=None)
        # State instruction phrase was changed from "no faltan campos de perfil"
        # to "no faltan datos de perfil" to keep "confirmar" out of the prompt.
        assert "no faltan datos de perfil" in result
        assert "confirm_selected_slot_and_create_event" in result

    def test_awaiting_consultation_review(self) -> None:
        builder = _build_builder()
        ctx = agentic_state_models.RuntimePromptContext(
            state="AWAITING_CONSULTATION_REVIEW",
            request_id="req-1",
            request_status="AWAITING_CONSULTATION_REVIEW",
            enabled_tool_names=["handoff_to_human"],
        )
        result = builder.build_runtime_system_prompt(ctx, known_patient=None)
        # The assembler must emit a state instruction explaining the bot is
        # waiting on an internal step, but NOT one that the LLM would relay
        # verbatim to the patient (which used to leak as "ya envie tu motivo
        # a la doctora para revision"). We assert two things: the bot is
        # told to pause silently ("dame un momento"), and the explicit
        # prohibition on revealing internal handoff is present.
        assert "dame un momento" in result
        assert "La gestion interna es invisible" in result

    def test_awaiting_payment_confirmation(self) -> None:
        builder = _build_builder()
        ctx = agentic_state_models.RuntimePromptContext(
            state="AWAITING_PAYMENT_CONFIRMATION",
            request_id="req-1",
            request_status="AWAITING_PAYMENT_CONFIRMATION",
            enabled_tool_names=["handoff_to_human"],
        )
        result = builder.build_runtime_system_prompt(ctx, known_patient=None)
        assert "pago pendiente" in result
        assert "dame un momento" in result

    def test_post_booking_followup(self) -> None:
        builder = _build_builder()
        ctx = agentic_state_models.RuntimePromptContext(
            state="POST_BOOKING_FOLLOWUP",
            request_id="req-1",
            request_status="BOOKED",
            enabled_tool_names=["close_session", "handoff_to_human"],
        )
        result = builder.build_runtime_system_prompt(ctx, known_patient=None)
        assert "cita fue reservada exitosamente" in result
        assert "close_session" in result

    def test_post_booking_followup_presencial_includes_office_data_instruction(self) -> None:
        builder = _build_builder()
        ctx = agentic_state_models.RuntimePromptContext(
            state="POST_BOOKING_FOLLOWUP",
            request_id="req-1",
            request_status="BOOKED",
            appointment_modality="PRESENCIAL",
            enabled_tool_names=["close_session", "handoff_to_human"],
        )
        result = builder.build_runtime_system_prompt(ctx, known_patient=None)
        assert "PRESENCIAL" in result
        assert "Datos del consultorio" in result

    def test_post_booking_followup_virtual_includes_meet_instruction(self) -> None:
        builder = _build_builder()
        ctx = agentic_state_models.RuntimePromptContext(
            state="POST_BOOKING_FOLLOWUP",
            request_id="req-1",
            request_status="BOOKED",
            appointment_modality="VIRTUAL",
            enabled_tool_names=["close_session", "handoff_to_human"],
        )
        result = builder.build_runtime_system_prompt(ctx, known_patient=None)
        assert "VIRTUAL" in result
        assert "Meet" in result

    def test_post_booking_followup_grounds_llm_with_fecha_cita_and_locks_format(
        self,
    ) -> None:
        """Inject the booked datetime into the prompt and instruct the LLM to use
        it verbatim, so it can never paraphrase or invent the appointment date.
        """
        builder = _build_builder()
        ctx = agentic_state_models.RuntimePromptContext(
            state="POST_BOOKING_FOLLOWUP",
            request_id="req-1",
            request_status="BOOKED",
            appointment_modality="PRESENCIAL",
            appointment_start_at=datetime.datetime(2026, 5, 16, 14, 0, tzinfo=datetime.UTC),
            appointment_end_at=datetime.datetime(2026, 5, 16, 15, 0, tzinfo=datetime.UTC),
            patient_first_name="Danery",
            enabled_tool_names=["close_session", "handoff_to_human"],
        )
        result = builder.build_runtime_system_prompt(ctx, known_patient=None)
        assert "- fecha_cita: sabado 16 de mayo de 2026" in result
        assert "9:00 am" in result
        assert "10:00 am" in result
        assert "hora Colombia" in result
        assert "- nombre_paciente: Danery" in result
        assert "USA EXACTAMENTE el valor de `fecha_cita`" in result
        assert "FUENTE UNICA DE VERDAD" in result
        assert "NO inventes una direccion" in result

    def test_post_booking_followup_without_slot_data_warns_against_inventing(self) -> None:
        builder = _build_builder()
        ctx = agentic_state_models.RuntimePromptContext(
            state="POST_BOOKING_FOLLOWUP",
            request_id="req-1",
            request_status="BOOKED",
            enabled_tool_names=["close_session", "handoff_to_human"],
        )
        result = builder.build_runtime_system_prompt(ctx, known_patient=None)
        assert "fecha_cita" not in result.split("\n", 1)[0]
        assert "NO menciones fecha ni hora" in result
        assert "invitacion de Google Calendar" in result

    def test_compose_full_prompt(self) -> None:
        builder = _build_builder()
        ctx = agentic_state_models.RuntimePromptContext(
            state="NO_ACTIVE_REQUEST",
            enabled_tool_names=["set_contact_name"],
        )
        runtime = builder.build_runtime_system_prompt(ctx, known_patient=None)
        full = builder.compose_base_and_runtime_system_prompt("Base prompt", runtime)
        assert full.startswith("Base prompt")
        assert "### Runtime Context (Generated by Backend)" in full
        assert "INSTRUCCIONES RUNTIME" in full
