"""Helpers for safely extracting values from Firestore aggregation query results."""

import typing


class _AggregationResult(typing.Protocol):
    value: object


def _extract_aggregation_value(
    result: list[list[_AggregationResult]],
    default: int = 0,
) -> int | float:
    """Return the numeric value at result[0][0].value, or *default* if absent or non-numeric.

    Firestore aggregation queries (count, sum) return a list[list[AggregationResult]].
    If Firestore returns an empty list — or an inner list with no elements — indexing
    would raise an IndexError.  This helper guards both cases and also rejects non-numeric
    values (e.g. None or an unexpected type) by returning *default*.
    """
    if not result or not result[0]:
        return default
    value = result[0][0].value
    if value is None:
        return default
    if not isinstance(value, int | float):
        return default
    return value
