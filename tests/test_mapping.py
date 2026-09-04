"""Tests for mapping normalization and static source-period roll-up."""

from __future__ import annotations

from collections.abc import Callable
import datetime as dt
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest

from perfattr import PreparationError, normalize_mapping
from perfattr._schemas import NORMALIZED_PERFORMANCE_COLUMNS
from perfattr.mapping import (
    _map_performance,
    _normalize_mapping,
    _resolve_effective_identifier,
)
from perfattr.preparation import _normalize_performance


def _basic_performance() -> pd.DataFrame:
    """Return one normalized period containing a future collision and fallback row."""
    source = pd.DataFrame(
        {
            "from_date": ["2024-01-01"] * 3,
            "thru_date": ["2024-01-31"] * 3,
            "identifier": ["A", "EQ", "B"],
            "weight": [0.2, 0.3, 0.5],
            "return": [0.10, 0.20, 0.04],
            "portfolio_code": ["P"] * 3,
            "name": ["Asset A", "Equity", "Asset B"],
        }
    )
    return _normalize_performance(source, "portfolio input").frame


def _changed_mapping(change: Callable[[pd.DataFrame], None]) -> pd.DataFrame:
    """Return one ordinary mapping after applying a test-specific mutation."""
    mapping = pd.DataFrame(
        {
            "identifier": ["A", "B"],
            "classification_identifier": ["EQ", "FI"],
        }
    )
    change(mapping)
    return mapping


def _duplicate_column_mapping() -> pd.DataFrame:
    """Return a mapping with two source-identifier labels."""
    return pd.DataFrame(
        [["A", "A", "EQ"]],
        columns=[
            "identifier",
            "identifier",
            "classification_identifier",
        ],
    )


def test_mapping_normalization_trims_deduplicates_and_preserves_leading_zeroes() -> None:
    """Normalized exact duplicate pairs should collapse without identity coercion."""
    mapping = pd.DataFrame(
        {
            "identifier": [" A ", "A", "001"],
            "classification_identifier": [" EQ ", "EQ", " 010 "],
        }
    )
    mapping_before = mapping.copy(deep=True)

    normalized = _normalize_mapping(mapping, "portfolio mapping")

    expected = pd.DataFrame(
        {
            "identifier": pd.Series(["001", "A"], dtype="string[python]"),
            "classification_identifier": pd.Series(
                ["010", "EQ"],
                dtype="string[python]",
            ),
        }
    )
    pd.testing.assert_frame_equal(normalized, expected)
    pd.testing.assert_frame_equal(mapping, mapping_before)


@pytest.mark.parametrize(
    ("mapping", "message"),
    [
        pytest.param(
            pd.DataFrame({"identifier": ["A"]}),
            "missing columns: classification_identifier",
            id="missing-column",
        ),
        pytest.param(
            pd.DataFrame(
                {
                    "identifier": ["A"],
                    "classification_identifier": ["EQ"],
                    "name": ["Equity"],
                }
            ),
            "unexpected columns: name",
            id="extra-column",
        ),
        pytest.param(
            _duplicate_column_mapping(),
            "duplicate column labels",
            id="duplicate-column",
        ),
        pytest.param(
            _changed_mapping(
                lambda frame: frame.__setitem__("identifier", ["A", None])
            ),
            "identifier.*non-null strings",
            id="null-identifier",
        ),
        pytest.param(
            _changed_mapping(
                lambda frame: frame.__setitem__("classification_identifier", ["EQ", " "])
            ),
            "classification_identifier.*empty string",
            id="blank-classification",
        ),
        pytest.param(
            _changed_mapping(
                lambda frame: frame.__setitem__("classification_identifier", ["EQ", 7])
            ),
            "classification_identifier.*non-null strings",
            id="numeric-classification",
        ),
        pytest.param(
            pd.DataFrame(
                {
                    "identifier": ["A", " A "],
                    "classification_identifier": ["EQ", "OTHER"],
                }
            ),
            "multiple classifications.*A",
            id="conflicting-pairs-after-normalization",
        ),
    ],
)
def test_mapping_normalization_rejects_invalid_schema_or_identities(
    mapping: pd.DataFrame,
    message: str,
) -> None:
    """A static mapping should reject ambiguity rather than guessing intent."""
    with pytest.raises(PreparationError, match=message):
        _normalize_mapping(mapping, "portfolio mapping")


