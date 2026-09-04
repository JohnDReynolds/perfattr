"""Tests for the public package boundary."""

import perfattr


def test_package_exposes_version() -> None:
    """The installed package should expose its distribution version."""
    assert perfattr.__version__ == "0.3.0a1"


def test_package_exposes_step_two_preparation_api() -> None:
    """The root package should expose the implemented preparation entry points."""
    assert perfattr.PreparationError is not None
    assert perfattr.PreparationWarning is not None
    assert callable(perfattr.select_portfolio)


def test_package_exposes_step_three_frequency_api() -> None:
    """The root package should expose the accepted reporting-frequency enum."""
    assert perfattr.Frequency.MONTHLY.value == "Monthly"


def test_package_exposes_step_six_composition_api() -> None:
    """The root package should expose preparation composition and its result type."""
    assert perfattr.PreparationResult is not None
    assert callable(perfattr.prepare_attribution)


def test_package_exposes_step_seven_csv_readers() -> None:
    """The root package should expose all three canonical local CSV readers."""
    assert callable(perfattr.read_performance_csv)
    assert callable(perfattr.read_mapping_csv)
    assert callable(perfattr.read_classification_csv)
    assert callable(perfattr.normalize_mapping)
    assert callable(perfattr.normalize_classification)
