"""
FRTB IMA prototype — NPR 2.0-style capital calculator.

Prototype only. Not for regulatory reporting.
All regulatory statements are working assumptions based on the
March 2026 U.S. NPR 2.0 proposal and Basel FRTB IMA concepts.
"""

from frtb_ima.data_models import (
    DeskCapitalResult,
    LiquidityHorizon,
    ModellabilityStatus,
    RealPriceObservation,
    RiskClass,
    RiskFactor,
    ScenarioPnL,
)
from frtb_ima.scenario import (
    ScenarioMetadata,
    ScenarioSetType,
    ScenarioVector,
    make_scenario_metadata,
    validate_aligned_metadata,
    validate_unique_scenarios,
)
from frtb_ima.scenario_validation import (
    NestedLHValidationError,
    NestedLHValidationResult,
    validate_nested_lh_vectors,
)

__all__ = [
    "DeskCapitalResult",
    "LiquidityHorizon",
    "ModellabilityStatus",
    "RealPriceObservation",
    "RiskClass",
    "RiskFactor",
    "ScenarioPnL",
    "ScenarioMetadata",
    "ScenarioSetType",
    "ScenarioVector",
    "make_scenario_metadata",
    "validate_aligned_metadata",
    "validate_unique_scenarios",
    "NestedLHValidationError",
    "NestedLHValidationResult",
    "validate_nested_lh_vectors",
]