def test_mapping_normalization_requires_a_dataframe() -> None:
    """A mapping lookalike should fail at the pandas boundary."""
    with pytest.raises(TypeError, match="must be a pandas DataFrame"):
        _normalize_mapping(cast(pd.DataFrame, []), "portfolio mapping")


def test_effective_mapping_normalizes_dates_identities_duplicates_and_order() -> None:
    """Dated assignments should normalize without losing inclusive interval meaning.

    The two January rows become the same assignment only after their date and identity
    values are normalized, so they must collapse. The February assignment starts on
    the calendar day after January ends and is therefore adjacent rather than
    overlapping. Leading zeroes remain part of the separate ``001`` identity.
    """
    mapping = pd.DataFrame(
        {
            "classification_identifier": [" FI ", " EQ ", "EQ", " 010 "],
            "identifier": ["A", " A ", "A", "001"],
            "thru_date": [
                "2024-02-29",
                "2024-01-31",
                dt.date(2024, 1, 31),
                "2024-12-31",
            ],
            "from_date": [
                "2024-02-01",
                "2024-01-01",
                dt.date(2024, 1, 1),
                "2024-01-01",
            ],
        }
    )
    mapping_before = mapping.copy(deep=True)

    normalized = normalize_mapping(mapping)

    expected = pd.DataFrame(
        {
            "from_date": pd.Series(
                ["2024-01-01", "2024-01-01", "2024-02-01"],
                dtype="datetime64[ns]",
            ),
            "thru_date": pd.Series(
                ["2024-12-31", "2024-01-31", "2024-02-29"],
                dtype="datetime64[ns]",
            ),
            "identifier": pd.Series(["001", "A", "A"], dtype="string[python]"),
            "classification_identifier": pd.Series(
                ["010", "EQ", "FI"], dtype="string[python]"
            ),
        }
    )
    pd.testing.assert_frame_equal(normalized, expected)
    pd.testing.assert_frame_equal(mapping, mapping_before)


def test_empty_effective_mapping_retains_canonical_dtypes() -> None:
    """An empty dated mapping should remain distinguishable from an empty static one."""
    mapping = pd.DataFrame(
        columns=[
            "from_date",
            "thru_date",
            "identifier",
            "classification_identifier",
        ]
    )

    normalized = normalize_mapping(mapping)

    expected = pd.DataFrame(
        {
            "from_date": pd.Series(dtype="datetime64[ns]"),
            "thru_date": pd.Series(dtype="datetime64[ns]"),
            "identifier": pd.Series(dtype="string[python]"),
            "classification_identifier": pd.Series(dtype="string[python]"),
        }
    )
    pd.testing.assert_frame_equal(normalized, expected)


