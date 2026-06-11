"""RFET required-observation threshold validation stage."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from frtb_ima.data_contracts import RFETEvidence, RiskFactorDefinition
from frtb_ima.regimes import RegulatoryPolicy
from frtb_ima.validation.rfet_window import _RFETObservationWindow


@dataclass(frozen=True)
class _RFETRequiredObservations:
    base_required: int
    required: int
    new_issuance_prorated: bool


def base_required_observation_count(
    risk_factor: RiskFactorDefinition,
    policy: RegulatoryPolicy,
) -> int:
    """Return the policy RFET observation threshold for one risk factor.
    Parameters
    ----------
    risk_factor : RiskFactorDefinition
        Risk factor.
    policy : RegulatoryPolicy
        Policy.

    Returns
    -------
    int
        Result of the operation.
    """
    if risk_factor.liquidity_horizon.value <= policy.rfet_short_lh_max_days:
        return policy.rfet_short_lh_threshold
    return policy.rfet_long_lh_threshold


def prorated_required_observation_count(
    base_required_observations: int,
    *,
    lookback_start: date,
    as_of_date: date,
    issue_date: date,
) -> int:
    """Prorate an RFET threshold for a new issuance.

    The proposal contemplates special treatment for new issuances. Production
    callers should provide RFET new-issuance evidence so the assessment records
    the policy citation or modelling-choice rationale.
    Parameters
    ----------
    base_required_observations : int
        Base required observations.
    lookback_start : date
        Lookback start.
    as_of_date : date
        As of date.
    issue_date : date
        Issue date.

    Returns
    -------
    int
        Result of the operation.
    """
    if issue_date > as_of_date:
        raise ValueError("issue_date cannot be after as_of_date")
    if issue_date <= lookback_start:
        return base_required_observations

    available_days = (as_of_date - issue_date).days + 1
    lookback_days = (as_of_date - lookback_start).days + 1
    prorated = math.ceil(base_required_observations * available_days / lookback_days)
    return max(1, min(base_required_observations, prorated))


def _rfet_required_observations(
    risk_factor: RiskFactorDefinition,
    evidence: RFETEvidence,
    policy: RegulatoryPolicy,
    window: _RFETObservationWindow,
    *,
    issue_date: date | None = None,
    allow_new_issuance_prorating: bool = False,
) -> _RFETRequiredObservations:
    base_required = base_required_observation_count(risk_factor, policy)
    new_issuance = evidence.new_issuance
    effective_issue_date = new_issuance.issue_date if new_issuance is not None else issue_date
    prorating_approved = (
        new_issuance is not None and new_issuance.prorating_approved
    ) or allow_new_issuance_prorating
    if effective_issue_date is None or not prorating_approved:
        return _RFETRequiredObservations(
            base_required=base_required,
            required=base_required,
            new_issuance_prorated=False,
        )

    required = prorated_required_observation_count(
        base_required,
        lookback_start=window.lookback_start,
        as_of_date=evidence.as_of_date,
        issue_date=effective_issue_date,
    )
    return _RFETRequiredObservations(
        base_required=base_required,
        required=required,
        new_issuance_prorated=required != base_required,
    )
