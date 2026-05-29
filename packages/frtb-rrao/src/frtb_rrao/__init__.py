"""Standardised Approach residual risk add-on package."""

from frtb_rrao._version import __version__
from frtb_rrao.allocation import (
    SUPPORTED_RRAO_ALLOCATION_DIMENSIONS,
    build_rrao_allocation_report,
    build_rrao_allocation_reports,
    resolve_rrao_allocation_dimension,
    serialize_rrao_allocation_report,
    validate_rrao_allocation_report,
)
from frtb_rrao.audit import (
    input_hash_for_positions,
    serialize_rrao_result,
    validate_rrao_result_reconciliation,
)
from frtb_rrao.classification import classify_rrao_position, classify_rrao_positions
from frtb_rrao.crif import (
    RraoAdapterResult,
    RraoAdapterWarning,
    RraoRejectedRow,
    adapt_crif_records,
    adapt_fnet_records,
    adapt_rrao_records,
)
from frtb_rrao.data_models import (
    RraoAllocationBucket,
    RraoAllocationDimension,
    RraoAllocationReport,
    RraoBackToBackMatch,
    RraoCalculationContext,
    RraoCapitalLine,
    RraoCapitalResult,
    RraoCitation,
    RraoClassification,
    RraoClassificationDecision,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoInvestmentFundDescriptor,
    RraoInvestmentFundExposureType,
    RraoInvestmentFundMethod,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    RraoSubtotal,
)
from frtb_rrao.regimes import (
    RraoRuleProfile,
    get_rrao_rule_profile,
)
from frtb_rrao.scaffold import PACKAGE_METADATA, calculate_rrao_capital
from frtb_rrao.validation import (
    RraoInputError,
    validate_rrao_positions,
)

__all__ = [
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
]