@pytest.mark.parametrize(
    ("mapping", "message"),
    [
        pytest.param(
            pd.DataFrame(
                {
                    "from_date": ["2024-01-01"],
                    "identifier": ["A"],
                    "classification_identifier": ["EQ"],
                }
            ),
            "missing columns: thru_date",
            id="missing-thru-date",
        ),
        pytest.param(
            pd.DataFrame(
                {
                    "from_date": [None],
                    "thru_date": ["2024-01-31"],
                    "identifier": ["A"],
                    "classification_identifier": ["EQ"],
                }
            ),
            "from_date.*null values",
            id="null-date",
        ),
        pytest.param(
            pd.DataFrame(
                {
                    "from_date": [20240101],
                    "thru_date": ["2024-01-31"],
                    "identifier": ["A"],
                    "classification_identifier": ["EQ"],
                }
            ),
            "from_date.*must contain dates",
            id="numeric-date",
        ),
        pytest.param(
            pd.DataFrame(
                {
                    "from_date": ["not-a-date"],
                    "thru_date": ["2024-01-31"],
                    "identifier": ["A"],
                    "classification_identifier": ["EQ"],
                }
            ),
            "from_date.*invalid date",
            id="invalid-date",
        ),
        pytest.param(
            pd.DataFrame(
                {
                    "from_date": [pd.Timestamp("2024-01-01", tz="UTC")],
                    "thru_date": [pd.Timestamp("2024-01-31", tz="UTC")],
                    "identifier": ["A"],
                    "classification_identifier": ["EQ"],
                }
            ),
            "from_date.*timezone-naive",
            id="timezone-aware-date",
        ),
        pytest.param(
            pd.DataFrame(
                {
                    "from_date": ["2024-02-01"],
                    "thru_date": ["2024-01-31"],
                    "identifier": ["A"],
                    "classification_identifier": ["EQ"],
                }
            ),
            "from_date after thru_date.*A.*2024-02-01.*2024-01-31",
            id="reversed-interval",
        ),
        pytest.param(
            pd.DataFrame(
                {
                    "from_date": ["2024-01-01"],
                    "thru_date": ["2024-01-31"],
                    "identifier": [" "],
                    "classification_identifier": ["EQ"],
                }
            ),
            "identifier.*empty string",
            id="blank-identifier",
        ),
    ],
)
def test_effective_mapping_rejects_invalid_schema_dates_or_identities(
    mapping: pd.DataFrame,
    message: str,
) -> None:
    """Dated mapping normalization should reject every ambiguous boundary value."""
    with pytest.raises(PreparationError, match=message):
        _normalize_mapping(mapping, "portfolio mapping")


@pytest.mark.parametrize(
    "classification_identifiers",
    [
        pytest.param(["EQ", "EQ"], id="same-classification"),
        pytest.param(["EQ", "FI"], id="different-classifications"),
    ],
)
def test_effective_mapping_rejects_inclusive_interval_overlap(
    classification_identifiers: list[str],
) -> None:
    """Sharing one inclusive boundary date is an overlap regardless of target class."""
    mapping = pd.DataFrame(
        {
            "from_date": ["2024-01-01", "2024-01-31"],
            "thru_date": ["2024-01-31", "2024-02-29"],
            "identifier": ["A", "A"],
            "classification_identifier": classification_identifiers,
        }
    )

    with pytest.raises(
        PreparationError,
        match="overlapping effective intervals.*A.*2024-01-31.*2024-02-29",
    ):
        normalize_mapping(mapping)


def test_effective_mapping_rejects_interval_nested_beyond_previous_row() -> None:
    """A long interval must remain visible when a shorter nested interval follows it.

    The March interval does not overlap the immediately preceding February interval,
    but it still overlaps the January-through-March interval. This proves validation
    retains the latest prior end rather than comparing only adjacent rows.
    """
    mapping = pd.DataFrame(
        {
            "from_date": ["2024-01-01", "2024-02-01", "2024-03-01"],
            "thru_date": ["2024-03-31", "2024-02-29", "2024-03-15"],
            "identifier": ["A", "A", "A"],
            "classification_identifier": ["LONG", "FEB", "MAR"],
        }
    )

    with pytest.raises(PreparationError, match="overlapping effective intervals.*A"):
        normalize_mapping(mapping)


