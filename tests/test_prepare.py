"""Tests for the public portable preparation composition API."""

from __future__ import annotations

import datetime as dt
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest

from perfattr import (
    Frequency,
    PreparationError,
    PreparationResult,
    calculate_attribution,
    prepare_attribution,
)
from perfattr._schemas import (
    PREPARATION_RECONCILIATION_COLUMNS,
    PREPARED_PERFORMANCE_COLUMNS,
)
from perfattr.prepare import _reconciliation_row


def _native_side(returns: list[float]) -> pd.DataFrame:
    """Return three one-identifier monthly source periods."""
    return pd.DataFrame(
        {
            "from_date": ["2024-01-01", "2024-02-01", "2024-03-01"],
            "thru_date": ["2024-01-31", "2024-02-29", "2024-03-31"],
            "identifier": ["TOTAL"] * 3,
            "weight": [1.0] * 3,
            "return": returns,
        }
    )


def _mapped_monthly_inputs() -> tuple[
    pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame
]:
    """Return independently mapped authoritative inputs spanning two source periods."""
    portfolio = pd.DataFrame(
        {
            "from_date": ["2024-01-01"] * 2 + ["2024-01-16"] * 2,
            "thru_date": ["2024-01-15"] * 2 + ["2024-01-31"] * 2,
            "identifier": ["P_A", "P_B", "P_A", "P_B"],
            "weight": [0.6, 0.4, 0.5, 0.5],
            "return": [0.10, 0.05, -0.02, 0.04],
            # Authoritative period totals are 8% and 2%, intentionally distinct
            # from the sums of weight times the supplied identifier returns.
            "contribution": [0.07, 0.01, -0.01, 0.03],
        }
    )
    benchmark = pd.DataFrame(
        {
            "from_date": ["2024-01-01"] * 2 + ["2024-01-16"] * 2,
            "thru_date": ["2024-01-15"] * 2 + ["2024-01-31"] * 2,
            "identifier": ["B_A", "B_B", "B_A", "B_B"],
            "weight": [0.5, 0.5, 0.4, 0.6],
            "return": [0.04, 0.06, 0.01, 0.02],
            # Benchmark source totals are 4% and 1%, so January compounds to
            # 1.04 * 1.01 - 1 = 5.04%.
            "contribution": [0.01, 0.03, 0.004, 0.006],
        }
    )
    portfolio_mapping = pd.DataFrame(
        {
            "identifier": ["P_A", "P_B"],
            "classification_identifier": ["PORT_CLASS", "PORT_CLASS"],
        }
    )
    benchmark_mapping = pd.DataFrame(
        {
            "identifier": ["B_A", "B_B"],
            "classification_identifier": ["BENCH_CLASS", "BENCH_CLASS"],
        }
    )
    return portfolio, benchmark, portfolio_mapping, benchmark_mapping


def _effective_quarterly_inputs() -> tuple[
    pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame
]:
    """Return independent dated mappings and three monthly returns-only periods.

    Portfolio P_A changes from EQ to FI after January; benchmark B_A changes after
    February. P_B and B_B remain BOND throughout. The source weights sum to one each
    month, and the deliberately simple returns produce portfolio monthly contributions
    of 4%, 3%, and 0% and benchmark contributions of 3%, 2%, and 1%.
    """
    from_dates = ["2024-01-01"] * 2 + ["2024-02-01"] * 2 + ["2024-03-01"] * 2
    thru_dates = ["2024-01-31"] * 2 + ["2024-02-29"] * 2 + ["2024-03-31"] * 2
    portfolio = pd.DataFrame(
        {
            "from_date": from_dates,
            "thru_date": thru_dates,
            "identifier": ["P_A", "P_B"] * 3,
            "weight": [0.6, 0.4, 0.5, 0.5, 0.4, 0.6],
            # P_A contributes 3%, 2%, and -1%; P_B contributes 1% each month.
            "return": [0.05, 0.025, 0.04, 0.02, -0.025, 1.0 / 60.0],
        }
    )
    benchmark = pd.DataFrame(
        {
            "from_date": from_dates,
            "thru_date": thru_dates,
            "identifier": ["B_A", "B_B"] * 3,
            "weight": [0.5, 0.5, 0.4, 0.6, 0.3, 0.7],
            # B_A contributes 2%, 1%, and 1%; B_B contributes 1%, 1%, and 0%.
            "return": [0.04, 0.02, 0.025, 1.0 / 60.0, 1.0 / 30.0, 0.0],
        }
    )
    portfolio_mapping = pd.DataFrame(
        {
            "from_date": ["2024-01-01", "2024-02-01", "2024-01-01"],
            "thru_date": ["2024-01-31", "2024-03-31", "2024-03-31"],
            "identifier": ["P_A", "P_A", "P_B"],
            "classification_identifier": ["EQ", "FI", "BOND"],
        }
    )
    benchmark_mapping = pd.DataFrame(
        {
            "from_date": ["2024-01-01", "2024-03-01", "2024-01-01"],
            "thru_date": ["2024-02-29", "2024-03-31", "2024-03-31"],
            "identifier": ["B_A", "B_A", "B_B"],
            "classification_identifier": ["EQ", "FI", "BOND"],
        }
    )
    return portfolio, benchmark, portfolio_mapping, benchmark_mapping


