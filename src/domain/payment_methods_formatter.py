"""Format the structured PaymentMethod list into a single WhatsApp-safe string.

Used by reminder templates that need to inline the payment instructions in a
template body parameter. Single line, separated by ` · ` so it fits the
WhatsApp Cloud API constraint that template params cannot contain newlines.

Source of truth is `AgentProfile.payment_methods`. The legacy
`AgentProfile.payment_details_text` field is kept only as a fallback for
tenants that haven't migrated to the structured form yet.
"""

import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.whatsapp_template_params as whatsapp_template_params


def format_payment_methods_for_template(
    methods: list[agent_profile_entity.PaymentMethod],
) -> str:
    """Render payment methods as a single inline string safe for WhatsApp.

    Each method becomes "method_name: instructions (a nombre de holder)";
    methods are joined with ` · `. Empty fields are skipped silently.
    Returns an empty string when the list has no usable content.
    """
    if not methods:
        return ""
    rendered: list[str] = []
    for method in methods:
        primary_parts: list[str] = []
        if method.method_name:
            if method.instructions:
                primary_parts.append(f"{method.method_name}: {method.instructions}")
            else:
                primary_parts.append(method.method_name)
        elif method.instructions:
            primary_parts.append(method.instructions)
        if not primary_parts:
            continue
        if method.holder:
            primary_parts.append(f"a nombre de {method.holder}")
        rendered.append(" · ".join(primary_parts))
    if not rendered:
        return ""
    combined = " · ".join(rendered)
    return whatsapp_template_params.sanitize_template_param(combined)