def test_effective_mapping_changes_assignment_between_adjacent_periods() -> None:
    """One identifier may change class between complete adjacent source periods.

    The January assignment ends on January 31 and the February assignment begins on
    February 1, so each inclusive source period has exactly one classification. The
    financial values remain attached to their complete original periods.
    """
    source = pd.DataFrame(
        {
            "from_date": ["2024-01-01", "2024-02-01"],
            "thru_date": ["2024-01-31", "2024-02-29"],
            "identifier": ["A", "A"],
            "weight": [1.0, 1.0],
            "return": [0.10, 0.20],
        }
    )
    performance = _normalize_performance(source, "portfolio input").frame
    mapping = pd.DataFrame(
        {
            "from_date": ["2024-01-01", "2024-02-01"],
            "thru_date": ["2024-01-31", "2024-02-29"],
            "identifier": ["A", "A"],
            "classification_identifier": ["EQ", "FI"],
        }
    )

    mapped = _map_performance(performance, mapping, "portfolio input")

    assert list(mapped["identifier"]) == ["EQ", "FI"]
    np.testing.assert_allclose(mapped["weight"], [1.0, 1.0])
    np.testing.assert_allclose(mapped["return"], [0.10, 0.20])
    np.testing.assert_allclose(mapped["contribution"], [0.10, 0.20])


def test_effective_mapping_resolves_exact_contained_and_fallback_rows() -> None:
    """Exact, wider, and absent assignments should each resolve deterministically.

    A's assignment exactly equals the source period. B's annual assignment strictly
    contains it. C never appears in the dated mapping and therefore retains its own
    identifier under the approved identity-fallback rule.
    """
    source = pd.DataFrame(
        {
            "from_date": ["2024-01-10"] * 3,
            "thru_date": ["2024-01-20"] * 3,
            "identifier": ["A", "B", "C"],
            "weight": [0.2, 0.3, 0.5],
            "return": [0.10, 0.20, 0.04],
        }
    )
    performance = _normalize_performance(source, "portfolio input").frame
    mapping = pd.DataFrame(
        {
            "from_date": ["2024-01-10", "2024-01-01", "2024-01-01"],
            "thru_date": ["2024-01-20", "2024-12-31", "2024-12-31"],
            "identifier": ["A", "B", "UNUSED"],
            "classification_identifier": ["EQ", "FI", "OTHER"],
        }
    )
    performance_before = performance.copy(deep=True)
    mapping_before = mapping.copy(deep=True)

    mapped = _map_performance(performance, mapping, "portfolio input")

    assert list(mapped["identifier"]) == ["C", "EQ", "FI"]
    np.testing.assert_allclose(mapped["weight"], [0.5, 0.2, 0.3])
    np.testing.assert_allclose(mapped["return"], [0.04, 0.10, 0.20])
    np.testing.assert_allclose(mapped["contribution"], [0.02, 0.02, 0.06])
    pd.testing.assert_frame_equal(performance, performance_before)
    pd.testing.assert_frame_equal(mapping, mapping_before)


@pytest.mark.parametrize(
    ("source_from", "source_thru"),
    [
        pytest.param("2023-12-01", "2023-12-31", id="before"),
        pytest.param("2024-02-01", "2024-02-29", id="between"),
        pytest.param("2024-04-01", "2024-04-30", id="after"),
    ],
)
def test_effective_mapping_rejects_relevant_assignment_gap(
    source_from: str,
    source_thru: str,
) -> None:
    """An identifier present in dated mappings must cover every retained source row."""
    source = pd.DataFrame(
        {
            "from_date": [source_from],
            "thru_date": [source_thru],
            "identifier": ["A"],
            "weight": [1.0],
            "return": [0.05],
        }
    )
    performance = _normalize_performance(source, "portfolio input").frame
    mapping = pd.DataFrame(
        {
            "from_date": ["2024-01-01", "2024-03-01"],
            "thru_date": ["2024-01-31", "2024-03-31"],
            "identifier": ["A", "A"],
            "classification_identifier": ["EQ", "FI"],
        }
    )

    with pytest.raises(
        PreparationError,
        match=rf"effective-assignment gap.*A.*{source_from}.*{source_thru}",
    ):
        _map_performance(performance, mapping, "portfolio input")


