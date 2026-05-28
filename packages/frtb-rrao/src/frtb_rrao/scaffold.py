"""Scaffold boundary for the future RRAO calculation package."""

from __future__ import annotations

from typing import NoReturn

from frtb_common import (
    CapitalComponentMetadata,
    ImplementationStatus,
    NotImplementedCapitalComponentError,
    ValidationStatus,
)

PACKAGE_METADATA = CapitalComponentMetadata(
    package_name="frtb-rrao",
    import_name="frtb_rrao",
    component_name="Standardised Approach residual risk add-on",
    implementation_status=ImplementationStatus.SCAFFOLDED,
    validation_status=ValidationStatus.NOT_STARTED,
)


def calculate_rrao_capital(*_args: object, **_kwargs: object) -> NoReturn:
    """Fail explicitly until the RRAO calculation is implemented."""

    raise NotImplementedCapitalComponentError(
        component="frtb-rrao",
        feature="RRAO capital calculation",
    )
