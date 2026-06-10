"""Orchestration-layer wrapper for component-level contribution records.

``ComponentContributionBundle`` is the contract that ``frtb-orchestration``
uses to aggregate capital contributions from each component without altering
the individual records.  See ADR 0038.
"""

from __future__ import annotations

from dataclasses import dataclass

from frtb_common.attribution import (
    DEFAULT_RECONCILIATION_TOLERANCE,
    CapitalContribution,
    validate_contribution_reconciliation,
)
from frtb_common.serialization import dataclass_as_dict


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
        try:
            validate_contribution_reconciliation(
                self.contributions,
                self.component_total,
                relative_tolerance=DEFAULT_RECONCILIATION_TOLERANCE,
            )
        except ValueError as exc:
            raise ValueError(
                f"ComponentContributionBundle for '{self.component}': {exc}"
            ) from exc

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable mapping of bundle fields.

        Returns
        -------
        dict[str, object]
            Dataclass field names mapped through :func:`frtb_common.serialization.jsonable`.
        """
        return dataclass_as_dict(self)


__all__ = ["ComponentContributionBundle"]