@pytest.mark.parametrize(
    ("mapping_from", "mapping_thru", "classifications"),
    [
        pytest.param(
            ["2024-01-15"],
            ["2024-01-31"],
            ["EQ"],
            id="mapping-start-inside-source",
        ),
        pytest.param(
            ["2024-01-01"],
            ["2024-01-15"],
            ["EQ"],
            id="mapping-end-inside-source",
        ),
        pytest.param(
            ["2024-01-01", "2024-01-16"],
            ["2024-01-15", "2024-01-31"],
            ["EQ", "FI"],
            id="classification-change-inside-source",
        ),
    ],
)
def test_effective_mapping_rejects_boundary_inside_source_period(
    mapping_from: list[str],
    mapping_thru: list[str],
    classifications: list[str],
) -> None:
    """Preparation must not split or prorate a period crossed by a mapping boundary."""
    source = pd.DataFrame(
        {
            "from_date": ["2024-01-01"],
            "thru_date": ["2024-01-31"],
            "identifier": ["A"],
            "weight": [1.0],
            "return": [0.05],
        }
    )
    performance = _normalize_performance(source, "portfolio input").frame
    mapping = pd.DataFrame(
        {
            "from_date": mapping_from,
            "thru_date": mapping_thru,
            "identifier": ["A"] * len(mapping_from),
            "classification_identifier": classifications,
        }
    )

    with pytest.raises(
        PreparationError,
        match="classification boundary inside source period.*A.*2024-01-01.*2024-01-31",
    ):
        _map_performance(performance, mapping, "portfolio input")


def test_effective_resolver_defensively_rejects_multiple_containing_intervals() -> None:
    """The resolver should reject ambiguity even after normalization guards it.

    Public normalization rejects these overlapping assignments first. This direct
    package-boundary test protects the resolver's own invariant so a future internal
    caller cannot silently choose EQ or FI for the same January 10–20 source period.
    """
    assignments: list[tuple[pd.Timestamp, pd.Timestamp, str]] = [
        (
            cast(pd.Timestamp, pd.Timestamp("2024-01-01")),
            cast(pd.Timestamp, pd.Timestamp("2024-01-31")),
            "EQ",
        ),
        (
            cast(pd.Timestamp, pd.Timestamp("2024-01-01")),
            cast(pd.Timestamp, pd.Timestamp("2024-02-29")),
            "FI",
        ),
    ]

    with pytest.raises(
        PreparationError,
        match="A.*2024-01-10.*2024-01-20.*multiple effective assignments",
    ):
        _resolve_effective_identifier(
            "A",
            cast(pd.Timestamp, pd.Timestamp("2024-01-10")),
            cast(pd.Timestamp, pd.Timestamp("2024-01-20")),
            assignments,
            "portfolio input mapping",
        )


def test_effective_mapping_rolls_up_collision_with_identity_fallback() -> None:
    """A dated assignment may collide with an already-classified fallback row.

    A maps to EQ while the existing EQ row is absent from the mapping and retains its
    identity. Their 20% and 30% weights combine to 50%; their independently derived 2%
    and 6% contributions combine to 8%, giving a 16% effective mapped return.
    """
    performance = _basic_performance()
    mapping = pd.DataFrame(
        {
            "from_date": ["2024-01-01"],
            "thru_date": ["2024-01-31"],
            "identifier": ["A"],
            "classification_identifier": ["EQ"],
        }
    )

    mapped = _map_performance(performance, mapping, "portfolio input")

    assert list(mapped["identifier"]) == ["B", "EQ"]
    np.testing.assert_allclose(mapped["weight"], [0.5, 0.5])
    np.testing.assert_allclose(mapped["contribution"], [0.02, 0.08])
    np.testing.assert_allclose(mapped["return"], [0.04, 0.16])


