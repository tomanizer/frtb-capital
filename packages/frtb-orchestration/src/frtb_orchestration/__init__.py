"""Suite-level orchestration scaffold."""

from frtb_common import ComponentCapitalSummary, StandardisedComponent

from frtb_orchestration._version import __version__
from frtb_orchestration.cva_summary import (
    CvaCapitalSummary,
    recognise_cva_summary,
)
from frtb_orchestration.ima_summary import (
    ImaCapitalSummary,
    recognise_ima_summary,
)
from frtb_orchestration.manifest import (
    CVA_COUNTERPARTY_INPUT_TABLE,
    CVA_HEDGE_INPUT_TABLE,
    CVA_NETTING_SET_INPUT_TABLE,
    CVA_SA_SENSITIVITY_INPUT_TABLE,
    DRC_CTP_INPUT_TABLE,
    DRC_NONSEC_INPUT_TABLE,
    DRC_SECURITISATION_NON_CTP_INPUT_TABLE,
    RRAO_POSITIONS_INPUT_TABLE,
    SBM_GIRR_DELTA_INPUT_TABLE,
    STANDARDISED_REQUIRED_INPUT_TABLE_KEYS,
    CapitalRunManifest,
    ManifestInputTableRoute,
    ManifestInputTableValidation,
    ManifestValidationResult,
    SaManifestRunResult,
    run_standardised_approach_from_manifest,
    validate_capital_run_manifest,
)
from frtb_orchestration.scaffold import (
    PACKAGE_METADATA,
    aggregate_suite_attribution,
    build_suite_attribution_report,
    calculate_suite_capital,
)
from frtb_orchestration.standardised import (
    OrchestrationInputError,
    StandardisedApproachCapitalResult,
    StandardisedComponentSubtotal,
    StandardisedFallbackRoute,
    compose_standardised_approach_capital,
    standardised_jurisdiction_family,
)
from frtb_orchestration.suite import (
    SuiteAttributionComponentReport,
    SuiteAttributionReport,
    SuiteAttributionResult,
    SuiteCapitalResult,
    suite_jurisdiction_family,
)
from frtb_orchestration.suite_attribution_summary import (
    SuiteAttributionGroupSummary,
    SuiteAttributionRecordSummary,
    SuiteAttributionSummary,
    suite_attribution_residual_records,
    suite_attribution_unsupported_records,
    summarise_suite_attribution,
    top_suite_attribution_contributors,
)

__all__ = [
    "CVA_COUNTERPARTY_INPUT_TABLE",
    "CVA_HEDGE_INPUT_TABLE",
    "CVA_NETTING_SET_INPUT_TABLE",
    "CVA_SA_SENSITIVITY_INPUT_TABLE",
    "DRC_CTP_INPUT_TABLE",
    "DRC_NONSEC_INPUT_TABLE",
    "DRC_SECURITISATION_NON_CTP_INPUT_TABLE",
    "PACKAGE_METADATA",
    "RRAO_POSITIONS_INPUT_TABLE",
    "SBM_GIRR_DELTA_INPUT_TABLE",
    "STANDARDISED_REQUIRED_INPUT_TABLE_KEYS",
    "CapitalRunManifest",
    "ComponentCapitalSummary",
    "CvaCapitalSummary",
    "ImaCapitalSummary",
    "ManifestInputTableRoute",
    "ManifestInputTableValidation",
    "ManifestValidationResult",
    "OrchestrationInputError",
    "SaManifestRunResult",
    "StandardisedApproachCapitalResult",
    "StandardisedComponent",
    "StandardisedComponentSubtotal",
    "StandardisedFallbackRoute",
    "SuiteAttributionComponentReport",
    "SuiteAttributionGroupSummary",
    "SuiteAttributionRecordSummary",
    "SuiteAttributionReport",
    "SuiteAttributionResult",
    "SuiteAttributionSummary",
    "SuiteCapitalResult",
    "__version__",
    "aggregate_suite_attribution",
    "build_suite_attribution_report",
    "calculate_suite_capital",
    "compose_standardised_approach_capital",
    "recognise_cva_summary",
    "recognise_ima_summary",
    "run_standardised_approach_from_manifest",
    "standardised_jurisdiction_family",
    "suite_attribution_residual_records",
    "suite_attribution_unsupported_records",
    "suite_jurisdiction_family",
    "summarise_suite_attribution",
    "top_suite_attribution_contributors",
    "validate_capital_run_manifest",
]
