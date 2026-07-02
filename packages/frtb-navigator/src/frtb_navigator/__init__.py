"""Read-only FRTB Navigator application package.

The package owns the backend and frontend application surfaces for inspecting
already-resolved FRTB capital read models. It does not calculate capital,
classify regulatory inputs, generate shocks, interpolate surfaces, or synthesize
missing rows.
"""

from __future__ import annotations

from frtb_common import CapitalComponentMetadata, ImplementationStatus, ValidationStatus

from frtb_navigator._version import __version__

PACKAGE_METADATA = CapitalComponentMetadata(
    package_name="frtb-navigator",
    import_name="frtb_navigator",
    component_name="FRTB Navigator",
    implementation_status=ImplementationStatus.PARTIAL,
    validation_status=ValidationStatus.PENDING,
)

__all__ = ["PACKAGE_METADATA", "__version__"]