def test_effective_mapping_preserves_unexposed_authoritative_contribution() -> None:
    """Dated roll-up must retain a zero-weight group's authoritative contribution.

    A and B have offsetting 50% weights but authoritative contributions of 6% and
    -5%. Their mapped ZERO group therefore has zero weight, a 1% contribution, and a
    mathematically undefined effective return represented by null. C preserves the
    source period's total unit weight.
    """
    source = pd.DataFrame(
        {
            "from_date": ["2024-01-01"] * 3,
            "thru_date": ["2024-01-31"] * 3,
            "identifier": ["A", "B", "C"],
            "weight": [0.5, -0.5, 1.0],
            "return": [0.12, 0.10, 0.02],
            "contribution": [0.06, -0.05, 0.02],
        }
    )
    performance = _normalize_performance(source, "portfolio input").frame
    mapping = pd.DataFrame(
        {
            "from_date": ["2024-01-01", "2024-01-01"],
            "thru_date": ["2024-01-31", "2024-01-31"],
            "identifier": ["A", "B"],
            "classification_identifier": ["ZERO", "ZERO"],
        }
    )

    mapped = _map_performance(performance, mapping, "portfolio input")
    zero_group = mapped.loc[mapped["identifier"] == "ZERO"].iloc[0]

    assert zero_group["weight"] == 0.0
    assert zero_group["contribution"] == pytest.approx(0.01)
    assert pd.isna(zero_group["return"])


def test_mapping_rollup_combines_collisions_and_uses_identity_fallback() -> None:
    """Mapped and already-classified rows should combine while absent keys survive."""
    performance = _basic_performance()
    mapping = pd.DataFrame(
        {
            # A maps onto the existing EQ identifier. UNUSED proves that irrelevant
            # but valid mapping rows do not affect the selected performance stream.
            "identifier": ["A", "UNUSED"],
            "classification_identifier": ["EQ", "OTHER"],
        }
    )
    performance_before = performance.copy(deep=True)
    mapping_before = mapping.copy(deep=True)

    mapped = _map_performance(performance, mapping, "portfolio input")

    assert list(mapped["identifier"]) == ["B", "EQ"]
    np.testing.assert_allclose(mapped["weight"], [0.5, 0.5], rtol=1e-12, atol=1e-12)
    # B is absent from the mapping and retains its 2% contribution. A contributes
    # 0.2 * 10% = 2%; existing EQ contributes 0.3 * 20% = 6%. Their mapped EQ
    # effective return is therefore (2% + 6%) / (20% + 30%) = 16%.
    np.testing.assert_allclose(
        mapped["contribution"],
        [0.02, 0.08],
        rtol=1e-12,
        atol=1e-12,
    )
    np.testing.assert_allclose(mapped["return"], [0.04, 0.16], rtol=1e-12, atol=1e-12)
    assert list(mapped.columns) == list(NORMALIZED_PERFORMANCE_COLUMNS)
    pd.testing.assert_frame_equal(performance, performance_before)
    pd.testing.assert_frame_equal(mapping, mapping_before)


def test_portfolio_and_benchmark_mappings_are_independent() -> None:
    """Each side should use only its own caller-supplied classification mapping."""
    performance = _basic_performance()
    portfolio_mapping = pd.DataFrame(
        {"identifier": ["A"], "classification_identifier": ["PORT_GROUP"]}
    )
    benchmark_mapping = pd.DataFrame(
        {"identifier": ["A"], "classification_identifier": ["BENCH_GROUP"]}
    )

    portfolio = _map_performance(performance, portfolio_mapping, "portfolio input")
    benchmark = _map_performance(performance, benchmark_mapping, "benchmark input")

    assert "PORT_GROUP" in set(portfolio["identifier"])
    assert "PORT_GROUP" not in set(benchmark["identifier"])
    assert "BENCH_GROUP" in set(benchmark["identifier"])
    assert "BENCH_GROUP" not in set(portfolio["identifier"])


