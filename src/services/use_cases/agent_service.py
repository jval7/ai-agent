import src.domain.entities.agent_profile as agent_profile_entity
import src.ports.agent_profile_repository_port as agent_profile_repository_port
import src.ports.clock_port as clock_port
import src.services.dto.agent_dto as agent_dto


def _office_location_to_dto(
    office_location: agent_profile_entity.OfficeLocation | None,
) -> agent_dto.OfficeLocationDTO | None:
    if office_location is None:
        return None
    return agent_dto.OfficeLocationDTO(
        address=office_location.address,
        arrival_instructions=office_location.arrival_instructions,
    )


def _office_location_dto_to_entity(
    dto: agent_dto.OfficeLocationDTO | None,
) -> agent_profile_entity.OfficeLocation | None:
    if dto is None:
        return None
    return agent_profile_entity.OfficeLocation(
        address=dto.address,
        arrival_instructions=dto.arrival_instructions,
    )


class AgentService:
    def __init__(
        self,
        agent_profile_repository: agent_profile_repository_port.AgentProfileRepositoryPort,
        clock: clock_port.ClockPort,
        default_system_prompt: str,
    ) -> None:
        self._agent_profile_repository = agent_profile_repository
        self._clock = clock
        self._default_system_prompt = default_system_prompt

    def get_system_prompt(self, tenant_id: str) -> agent_dto.SystemPromptResponseDTO:
        agent_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        if agent_profile is None:
            now_value = self._clock.now()
            agent_profile = agent_profile_entity.AgentProfile(
                tenant_id=tenant_id,
                system_prompt=self._default_system_prompt,
                updated_at=now_value,
            )
            self._agent_profile_repository.save(agent_profile)

        return agent_dto.SystemPromptResponseDTO(
            tenant_id=tenant_id,
            system_prompt=agent_profile.system_prompt,
        )

    def update_system_prompt(
        self, tenant_id: str, update_dto: agent_dto.UpdateSystemPromptDTO
    ) -> agent_dto.SystemPromptResponseDTO:
        now_value = self._clock.now()
        existing_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        agent_profile = agent_profile_entity.AgentProfile(
            tenant_id=tenant_id,
            system_prompt=update_dto.system_prompt,
            message_debounce_delay_seconds=(
                existing_profile.message_debounce_delay_seconds
                if existing_profile is not None
                else 0
            ),
            appointment_reminder_enabled=(
                existing_profile.appointment_reminder_enabled
                if existing_profile is not None
                else False
            ),
            appointment_reminder_days_before=(
                existing_profile.appointment_reminder_days_before
                if existing_profile is not None
                else None
            ),
            appointment_reminder_attendance_template_name=(
                existing_profile.appointment_reminder_attendance_template_name
                if existing_profile is not None
                else None
            ),
            appointment_reminder_payment_template_name=(
                existing_profile.appointment_reminder_payment_template_name
                if existing_profile is not None
                else None
            ),
            office_location=(
                existing_profile.office_location if existing_profile is not None else None
            ),
            virtual_session_instructions=(
                existing_profile.virtual_session_instructions
                if existing_profile is not None
                else None
            ),
            updated_at=now_value,
        )
        self._agent_profile_repository.save(agent_profile)
        return agent_dto.SystemPromptResponseDTO(
            tenant_id=tenant_id,
            system_prompt=agent_profile.system_prompt,
        )

    def get_agent_settings(self, tenant_id: str) -> agent_dto.AgentSettingsResponseDTO:
        agent_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        if agent_profile is None:
            return agent_dto.AgentSettingsResponseDTO(
                tenant_id=tenant_id,
                message_debounce_delay_seconds=0,
                appointment_reminder_enabled=False,
                appointment_reminder_days_before=None,
                appointment_reminder_attendance_template_name=None,
                appointment_reminder_payment_template_name=None,
                reminder_billing_test_phone_number=None,
                payment_details_text=None,
                office_location=None,
                virtual_session_instructions=None,
            )
        return agent_dto.AgentSettingsResponseDTO(
            tenant_id=tenant_id,
            message_debounce_delay_seconds=agent_profile.message_debounce_delay_seconds,
            appointment_reminder_enabled=agent_profile.appointment_reminder_enabled,
            appointment_reminder_days_before=agent_profile.appointment_reminder_days_before,
            appointment_reminder_attendance_template_name=agent_profile.appointment_reminder_attendance_template_name,
            appointment_reminder_payment_template_name=agent_profile.appointment_reminder_payment_template_name,
            reminder_billing_test_phone_number=agent_profile.reminder_billing_test_phone_number,
            payment_details_text=agent_profile.payment_details_text,
            office_location=_office_location_to_dto(agent_profile.office_location),
            virtual_session_instructions=agent_profile.virtual_session_instructions,
        )

    def update_agent_settings(
        self, tenant_id: str, update_dto: agent_dto.UpdateAgentSettingsDTO
    ) -> agent_dto.AgentSettingsResponseDTO:
        now_value = self._clock.now()
        existing_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        system_prompt = (
            existing_profile.system_prompt
            if existing_profile is not None
            else self._default_system_prompt
        )
        existing_billing_phone = (
            existing_profile.reminder_billing_test_phone_number
            if existing_profile is not None
            else None
        )
        agent_profile = agent_profile_entity.AgentProfile(
            tenant_id=tenant_id,
            system_prompt=system_prompt,
            message_debounce_delay_seconds=update_dto.message_debounce_delay_seconds,
            appointment_reminder_enabled=update_dto.appointment_reminder_enabled,
            appointment_reminder_days_before=update_dto.appointment_reminder_days_before,
            appointment_reminder_attendance_template_name=update_dto.appointment_reminder_attendance_template_name,
            appointment_reminder_payment_template_name=update_dto.appointment_reminder_payment_template_name,
            reminder_billing_test_phone_number=existing_billing_phone,
            payment_details_text=update_dto.payment_details_text,
            office_location=_office_location_dto_to_entity(update_dto.office_location),
            virtual_session_instructions=update_dto.virtual_session_instructions,
            updated_at=now_value,
        )
        self._agent_profile_repository.save(agent_profile)
        return agent_dto.AgentSettingsResponseDTO(
            tenant_id=tenant_id,
            message_debounce_delay_seconds=agent_profile.message_debounce_delay_seconds,
            appointment_reminder_enabled=agent_profile.appointment_reminder_enabled,
            appointment_reminder_days_before=agent_profile.appointment_reminder_days_before,
            appointment_reminder_attendance_template_name=agent_profile.appointment_reminder_attendance_template_name,
            appointment_reminder_payment_template_name=agent_profile.appointment_reminder_payment_template_name,
            reminder_billing_test_phone_number=agent_profile.reminder_billing_test_phone_number,
            payment_details_text=agent_profile.payment_details_text,
            office_location=_office_location_to_dto(agent_profile.office_location),
            virtual_session_instructions=agent_profile.virtual_session_instructions,
        )
