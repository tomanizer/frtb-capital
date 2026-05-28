"""Scaffold boundary for the future DRC calculation package."""

from __future__ import annotations

from typing import NoReturn

from frtb_common import (
    CapitalComponentMetadata,
    ImplementationStatus,
    NotImplementedCapitalComponentError,
    ValidationStatus,
)

PACKAGE_METADATA = CapitalComponentMetadata(
    package_name="frtb-drc",
    import_name="frtb_drc",
    component_name="Standardised Approach default risk charge",
    implementation_status=ImplementationStatus.SCAFFOLDED,
    validation_status=ValidationStatus.NOT_STARTED,
)


def calculate_drc_capital(*_args: object, **_kwargs: object) -> NoReturn:
    """Fail explicitly until the DRC calculation is implemented."""

    raise NotImplementedCapitalComponentError(
        component="frtb-drc",
        feature="DRC capital calculation",
    )