def test_mapping_rolls_up_each_source_period_independently() -> None:
    """Static assignments should aggregate within, never across, source periods."""
    source = pd.DataFrame(
        {
            "from_date": ["2024-01-01"] * 2 + ["2024-02-01"] * 2,
            "thru_date": ["2024-01-31"] * 2 + ["2024-02-29"] * 2,
            "identifier": ["A", "B", "A", "B"],
            "weight": [0.6, 0.4, 0.6, 0.4],
            "return": [0.10, 0.20, 0.05, -0.10],
        }
    )
    performance = _normalize_performance(source, "portfolio input").frame
    mapping = pd.DataFrame(
        {
            "identifier": ["A", "B"],
            "classification_identifier": ["TOTAL", "TOTAL"],
        }
    )

    mapped = _map_performance(performance, mapping, "portfolio input")

    assert list(mapped["identifier"]) == ["TOTAL", "TOTAL"]
    assert list(mapped["quantity_of_days"]) == [31, 29]
    np.testing.assert_allclose(mapped["weight"], [1.0, 1.0], rtol=1e-12, atol=1e-12)
    # January contributes 60% * 10% + 40% * 20% = 14%. February contributes
    # 60% * 5% + 40% * -10% = -1%. With unit mapped weight, effective returns
    # equal those independently calculated source-period contributions.
    np.testing.assert_allclose(
        mapped["contribution"],
        [0.14, -0.01],
        rtol=1e-12,
        atol=1e-12,
    )
    np.testing.assert_allclose(mapped["return"], [0.14, -0.01], rtol=1e-12, atol=1e-12)


@pytest.mark.parametrize(
    ("second_contribution", "expected_return"),
    [
        pytest.param(-0.06, 0.0, id="zero-contribution"),
        pytest.param(-0.05, np.nan, id="nonzero-contribution"),
    ],
)
def test_mapping_uses_defined_zero_or_null_for_zero_net_weight(
    second_contribution: float,
    expected_return: float,
) -> None:
    """Zero mapped exposure should follow its exact contribution-dependent branch."""
    source = pd.DataFrame(
        {
            "from_date": ["2024-01-01"] * 3,
            "thru_date": ["2024-01-31"] * 3,
            "identifier": ["A", "B", "C"],
            # A and B cancel to zero mapped exposure; C keeps the period net at one.
            "weight": [0.5, -0.5, 1.0],
            "return": [0.12, 0.10, 0.02],
            "contribution": [0.06, second_contribution, 0.02],
        }
    )
    performance = _normalize_performance(source, "portfolio input").frame
    mapping = pd.DataFrame(
        {
            "identifier": ["A", "B", "C"],
            "classification_identifier": ["ZERO", "ZERO", "OTHER"],
        }
    )

    mapped = _map_performance(performance, mapping, "portfolio input")
    zero_group = mapped.loc[mapped["identifier"] == "ZERO"].iloc[0]

    assert zero_group["weight"] == 0.0
    assert zero_group["contribution"] == pytest.approx(0.06 + second_contribution)
    if np.isnan(expected_return):
        assert pd.isna(zero_group["return"])
    else:
        assert zero_group["return"] == expected_return


def test_mapping_does_not_round_a_small_nonzero_weight_to_zero() -> None:
    """The tolerance should verify conservation, not choose effective-return branches."""
    source = pd.DataFrame(
        {
            "from_date": ["2024-01-01"] * 3,
            "thru_date": ["2024-01-31"] * 3,
            "identifier": ["A", "B", "C"],
            "weight": [0.5, -0.499999999999999, 0.999999999999999],
            "return": [0.02, 0.0, 0.0],
            "contribution": [0.01, 0.0, 0.0],
        }
    )
    performance = _normalize_performance(source, "portfolio input").frame
    mapping = pd.DataFrame(
        {
            "identifier": ["A", "B"],
            "classification_identifier": ["TINY", "TINY"],
        }
    )

    mapped = _map_performance(performance, mapping, "portfolio input")
    tiny_group = mapped.loc[mapped["identifier"] == "TINY"].iloc[0]

    assert tiny_group["weight"] != 0.0
    assert tiny_group["return"] == pytest.approx(
        tiny_group["contribution"] / tiny_group["weight"]
    )


