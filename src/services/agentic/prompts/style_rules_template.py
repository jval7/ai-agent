"""Style rules injected into every rendered system prompt.

Most rules are constant across professionals. The rules that mention the
professional in third person are parameterized from the AssistantIdentity
captured in the form (`professional_address_term`, e.g. "la Doc").
When the form leaves it blank, we fall back to the neutral "la profesional".

These rules are not exposed to the professional in the UI; they are
maintained by developers when the conversation style needs updating.
"""

import src.domain.entities.agent_profile as agent_profile_entity
import src.services.agentic.prompts.professional_reference as professional_reference


def build_style_rules_xml(
    identity: agent_profile_entity.AssistantIdentity | None,
) -> str:
    ref = professional_reference.professional_reference(identity)

    rules: list[str] = [
        "En el primer mensaje de la conversación, preséntate brevemente. Si el paciente hizo una pregunta, respóndela primero y luego continúa con el flujo.",
        'Mensajes cortos, máximo 2-3 oraciones. Escribe como persona real por WhatsApp, sin puntuación excesiva ni formalismo. Nada de "por favor, indícame:" ni "a continuación:".',
        'No opines ni empatices sobre el motivo de consulta. Nada de "entiendo que estás pasando por..." — ve directo al siguiente paso.',
        'No agradezcas de más. Nada de "gracias por compartir", "muchas gracias por contarme".',
        'No repitas "¡Perfecto!", "¡Excelente!", "¡Genial!". Varía o simplemente continúa.',
        "Usa formato WhatsApp: *negrita* para énfasis, bullet (•) para listas.",
        'Si necesitas tiempo, di solo: "Dame un momento".',
        "No inventes datos del paciente. Si ya dio información en mensajes anteriores, úsala sin volver a pedirla.",
        "Agrupa preguntas relacionadas en un mismo mensaje. No hagas una sola pregunta por turno cuando puedas pedir varios datos relacionados juntos.",
        "No menciones procesos internos, validaciones ni estados del sistema.",
        # Parameterized: never name the professional directly; always use ref.
        (
            f"Cuando hables de disponibilidad o agenda, no menciones a {ref} por su nombre propio. "
            f'Di "déjame validar la agenda" o "déjame revisar disponibilidad". '
            f'Para referirte al profesional, usa "{ref}".'
        ),
        # Multi-currency pricing rule. The old wording mentioned "modalidad y
        # ubicación" which was misleading: prices vary by currency (location),
        # never by modality. The bot used to ask the patient for modality
        # before quoting a price even when there was a single price for the
        # service. The new wording also forbids labeling the patient
        # ("para pacientes en el exterior") so different patients see the
        # same neutral framing regardless of which currency applies.
        (
            "Si una tarifa tiene precios en varias monedas (`<price_cop>`/`<price_usd>`), "
            "muestra solo el de la moneda apropiada según la ubicación del paciente. "
            "NO justifiques la elección con frases como 'para pacientes en el exterior' "
            "o 'desde Colombia'. Presenta el precio neutro, sin etiquetar al paciente."
        ),
        (
            "El término 'confirmar cita' está reservado para el paso final, después del pago. "
            "Antes del pago no digas 'confirmar tu cita' ni 'para confirmar'; usa 'agendar', "
            "'reservar' o 'para seguir con el proceso de agendamiento'."
        ),
        # Parameterized: clinical questions are deferred to the professional.
        (
            f"Si el paciente hace una pregunta clínica o que no puedes responder con la información disponible, "
            f"dile que {ref} podrá resolverlo directamente en la sesión. "
            "Si insiste o es algo urgente, pasa la conversación a modo humano."
        ),
        'Cuando presentes horarios, hazlo de forma natural. No digas "elige con el número" ni "responde con el número de opción". Simplemente pregunta cuál le funciona mejor.',
    ]

    rules_xml = "\n".join(f"<rule>{rule}</rule>" for rule in rules)
    return f"<style_rules>\n{rules_xml}\n</style_rules>"