# These expected vectors were calculated directly from the formulas documented in the
# effective-dated quarterly test. Keeping them outside the test makes each financial
# assertion concise without deriving an expected value from production code.
_EFFECTIVE_PORTFOLIO_WEIGHTS = (
    0.5,
    0.20439560439560436,
    0.2956043956043956,
)
_EFFECTIVE_PORTFOLIO_CONTRIBUTIONS = (
    0.030701838891117304,
    0.03045072461418916,
    0.010047436494693534,
)
_EFFECTIVE_PORTFOLIO_RETURNS = (
    0.06140367778223461,
    0.14897935160705453,
    0.033989469182792255,
)
_EFFECTIVE_BENCHMARK_WEIGHTS = (
    0.6,
    0.2978021978021978,
    0.10219780219780218,
)
_EFFECTIVE_BENCHMARK_CONTRIBUTIONS = (
    0.02035183332527551,
    0.030502828439161737,
    0.01025133823556274,
)
_EFFECTIVE_BENCHMARK_RETURNS = (
    0.03391972220879252,
    0.10242647188058,
    0.10030879348776446,
)


def test_prepare_native_returns_only_composes_with_calculation_core() -> None:
    """The ordinary weights-and-returns workflow should need one preparation call.

    Native alignment preserves the two source periods exactly. Preparation derives
    contribution as unit weight times return, and the resulting frames pass directly
    into the already-released calculation core without translation.
    """
    portfolio = _native_side([0.01, 0.02, 0.03]).iloc[:2].copy()
    benchmark = _native_side([0.005, 0.01, 0.015]).iloc[:2].copy()

    prepared = prepare_attribution(portfolio, benchmark)
    attribution = calculate_attribution(prepared.portfolio, prepared.benchmark)

    assert isinstance(prepared, PreparationResult)
    np.testing.assert_allclose(prepared.portfolio["contribution"], [0.01, 0.02])
    np.testing.assert_allclose(prepared.benchmark["contribution"], [0.005, 0.01])
    assert len(attribution.period_summary) == 2
    np.testing.assert_allclose(
        attribution.period_summary["portfolio_return"], [0.01, 0.02]
    )


def test_prepare_rejects_exact_authoritative_total_outside_calculation_domain() -> None:
    """Successful preparation must guarantee a positive period wealth base.

    Two 50% rows carry authoritative contributions of -60% and -50%, so their exact
    native-period total is -110%. The supplied identifier returns remain zero and the
    effective returns are finite, but ``log1p(-1.10)`` is undefined. Preparation must
    reject this period instead of returning frames that the calculation core rejects.
    """
    side = pd.DataFrame(
        {
            "from_date": ["2024-01-01"] * 2,
            "thru_date": ["2024-01-31"] * 2,
            "identifier": ["A", "B"],
            "weight": [0.5, 0.5],
            "return": [0.0, 0.0],
            "contribution": [-0.60, -0.50],
        }
    )

    with pytest.raises(
        PreparationError,
        match="prepared portfolio period return.*greater than -1.0",
    ):
        prepare_attribution(side, side)


