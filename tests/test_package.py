"""Tests for the public package boundary."""

import perfattr


def test_package_exposes_version() -> None:
    """The installed package should expose its distribution version."""
    assert perfattr.__version__ == "0.1.0"


def test_package_exposes_step_two_preparation_api() -> None:
    """The root package should expose the implemented preparation entry points."""
    assert perfattr.PreparationError is not None
    assert perfattr.PreparationWarning is not None
    assert callable(perfattr.select_portfolio)


def test_package_exposes_step_three_frequency_api() -> None:
    """The root package should expose the accepted reporting-frequency enum."""
    assert perfattr.Frequency.MONTHLY.value == "Monthly"
