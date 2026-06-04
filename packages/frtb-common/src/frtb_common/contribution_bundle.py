"""Orchestration-layer wrapper for component-level contribution records.

``ComponentContributionBundle`` is the contract that ``frtb-orchestration``
uses to aggregate capital contributions from each component without altering
the individual records.  See ADR 0038.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

from frtb_common.attribution import CapitalContribution
from frtb_common.serialization import jsonable

_RECONCILIATION_TOLERANCE = 1e-6


@dataclass(frozen=True)
class ComponentContributionBundle:
    """Component contributions as received by ``frtb-orchestration``.

    Invariant: ``component_total`` must equal the sum of all ``contribution``
    values (treating None as 0) plus all ``residual`` values across the bundle,
    within a relative tolerance of 1e-6.

    Orchestration MUST NOT alter ``contribution``, ``base_amount``, ``method``,
    ``source_id``, or ``citations`` on any record in ``contributions``.
    """

    component: str
    contributions: tuple[CapitalContribution, ...]
    component_total: float
    component_input_hash: str
    component_profile_hash: str

    def __post_init__(self) -> None:
        contributions_sum = sum((r.contribution or 0.0) + r.residual for r in self.contributions)
        total = self.component_total
        tol = _RECONCILIATION_TOLERANCE * max(abs(total), 1.0)
        if abs(contributions_sum - total) > tol:
            raise ValueError(
                f"ComponentContributionBundle for '{self.component}': "
                f"sum of contributions + residuals ({contributions_sum:.6g}) "
                f"does not match component_total ({total:.6g}) within tolerance {tol:.2e}"
            )

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable mapping of bundle fields.

        Returns
        -------
        dict[str, object]
            Dataclass field names mapped through :func:`frtb_common.serialization.jsonable`.
        """
        return {field.name: jsonable(getattr(self, field.name)) for field in fields(self)}


__all__ = ["ComponentContributionBundle"]
