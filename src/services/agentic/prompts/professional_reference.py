"""Resolve how the bot should refer to the professional in third person.

The professional configures `professional_address_term` in the form (e.g.
"la Doc", "el Lic.", "la Dra."). When the field is empty, fall back to a
neutral "la profesional" so the prompt stays readable for any tenant.

This helper is shared between `style_rules_template` (renders the static
<style_rules>) and `state_instructions` (per-state runtime instructions).
"""

import src.domain.entities.agent_profile as agent_profile_entity

_FALLBACK_REFERENCE = "la profesional"


def professional_reference(
    identity: agent_profile_entity.AssistantIdentity | None,
) -> str:
    if identity is None:
        return _FALLBACK_REFERENCE
    term = identity.professional_address_term
    if term is None or term.strip() == "":
        return _FALLBACK_REFERENCE
    return term.strip()
