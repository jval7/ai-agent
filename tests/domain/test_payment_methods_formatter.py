import src.domain.entities.agent_profile as agent_profile_entity
import src.domain.payment_methods_formatter as payment_methods_formatter


def _make(
    method_name: str = "Nequi",
    instructions: str | None = "318 732 6409",
    holder: str | None = "Aleja",
    currency: str = "COP",
    applies_when: str | None = None,
) -> agent_profile_entity.PaymentMethod:
    return agent_profile_entity.PaymentMethod(
        currency=currency,
        method_name=method_name,
        instructions=instructions,
        holder=holder,
        applies_when=applies_when,
    )


class TestPaymentMethodsFormatter:
    def test_empty_list_returns_empty_string(self) -> None:
        assert payment_methods_formatter.format_payment_methods_for_template([]) == ""

    def test_single_method_with_full_data(self) -> None:
        result = payment_methods_formatter.format_payment_methods_for_template([_make()])
        assert result == "Nequi: 318 732 6409 · a nombre de Aleja"

    def test_multiple_methods_joined_with_dot(self) -> None:
        result = payment_methods_formatter.format_payment_methods_for_template(
            [
                _make(method_name="Nequi", instructions="318", holder="Aleja"),
                _make(method_name="Zelle", instructions="786", holder="Nelson", currency="USD"),
            ]
        )
        assert result == "Nequi: 318 · a nombre de Aleja · Zelle: 786 · a nombre de Nelson"

    def test_holder_optional(self) -> None:
        result = payment_methods_formatter.format_payment_methods_for_template([_make(holder=None)])
        assert result == "Nequi: 318 732 6409"

    def test_skips_methods_with_no_usable_content(self) -> None:
        # method_name empty + no instructions → skipped, but second still renders.
        result = payment_methods_formatter.format_payment_methods_for_template(
            [
                _make(method_name="", instructions=None, holder="Nadie"),
                _make(method_name="Nequi", instructions="318", holder=None),
            ]
        )
        assert result == "Nequi: 318"

    def test_output_has_no_newlines_safe_for_whatsapp(self) -> None:
        # Even if instructions contain newlines, sanitizer collapses them.
        result = payment_methods_formatter.format_payment_methods_for_template(
            [_make(instructions="318\n732", holder=None)]
        )
        assert "\n" not in result
        assert "Nequi: 318 · 732" in result
