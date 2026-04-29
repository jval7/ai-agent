import datetime

import src.domain.entities.agent_profile as agent_profile_entity
import src.services.agentic.prompts.professional_profile_xml_renderer as renderer
import src.services.agentic.prompts.style_rules_template as style_rules_template


def _empty_profile() -> agent_profile_entity.AgentProfile:
    return agent_profile_entity.AgentProfile(
        tenant_id="t-1",
        updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
    )


def _full_profile() -> agent_profile_entity.AgentProfile:
    return agent_profile_entity.AgentProfile(
        tenant_id="t-1",
        identity=agent_profile_entity.AssistantIdentity(
            assistant_name="Claudia",
            professional_title="Psicóloga Aleja Escobar",
            professional_address_term="la Doc",
            main_city="Cali",
            tone="Profesional y cálida.",
            languages=["español"],
        ),
        professional_context=agent_profile_entity.ProfessionalContext(
            approach="Enfoque humanista e integral.",
            common_topics=["ansiedad", "duelo"],
            services_not_offered=["terapia de pareja"],
            coverage_notes="Atiende Colombia y exterior.",
        ),
        services=[
            agent_profile_entity.ServiceOffering(
                name="Consulta Individual Adultos",
                modalities=["PRESENCIAL", "VIRTUAL"],
                tariffs=[
                    agent_profile_entity.TariffOption(
                        label="Sesión individual",
                        prices=[
                            agent_profile_entity.TariffPrice(currency="COP", amount=130000),
                            agent_profile_entity.TariffPrice(currency="USD", amount=90),
                        ],
                    ),
                    agent_profile_entity.TariffOption(
                        label="Paquete 3 sesiones",
                        description="5% descuento",
                        prices=[
                            agent_profile_entity.TariffPrice(currency="COP", amount=370500),
                            agent_profile_entity.TariffPrice(currency="USD", amount=257),
                        ],
                    ),
                ],
            ),
        ],
        presencial_schedule=[
            agent_profile_entity.ScheduleBlock(
                weekday_from="WED", weekday_to="FRI", start_time="08:00", end_time="16:00"
            ),
            agent_profile_entity.ScheduleBlock(
                weekday_from="SAT", start_time="08:00", end_time="12:00"
            ),
        ],
        virtual_schedule=[
            agent_profile_entity.ScheduleBlock(
                weekday_from="MON", weekday_to="FRI", start_time="08:00", end_time="18:00"
            ),
        ],
        payment_methods=[
            agent_profile_entity.PaymentMethod(
                currency="COP",
                method_name="Nequi",
                holder="Alejandra Escobar",
                instructions="318 732 6409",
                applies_when="Colombia (COP)",
            ),
            agent_profile_entity.PaymentMethod(
                currency="USD",
                method_name="Zelle",
                holder="Nelson",
                instructions="7867673701",
                applies_when="Extranjeros (USD)",
            ),
        ],
        updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
    )


class TestRendererMinimum:
    def test_always_wraps_in_base_system_prompt(self) -> None:
        result = renderer.render_system_prompt_xml(_empty_profile())
        assert result.startswith("<base_system_prompt>")
        assert result.strip().endswith("</base_system_prompt>")

    def test_always_includes_style_rules(self) -> None:
        profile = _empty_profile()
        result = renderer.render_system_prompt_xml(profile)
        expected_rules = style_rules_template.build_style_rules_xml(profile.identity)
        assert expected_rules in result

    def test_style_rules_use_neutral_reference_when_address_term_missing(self) -> None:
        # Empty profile has no identity → style rules must fall back to the
        # neutral "la profesional" and never leak hardcoded names.
        result = renderer.render_system_prompt_xml(_empty_profile())
        assert "la profesional" in result
        assert "Aleja" not in result
        assert "la Doc" not in result

    def test_style_rules_use_address_term_when_provided(self) -> None:
        # Full profile has professional_address_term="la Doc" → both
        # parameterized rules render with that exact term.
        result = renderer.render_system_prompt_xml(_full_profile())
        assert "la Doc" in result

    def test_no_extra_sections_when_all_fields_empty(self) -> None:
        result = renderer.render_system_prompt_xml(_empty_profile())
        assert "<identity>" not in result
        assert "<professional_context>" not in result
        assert "<services>" not in result
        assert "<payment_info>" not in result


