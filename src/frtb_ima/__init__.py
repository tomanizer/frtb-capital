"""
FRTB IMA prototype — NPR 2.0-style capital calculator.

Prototype only. Not for regulatory reporting.
All regulatory statements are working assumptions based on the
March 2026 U.S. NPR 2.0 proposal and Basel FRTB IMA concepts.
"""

from frtb_ima.data_contracts import (
    CapitalRunResult,
    DeskRun,
    Position,
    RFETEvidence,
    RiskFactorBucket,
    RiskFactorDefinition,
    ScenarioCube,
)
from frtb_ima.data_models import (
    DeskCapitalResult,
    LiquidityHorizon,
    ModellabilityStatus,
    RealPriceObservation,
    RiskClass,
    RiskFactor,
    ScenarioPnL,
)
from frtb_ima.imcc import (
    IMCCResult,
    IMCCRiskClassComponent,
    StressScalingResult,
    imcc_breakdown,
    imcc_breakdown_for_policy,
    imcc_constrained_breakdown,
    imcc_unconstrained_breakdown,
    scale_stress_es_breakdown,
)
from frtb_ima.lha_builder import (
    NestedLHScenarioVectors,
    imcc_nested_lh_vectors_from_cube,
    nested_lh_vectors_from_cube,
    per_risk_class_nested_lh_vectors_from_cube,
    risk_factor_names_for_lh_subset,
)
from frtb_ima.regimes import (
    CalculationContext,
    NMRFTaxonomyMode,
    PLAMetricsRequired,
    RegulatoryPolicy,
    RegulatoryRegime,
    TypeASESAggregationMode,
    UnsupportedFeature,
    UnsupportedRegulatoryFeature,
    get_policy,
)
from frtb_ima.rfet_evidence import (
    RFETEvidenceAssessment,
    RFETExclusionReason,
    RFETObservationExclusion,
    assess_rfet_evidence,
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
    "CalculationContext",
    "CapitalRunResult",
    "DeskCapitalResult",
    "DeskRun",
    "IMCCResult",
    "IMCCRiskClassComponent",
    "LiquidityHorizon",
    "ModellabilityStatus",
    "NMRFTaxonomyMode",
    "NestedLHScenarioVectors",
    "NestedLHValidationError",
    "NestedLHValidationResult",
    "PLAMetricsRequired",
    "Position",
    "RFETEvidence",
    "RFETEvidenceAssessment",
    "RFETExclusionReason",
    "RFETObservationExclusion",
    "RealPriceObservation",
    "RegulatoryPolicy",
    "RegulatoryRegime",
    "RiskClass",
    "RiskFactor",
    "RiskFactorBucket",
    "RiskFactorDefinition",
    "ScenarioCube",
    "ScenarioMetadata",
    "ScenarioPnL",
    "ScenarioSetType",
    "ScenarioVector",
    "StressScalingResult",
    "TypeASESAggregationMode",
    "UnsupportedFeature",
    "UnsupportedRegulatoryFeature",
    "assess_rfet_evidence",
    "get_policy",
    "imcc_breakdown",
    "imcc_breakdown_for_policy",
    "imcc_constrained_breakdown",
    "imcc_nested_lh_vectors_from_cube",
    "imcc_unconstrained_breakdown",
    "make_scenario_metadata",
    "nested_lh_vectors_from_cube",
    "per_risk_class_nested_lh_vectors_from_cube",
    "risk_factor_names_for_lh_subset",
    "scale_stress_es_breakdown",
    "validate_aligned_metadata",
    "validate_nested_lh_vectors",
    "validate_unique_scenarios",
]
