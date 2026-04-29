import datetime

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.services.dto.agent_dto as agent_dto
import src.services.use_cases.agent_service as agent_service
import tests.fakes.fake_adapters as fake_adapters


def build_agent_settings_service() -> agent_service.AgentService:
    store = in_memory_store.InMemoryStore()
    repository = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(store)
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    return agent_service.AgentService(
        agent_profile_repository=repository,
        clock=clock,
        default_system_prompt="default-prompt",
    )


def build_agent_service() -> agent_service.AgentService:
    store = in_memory_store.InMemoryStore()
    repository = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(store)
    clock = fake_adapters.FixedClock(datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    return agent_service.AgentService(
        agent_profile_repository=repository,
        clock=clock,
        default_system_prompt="default-prompt",
    )


def test_get_system_prompt_creates_default_if_missing() -> None:
    service = build_agent_service()

    result = service.get_system_prompt("tenant-1")

    assert result.tenant_id == "tenant-1"
    assert result.system_prompt == "default-prompt"


def test_update_system_prompt_replaces_value() -> None:
    service = build_agent_service()

    updated = service.update_system_prompt(
        "tenant-1",
        agent_dto.UpdateSystemPromptDTO(system_prompt="custom prompt"),
    )

    fetched = service.get_system_prompt("tenant-1")

    assert updated.system_prompt == "custom prompt"
    assert fetched.system_prompt == "custom prompt"


def test_update_agent_settings_saves_office_location() -> None:
    service = build_agent_settings_service()

    result = service.update_agent_settings(
        "tenant-1",
        agent_dto.UpdateAgentSettingsDTO(
            message_debounce_delay_seconds=5,
            office_location=agent_dto.OfficeLocationDTO(
                address="Calle 5 # 38-25, Cali",
                arrival_instructions="Llegar 20 minutos antes",
            ),
        ),
    )

    assert result.office_location is not None
    assert result.office_location.address == "Calle 5 # 38-25, Cali"
    assert result.office_location.arrival_instructions == "Llegar 20 minutos antes"


def test_get_agent_settings_returns_office_location_after_save() -> None:
    service = build_agent_settings_service()

    service.update_agent_settings(
        "tenant-1",
        agent_dto.UpdateAgentSettingsDTO(
            message_debounce_delay_seconds=0,
            office_location=agent_dto.OfficeLocationDTO(address="Carrera 1 # 2-3, Bogota"),
        ),
    )

    fetched = service.get_agent_settings("tenant-1")

    assert fetched.office_location is not None
    assert fetched.office_location.address == "Carrera 1 # 2-3, Bogota"
    assert fetched.office_location.arrival_instructions is None


def test_update_agent_settings_sanitizes_template_unsafe_chars() -> None:
    """payment_details_text and arrival_instructions go to WhatsApp templates,
    which reject \\n / \\t / 5+ spaces. Sanitize at write time so the UI shows
    the same text that gets sent."""
    service = build_agent_settings_service()

    result = service.update_agent_settings(
        "tenant-1",
        agent_dto.UpdateAgentSettingsDTO(
            message_debounce_delay_seconds=0,
            payment_details_text="Nequi:123\nZelle: 456",
            office_location=agent_dto.OfficeLocationDTO(
                address="Calle 5 # 38-25",
                arrival_instructions="Llegar 20 min antes\ncon cédula",
            ),
        ),
    )

    assert result.payment_details_text == "Nequi:123 · Zelle: 456"
    assert result.office_location is not None
    assert result.office_location.arrival_instructions == "Llegar 20 min antes · con cédula"


def test_update_agent_settings_office_location_none_clears_field() -> None:
    service = build_agent_settings_service()

    service.update_agent_settings(
        "tenant-1",
        agent_dto.UpdateAgentSettingsDTO(
            message_debounce_delay_seconds=0,
            office_location=agent_dto.OfficeLocationDTO(address="Carrera 1 # 2-3"),
        ),
    )
    result = service.update_agent_settings(
        "tenant-1",
        agent_dto.UpdateAgentSettingsDTO(
            message_debounce_delay_seconds=0,
            office_location=None,
        ),
    )

    assert result.office_location is None


def test_update_agent_settings_preserves_professional_profile_fields() -> None:
    """Regression: saving 'Datos del consultorio' must NOT wipe the structured
    form fields (identity, services, payment_methods, etc.). Earlier versions
    rebuilt the AgentProfile without passing those fields, leaving defaults
    that erased everything the professional had configured.
    """
    service = build_agent_service()

    # 1. Seed the professional profile (identity, services, payment_methods).
    service.update_professional_profile(
        "tenant-1",
        agent_dto.UpdateProfessionalProfileDTO(
            identity=agent_dto.AssistantIdentityDTO(
                assistant_name="Claudia",
                professional_title="Psic.",
                professional_name="Aleja",
            ),
            services=[
                agent_dto.ServiceOfferingDTO(
                    name="Consulta Adultos",
                    modalities=["PRESENCIAL"],
                    tariffs=[
                        agent_dto.TariffOptionDTO(
                            label="Sesión",
                            prices=[agent_dto.TariffPriceDTO(currency="COP", amount=130000)],
                        )
                    ],
                )
            ],
            payment_methods=[
                agent_dto.PaymentMethodDTO(currency="COP", method_name="Nequi", holder="Aleja")
            ],
        ),
    )

    # 2. Save settings that have nothing to do with the form (debounce delay).
    service.update_agent_settings(
        "tenant-1",
        agent_dto.UpdateAgentSettingsDTO(message_debounce_delay_seconds=2),
    )

    # 3. Structured fields must still be there.
    profile = service.get_professional_profile("tenant-1")
    assert profile.identity is not None
    assert profile.identity.assistant_name == "Claudia"
    assert profile.identity.professional_title == "Psic."
    assert profile.identity.professional_name == "Aleja"
    assert len(profile.services) == 1
    assert profile.services[0].name == "Consulta Adultos"
    assert len(profile.payment_methods) == 1
    assert profile.payment_methods[0].method_name == "Nequi"


# ---------------------------------------------------------------------------
# Professional profile tests
# ---------------------------------------------------------------------------


def test_get_professional_profile_returns_empty_dto_when_unset() -> None:
    service = build_agent_service()

    result = service.get_professional_profile("tenant-1")

    assert result.tenant_id == "tenant-1"
    assert result.identity is None
    assert result.professional_context is None
    assert result.services == []
    assert result.presencial_schedule == []
    assert result.virtual_schedule == []
    assert result.payment_methods == []


def test_update_professional_profile_persists_structured_fields() -> None:
    service = build_agent_service()

    update_dto = agent_dto.UpdateProfessionalProfileDTO(
        identity=agent_dto.AssistantIdentityDTO(
            assistant_name="Claudia",
            professional_title="Psicóloga",
            main_city="Cali",
        ),
        professional_context=agent_dto.ProfessionalContextDTO(
            approach="Enfoque humanista.",
            common_topics=["ansiedad", "duelo"],
        ),
        services=[
            agent_dto.ServiceOfferingDTO(
                name="Consulta Adultos",
                modalities=["PRESENCIAL"],
                tariffs=[
                    agent_dto.TariffOptionDTO(
                        label="Sesión",
                        prices=[agent_dto.TariffPriceDTO(currency="COP", amount=130000)],
                    )
                ],
            )
        ],
        presencial_schedule=[
            agent_dto.ScheduleBlockDTO(
                weekday_from="WED", weekday_to="FRI", start_time="08:00", end_time="16:00"
            )
        ],
        virtual_schedule=[
            agent_dto.ScheduleBlockDTO(
                weekday_from="MON", weekday_to="FRI", start_time="08:00", end_time="18:00"
            )
        ],
        payment_methods=[
            agent_dto.PaymentMethodDTO(
                currency="COP",
                method_name="Nequi",
                holder="Aleja",
                instructions="318-000-0000",
            )
        ],
    )

    service.update_professional_profile("tenant-1", update_dto)
    result = service.get_professional_profile("tenant-1")

    assert result.tenant_id == "tenant-1"
    assert result.identity is not None
    assert result.identity.assistant_name == "Claudia"
    assert result.identity.main_city == "Cali"
    assert result.professional_context is not None
    assert result.professional_context.approach == "Enfoque humanista."
    assert "ansiedad" in result.professional_context.common_topics
    assert len(result.services) == 1
    assert result.services[0].name == "Consulta Adultos"
    assert len(result.presencial_schedule) == 1
    assert result.presencial_schedule[0].weekday_from == "WED"
    assert len(result.virtual_schedule) == 1
    assert len(result.payment_methods) == 1
    assert result.payment_methods[0].method_name == "Nequi"


def test_update_professional_profile_regenerates_system_prompt_xml() -> None:
    service = build_agent_service()

    update_dto = agent_dto.UpdateProfessionalProfileDTO(
        identity=agent_dto.AssistantIdentityDTO(
            assistant_name="Bot",
            professional_title="Psicóloga",
        ),
    )

    service.update_professional_profile("tenant-1", update_dto)
    prompt_result = service.get_system_prompt("tenant-1")

    assert "<base_system_prompt>" in prompt_result.system_prompt
    assert "<style_rules>" in prompt_result.system_prompt
    assert "Bot" in prompt_result.system_prompt
    assert "</base_system_prompt>" in prompt_result.system_prompt


def test_update_professional_profile_preserves_office_location_and_reminders() -> None:
    service = build_agent_service()

    # First set settings (office_location, reminders, debounce)
    service.update_agent_settings(
        "tenant-1",
        agent_dto.UpdateAgentSettingsDTO(
            message_debounce_delay_seconds=10,
            payment_details_text="Nequi 318",
            office_location=agent_dto.OfficeLocationDTO(address="Calle 5 # 38-25, Cali"),
        ),
    )

    # Now update the professional profile
    service.update_professional_profile(
        "tenant-1",
        agent_dto.UpdateProfessionalProfileDTO(
            identity=agent_dto.AssistantIdentityDTO(assistant_name="Claudia"),
        ),
    )

    # Agent settings should be unchanged
    settings = service.get_agent_settings("tenant-1")
    assert settings.message_debounce_delay_seconds == 10
    assert settings.payment_details_text == "Nequi 318"
    assert settings.office_location is not None
    assert settings.office_location.address == "Calle 5 # 38-25, Cali"


# ---------------------------------------------------------------------------
# payment_timing tests
# ---------------------------------------------------------------------------


def test_update_agent_settings_payment_timing_default_is_before_session() -> None:
    service = build_agent_settings_service()

    result = service.update_agent_settings(
        "tenant-1",
        agent_dto.UpdateAgentSettingsDTO(message_debounce_delay_seconds=0),
    )

    assert result.payment_timing == "BEFORE_SESSION"


def test_update_agent_settings_payment_timing_after_session_roundtrip() -> None:
    service = build_agent_settings_service()

    result = service.update_agent_settings(
        "tenant-1",
        agent_dto.UpdateAgentSettingsDTO(
            message_debounce_delay_seconds=0,
            payment_timing="AFTER_SESSION",
        ),
    )

    assert result.payment_timing == "AFTER_SESSION"
    fetched = service.get_agent_settings("tenant-1")
    assert fetched.payment_timing == "AFTER_SESSION"


def test_get_agent_settings_returns_default_payment_timing_when_no_profile() -> None:
    service = build_agent_settings_service()

    result = service.get_agent_settings("tenant-1")

    assert result.payment_timing == "BEFORE_SESSION"
