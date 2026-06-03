"""Suite-level orchestration scaffold."""

from frtb_common import ComponentCapitalSummary, StandardisedComponent

from frtb_orchestration._version import __version__
from frtb_orchestration.cva_handoff import (
    CvaCapitalSummary,
    CvaResultHandoff,
    recognise_cva_result,
    recognise_cva_summary,
)
from frtb_orchestration.manifest import (
    CVA_COUNTERPARTY_HANDOFF,
    CVA_HEDGE_HANDOFF,
    CVA_NETTING_SET_HANDOFF,
    CVA_SA_SENSITIVITY_HANDOFF,
    DRC_CTP_HANDOFF,
    DRC_NONSEC_HANDOFF,
    DRC_SECURITISATION_NON_CTP_HANDOFF,
    RRAO_POSITIONS_HANDOFF,
    SBM_GIRR_DELTA_HANDOFF,
    STANDARDISED_REQUIRED_HANDOFF_KEYS,
    STANDARDISED_REQUIRED_INPUT_TABLE_KEYS,
    CapitalRunManifest,
    ManifestHandoffRoute,
    ManifestHandoffValidation,
    ManifestValidationResult,
    SaManifestRunResult,
    run_standardised_approach_from_manifest,
    validate_capital_run_manifest,
)
from frtb_orchestration.scaffold import PACKAGE_METADATA, calculate_suite_capital
from frtb_orchestration.standardised import (
    OrchestrationInputError,
    StandardisedApproachCapitalResult,
    StandardisedComponentSubtotal,
    StandardisedFallbackRoute,
    compose_standardised_approach_capital,
    standardised_jurisdiction_family,
)

__all__ = [
    "CVA_COUNTERPARTY_HANDOFF",
    "CVA_HEDGE_HANDOFF",
    "CVA_NETTING_SET_HANDOFF",
    "CVA_SA_SENSITIVITY_HANDOFF",
    "DRC_CTP_HANDOFF",
    "DRC_NONSEC_HANDOFF",
    "DRC_SECURITISATION_NON_CTP_HANDOFF",
    "PACKAGE_METADATA",
    "RRAO_POSITIONS_HANDOFF",
    "SBM_GIRR_DELTA_HANDOFF",
    "STANDARDISED_REQUIRED_HANDOFF_KEYS",
    "STANDARDISED_REQUIRED_INPUT_TABLE_KEYS",
    "CapitalRunManifest",
    "ComponentCapitalSummary",
    "CvaCapitalSummary",
    "CvaResultHandoff",
    "ManifestHandoffRoute",
    "ManifestHandoffValidation",
    "ManifestValidationResult",
    "OrchestrationInputError",
    "SaManifestRunResult",
    "StandardisedApproachCapitalResult",
    "StandardisedComponent",
    "StandardisedComponentSubtotal",
    "StandardisedFallbackRoute",
    "__version__",
    "calculate_suite_capital",
    "compose_standardised_approach_capital",
    "recognise_cva_result",
    "recognise_cva_summary",
    "run_standardised_approach_from_manifest",
    "standardised_jurisdiction_family",
    "validate_capital_run_manifest",
]
