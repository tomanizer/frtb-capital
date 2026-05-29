"""Public boundary for the SBM calculation package."""

from __future__ import annotations

from frtb_common import (
    CapitalComponentMetadata,
    ImplementationStatus,
    ValidationStatus,
)

from frtb_sbm.capital import calculate_sbm_capital

PACKAGE_METADATA = CapitalComponentMetadata(
    package_name="frtb-sbm",
    import_name="frtb_sbm",
    component_name="Standardised Approach sensitivities-based method",
    implementation_status=ImplementationStatus.PARTIAL,
    validation_status=ValidationStatus.PENDING,
)

__all__ = ["PACKAGE_METADATA", "calculate_sbm_capital"]
