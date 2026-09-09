"""Shared readers for complete prepared-input fixture pairs."""

from pathlib import Path

import pandas as pd


_FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def read_prepared_inputs(case_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read a fixture's prepared portfolio and benchmark frames."""
    case_path = _FIXTURE_ROOT / case_name
    return (
        pd.read_csv(case_path / "portfolio.csv"),
        pd.read_csv(case_path / "benchmark.csv"),
    )
