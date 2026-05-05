"""Unit tests for the _extract_aggregation_value helper."""

import src.adapters.outbound.firestore.aggregations as firestore_aggregations


class _FakeAggResult:
    """Minimal stand-in for google.cloud.firestore AggregationResult.

    Satisfies the _AggregationResult Protocol used by _extract_aggregation_value.
    """

    def __init__(self, value: object) -> None:
        self.value = value


def _wrap(value: object) -> list[list[_FakeAggResult]]:
    return [[_FakeAggResult(value)]]


def test_empty_outer_list_returns_default() -> None:
    result: list[list[_FakeAggResult]] = []
    assert firestore_aggregations._extract_aggregation_value(result) == 0  # type: ignore[arg-type]


def test_empty_inner_list_returns_default() -> None:
    result: list[list[_FakeAggResult]] = [[]]
    assert firestore_aggregations._extract_aggregation_value(result) == 0  # type: ignore[arg-type]


def test_none_value_returns_default() -> None:
    assert firestore_aggregations._extract_aggregation_value(_wrap(None)) == 0  # type: ignore[arg-type]


def test_integer_value_returned() -> None:
    assert firestore_aggregations._extract_aggregation_value(_wrap(42)) == 42  # type: ignore[arg-type]


def test_float_value_returned() -> None:
    value = firestore_aggregations._extract_aggregation_value(_wrap(3.14))  # type: ignore[arg-type]
    assert abs(value - 3.14) < 1e-9


def test_string_value_returns_default() -> None:
    assert firestore_aggregations._extract_aggregation_value(_wrap("unexpected")) == 0  # type: ignore[arg-type]


def test_custom_default_returned_on_empty() -> None:
    result: list[list[_FakeAggResult]] = []
    assert firestore_aggregations._extract_aggregation_value(result, default=99) == 99  # type: ignore[arg-type]


def test_zero_integer_is_returned_not_default() -> None:
    assert firestore_aggregations._extract_aggregation_value(_wrap(0)) == 0  # type: ignore[arg-type]
