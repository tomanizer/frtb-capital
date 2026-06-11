"""Compatibility exports for RRAO position validation."""

from frtb_rrao.validation.position import (
    NotionalSignConvention,
    RraoInputError,
    _validate_position_without_back_to_back_groups,
    normalise_gross_effective_notional,
    validate_rrao_positions,
)

__all__ = [
    "NotionalSignConvention",
    "RraoInputError",
    "_validate_position_without_back_to_back_groups",
    "normalise_gross_effective_notional",
    "validate_rrao_positions",
]