def test_no_mapping_preserves_authoritative_return_and_drops_metadata() -> None:
    """Without mapping, source financial values should be copied without reinterpretation."""
    source = pd.DataFrame(
        {
            "from_date": ["2024-01-01"],
            "thru_date": ["2024-01-31"],
            "identifier": ["A"],
            "weight": [1.0],
            "return": [0.10],
            # Authoritative contribution may intentionally differ from weight * return.
            "contribution": [0.12],
            "portfolio_code": ["P"],
            "name": ["Asset A"],
        }
    )
    performance = _normalize_performance(source, "portfolio input").frame

    mapped = _map_performance(performance, None, "portfolio input")

    assert mapped.loc[0, "return"] == 0.10
    assert mapped.loc[0, "contribution"] == 0.12
    assert "portfolio_code" not in mapped.columns
    assert "name" not in mapped.columns


def test_empty_mapping_uses_identity_fallback_but_applies_effective_returns() -> None:
    """An explicitly supplied empty mapping should classify every row as itself."""
    performance = _basic_performance()
    empty_mapping = pd.DataFrame(columns=["identifier", "classification_identifier"])

    mapped = _map_performance(performance, empty_mapping, "portfolio input")

    assert list(mapped["identifier"]) == ["A", "B", "EQ"]
    np.testing.assert_allclose(mapped["return"], [0.10, 0.04, 0.20])


def test_invalid_unused_mapping_row_is_not_silently_filtered() -> None:
    """All mapping identities should be valid even when no source row uses them."""
    performance = _basic_performance()
    mapping = pd.DataFrame(
        {
            "identifier": ["A", "UNUSED"],
            "classification_identifier": ["EQ", None],
        }
    )

    with pytest.raises(PreparationError, match="classification_identifier.*non-null"):
        _map_performance(performance, mapping, "portfolio input")


@pytest.mark.parametrize("value", [True, "1e-12", 0.0, -1.0, np.inf, np.nan])
def test_mapping_rejects_invalid_reconciliation_tolerances(value: Any) -> None:
    """Mapping conservation should use only a finite positive numerical tolerance."""
    expected_error = TypeError if isinstance(value, str | bool) else PreparationError

    with pytest.raises(expected_error):
        _map_performance(
            _basic_performance(),
            None,
            "portfolio input",
            reconciliation_tolerance=cast(float, value),
        )


def test_mapping_requires_a_performance_dataframe() -> None:
    """The mapping stage should enforce its normalized pandas input boundary."""
    with pytest.raises(TypeError, match="must be a pandas DataFrame"):
        _map_performance(cast(pd.DataFrame, []), None, "portfolio input")


def test_mapping_rejects_nonfinite_group_aggregation() -> None:
    """Finite source rows must not be allowed to overflow a mapped group total."""
    source = pd.DataFrame(
        {
            "from_date": ["2024-01-01"] * 5,
            "thru_date": ["2024-01-31"] * 5,
            "identifier": ["P1", "N1", "P2", "N2", "UNIT"],
            "weight": [1.0, -1.0, 1.0, -1.0, 1.0],
            "return": [0.0] * 5,
            # The complete source period nets to zero contribution. Mapping the two
            # positive rows together overflows before opposite groups can cancel it.
            "contribution": [1e308, -1e308, 1e308, -1e308, 0.0],
        }
    )
    performance = _normalize_performance(source, "portfolio input").frame
    mapping = pd.DataFrame(
        {
            "identifier": ["P1", "P2", "N1", "N2"],
            "classification_identifier": ["POS", "POS", "NEG", "NEG"],
        }
    )

    with pytest.raises(PreparationError, match="aggregation produced a non-finite value"):
        _map_performance(performance, mapping, "portfolio input")
