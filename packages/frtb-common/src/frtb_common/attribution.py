"""Unified capital contribution types for analytical Euler decomposition."""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from typing import TypeVar

from frtb_common.serialization import jsonable


class AttributionMethod(StrEnum):
    """Supported attribution method labels."""

    ANALYTICAL_EULER = "ANALYTICAL_EULER"
    RESIDUAL = "RESIDUAL"
    UNSUPPORTED = "UNSUPPORTED"


EnumT = TypeVar("EnumT", bound=StrEnum)


def _coerce_enum(value: EnumT | str, enum_type: type[EnumT], field_name: str) -> EnumT:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValueError(f"{field_name} must be one of: {allowed}") from exc


@dataclass(frozen=True)
class CapitalContribution:
    """Stable, package-neutral view of one capital source attribution record."""

    contribution_id: str
    source_id: str
    source_level: str
    bucket_key: str | None
    category: str
    base_amount: float
    marginal_multiplier: float | None
    contribution: float | None
    method: AttributionMethod | str
    residual: float = 0.0
    reason: str = ""

    def __post_init__(self) -> None:
        coerced_method = _coerce_enum(self.method, AttributionMethod, "method")
        object.__setattr__(
            self,
            "method",
            coerced_method,
        )
        if coerced_method == AttributionMethod.ANALYTICAL_EULER:
            if self.marginal_multiplier is None:
                raise ValueError(
                    "marginal_multiplier must not be None when method is ANALYTICAL_EULER"
                )
            if self.contribution is None:
                raise ValueError("contribution must not be None when method is ANALYTICAL_EULER")

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dictionary representation."""
        return {field.name: jsonable(getattr(self, field.name)) for field in fields(self)}
