from __future__ import annotations

import frtb_rrao

EXPECTED_PUBLIC_API = (
    "PACKAGE_METADATA",
    "SUPPORTED_RRAO_ALLOCATION_DIMENSIONS",
    "RraoAdapterResult",
    "RraoAdapterWarning",
    "RraoAllocationBucket",
    "RraoAllocationDimension",
    "RraoAllocationReport",
    "RraoBackToBackMatch",
    "RraoCalculationContext",
    "RraoCapitalLine",
    "RraoCapitalResult",
    "RraoCitation",
    "RraoClassification",
    "RraoClassificationDecision",
    "RraoEvidenceType",
    "RraoExclusionReason",
    "RraoInputError",
    "RraoInvestmentFundDescriptor",
    "RraoInvestmentFundExposureType",
    "RraoInvestmentFundMethod",
    "RraoPosition",
    "RraoRegulatoryProfile",
    "RraoRejectedRow",
    "RraoRuleProfile",
    "RraoSourceLineage",
    "RraoSubtotal",
    "__version__",
    "adapt_crif_records",
    "adapt_fnet_records",
    "adapt_rrao_records",
    "build_rrao_allocation_report",
    "build_rrao_allocation_reports",
    "calculate_rrao_capital",
    "classify_rrao_position",
    "classify_rrao_positions",
    "get_rrao_rule_profile",
    "input_hash_for_positions",
    "resolve_rrao_allocation_dimension",
    "serialize_rrao_allocation_report",
    "serialize_rrao_result",
    "validate_rrao_allocation_report",
    "validate_rrao_positions",
    "validate_rrao_result_reconciliation",
)


def test_top_level_public_api_surface_is_explicit_and_narrow() -> None:
    assert frtb_rrao.__all__ == list(EXPECTED_PUBLIC_API)
    assert len(frtb_rrao.__all__) < 50
