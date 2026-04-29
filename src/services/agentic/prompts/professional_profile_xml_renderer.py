"""Pure function that renders an AgentProfile into the XML system prompt string.

The output is consumed verbatim by the LLM at runtime via
RuntimePromptBuilder.compose_base_and_runtime_system_prompt().

Design decisions:
- Sections are omitted entirely when the corresponding fields are empty.
- style_rules are always included regardless of form completion state.
- schedule blocks are formatted as human-readable Spanish text.
- Foreign tariffs block is emitted only when tariffs_foreign is non-empty.
"""

import src.domain.entities.agent_profile as agent_profile_entity
import src.services.agentic.prompts.style_rules_template as style_rules_template

_WEEKDAY_LABELS: dict[str, str] = {
    "MON": "Lunes",
    "TUE": "Martes",
    "WED": "Miércoles",
    "THU": "Jueves",
    "FRI": "Viernes",
    "SAT": "Sábados",
    "SUN": "Domingos",
}


def _format_time(time_str: str) -> str:
    """Convert "HH:MM" 24h to a human-readable label like "8am" or "4:30pm"."""
    hour_str, minute_str = time_str.split(":")
    hour = int(hour_str)
    minute = int(minute_str)
    suffix = "am" if hour < 12 else "pm"
    display_hour = hour if hour <= 12 else hour - 12
    if display_hour == 0:
        display_hour = 12
    if minute == 0:
        return f"{display_hour}{suffix}"
    return f"{display_hour}:{minute_str}{suffix}"


def _format_schedule_block(block: agent_profile_entity.ScheduleBlock) -> str:
    """Return a Spanish sentence like 'Miércoles a Viernes de 8am a 4pm'."""
    from_label = _WEEKDAY_LABELS.get(block.weekday_from, block.weekday_from)
    start = _format_time(block.start_time)
    end = _format_time(block.end_time)
    if block.weekday_to is not None and block.weekday_to != block.weekday_from:
        to_label = _WEEKDAY_LABELS.get(block.weekday_to, block.weekday_to)
        return f"{from_label} a {to_label} de {start} a {end}"
    return f"{from_label} de {start} a {end}"


def _render_identity(identity: agent_profile_entity.AssistantIdentity) -> str:
    parts: list[str] = []
    if identity.assistant_name or identity.professional_title or identity.main_city:
        role_parts: list[str] = []
        if identity.assistant_name:
            role_parts.append(identity.assistant_name)
        if identity.professional_title:
            role_parts.append(f"la asistente virtual de WhatsApp de {identity.professional_title}")
        if identity.main_city:
            role_parts.append(f"({identity.main_city})")
        parts.append(f"<assistant_role>{' '.join(role_parts)}</assistant_role>")
    if identity.tone:
        parts.append(f"<tone>{identity.tone}</tone>")
    if not parts:
        return ""
    return "<identity>\n" + "\n".join(parts) + "\n</identity>"


def _render_professional_context(
    context: agent_profile_entity.ProfessionalContext | None,
    presencial_schedule: list[agent_profile_entity.ScheduleBlock],
    virtual_schedule: list[agent_profile_entity.ScheduleBlock],
    identity: agent_profile_entity.AssistantIdentity | None,
) -> str:
    items: list[str] = []

    if context is not None:
        if context.approach:
            items.append(f"<item>{context.approach}</item>")
        for topic in context.common_topics:
            stripped = topic.strip()
            if stripped:
                items.append(f"<item>{stripped}</item>")
        if context.coverage_notes:
            items.append(f"<item>{context.coverage_notes}</item>")

    # Languages from identity
    if identity is not None and identity.languages:
        langs = ", ".join(identity.languages)
        items.append(f"<item>Idiomas: {langs}.</item>")

    # Schedules
    if presencial_schedule:
        schedule_text = ", ".join(_format_schedule_block(b) for b in presencial_schedule)
        items.append(f"<item>Horario Presencial: {schedule_text}</item>")
    if virtual_schedule:
        schedule_text = ", ".join(_format_schedule_block(b) for b in virtual_schedule)
        items.append(f"<item>Horario Virtual: {schedule_text}</item>")

    if not items:
        return ""
    return "<professional_context>\n" + "\n".join(items) + "\n</professional_context>"


