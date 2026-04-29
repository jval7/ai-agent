import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.whatsapp_template_params as whatsapp_template_params
import src.ports.agent_profile_repository_port as agent_profile_repository_port
import src.ports.clock_port as clock_port
import src.services.agentic.prompts.professional_profile_xml_renderer as xml_renderer
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
    # Sanitize fields that travel verbatim into a WhatsApp template parameter
    # so what the professional sees in the UI matches what gets sent.
    sanitized_arrival = (
        whatsapp_template_params.sanitize_template_param(dto.arrival_instructions)
        if dto.arrival_instructions is not None
        else None
    )
    return agent_profile_entity.OfficeLocation(
        address=dto.address,
        arrival_instructions=sanitized_arrival or None,
    )


def _sanitize_payment_details(value: str | None) -> str | None:
    if value is None:
        return None
    sanitized = whatsapp_template_params.sanitize_template_param(value)
    return sanitized or None


# ---------------------------------------------------------------------------
# Professional Profile mapping helpers
# ---------------------------------------------------------------------------


def _identity_to_dto(
    identity: agent_profile_entity.AssistantIdentity | None,
) -> agent_dto.AssistantIdentityDTO | None:
    if identity is None:
        return None
    return agent_dto.AssistantIdentityDTO(
        assistant_name=identity.assistant_name,
        professional_title=identity.professional_title,
        professional_name=identity.professional_name,
        professional_address_term=identity.professional_address_term,
        main_city=identity.main_city,
        tone=identity.tone,
        languages=list(identity.languages),
    )


def _identity_dto_to_entity(
    dto: agent_dto.AssistantIdentityDTO | None,
) -> agent_profile_entity.AssistantIdentity | None:
    if dto is None:
        return None
    return agent_profile_entity.AssistantIdentity(
        assistant_name=dto.assistant_name,
        professional_title=dto.professional_title,
        professional_name=dto.professional_name,
        professional_address_term=dto.professional_address_term,
        main_city=dto.main_city,
        tone=dto.tone,
        languages=list(dto.languages),
    )


def _professional_context_to_dto(
    ctx: agent_profile_entity.ProfessionalContext | None,
) -> agent_dto.ProfessionalContextDTO | None:
    if ctx is None:
        return None
    return agent_dto.ProfessionalContextDTO(
        approach=ctx.approach,
        common_topics=list(ctx.common_topics),
        services_not_offered=list(ctx.services_not_offered),
        coverage_notes=ctx.coverage_notes,
    )


def _professional_context_dto_to_entity(
    dto: agent_dto.ProfessionalContextDTO | None,
) -> agent_profile_entity.ProfessionalContext | None:
    if dto is None:
        return None
    return agent_profile_entity.ProfessionalContext(
        approach=dto.approach,
        common_topics=list(dto.common_topics),
        services_not_offered=list(dto.services_not_offered),
        coverage_notes=dto.coverage_notes,
    )


def _tariff_to_dto(t: agent_profile_entity.TariffOption) -> agent_dto.TariffOptionDTO:
    return agent_dto.TariffOptionDTO(
        label=t.label,
        description=t.description,
        prices=[agent_dto.TariffPriceDTO(currency=p.currency, amount=p.amount) for p in t.prices],
    )


def _tariff_dto_to_entity(dto: agent_dto.TariffOptionDTO) -> agent_profile_entity.TariffOption:
    return agent_profile_entity.TariffOption(
        label=dto.label,
        description=dto.description,
        prices=[
            agent_profile_entity.TariffPrice(currency=p.currency, amount=p.amount)
            for p in dto.prices
        ],
    )


def _service_offering_to_dto(
    svc: agent_profile_entity.ServiceOffering,
) -> agent_dto.ServiceOfferingDTO:
    return agent_dto.ServiceOfferingDTO(
        name=svc.name,
        description=svc.description,
        modalities=list(svc.modalities),
        tariffs=[_tariff_to_dto(t) for t in svc.tariffs],
    )


def _service_offering_dto_to_entity(
    dto: agent_dto.ServiceOfferingDTO,
) -> agent_profile_entity.ServiceOffering:
    return agent_profile_entity.ServiceOffering(
        name=dto.name,
        description=dto.description,
        modalities=list(dto.modalities),
        tariffs=[_tariff_dto_to_entity(t) for t in dto.tariffs],
    )


def _schedule_block_to_dto(
    block: agent_profile_entity.ScheduleBlock,
) -> agent_dto.ScheduleBlockDTO:
    return agent_dto.ScheduleBlockDTO(
        weekday_from=block.weekday_from,
        weekday_to=block.weekday_to,
        start_time=block.start_time,
        end_time=block.end_time,
    )


def _schedule_block_dto_to_entity(
    dto: agent_dto.ScheduleBlockDTO,
) -> agent_profile_entity.ScheduleBlock:
    return agent_profile_entity.ScheduleBlock(
        weekday_from=dto.weekday_from,
        weekday_to=dto.weekday_to,
        start_time=dto.start_time,
        end_time=dto.end_time,
    )


def _payment_method_to_dto(pm: agent_profile_entity.PaymentMethod) -> agent_dto.PaymentMethodDTO:
    return agent_dto.PaymentMethodDTO(
        currency=pm.currency,
        method_name=pm.method_name,
        holder=pm.holder,
        instructions=pm.instructions,
        applies_when=pm.applies_when,
    )


