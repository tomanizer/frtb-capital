"""Public boundary for the RRAO calculation package."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from frtb_common import (
    CapitalComponentMetadata,
    ImplementationStatus,
    ValidationStatus,
)

from frtb_rrao.assembly.results import validate_context
from frtb_rrao.batch import build_rrao_batch_from_positions, calculate_rrao_capital_from_batch
from frtb_rrao.data_models import (
    RraoCalculationContext,
    RraoCapitalResult,
    RraoPosition,
)
from frtb_rrao.validation import RraoInputError

PACKAGE_METADATA = CapitalComponentMetadata(
    package_name="frtb-rrao",
    import_name="frtb_rrao",
    component_name="Standardised Approach residual risk add-on",
    implementation_status=ImplementationStatus.IMPLEMENTED,
    validation_status=ValidationStatus.AVAILABLE,
)


def calculate_rrao_capital(
    positions: object | None = None,
    *,
    context: RraoCalculationContext | None = None,
) -> RraoCapitalResult:
    """Calculate a supported canonical-input RRAO capital result."""

    if positions is None:
        raise RraoInputError("positions are required", field="positions")
    if context is None:
        raise RraoInputError("calculation context is required", field="context")

    validate_context(context)
    batch = build_rrao_batch_from_positions(cast(Iterable[RraoPosition], positions))
    return calculate_rrao_capital_from_batch(batch, context=context).result
