"""Pure function that renders an AgentProfile into the XML system prompt string.

The output is consumed verbatim by the LLM at runtime via
RuntimePromptBuilder.compose_base_and_runtime_system_prompt().

Design decisions:
- Sections are omitted entirely when the corresponding fields are empty.
- style_rules are always included regardless of form completion state.
- Each service emits a single <tariffs> block; multiple currencies coexist.
"""

import src.domain.entities.agent_profile as agent_profile_entity
import src.services.agentic.prompts.style_rules_template as style_rules_template


def _professional_label(identity: agent_profile_entity.AssistantIdentity) -> str:
    """Combine professional_title + professional_name into a single label.

    Title alone:                "Doc."        → "Doc."
    Name alone:                 "Ana Rodriguez" → "Ana Rodriguez"
    Title + name (typical):     "Doc." + "Ana Rodriguez" → "Doc. Ana Rodriguez"
    Both empty:                 "" (caller should skip rendering)
    """
    title = identity.professional_title.strip() if identity.professional_title else ""
    name = identity.professional_name.strip() if identity.professional_name else ""
    if title and name:
        return f"{title} {name}"
    return title or name


def _render_identity(identity: agent_profile_entity.AssistantIdentity) -> str:
    """Render <identity> with each field as its own semantic tag.

    Previous shape concatenated everything into a single <assistant_role>
    string ("Claudia la asistente virtual de WhatsApp de Dra. X (Cali)") which
    was agrammatical and led the LLM to drop the assistant_name and fall back
    to a generic "soy tu asistente virtual de la Dra. X" greeting. Splitting
    each field into its own tag lets the LLM compose the presentation
    naturally per the style rule (e.g. "soy Claudia, asistente virtual de la
    Dra. X").
    """
    parts: list[str] = []
    if identity.assistant_name:
        parts.append(f"<assistant_name>{identity.assistant_name}</assistant_name>")
    pro_label = _professional_label(identity)
    if pro_label:
        parts.append(f"<professional>{pro_label}</professional>")
    if identity.main_city:
        parts.append(f"<main_city>{identity.main_city}</main_city>")
    if identity.tone:
        parts.append(f"<tone>{identity.tone}</tone>")
    if not parts:
        return ""
    return "<identity>\n" + "\n".join(parts) + "\n</identity>"


def _render_professional_context(
    context: agent_profile_entity.ProfessionalContext | None,
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

    # Timezone from identity — surfaces the IANA zone to the LLM so it can
    # present appointment times in the correct local zone.
    if identity is not None and identity.timezone:
        items.append(f"<item>Zona horaria: {identity.timezone}</item>")

    if not items:
        return ""
    return "<professional_context>\n" + "\n".join(items) + "\n</professional_context>"


def _format_amount(amount: float) -> str:
    return f"{amount:,.0f}" if amount == int(amount) else f"{amount:,.2f}"


def _render_tariff_option(tariff: agent_profile_entity.TariffOption) -> str:
    """Render a tariff with one <price_xxx> tag per currency.

    Tag name is derived from the currency code: a tariff with COP+USD prices
    emits <price_cop> and <price_usd>. This way the LLM doesn't have to
    decide which "category" applies — it just looks up the currency tag.
    """
    parts = [f"<label>{tariff.label}</label>"]
    if tariff.description:
        parts.append(f"<description>{tariff.description}</description>")
    for price in tariff.prices:
        tag = f"price_{price.currency.lower()}"
        parts.append(f"<{tag}>{_format_amount(price.amount)} {price.currency}</{tag}>")
    return "<tariff>\n" + "\n".join(parts) + "\n</tariff>"


_TARGET_PATIENTS_LABELS: dict[tuple[str, ...], str] = {
    ("NEW", "RETURNING"): "Pacientes nuevos y recurrentes",
    ("NEW",): "Solo pacientes nuevos (primera consulta)",
    ("RETURNING",): "Solo pacientes recurrentes (ya tuvieron una cita previa)",
}


def _format_target_patients(target_patients: list[str]) -> str | None:
    """Return a human-readable Spanish label for the target_patients list,
    or None if the list is empty / has no usable values.
    """
    if not target_patients:
        return None
    key = tuple(sorted(target_patients))
    return _TARGET_PATIENTS_LABELS.get(key)


def _render_services(services: list[agent_profile_entity.ServiceOffering]) -> str:
    service_blocks: list[str] = []
    for svc in services:
        if not svc.name and not svc.description and not svc.tariffs:
            continue
        lines: list[str] = []
        if svc.name:
            lines.append(f"<name>{svc.name}</name>")
        if svc.modalities:
            modalities_text = " y ".join(m.capitalize() for m in svc.modalities)
            lines.append(f"<modalities>{modalities_text}</modalities>")
        target_label = _format_target_patients(list(svc.target_patients))
        if target_label is not None:
            lines.append(f"<target_patients>{target_label}</target_patients>")
        if svc.description:
            lines.append(f"<description>{svc.description}</description>")
        if svc.tariffs:
            tariffs_xml = "\n".join(_render_tariff_option(t) for t in svc.tariffs)
            lines.append(f"<tariffs>\n{tariffs_xml}\n</tariffs>")

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

    # Professional context (includes languages and timezone)
    context_rendered = _render_professional_context(
        context=profile.professional_context,
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


def _has_structured_data(profile: agent_profile_entity.AgentProfile) -> bool:
    """Return True when the form has been populated with at least one
    structured field. Used to decide whether to regenerate the system prompt
    from the form data instead of falling back to the legacy persisted string.
    """
    if profile.identity is not None:
        return True
    if profile.professional_context is not None:
        return True
    if profile.services:
        return True
    return bool(profile.payment_methods)


def effective_system_prompt(profile: agent_profile_entity.AgentProfile) -> str:
    """Return the system prompt the runtime should actually use.

    When the structured form has been populated, the prompt is rendered fresh
    from those fields on every call. The persisted `system_prompt` string is
    used only as a legacy fallback for tenants who haven't migrated to the
    form yet. This avoids stale data (old <audience>, old <category> blocks)
    leaking into the LLM after a renderer change.
    """
    if _has_structured_data(profile):
        return render_system_prompt_xml(profile)
    return profile.system_prompt