def _payment_method_dto_to_entity(
    dto: agent_dto.PaymentMethodDTO,
) -> agent_profile_entity.PaymentMethod:
    return agent_profile_entity.PaymentMethod(
        currency=dto.currency,
        method_name=dto.method_name,
        holder=dto.holder,
        instructions=dto.instructions,
        applies_when=dto.applies_when,
    )


def _professional_profile_to_dto(
    tenant_id: str,
    profile: agent_profile_entity.AgentProfile,
) -> agent_dto.ProfessionalProfileResponseDTO:
    return agent_dto.ProfessionalProfileResponseDTO(
        tenant_id=tenant_id,
        identity=_identity_to_dto(profile.identity),
        professional_context=_professional_context_to_dto(profile.professional_context),
        services=[_service_offering_to_dto(s) for s in profile.services],
        presencial_schedule=[_schedule_block_to_dto(b) for b in profile.presencial_schedule],
        virtual_schedule=[_schedule_block_to_dto(b) for b in profile.virtual_schedule],
        payment_methods=[_payment_method_to_dto(pm) for pm in profile.payment_methods],
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

        # Always regenerate from structured fields when they exist so the dev
        # preview reflects the live renderer output (no stale audience/category
        # blocks from before the schema migration).
        return agent_dto.SystemPromptResponseDTO(
            tenant_id=tenant_id,
            system_prompt=xml_renderer.effective_system_prompt(agent_profile),
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
            payment_timing=(
                existing_profile.payment_timing
                if existing_profile is not None
                else "BEFORE_SESSION"
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
                payment_details_text=None,
                office_location=None,
                payment_timing="BEFORE_SESSION",
            )
        return agent_dto.AgentSettingsResponseDTO(
            tenant_id=tenant_id,
            message_debounce_delay_seconds=agent_profile.message_debounce_delay_seconds,
            appointment_reminder_enabled=agent_profile.appointment_reminder_enabled,
            appointment_reminder_days_before=agent_profile.appointment_reminder_days_before,
            appointment_reminder_attendance_template_name=agent_profile.appointment_reminder_attendance_template_name,
            appointment_reminder_payment_template_name=agent_profile.appointment_reminder_payment_template_name,
            payment_details_text=agent_profile.payment_details_text,
            office_location=_office_location_to_dto(agent_profile.office_location),
            payment_timing=agent_profile.payment_timing,
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
        agent_profile = agent_profile_entity.AgentProfile(
            tenant_id=tenant_id,
            system_prompt=system_prompt,
            message_debounce_delay_seconds=update_dto.message_debounce_delay_seconds,
            appointment_reminder_enabled=update_dto.appointment_reminder_enabled,
            appointment_reminder_days_before=update_dto.appointment_reminder_days_before,
            appointment_reminder_attendance_template_name=update_dto.appointment_reminder_attendance_template_name,
            appointment_reminder_payment_template_name=update_dto.appointment_reminder_payment_template_name,
            payment_details_text=_sanitize_payment_details(update_dto.payment_details_text),
            office_location=_office_location_dto_to_entity(update_dto.office_location),
            payment_timing=update_dto.payment_timing,
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
            payment_details_text=agent_profile.payment_details_text,
            office_location=_office_location_to_dto(agent_profile.office_location),
            payment_timing=agent_profile.payment_timing,
        )

    def get_professional_profile(self, tenant_id: str) -> agent_dto.ProfessionalProfileResponseDTO:
        agent_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        if agent_profile is None:
            return agent_dto.ProfessionalProfileResponseDTO(tenant_id=tenant_id)
        return _professional_profile_to_dto(tenant_id, agent_profile)

    def update_professional_profile(
        self, tenant_id: str, update_dto: agent_dto.UpdateProfessionalProfileDTO
    ) -> agent_dto.ProfessionalProfileResponseDTO:
        now_value = self._clock.now()
        existing_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)

        # Preserve non-touched fields
        base = (
            existing_profile
            if existing_profile is not None
            else agent_profile_entity.AgentProfile(
                tenant_id=tenant_id,
                system_prompt="",
                updated_at=now_value,
            )
        )

        updated_profile = agent_profile_entity.AgentProfile(
            tenant_id=tenant_id,
            system_prompt="",  # will be overwritten below
            message_debounce_delay_seconds=base.message_debounce_delay_seconds,
            appointment_reminder_enabled=base.appointment_reminder_enabled,
            appointment_reminder_days_before=base.appointment_reminder_days_before,
            appointment_reminder_attendance_template_name=base.appointment_reminder_attendance_template_name,
            appointment_reminder_payment_template_name=base.appointment_reminder_payment_template_name,
            payment_details_text=base.payment_details_text,
            office_location=base.office_location,
            identity=_identity_dto_to_entity(update_dto.identity),
            professional_context=_professional_context_dto_to_entity(
                update_dto.professional_context
            ),
            services=[_service_offering_dto_to_entity(s) for s in update_dto.services],
            presencial_schedule=[
                _schedule_block_dto_to_entity(b) for b in update_dto.presencial_schedule
            ],
            virtual_schedule=[
                _schedule_block_dto_to_entity(b) for b in update_dto.virtual_schedule
            ],
            payment_methods=[
                _payment_method_dto_to_entity(pm) for pm in update_dto.payment_methods
            ],
            updated_at=now_value,
        )

        rendered_xml = xml_renderer.render_system_prompt_xml(updated_profile)
        updated_profile = updated_profile.model_copy(update={"system_prompt": rendered_xml})

        self._agent_profile_repository.save(updated_profile)
        return _professional_profile_to_dto(tenant_id, updated_profile)