def _render_tariff_option(tariff: agent_profile_entity.TariffOption) -> str:
    amount_formatted = (
        f"{tariff.amount:,.0f}" if tariff.amount == int(tariff.amount) else f"{tariff.amount:,.2f}"
    )
    text = f"{tariff.label}: {amount_formatted} {tariff.currency}"
    if tariff.discount_percent is not None:
        text += f" ({tariff.discount_percent:.0f}% off)"
    return f"<option>{text}</option>"


def _render_services(services: list[agent_profile_entity.ServiceOffering]) -> str:
    service_blocks: list[str] = []
    for svc in services:
        if not svc.name and not svc.description:
            continue
        lines: list[str] = []
        if svc.name:
            lines.append(f"<name>{svc.name}</name>")
        if svc.audience:
            lines.append(f"<audience>{svc.audience}</audience>")
        if svc.modalities:
            modalities_text = " y ".join(m.capitalize() for m in svc.modalities)
            lines.append(f"<modalities>{modalities_text}</modalities>")
        if svc.description:
            lines.append(f"<description>{svc.description}</description>")

        # Pricing
        pricing_parts: list[str] = []
        if svc.tariffs_local:
            local_currency = svc.tariffs_local[0].currency if svc.tariffs_local else ""
            category_name = f"{svc.name or 'Servicio'} ({local_currency})"
            options = "\n".join(_render_tariff_option(t) for t in svc.tariffs_local)
            pricing_parts.append(f'<category name="{category_name}">\n{options}\n</category>')
        if svc.tariffs_foreign:
            foreign_currency = svc.tariffs_foreign[0].currency if svc.tariffs_foreign else "USD"
            category_name = (
                f"Pacientes extranjeros - solo si está fuera de Colombia ({foreign_currency})"
            )
            options = "\n".join(_render_tariff_option(t) for t in svc.tariffs_foreign)
            pricing_parts.append(f'<category name="{category_name}">\n{options}\n</category>')

        if pricing_parts:
            lines.append("<pricing>\n" + "\n".join(pricing_parts) + "\n</pricing>")

        service_blocks.append("<service>\n" + "\n".join(lines) + "\n</service>")

    if not service_blocks:
        return ""
    return "<services>\n" + "\n".join(service_blocks) + "\n</services>"


def _render_payment_info(payment_methods: list[agent_profile_entity.PaymentMethod]) -> str:
    """Render payment methods with explicit nested tags per field.

    Each <method> bundles a <use_when> (when this method applies),
    <method_name> (e.g. "Nequi"), <account_holder>, and <account_details>
    (number / instructions). Tags are emitted only when the corresponding
    field is non-empty so the LLM doesn't see blank slots.
    """
    if not payment_methods:
        return ""
    methods: list[str] = []
    for pm in payment_methods:
        inner: list[str] = []
        use_when = pm.applies_when or pm.currency
        if use_when:
            inner.append(f"<use_when>{use_when}</use_when>")
        if pm.method_name:
            inner.append(f"<method_name>{pm.method_name}</method_name>")
        if pm.holder:
            inner.append(f"<account_holder>{pm.holder}</account_holder>")
        if pm.instructions:
            inner.append(f"<account_details>{pm.instructions}</account_details>")
        if not inner:
            continue
        methods.append("<method>\n" + "\n".join(inner) + "\n</method>")
    if not methods:
        return ""
    return "<payment_info>\n" + "\n".join(methods) + "\n</payment_info>"


def render_system_prompt_xml(profile: agent_profile_entity.AgentProfile) -> str:
    """Render the structured AgentProfile fields into the XML system prompt string.

    Always includes <base_system_prompt> wrapper and <style_rules>.
    All other sections are omitted when their fields are empty.
    """
    sections: list[str] = []
    sections.append("<base_system_prompt>")
    sections.append(style_rules_template.build_style_rules_xml(profile.identity))

    # Identity
    if profile.identity is not None:
        rendered = _render_identity(profile.identity)
        if rendered:
            sections.append(rendered)

    # Professional context (includes schedule and languages)
    context_rendered = _render_professional_context(
        context=profile.professional_context,
        presencial_schedule=profile.presencial_schedule,
        virtual_schedule=profile.virtual_schedule,
        identity=profile.identity,
    )
    if context_rendered:
        sections.append(context_rendered)

    # Services
    if profile.services:
        rendered = _render_services(profile.services)
        if rendered:
            sections.append(rendered)

    # Payment methods
    if profile.payment_methods:
        rendered = _render_payment_info(profile.payment_methods)
        if rendered:
            sections.append(rendered)

    sections.append("</base_system_prompt>")
    return "\n".join(sections)
