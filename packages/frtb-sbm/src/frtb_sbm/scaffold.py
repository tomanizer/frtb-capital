"""Scaffold boundary for the future SBM calculation package."""

from __future__ import annotations

from typing import NoReturn

from frtb_common import (
    CapitalComponentMetadata,
    ImplementationStatus,
    NotImplementedCapitalComponentError,
    ValidationStatus,
)

PACKAGE_METADATA = CapitalComponentMetadata(
    package_name="frtb-sbm",
    import_name="frtb_sbm",
    component_name="Standardised Approach sensitivities-based method",
    implementation_status=ImplementationStatus.SCAFFOLDED,
    validation_status=ValidationStatus.NOT_STARTED,
)


def calculate_sbm_capital(*_args: object, **_kwargs: object) -> NoReturn:
    """Fail explicitly until the SBM calculation is implemented."""

    raise NotImplementedCapitalComponentError(
        component="frtb-sbm",
        feature="SBM capital calculation",
    )