def test_prepare_rejects_exact_mapped_return_outside_calculation_domain() -> None:
    """An exact mapped group must retain a compoundable downstream input return.

    The period contribution total is a valid positive 10%, but mapping the two rows
    separately makes X's effective return ``-0.60 / 0.50 = -1.20``. Because that
    mapped value becomes the calculation core's supplied return, preparation must
    reject it before claiming successful composition.
    """
    side = pd.DataFrame(
        {
            "from_date": ["2024-01-01"] * 2,
            "thru_date": ["2024-01-31"] * 2,
            "identifier": ["A", "B"],
            "weight": [0.5, 0.5],
            "return": [0.0, 0.0],
            "contribution": [-0.60, 0.70],
        }
    )
    mapping = pd.DataFrame(
        {
            "identifier": ["A", "B"],
            "classification_identifier": ["X", "Y"],
        }
    )

    with pytest.raises(
        PreparationError,
        match="prepared portfolio returns.*greater than -1.0",
    ):
        prepare_attribution(
            side,
            side,
            portfolio_mapping=mapping,
            benchmark_mapping=mapping,
        )


def test_preparation_result_has_stable_schemas_order_and_dtypes() -> None:
    """Public prepared and reconciliation frames should establish their contracts."""
    prepared = prepare_attribution(
        _native_side([0.01, 0.02, 0.03]).iloc[:2],
        _native_side([0.005, 0.01, 0.015]).iloc[:2],
    )

    for frame in (prepared.portfolio, prepared.benchmark):
        assert list(frame.columns) == list(PREPARED_PERFORMANCE_COLUMNS)
        assert isinstance(frame.index, pd.RangeIndex)
        assert frame.index.start == 0
        assert frame.index.step == 1
        assert str(frame["identifier"].dtype) == "string"
        assert frame["from_date"].dtype == np.dtype("datetime64[ns]")
        assert frame["thru_date"].dtype == np.dtype("datetime64[ns]")
        assert frame["quantity_of_days"].dtype == np.dtype("int64")
        assert all(
            frame[column].dtype == np.dtype("float64")
            for column in ("weight", "return", "contribution")
        )
    portfolio_periods = prepared.portfolio[
        ["from_date", "thru_date", "quantity_of_days"]
    ].drop_duplicates(ignore_index=True)
    benchmark_periods = prepared.benchmark[
        ["from_date", "thru_date", "quantity_of_days"]
    ].drop_duplicates(ignore_index=True)
    pd.testing.assert_frame_equal(portfolio_periods, benchmark_periods)

    reconciliation = prepared.reconciliation
    assert list(reconciliation.columns) == list(PREPARATION_RECONCILIATION_COLUMNS)
    assert isinstance(reconciliation.index, pd.RangeIndex)
    assert str(reconciliation["stage"].dtype) == "string"
    assert str(reconciliation["side"].dtype) == "string"
    assert str(reconciliation["check"].dtype) == "string"
    assert reconciliation["passed"].dtype == np.dtype("bool")
    assert all(
        reconciliation[column].dtype == np.dtype("float64")
        for column in ("actual", "expected", "residual", "tolerance")
    )


def test_native_reconciliation_has_specified_stage_side_and_check_order() -> None:
    """Native returns-only evidence should be deterministic and omit unused checks."""
    prepared = prepare_attribution(
        _native_side([0.01, 0.02, 0.03]).iloc[:2],
        _native_side([0.005, 0.01, 0.015]).iloc[:2],
    )
    reconciliation = prepared.reconciliation

    assert list(reconciliation["stage"]) == ["source"] * 8 + ["reporting"] * 4
    assert list(reconciliation["side"]) == (
        ["portfolio"] * 4
        + ["benchmark"] * 4
        + ["portfolio"] * 2
        + ["benchmark"] * 2
    )
    assert list(reconciliation["check"]) == (
        ["weight_sum", "derived_contribution"] * 4
        + ["weight_sum"] * 4
    )
    assert bool(np.asarray(reconciliation["passed"], dtype=np.bool_).all())
    np.testing.assert_allclose(reconciliation["residual"], 0.0, atol=1e-12)


