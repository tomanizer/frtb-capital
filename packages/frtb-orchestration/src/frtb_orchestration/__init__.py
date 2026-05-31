"""Suite-level orchestration scaffold."""

from frtb_orchestration._version import __version__
from frtb_orchestration.cva_handoff import CvaResultHandoff, recognise_cva_result
from frtb_orchestration.scaffold import PACKAGE_METADATA, calculate_suite_capital
from frtb_orchestration.standardised import (
    ComponentResultHandoff,
    OrchestrationInputError,
    StandardisedComponent,
    compose_standardised_approach_capital,
    recognise_drc_result,
    recognise_rrao_result,
    recognise_sbm_result,
)

__all__ = [
    "PACKAGE_METADATA",
    "ComponentResultHandoff",
    "CvaResultHandoff",
    "OrchestrationInputError",
    "StandardisedComponent",
    "__version__",
    "calculate_suite_capital",
    "compose_standardised_approach_capital",
    "recognise_cva_result",
    "recognise_drc_result",
    "recognise_rrao_result",
    "recognise_sbm_result",
]
