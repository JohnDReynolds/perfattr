"""Tests for the public attribution-effect-linking policy boundary."""

from pathlib import Path
from typing import cast

import pandas as pd
import pytest

from perfattr import (
    AttributionError,
    AttributionMethod,
    EffectLinkingMethod,
    calculate_attribution,
)


_FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def _read_inputs(case_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read a fixture's two prepared input frames."""
    case_path = _FIXTURE_ROOT / case_name
    return (
        pd.read_csv(case_path / "portfolio.csv"),
        pd.read_csv(case_path / "benchmark.csv"),
    )


@pytest.mark.parametrize(
    "invalid_linker",
    (
        EffectLinkingMethod.FRONGELLO.value,
        EffectLinkingMethod.MENCHERO.value,
        AttributionMethod.BRINSON_FACHLER_TWO_EFFECT,
        object(),
    ),
)
def test_calculation_rejects_an_unvalidated_effect_linker(
    invalid_linker: object,
) -> None:
    """Only the dedicated enum may select a financial linking policy."""
    portfolio, benchmark = _read_inputs("single_period_derived")

    with pytest.raises(
        TypeError,
        match="effect_linking_method must be an EffectLinkingMethod",
    ):
        calculate_attribution(
            portfolio,
            benchmark,
            effect_linking_method=cast(EffectLinkingMethod, invalid_linker),
        )


def test_frongello_reaches_the_released_financial_validation() -> None:
    """The implemented public policy must enter ordinary input validation."""
    with pytest.raises(AttributionError, match="portfolio input is missing required"):
        calculate_attribution(
            pd.DataFrame(),
            pd.DataFrame(),
            effect_linking_method=EffectLinkingMethod.FRONGELLO,
        )


def test_menchero_reaches_the_released_financial_validation() -> None:
    """The implemented public policy must enter ordinary input validation."""
    with pytest.raises(AttributionError, match="portfolio input is missing required"):
        calculate_attribution(
            pd.DataFrame(),
            pd.DataFrame(),
            effect_linking_method=EffectLinkingMethod.MENCHERO,
        )
