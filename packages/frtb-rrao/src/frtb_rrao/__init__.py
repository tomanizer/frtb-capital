"""Standardised Approach residual risk add-on scaffold."""

from frtb_rrao._version import __version__
from frtb_rrao.data_models import (
    RraoCalculationContext,
    RraoCapitalLine,
    RraoCapitalResult,
    RraoCitation,
    RraoClassification,
    RraoClassificationDecision,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    RraoSubtotal,
)
from frtb_rrao.scaffold import PACKAGE_METADATA, calculate_rrao_capital
from frtb_rrao.validation import (
    RraoInputError,
    normalise_gross_effective_notional,
    validate_rrao_positions,
)

__all__ = [
    "PACKAGE_METADATA",
    "RraoCalculationContext",
    "RraoCapitalLine",
    "RraoCapitalResult",
    "RraoCitation",
    "RraoClassification",
    "RraoClassificationDecision",
    "RraoEvidenceType",
    "RraoExclusionReason",
    "RraoInputError",
    "RraoPosition",
    "RraoRegulatoryProfile",
    "RraoSourceLineage",
    "RraoSubtotal",
    "__version__",
    "calculate_rrao_capital",
    "normalise_gross_effective_notional",
    "validate_rrao_positions",
]