def test_prepare_maps_then_consolidates_authoritative_inputs() -> None:
    """Composition should preserve independent mappings and linked contributions.

    Portfolio source totals of 8% and 2% compound to 10.16%; benchmark totals of 4%
    and 1% compound to 5.04%. Each side maps its two identifiers into its own class
    before consolidation. Unit final class weights make the mapped effective returns
    equal those independently calculated linked contributions.
    """
    portfolio, benchmark, portfolio_mapping, benchmark_mapping = (
        _mapped_monthly_inputs()
    )

    prepared = prepare_attribution(
        portfolio,
        benchmark,
        frequency=Frequency.MONTHLY,
        portfolio_mapping=portfolio_mapping,
        benchmark_mapping=benchmark_mapping,
    )

    assert list(prepared.portfolio["identifier"]) == ["PORT_CLASS"]
    assert list(prepared.benchmark["identifier"]) == ["BENCH_CLASS"]
    assert prepared.portfolio.loc[0, "weight"] == pytest.approx(1.0)
    assert prepared.benchmark.loc[0, "weight"] == pytest.approx(1.0)
    assert prepared.portfolio.loc[0, "return"] == pytest.approx(0.1016)
    assert prepared.portfolio.loc[0, "contribution"] == pytest.approx(0.1016)
    assert prepared.benchmark.loc[0, "return"] == pytest.approx(0.0504)
    assert prepared.benchmark.loc[0, "contribution"] == pytest.approx(0.0504)
    assert prepared.portfolio.loc[0, "quantity_of_days"] == 31


def test_prepare_resolves_effective_mappings_before_quarterly_consolidation() -> None:
    """Independent dated assignments should consolidate and reconcile end to end.

    Hand calculation uses ``s(x) = log1p(x) / x``. Portfolio monthly returns of 4%,
    3%, and 0% compound to 7.12%, with linking coefficients
    ``[1.0150241538063054, 1.0199677949249262, 1.0351919403804988]``. Benchmark
    monthly returns of 3%, 2%, and 1% compound to 6.1106%, with coefficients
    ``[1.0150995113886225, 1.0200838211389285, 1.025133823556274]``.

    P_A maps to EQ only in January and to FI in February and March. B_A independently
    maps to EQ through February and to FI in March. BOND remains unchanged. Applying
    the coefficients to each explicitly documented monthly contribution produces the
    expected class contributions below; dividing by the 91-day weighted class weights
    produces the expected effective returns. Each side's contributions reconcile to
    its compounded quarterly return before the prepared frames enter the calculation
    core.
    """
    portfolio, benchmark, portfolio_mapping, benchmark_mapping = (
        _effective_quarterly_inputs()
    )

    prepared = prepare_attribution(
        portfolio,
        benchmark,
        frequency=Frequency.QUARTERLY,
        portfolio_mapping=portfolio_mapping,
        benchmark_mapping=benchmark_mapping,
    )

    expected_identifiers = ["BOND", "EQ", "FI"]
    assert list(prepared.portfolio.columns) == list(PREPARED_PERFORMANCE_COLUMNS)
    assert list(prepared.benchmark.columns) == list(PREPARED_PERFORMANCE_COLUMNS)
    assert list(prepared.portfolio["identifier"]) == expected_identifiers
    assert list(prepared.benchmark["identifier"]) == expected_identifiers
    assert list(prepared.portfolio["from_date"].dt.date.unique()) == [
        dt.date(2024, 1, 1)
    ]
    assert list(prepared.portfolio["thru_date"].dt.date.unique()) == [
        dt.date(2024, 3, 31)
    ]
    assert list(prepared.portfolio["quantity_of_days"]) == [91, 91, 91]
    assert list(prepared.benchmark["quantity_of_days"]) == [91, 91, 91]

    # Portfolio weights are day-weighted from BOND [40%, 50%, 60%], EQ [60%, 0%, 0%],
    # and FI [0%, 50%, 40%] over month lengths [31, 29, 31].
    # Linked contributions are BOND=.01*(L1+L2+L3), EQ=.03*L1, and
    # FI=.02*L2-.01*L3. Their sum is the independently compounded 7.12%.
    np.testing.assert_allclose(
        prepared.portfolio["weight"],
        _EFFECTIVE_PORTFOLIO_WEIGHTS,
        rtol=1e-12,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        prepared.portfolio["contribution"],
        _EFFECTIVE_PORTFOLIO_CONTRIBUTIONS,
        rtol=1e-12,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        prepared.portfolio["return"],
        _EFFECTIVE_PORTFOLIO_RETURNS,
        rtol=1e-12,
        atol=1e-12,
    )

    # Benchmark weights are BOND [50%, 60%, 70%], EQ [50%, 40%, 0%], and
    # FI [0%, 0%, 30%] over the same source-period day counts.
    # Linked contributions are BOND=.01*(L1+L2), EQ=.02*L1+.01*L2, and FI=.01*L3.
    # They sum to the independently compounded 6.1106% benchmark return.
    np.testing.assert_allclose(
        prepared.benchmark["weight"],
        _EFFECTIVE_BENCHMARK_WEIGHTS,
        rtol=1e-12,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        prepared.benchmark["contribution"],
        _EFFECTIVE_BENCHMARK_CONTRIBUTIONS,
        rtol=1e-12,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        prepared.benchmark["return"],
        _EFFECTIVE_BENCHMARK_RETURNS,
        rtol=1e-12,
        atol=1e-12,
    )

    reconciliation = prepared.reconciliation
    assert list(reconciliation.columns) == list(PREPARATION_RECONCILIATION_COLUMNS)
    assert len(reconciliation) == 28
    assert bool(np.asarray(reconciliation["passed"], dtype=np.bool_).all())
    np.testing.assert_allclose(reconciliation["residual"], 0.0, atol=1e-12)
    assert list(reconciliation["stage"]) == (
        ["source"] * 12 + ["mapped"] * 12 + ["reporting"] * 4
    )
    assert list(reconciliation["check"]) == (
        ["weight_sum", "derived_contribution"] * 6
        + ["mapped_weight", "mapped_contribution"] * 6
        + ["weight_sum", "linked_contribution"] * 2
    )
    linked = reconciliation.loc[
        reconciliation["check"] == "linked_contribution"
    ]
    np.testing.assert_allclose(linked["actual"], [0.0712, 0.061106], atol=1e-12)
    np.testing.assert_allclose(linked["expected"], [0.0712, 0.061106], atol=1e-12)

    attribution = calculate_attribution(prepared.portfolio, prepared.benchmark)
    summary = attribution.period_summary.iloc[0]
    assert summary["portfolio_return"] == pytest.approx(0.0712, abs=1e-12)
    assert summary["benchmark_return"] == pytest.approx(0.061106, abs=1e-12)
    assert summary["active_return"] == pytest.approx(0.010094, abs=1e-12)


