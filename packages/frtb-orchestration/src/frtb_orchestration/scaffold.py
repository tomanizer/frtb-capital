"""Suite-level aggregation entry point and package metadata."""

from __future__ import annotations

from frtb_common import (
    CapitalComponentMetadata,
    ImplementationStatus,
    ValidationStatus,
)

from frtb_orchestration.suite import calculate_suite_capital

PACKAGE_METADATA = CapitalComponentMetadata(
    package_name="frtb-orchestration",
    import_name="frtb_orchestration",
    component_name="Suite-level capital aggregation",
    implementation_status=ImplementationStatus.IMPLEMENTED,
    validation_status=ValidationStatus.PENDING,
)

__all__ = [
    "PACKAGE_METADATA",
    "calculate_suite_capital",
]
