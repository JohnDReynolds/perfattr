"""Tests for the public package boundary."""

import perfattr


def test_package_exposes_version() -> None:
    """The installed package should expose its distribution version."""
    assert perfattr.__version__ == "0.1.0"
