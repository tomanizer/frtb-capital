"""Scaffold boundary for future suite-level aggregation."""

from __future__ import annotations

from typing import NoReturn

from frtb_common import (
    CapitalComponentMetadata,
    ImplementationStatus,
    NotImplementedCapitalComponentError,
    ValidationStatus,
)

PACKAGE_METADATA = CapitalComponentMetadata(
    package_name="frtb-orchestration",
    import_name="frtb_orchestration",
    component_name="Suite-level capital aggregation",
    implementation_status=ImplementationStatus.SCAFFOLDED,
    validation_status=ValidationStatus.NOT_STARTED,
)


def calculate_suite_capital(*_args: object, **_kwargs: object) -> NoReturn:
    """Fail explicitly until suite aggregation is implemented."""

    raise NotImplementedCapitalComponentError(
        component="frtb-orchestration",
        feature="suite capital aggregation",
    )
