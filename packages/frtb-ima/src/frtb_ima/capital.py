"""
Models-based capital assembly.

Callers must determine desk IMA eligibility before invoking models-based
capital assembly. Use DeskEligibilityStatus and the policy wrapper in this
module to make that handoff explicit; SA fallback capital remains out of scope
for this package.

Desk-level formula implemented from the cited NPR 2.0 / Basel FRTB IMA model:

    MBC = max(IMCC_t-1 + SES_t-1,  multiplier * IMCC_60d_avg + SES_60d_avg)
          + PLA_addon

    multiplier:  supervisory multiplier, floor 1.5 (increases with backtesting exceptions).
    pla_addon:   additional capital charge from PLA amber/red zone.

This is the desk-level aggregation. Firm-level capital would sum approved desks
and add fallback SA capital for non-approved desks — not implemented here.

Regulatory traceability:
    Basel MAR33 capital calculation; U.S. NPR 2.0 models-based market-risk
    measure; EU CRR Article 325ba. See docs/REGULATORY_TRACEABILITY.md.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass

from frtb_ima.backtesting import TradingDeskBacktestResult
from frtb_ima.logging import calculation_log_extra
from frtb_ima.regimes import (
    DeskEligibilityStatus,
    RegulatoryPolicy,
)

DEFAULT_PLA_ZONE_LABELS: tuple[str, str, str] = ("GREEN", "AMBER", "RED")
logger = logging.getLogger(__name__)


class IMAIneligibleError(ValueError):
    """Raised when models-based capital is requested for a non-IMA-eligible desk."""


@dataclass(frozen=True)
class CapitalComponents:
    """Decomposition of desk-level models-based capital."""

    imcc_t_minus_1: float
    ses_t_minus_1: float
    imcc_60d_avg: float
    ses_60d_avg: float
    multiplier: float
    pla_addon: float
    models_based_capital: float
    binding_term: str  # "SPOT" or "AVERAGE"

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "imcc_t_minus_1": self.imcc_t_minus_1,
            "ses_t_minus_1": self.ses_t_minus_1,
            "imcc_60d_avg": self.imcc_60d_avg,
            "ses_60d_avg": self.ses_60d_avg,
            "multiplier": self.multiplier,
            "pla_addon": self.pla_addon,
            "models_based_capital": self.models_based_capital,
            "binding_term": self.binding_term,
        }


@dataclass(frozen=True)
class PLAAddonResult:
    """Decomposition of the NPR 2.0 PLA add-on for green/amber model desks."""

    k_factor: float
    standardized_green_amber: float
    standardized_amber: float
    ima_green_amber: float
    capital_benefit: float
    pla_addon: float

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "k_factor": self.k_factor,
            "standardized_green_amber": self.standardized_green_amber,
            "standardized_amber": self.standardized_amber,
            "ima_green_amber": self.ima_green_amber,
            "capital_benefit": self.capital_benefit,
            "pla_addon": self.pla_addon,
        }


def _validate_non_negative_finite(value: float, name: str) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value}")
    if value < 0.0:
        raise ValueError(f"{name} must be non-negative, got {value}")


def _validate_pla_zone_labels(zone_labels: Sequence[str]) -> tuple[str, str, str]:
    try:
        labels = tuple(zone_labels)
    except TypeError as exc:
        raise ValueError("pla_zone_labels must be a sequence of three labels") from exc
    if len(labels) != 3:
        raise ValueError("pla_zone_labels must contain exactly three labels")
    if any(not isinstance(label, str) or not label for label in labels):
        raise ValueError("pla_zone_labels must contain non-empty string labels")
    if len(set(labels)) != len(labels):
        raise ValueError("pla_zone_labels must contain distinct labels")
    return labels[0], labels[1], labels[2]


def models_based_capital(
    imcc_t_minus_1: float,
    ses_t_minus_1: float,
    imcc_60d_avg: float,
    ses_60d_avg: float,
    multiplier: float,
    pla_addon: float = 0.0,
) -> CapitalComponents:
    """
    Compute models-based capital for one approved desk.

    Formula:
        MBC = max(
            IMCC_{t-1} + SES_{t-1},
            multiplier * IMCC_60d_avg + SES_60d_avg
        ) + PLA_addon

    Args:
        imcc_t_minus_1: Most recent day's IMCC.
        ses_t_minus_1:  Most recent day's SES.
        imcc_60d_avg:   60-business-day average IMCC.
        ses_60d_avg:    60-business-day average SES.
        multiplier:     Supervisory multiplier (floor 1.5; increases with
                        backtesting exceptions per Basel / NPR 2.0).
        pla_addon:      PLA capital add-on (zero for green zone desks).

    Returns:
        CapitalComponents with breakdown and binding term.
    """
    _validate_non_negative_finite(imcc_t_minus_1, "imcc_t_minus_1")
    _validate_non_negative_finite(ses_t_minus_1, "ses_t_minus_1")
    _validate_non_negative_finite(imcc_60d_avg, "imcc_60d_avg")
    _validate_non_negative_finite(ses_60d_avg, "ses_60d_avg")
    _validate_non_negative_finite(pla_addon, "pla_addon")

    if not math.isfinite(multiplier):
        raise ValueError(f"multiplier must be finite, got {multiplier}")
    if multiplier < 1.5:
        raise ValueError(f"multiplier must be at least the supervisory floor, got {multiplier}")

    spot_term = imcc_t_minus_1 + ses_t_minus_1
    average_term = multiplier * imcc_60d_avg + ses_60d_avg

    if spot_term >= average_term:
        binding = "SPOT"
        mbc = spot_term + pla_addon
    else:
        binding = "AVERAGE"
        mbc = average_term + pla_addon

    return CapitalComponents(
        imcc_t_minus_1=imcc_t_minus_1,
        ses_t_minus_1=ses_t_minus_1,
        imcc_60d_avg=imcc_60d_avg,
        ses_60d_avg=ses_60d_avg,
        multiplier=multiplier,
        pla_addon=pla_addon,
        models_based_capital=mbc,
        binding_term=binding,
    )


def desk_eligibility_from_results(
    backtest_result: TradingDeskBacktestResult,
    pla_zone: str,
    *,
    pla_zone_labels: Sequence[str] = DEFAULT_PLA_ZONE_LABELS,
) -> DeskEligibilityStatus:
    """Return IMA eligibility from trailing backtesting and PLA assessment results.

    ``pla_zone_labels`` follows the same green, amber, red ordering used by
    ``RegulatoryPolicy.pla_zone_labels``.
    """
    if not isinstance(backtest_result, TradingDeskBacktestResult):
        raise ValueError("backtest_result must be a TradingDeskBacktestResult")
    if not isinstance(pla_zone, str) or not pla_zone:
        raise ValueError("pla_zone must be a non-empty string")
    green_label, amber_label, red_label = _validate_pla_zone_labels(pla_zone_labels)
    if pla_zone not in (green_label, amber_label, red_label):
        expected = ", ".join((green_label, amber_label, red_label))
        raise ValueError(f"pla_zone must be one of {expected}, got {pla_zone!r}")
    if not backtest_result.model_eligible or pla_zone == red_label:
        return DeskEligibilityStatus.SA_FALLBACK
    return DeskEligibilityStatus.IMA_ELIGIBLE


def models_based_capital_for_policy(
    desk_eligibility: DeskEligibilityStatus,
    imcc_t_minus_1: float,
    ses_t_minus_1: float,
    imcc_60d_avg: float,
    ses_60d_avg: float,
    pla_addon: float,
    policy: RegulatoryPolicy,
    *,
    exception_count: int = 0,
) -> CapitalComponents:
    """Guard and compute models-based capital for one IMA-eligible desk."""
    status = DeskEligibilityStatus(desk_eligibility)
    if not isinstance(policy, RegulatoryPolicy):
        raise ValueError("policy must be a RegulatoryPolicy")
    if not isinstance(exception_count, int):
        raise ValueError("exception_count must be an integer")
    if status == DeskEligibilityStatus.SA_FALLBACK:
        raise IMAIneligibleError(
            f"models-based capital requires IMA eligibility; desk eligibility is {status.value}"
        )

    result = models_based_capital(
        imcc_t_minus_1=imcc_t_minus_1,
        ses_t_minus_1=ses_t_minus_1,
        imcc_60d_avg=imcc_60d_avg,
        ses_60d_avg=ses_60d_avg,
        multiplier=supervisory_multiplier_for_policy(exception_count, policy),
        pla_addon=pla_addon,
    )
    logger.info(
        "models_based_capital_complete",
        extra=calculation_log_extra(
            regime=policy.regime.value,
            desk_eligibility=status.value,
            models_based_capital=result.models_based_capital,
            binding_term=result.binding_term,
            multiplier=result.multiplier,
            exception_count=exception_count,
            pla_addon=result.pla_addon,
        ),
    )
    return result


def pla_addon(
    standardized_green_amber: float,
    standardized_amber: float,
    ima_green_amber: float,
) -> PLAAddonResult:
    """
    Compute the NPR 2.0 PLA add-on for desks in the amber zone.

    Formula implemented from proposed Sec. __.213(c)(4):

        k = 0.5 * standardized_amber / standardized_green_amber
        PLA_addon = k * max(standardized_green_amber - ima_green_amber, 0)

    Args:
        standardized_green_amber: SA non-default capital for model-eligible
            desks in green or amber PLA zones.
        standardized_amber: SA non-default capital for model-eligible desks in
            amber PLA zone.
        ima_green_amber: Models-based non-default capital for the same green
            or amber population before the PLA add-on.
    """
    _validate_non_negative_finite(
        standardized_green_amber,
        "standardized_green_amber",
    )
    _validate_non_negative_finite(standardized_amber, "standardized_amber")
    _validate_non_negative_finite(ima_green_amber, "ima_green_amber")

    if standardized_green_amber == 0.0:
        if standardized_amber != 0.0:
            raise ValueError(
                "standardized_amber cannot be positive when standardized_green_amber is zero"
            )
        k_factor = 0.0
    elif standardized_amber > standardized_green_amber:
        raise ValueError("standardized_amber cannot exceed standardized_green_amber")
    else:
        k_factor = 0.5 * standardized_amber / standardized_green_amber

    capital_benefit = max(standardized_green_amber - ima_green_amber, 0.0)
    addon = k_factor * capital_benefit
    return PLAAddonResult(
        k_factor=k_factor,
        standardized_green_amber=standardized_green_amber,
        standardized_amber=standardized_amber,
        ima_green_amber=ima_green_amber,
        capital_benefit=capital_benefit,
        pla_addon=addon,
    )


def supervisory_multiplier(
    exception_count: int,
    schedule: Sequence[tuple[int, float]],
    red_zone_multiplier: float,
) -> float:
    """
    Map backtesting exception count to supervisory multiplier.

    Basel MAR99 Table 2 traffic-light multiplier schedule, used with the MAR32
    backtesting context:
        0-4   exceptions: 1.50
        5     exceptions: 1.70
        6     exceptions: 1.76
        7     exceptions: 1.83
        8     exceptions: 1.88
        9     exceptions: 1.92
        10+   exceptions: 2.00

    These are the Basel MAR99 Table 2 multipliers used by the policy schedule.
    """
    if not isinstance(exception_count, int):
        raise TypeError("exception_count must be an integer")
    if exception_count < 0:
        raise ValueError(f"exception_count must be non-negative, got {exception_count}")
    if not math.isfinite(red_zone_multiplier) or red_zone_multiplier < 1.5:
        raise ValueError(
            "red_zone_multiplier must be finite and at least the 1.5 floor, "
            f"got {red_zone_multiplier}"
        )

    multipliers = dict(schedule)
    for count, multiplier in multipliers.items():
        if count < 0:
            raise ValueError(f"schedule exception counts must be non-negative, got {count}")
        if not math.isfinite(multiplier) or multiplier < 1.5:
            raise ValueError(
                f"schedule multipliers must be finite and at least the 1.5 floor, got {multiplier}"
            )
    return multipliers.get(exception_count, red_zone_multiplier)


def supervisory_multiplier_for_policy(
    exception_count: int,
    policy: RegulatoryPolicy,
) -> float:
    """Map exception count to multiplier using the policy schedule."""
    return supervisory_multiplier(
        exception_count,
        schedule=policy.supervisory_multiplier_schedule,
        red_zone_multiplier=policy.supervisory_multiplier_red_zone,
    )
