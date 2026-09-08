"""Tests for the public package boundary."""

import perfattr


def test_package_exposes_version() -> None:
    """The installed package should expose its distribution version."""
    assert perfattr.__version__ == "0.11.0a1"


def test_package_exposes_attribution_methods() -> None:
    """The root package should expose every approved effect convention."""
    assert (
        perfattr.AttributionMethod.BRINSON_FACHLER_TWO_EFFECT.value
        == "Brinson-Fachler Two-Effect"
    )
    assert (
        perfattr.AttributionMethod.BRINSON_FACHLER_THREE_EFFECT.value
        == "Brinson-Fachler Three-Effect"
    )
    assert (
        perfattr.AttributionMethod.BRINSON_HOOD_BEEBOWER_THREE_EFFECT.value
        == "Brinson-Hood-Beebower Three-Effect"
    )
    assert (
        perfattr.AttributionMethod.BRINSON_HOOD_BEEBOWER_TWO_EFFECT.value
        == "Brinson-Hood-Beebower Two-Effect"
    )


def test_package_exposes_effect_linking_methods() -> None:
    """The root package should expose every approved effect-linking identity."""
    assert perfattr.EffectLinkingMethod.CARINO.value == "Carino"
    assert perfattr.EffectLinkingMethod.FRONGELLO.value == "Frongello"
    assert perfattr.EffectLinkingMethod.MENCHERO.value == "Menchero"


def test_package_exposes_staged_geometric_api() -> None:
    """The root package should expose the approved separate geometric boundary."""
    assert perfattr.GeometricAttributionResult is not None
    assert callable(perfattr.calculate_geometric_attribution)


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
