"""Scaffold boundary for the future CVA calculation package."""

from __future__ import annotations

from typing import NoReturn

from frtb_common import (
    CapitalComponentMetadata,
    ImplementationStatus,
    NotImplementedCapitalComponentError,
    ValidationStatus,
)

PACKAGE_METADATA = CapitalComponentMetadata(
    package_name="frtb-cva",
    import_name="frtb_cva",
    component_name="Credit Valuation Adjustment capital",
    implementation_status=ImplementationStatus.SCAFFOLDED,
    validation_status=ValidationStatus.NOT_STARTED,
)


def calculate_cva_capital(*_args: object, **_kwargs: object) -> NoReturn:
    """Fail explicitly until the CVA calculation is implemented."""

    raise NotImplementedCapitalComponentError(
        component="frtb-cva",
        feature="CVA capital calculation",
    )
