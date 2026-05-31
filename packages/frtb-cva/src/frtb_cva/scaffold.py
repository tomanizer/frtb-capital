"""Scaffold boundary for the CVA calculation package."""

from __future__ import annotations

from frtb_common import (
    CapitalComponentMetadata,
    ImplementationStatus,
    ValidationStatus,
)

PACKAGE_METADATA = CapitalComponentMetadata(
    package_name="frtb-cva",
    import_name="frtb_cva",
    component_name="Credit Valuation Adjustment capital",
    implementation_status=ImplementationStatus.PARTIAL,
    validation_status=ValidationStatus.NOT_STARTED,
)