def test_prepare_accepts_different_source_partitions_with_common_coverage() -> None:
    """Each side should consolidate independently to one aligned reporting period.

    Portfolio has 1% and 2% half-month returns, which compound to 3.02%. Benchmark is
    already one complete January period at 1.5% and must be preserved rather than
    relinked. The common prepared boundary is January 1 through January 31.
    """
    portfolio = pd.DataFrame(
        {
            "from_date": ["2024-01-01", "2024-01-16"],
            "thru_date": ["2024-01-15", "2024-01-31"],
            "identifier": ["TOTAL", "TOTAL"],
            "weight": [1.0, 1.0],
            "return": [0.01, 0.02],
        }
    )
    benchmark = pd.DataFrame(
        {
            "from_date": ["2024-01-01"],
            "thru_date": ["2024-01-31"],
            "identifier": ["TOTAL"],
            "weight": [1.0],
            "return": [0.015],
        }
    )

    prepared = prepare_attribution(
        portfolio, benchmark, frequency=Frequency.MONTHLY
    )

    assert prepared.portfolio.loc[0, "return"] == pytest.approx(0.0302)
    assert prepared.portfolio.loc[0, "contribution"] == pytest.approx(0.0302)
    assert prepared.benchmark.loc[0, "return"] == 0.015
    assert prepared.benchmark.loc[0, "contribution"] == 0.015
    assert prepared.portfolio["from_date"].dtype == np.dtype("datetime64[ns]")
    assert prepared.benchmark["from_date"].dtype == np.dtype("datetime64[ns]")
    linked = prepared.reconciliation.loc[
        prepared.reconciliation["check"] == "linked_contribution"
    ]
    assert list(linked["side"]) == ["portfolio"]


