"""Suite-wide capital impact contract for baseline-vs-candidate capital deltas."""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum

from frtb_common.serialization import jsonable


class ImpactMethod(StrEnum):
    """Method used to compute a capital impact record."""

    FINITE_DIFFERENCE = "FINITE_DIFFERENCE"
    ANALYTICAL = "ANALYTICAL"


@dataclass(frozen=True)
class CapitalImpact:
    """Baseline-vs-candidate capital delta. Package-neutral.

    ``delta`` is always ``candidate_total - baseline_total``.  Callers must
    not present a ``CapitalImpact`` as a marginal contribution; it is a
    finite-difference between two reconciled capital runs.
    """

    baseline_run_id: str
    candidate_run_id: str
    component: str
    baseline_total: float
    candidate_total: float
    delta: float
    method: ImpactMethod | str
    baseline_input_hash: str
    candidate_input_hash: str
    baseline_profile_hash: str = ""
    candidate_profile_hash: str = ""
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        from frtb_common.attribution import _coerce_enum

        coerced = _coerce_enum(self.method, ImpactMethod, "method")
        object.__setattr__(self, "method", coerced)
        expected = round(self.candidate_total - self.baseline_total, 12)
        if abs(self.delta - expected) > 1e-9:
            raise ValueError(
                f"delta {self.delta!r} does not equal candidate_total - baseline_total "
                f"({expected!r})"
            )

    def as_dict(self) -> dict[str, object]:
        return {field.name: jsonable(getattr(self, field.name)) for field in fields(self)}


__all__ = ["CapitalImpact", "ImpactMethod"]
