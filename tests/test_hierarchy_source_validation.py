"""Tests for mutable source-result validation at the hierarchy boundary."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

import pandas as pd
import pytest

from perfattr import (
    AttributionError,
    AttributionMethod,
    AttributionResult,
    EffectLinkingMethod,
    calculate_attribution,
    roll_up_attribution,
)


_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "multi_period_linking"
_Mutation = Callable[[AttributionResult], None]


def _valid_case() -> tuple[AttributionResult, pd.DataFrame]:
    """Return a released multi-period result and complete one-parent hierarchy."""
    inputs = {
        side: pd.read_csv(_FIXTURE_ROOT / f"{side}.csv")
        for side in ("portfolio", "benchmark")
    }
    result = calculate_attribution(inputs["portfolio"], inputs["benchmark"])
    hierarchy = pd.DataFrame(
        {
            "identifier": ["Bonds", "Equity"],
            "parent_identifier": ["Total", "Total"],
        }
    )
    return result, hierarchy


def _swap_period_columns(result: AttributionResult) -> None:
    """Move identifier before quantity_of_days without changing the column set."""
    columns = list(result.period_detail.columns)
    identifier_index = columns.index("identifier")
    quantity_index = columns.index("quantity_of_days")
    columns[identifier_index], columns[quantity_index] = (
        columns[quantity_index],
        columns[identifier_index],
    )
    result.period_detail = result.period_detail.loc[:, columns]


def _change_weight_dtype(result: AttributionResult) -> None:
    """Replace one canonical float64 column with float32."""
    result.overall_detail["portfolio_weight"] = result.overall_detail[
        "portfolio_weight"
    ].astype("float32")


def _shift_period_index(result: AttributionResult) -> None:
    """Replace the canonical zero-based index with a one-based RangeIndex."""
    result.period_detail.index = pd.RangeIndex(1, len(result.period_detail) + 1)


def _duplicate_period_key(result: AttributionResult) -> None:
    """Append an otherwise valid duplicate period-and-identifier row."""
    result.period_detail = pd.concat(
        [result.period_detail, result.period_detail.iloc[[0]]],
        ignore_index=True,
    )


def _reverse_period_rows(result: AttributionResult) -> None:
    """Retain unique rows but violate released deterministic ordering."""
    result.period_detail = result.period_detail.iloc[::-1].reset_index(drop=True)


def _change_overall_identifier(result: AttributionResult) -> None:
    """Make the horizon leaf set disagree with period detail."""
    result.overall_detail.loc[0, "identifier"] = "Different Leaf"


def _change_summary_day_count(result: AttributionResult) -> None:
    """Make one summary period disagree with its detail day count."""
    result.period_summary.loc[0, "quantity_of_days"] = 99


def _change_horizon_start(result: AttributionResult) -> None:
    """Move every horizon start away from the earliest source period."""
    result.overall_detail["from_date"] += pd.Timedelta(days=1)


def _break_effective_return(result: AttributionResult) -> None:
    """Make a period return disagree with authoritative weight and contribution."""
    current = cast(float, result.period_detail.at[0, "portfolio_return"])
    result.period_detail.at[0, "portfolio_return"] = current + 0.01


def _break_overall_active_return(result: AttributionResult) -> None:
    """Make a defined horizon active return disagree with the side difference."""
    current = cast(float, result.overall_detail.at[0, "active_return"])
    result.overall_detail.at[0, "active_return"] = current + 0.01


def _make_effect_nonfinite(result: AttributionResult) -> None:
    """Introduce an infinite additive value into the source result."""
    result.period_detail.loc[0, "linked_total_effect"] = float("inf")


def _fail_source_reconciliation(result: AttributionResult) -> None:
    """Mark one source calculation invariant as failed."""
    result.reconciliation.loc[0, "passed"] = False


def _reverse_reconciliation_rows(result: AttributionResult) -> None:
    """Retain passing rows but violate the released check order."""
    result.reconciliation = result.reconciliation.iloc[::-1].reset_index(drop=True)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (_swap_period_columns, "exact released column order"),
        (_change_weight_dtype, "does not use its released dtype"),
        (_shift_period_index, "zero-based RangeIndex"),
        (_duplicate_period_key, "contains duplicate keys"),
        (_reverse_period_rows, "not deterministically sorted"),
        (_change_overall_identifier, "identifiers do not match"),
        (_change_summary_day_count, "periods do not match"),
        (_change_horizon_start, "horizon dates do not match"),
        (_break_effective_return, "invalid portfolio effective returns"),
        (_break_overall_active_return, "invalid active returns"),
        (_make_effect_nonfinite, "contains a non-finite value"),
        (_fail_source_reconciliation, "must contain only passes"),
        (_reverse_reconciliation_rows, "released check order"),
    ),
)
def test_public_rollup_rejects_a_mutated_source_result(
    mutation: _Mutation,
    message: str,
) -> None:
    """Mutable dataclass frames must still satisfy the released source contract."""
    result, hierarchy = _valid_case()
    mutation(result)

    with pytest.raises(AttributionError, match=message):
        roll_up_attribution(result, hierarchy)


def test_public_rollup_rejects_invalid_source_metadata_types() -> None:
    """Strings must not impersonate either dedicated financial-policy enum."""
    result, hierarchy = _valid_case()
    result.method = cast(AttributionMethod, result.method.value)
    with pytest.raises(TypeError, match="result.method must be an AttributionMethod"):
        roll_up_attribution(result, hierarchy)

    result, hierarchy = _valid_case()
    result.effect_linking_method = cast(
        EffectLinkingMethod,
        result.effect_linking_method.value,
    )
    with pytest.raises(
        TypeError,
        match="result.effect_linking_method must be an EffectLinkingMethod",
    ):
        roll_up_attribution(result, hierarchy)


def test_public_rollup_rejects_a_non_dataframe_result_field() -> None:
    """A directly constructed result cannot use a frame-shaped iterable."""
    result, hierarchy = _valid_case()
    result.period_summary = cast(pd.DataFrame, [])

    with pytest.raises(
        TypeError,
        match="source result period_summary must be a pandas DataFrame",
    ):
        roll_up_attribution(result, hierarchy)