def test_mapped_consolidation_reconciliation_covers_every_applicable_check() -> None:
    """Authoritative mapped inputs should emit only applicable passing evidence.

    There are four source weight checks, eight mapping conservation checks, and four
    reporting checks. Derived-contribution checks are absent because both sources
    supplied contribution; linked-contribution checks are present because each side
    consolidates two source periods.
    """
    portfolio, benchmark, portfolio_mapping, benchmark_mapping = (
        _mapped_monthly_inputs()
    )
    prepared = prepare_attribution(
        portfolio,
        benchmark,
        frequency=Frequency.MONTHLY,
        portfolio_mapping=portfolio_mapping,
        benchmark_mapping=benchmark_mapping,
    )
    reconciliation = prepared.reconciliation

    assert len(reconciliation) == 16
    assert list(reconciliation["stage"]) == (
        ["source"] * 4 + ["mapped"] * 8 + ["reporting"] * 4
    )
    assert list(reconciliation["check"]) == (
        ["weight_sum"] * 4
        + ["mapped_weight", "mapped_contribution"] * 4
        + ["weight_sum", "linked_contribution"] * 2
    )
    assert bool(np.asarray(reconciliation["passed"], dtype=np.bool_).all())
    assert bool(
        np.asarray(reconciliation["tolerance"] == 1e-12, dtype=np.bool_).all()
    )


def test_portfolio_and_benchmark_input_forms_remain_independent() -> None:
    """Derived-contribution evidence should appear only for a returns-only side."""
    portfolio = _native_side([0.01, 0.02, 0.03]).iloc[:1].copy()
    benchmark = _native_side([0.005, 0.01, 0.015]).iloc[:1].copy()
    benchmark["contribution"] = [0.006]

    prepared = prepare_attribution(portfolio, benchmark)
    derived = prepared.reconciliation.loc[
        prepared.reconciliation["check"] == "derived_contribution"
    ]

    assert list(derived["side"]) == ["portfolio"]
    assert prepared.benchmark.loc[0, "return"] == 0.005
    assert prepared.benchmark.loc[0, "contribution"] == 0.006


def test_date_window_filters_whole_periods_by_inclusive_endpoint() -> None:
    """Bounds should select inclusive source endpoints without clipping periods."""
    portfolio = _native_side([0.01, 0.02, 0.03])
    benchmark = _native_side([0.005, 0.01, 0.015])

    prepared = prepare_attribution(
        portfolio,
        benchmark,
        from_date=dt.date(2024, 1, 31),
        thru_date="2024-02-29",
    )

    assert list(prepared.portfolio["from_date"]) == [
        pd.Timestamp("2024-01-01"),
        pd.Timestamp("2024-02-01"),
    ]
    assert list(prepared.portfolio["thru_date"]) == [
        pd.Timestamp("2024-01-31"),
        pd.Timestamp("2024-02-29"),
    ]
    assert list(prepared.portfolio["quantity_of_days"]) == [31, 29]


@pytest.mark.parametrize(
    ("kwargs", "error_type", "message"),
    [
        pytest.param(
            {"from_date": "bad"},
            PreparationError,
            "from_date.*invalid date",
            id="invalid-string",
        ),
        pytest.param(
            {"from_date": 20240101},
            TypeError,
            "from_date must be a date string",
            id="wrong-type",
        ),
        pytest.param(
            {"from_date": dt.datetime(2024, 1, 1)},
            TypeError,
            "from_date must be a date string",
            id="datetime-not-date",
        ),
        pytest.param(
            {"from_date": "2024-02-01", "thru_date": "2024-01-31"},
            PreparationError,
            "from_date must not be after thru_date",
            id="reversed",
        ),
        pytest.param(
            {"from_date": "2025-01-01"},
            PreparationError,
            "portfolio input has no rows",
            id="empty",
        ),
    ],
)
def test_prepare_rejects_invalid_or_empty_date_windows(
    kwargs: dict[str, Any],
    error_type: type[Exception],
    message: str,
) -> None:
    """Date-window errors should identify invalid boundaries or empty selection."""
    with pytest.raises(error_type, match=message):
        prepare_attribution(
            _native_side([0.01, 0.02, 0.03]),
            _native_side([0.005, 0.01, 0.015]),
            **kwargs,
        )