class TestRendererSectionOmission:
    def test_omits_identity_when_not_set(self) -> None:
        profile = agent_profile_entity.AgentProfile(
            tenant_id="t-1",
            professional_context=agent_profile_entity.ProfessionalContext(approach="Enfoque A"),
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
        result = renderer.render_system_prompt_xml(profile)
        assert "<identity>" not in result
        assert "<professional_context>" in result

    def test_omits_services_when_list_empty(self) -> None:
        profile = agent_profile_entity.AgentProfile(
            tenant_id="t-1",
            identity=agent_profile_entity.AssistantIdentity(assistant_name="Bot"),
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
        result = renderer.render_system_prompt_xml(profile)
        assert "<services>" not in result

    def test_omits_payment_info_when_list_empty(self) -> None:
        result = renderer.render_system_prompt_xml(_empty_profile())
        assert "<payment_info>" not in result

    def test_omits_professional_context_when_all_context_fields_empty(self) -> None:
        profile = agent_profile_entity.AgentProfile(
            tenant_id="t-1",
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
        result = renderer.render_system_prompt_xml(profile)
        assert "<professional_context>" not in result


class TestRendererFullProfile:
    def test_full_profile_contains_all_section_tags(self) -> None:
        result = renderer.render_system_prompt_xml(_full_profile())
        assert "<identity>" in result
        assert "<professional_context>" in result
        assert "<services>" in result
        assert "<payment_info>" in result

    def test_full_profile_contains_identity_fields(self) -> None:
        result = renderer.render_system_prompt_xml(_full_profile())
        assert "Claudia" in result
        assert "Cali" in result
        assert "Profesional y cálida" in result

    def test_full_profile_contains_professional_context_items(self) -> None:
        result = renderer.render_system_prompt_xml(_full_profile())
        assert "Enfoque humanista" in result
        assert "ansiedad" in result
        assert "duelo" in result

    def test_full_profile_contains_service_name(self) -> None:
        result = renderer.render_system_prompt_xml(_full_profile())
        assert "Consulta Individual Adultos" in result

    def test_full_profile_contains_local_tariff(self) -> None:
        result = renderer.render_system_prompt_xml(_full_profile())
        assert "130,000 COP" in result

    def test_full_profile_contains_foreign_tariff(self) -> None:
        result = renderer.render_system_prompt_xml(_full_profile())
        assert "90 USD" in result

    def test_full_profile_contains_payment_methods(self) -> None:
        result = renderer.render_system_prompt_xml(_full_profile())
        assert "Nequi" in result
        assert "Zelle" in result


class TestRendererScheduleFormat:
    def test_range_weekday_schedule_formats_correctly(self) -> None:
        profile = agent_profile_entity.AgentProfile(
            tenant_id="t-1",
            presencial_schedule=[
                agent_profile_entity.ScheduleBlock(
                    weekday_from="WED", weekday_to="FRI", start_time="08:00", end_time="16:00"
                )
            ],
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
        result = renderer.render_system_prompt_xml(profile)
        assert "Miércoles a Viernes de 8am a 4pm" in result

    def test_single_weekday_schedule_formats_correctly(self) -> None:
        profile = agent_profile_entity.AgentProfile(
            tenant_id="t-1",
            virtual_schedule=[
                agent_profile_entity.ScheduleBlock(
                    weekday_from="SAT", start_time="08:00", end_time="12:00"
                )
            ],
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
        result = renderer.render_system_prompt_xml(profile)
        assert "Sábados de 8am a 12pm" in result

    def test_time_with_minutes_formats_correctly(self) -> None:
        profile = agent_profile_entity.AgentProfile(
            tenant_id="t-1",
            presencial_schedule=[
                agent_profile_entity.ScheduleBlock(
                    weekday_from="MON", start_time="09:30", end_time="17:45"
                )
            ],
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
        result = renderer.render_system_prompt_xml(profile)
        assert "9:30am" in result
        assert "5:45pm" in result

    def test_presencial_and_virtual_schedules_labeled_separately(self) -> None:
        profile = agent_profile_entity.AgentProfile(
            tenant_id="t-1",
            presencial_schedule=[
                agent_profile_entity.ScheduleBlock(
                    weekday_from="WED", weekday_to="FRI", start_time="08:00", end_time="16:00"
                )
            ],
            virtual_schedule=[
                agent_profile_entity.ScheduleBlock(
                    weekday_from="MON", weekday_to="FRI", start_time="08:00", end_time="18:00"
                )
            ],
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
        result = renderer.render_system_prompt_xml(profile)
        assert "Horario Presencial" in result
        assert "Horario Virtual" in result


class TestRendererPaymentMethods:
    def test_multiple_currencies_rendered(self) -> None:
        profile = agent_profile_entity.AgentProfile(
            tenant_id="t-1",
            payment_methods=[
                agent_profile_entity.PaymentMethod(
                    currency="COP",
                    method_name="Nequi",
                    holder="Aleja",
                    instructions="318-000-0000",
                    applies_when="Colombia (COP)",
                ),
                agent_profile_entity.PaymentMethod(
                    currency="USD",
                    method_name="Zelle",
                    holder="Nelson",
                    instructions="786-000-0000",
                    applies_when="Extranjeros (USD)",
                ),
            ],
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
        result = renderer.render_system_prompt_xml(profile)
        # New explicit-tag format: each field gets its own nested tag.
        assert "<method_name>Nequi</method_name>" in result
        assert "<method_name>Zelle</method_name>" in result
        assert "<use_when>Colombia (COP)</use_when>" in result
        assert "<use_when>Extranjeros (USD)</use_when>" in result
        assert "<account_holder>Aleja</account_holder>" in result
        assert "<account_holder>Nelson</account_holder>" in result
        assert "<account_details>318-000-0000</account_details>" in result
        assert "<account_details>786-000-0000</account_details>" in result


class TestRendererUnifiedTariffs:
    def test_tariff_emits_one_price_tag_per_currency(self) -> None:
        # New schema: each tariff carries a `prices` list. Renderer emits one
        # <price_xxx> tag per currency, derived from the currency code.
        profile = agent_profile_entity.AgentProfile(
            tenant_id="t-1",
            services=[
                agent_profile_entity.ServiceOffering(
                    name="Adultos",
                    tariffs=[
                        agent_profile_entity.TariffOption(
                            label="Sesión",
                            prices=[
                                agent_profile_entity.TariffPrice(currency="COP", amount=130000),
                                agent_profile_entity.TariffPrice(currency="USD", amount=90),
                            ],
                        ),
                    ],
                )
            ],
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
        result = renderer.render_system_prompt_xml(profile)
        assert "<label>Sesión</label>" in result
        assert "<price_cop>130,000 COP</price_cop>" in result
        assert "<price_usd>90 USD</price_usd>" in result

    def test_tariff_description_is_emitted_when_set(self) -> None:
        profile = agent_profile_entity.AgentProfile(
            tenant_id="t-1",
            services=[
                agent_profile_entity.ServiceOffering(
                    name="Adultos",
                    tariffs=[
                        agent_profile_entity.TariffOption(
                            label="Paquete 3",
                            description="5% descuento",
                            prices=[
                                agent_profile_entity.TariffPrice(currency="COP", amount=370500)
                            ],
                        )
                    ],
                )
            ],
            updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
        result = renderer.render_system_prompt_xml(profile)
        assert "<description>5% descuento</description>" in result

    def test_legacy_split_tariffs_are_migrated_on_read(self) -> None:
        # Pre-existing Firestore data may have `tariffs_local` and
        # `tariffs_foreign`. The model validator merges them into `tariffs`.
        legacy_dict = {
            "name": "Adultos",
            "tariffs_local": [{"label": "Local", "amount": 100, "currency": "COP"}],
            "tariffs_foreign": [{"label": "Foreign", "amount": 90, "currency": "USD"}],
        }
        svc = agent_profile_entity.ServiceOffering.model_validate(legacy_dict)
        assert len(svc.tariffs) == 2
        # Legacy {currency, amount} is also wrapped into prices: [{...}].
        assert svc.tariffs[0].prices[0].currency == "COP"
        assert svc.tariffs[0].prices[0].amount == 100
        assert svc.tariffs[1].prices[0].currency == "USD"

    def test_legacy_discount_percent_is_migrated_to_description(self) -> None:
        legacy_tariff = {
            "label": "Paquete",
            "amount": 100,
            "currency": "COP",
            "discount_percent": 5,
        }
        tariff = agent_profile_entity.TariffOption.model_validate(legacy_tariff)
        assert tariff.description == "5% descuento"
        # And the legacy {currency, amount} should have been wrapped.
        assert tariff.prices[0].currency == "COP"
        assert tariff.prices[0].amount == 100

    def test_legacy_audience_is_dropped_silently(self) -> None:
        legacy_dict = {"name": "Adultos", "audience": "should disappear"}
        svc = agent_profile_entity.ServiceOffering.model_validate(legacy_dict)
        assert svc.name == "Adultos"
        # `audience` no longer exists on the model: not in serialized output.
        assert "audience" not in svc.model_dump()