def test_prepare_does_not_mutate_any_caller_owned_input() -> None:
    """Composition and returned-frame mutation must not reach any caller input."""
    portfolio, benchmark, portfolio_mapping, benchmark_mapping = (
        _mapped_monthly_inputs()
    )
    inputs = (portfolio, benchmark, portfolio_mapping, benchmark_mapping)
    before = tuple(frame.copy(deep=True) for frame in inputs)
    holidays = [dt.date(2024, 1, 1)]

    prepared = prepare_attribution(
        portfolio,
        benchmark,
        frequency=Frequency.MONTHLY,
        holidays=holidays,
        portfolio_mapping=portfolio_mapping,
        benchmark_mapping=benchmark_mapping,
    )
    prepared.portfolio.loc[0, "weight"] = 99.0
    prepared.reconciliation.loc[0, "actual"] = 99.0

    for frame, expected in zip(inputs, before, strict=True):
        pd.testing.assert_frame_equal(frame, expected)
    assert holidays == [dt.date(2024, 1, 1)]


def test_prepare_is_deterministic_for_shuffled_inputs_and_mappings() -> None:
    """Input row and mapping order must not affect any public result frame."""
    portfolio, benchmark, portfolio_mapping, benchmark_mapping = (
        _mapped_monthly_inputs()
    )
    expected = prepare_attribution(
        portfolio,
        benchmark,
        frequency=Frequency.MONTHLY,
        portfolio_mapping=portfolio_mapping,
        benchmark_mapping=benchmark_mapping,
    )
    actual = prepare_attribution(
        portfolio.sample(frac=1.0, random_state=1),
        benchmark.sample(frac=1.0, random_state=2),
        frequency=Frequency.MONTHLY,
        portfolio_mapping=portfolio_mapping.iloc[::-1],
        benchmark_mapping=benchmark_mapping.iloc[::-1],
    )

    pd.testing.assert_frame_equal(actual.portfolio, expected.portfolio)
    pd.testing.assert_frame_equal(actual.benchmark, expected.benchmark)
    pd.testing.assert_frame_equal(actual.reconciliation, expected.reconciliation)


@pytest.mark.parametrize("value", [True, "1e-12", 0.0, -1.0, np.inf, np.nan])
def test_prepare_rejects_invalid_reconciliation_tolerances(value: Any) -> None:
    """The public composition boundary should validate its tolerance once."""
    expected_error = TypeError if isinstance(value, str | bool) else PreparationError
    with pytest.raises(expected_error, match="reconciliation_tolerance"):
        prepare_attribution(
            _native_side([0.01, 0.02, 0.03]),
            _native_side([0.005, 0.01, 0.015]),
            reconciliation_tolerance=cast(float, value),
        )


def test_prepare_uses_requested_tolerance_without_rounding_source_values() -> None:
    """An accepted compatibility tolerance should be visible in every audit row."""
    side = pd.DataFrame(
        {
            "from_date": ["2024-01-01", "2024-01-01"],
            "thru_date": ["2024-01-31", "2024-01-31"],
            "identifier": ["A", "B"],
            "weight": [0.6, 0.400000004],
            "return": [0.01, 0.02],
        }
    )

    prepared = prepare_attribution(
        side, side, reconciliation_tolerance=5e-9
    )

    assert np.asarray(prepared.portfolio["weight"], dtype=np.float64).sum() == (
        pytest.approx(1.000000004)
    )
    assert bool(
        np.asarray(
            prepared.reconciliation["tolerance"] == 5e-9,
            dtype=np.bool_,
        ).all()
    )


def test_reconciliation_failure_raises_before_a_result_can_be_returned() -> None:
    """A failed scalar invariant must raise instead of appearing as a failed row."""
    with pytest.raises(PreparationError, match="source portfolio weight_sum"):
        _reconciliation_row(
            "source",
            "portfolio",
            (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
            "weight_sum",
            0.9,
            1.0,
            1e-12,
        )
