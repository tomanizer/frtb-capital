"""
Profit and Loss Attribution (PLA) diagnostics.

The Fed NPR profile uses a Kolmogorov-Smirnov (KS) statistic to compare
Hypothetical P&L (HPL) and Risk-Theoretical P&L (RTPL) vectors. EU/PRA
comparison profiles also compute a Spearman rank-correlation metric over the
same positive-profit HPL/RTPL sign convention; higher Spearman correlation is
better.

A large KS statistic indicates the two distributions differ significantly,
which under NPR 2.0 / Basel FRTB IMA would trigger a PLA add-on or
model failure. For EU/PRA profiles, the authoritative PLA zone is the worse of
the KS zone and Spearman zone.

Zone thresholds:
    Green (pass):  KS <= policy green threshold
    Amber:         green threshold < KS <= policy amber threshold
    Red (fail):    KS > policy amber threshold

Threshold values are sourced from ``RegulatoryPolicy`` by policy-aware wrappers.

Regulatory traceability:
    Basel MAR32 PLA; U.S. NPR 2.0 KS-based PLA proposal; EU CRR Article 325bg
    and Delegated Regulation (EU) 2022/2059 Articles 4-5. See
    docs/REGULATORY_TRACEABILITY.md.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
import numpy.typing as npt

from frtb_ima._array_utils import finite_1d_float_array
from frtb_ima._observation_utils import (
    select_recent_observation_window as _select_recent_observation_window,
)
from frtb_ima._observation_utils import (
    validate_observation_dates as _validate_observation_dates,
)
from frtb_ima.calendar import BusinessCalendar, ObservationWindowBasis
from frtb_ima.logging import calculation_log_extra
from frtb_ima.regimes import (
    PLAMetricsRequired,
    RegulatoryPolicy,
)

DEFAULT_ZONE_LABELS: tuple[str, str, str] = ("GREEN", "AMBER", "RED")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlaResult:
    ks_statistic: float
    zone: str  # "GREEN", "AMBER", or "RED"
    n_hpl: int
    n_rtpl: int

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "ks_statistic": self.ks_statistic,
            "zone": self.zone,
            "n_hpl": self.n_hpl,
            "n_rtpl": self.n_rtpl,
        }


@dataclass(frozen=True)
class SpearmanPlaResult:
    spearman_correlation: float
    zone: str  # "GREEN", "AMBER", or "RED"
    n_hpl: int
    n_rtpl: int

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "spearman_correlation": self.spearman_correlation,
            "zone": self.zone,
            "n_hpl": self.n_hpl,
            "n_rtpl": self.n_rtpl,
        }


@dataclass(frozen=True)
class PlaWindowDiagnostics:
    """Policy-window diagnostics for a PLA assessment."""

    available_observations: int
    minimum_history: int
    window_size: int
    start_index: int
    end_index_exclusive: int
    start_date: date | None = None
    end_date: date | None = None
    calendar_source: str = ""
    calendar_version: str = ""
    calendar_basis: str = ObservationWindowBasis.OBSERVATION_COUNT_PROXY.value
    official_holiday_count: int = 0
    missing_business_dates: tuple[date, ...] = ()

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and notebooks."""
        return {
            "available_observations": self.available_observations,
            "minimum_history": self.minimum_history,
            "window_size": self.window_size,
            "start_index": self.start_index,
            "end_index_exclusive": self.end_index_exclusive,
            "start_date": self.start_date.isoformat() if self.start_date is not None else None,
            "end_date": self.end_date.isoformat() if self.end_date is not None else None,
            "calendar_source": self.calendar_source,
            "calendar_version": self.calendar_version,
            "calendar_basis": self.calendar_basis,
            "official_holiday_count": self.official_holiday_count,
            "missing_business_dates": [item.isoformat() for item in self.missing_business_dates],
        }


@dataclass(frozen=True)
class PlaPolicyAssessmentResult:
    """Policy PLA result with explicit window diagnostics."""

    pla: PlaResult
    diagnostics: PlaWindowDiagnostics
    spearman: SpearmanPlaResult | None = None
    zone_labels: tuple[str, str, str] = DEFAULT_ZONE_LABELS

    @property
    def ks_statistic(self) -> float:
        """PLA KS statistic."""
        return self.pla.ks_statistic

    @property
    def zone(self) -> str:
        """Policy PLA zone label."""
        if self.spearman is None:
            return self.pla.zone
        return _worse_zone(self.pla.zone, self.spearman.zone, self.zone_labels)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and notebooks."""
        return {
            "pla": self.pla.as_dict(),
            "spearman": self.spearman.as_dict() if self.spearman is not None else None,
            "diagnostics": self.diagnostics.as_dict(),
        }


FloatVector = Sequence[float] | npt.NDArray[np.float64]


def _as_finite_1d_array(values: FloatVector, name: str) -> npt.NDArray[np.float64]:
    return finite_1d_float_array(
        values,
        name,
        descriptor=" vector",
        require_float_sequence=True,
    )


def _validate_unit_threshold(value: float, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} must be a float or int")
    threshold = float(value)
    if not math.isfinite(threshold):
        raise ValueError(f"{name} must be finite")
    return threshold


def _validate_zone_labels(zone_labels: Sequence[str]) -> tuple[str, str, str]:
    if isinstance(zone_labels, (str, bytes)) or not isinstance(zone_labels, Sequence):
        raise ValueError("zone_labels must be a tuple of three strings")
    labels = tuple(zone_labels)
    if len(labels) != 3:
        raise ValueError("zone_labels must be a tuple of three strings")
    if any(not isinstance(label, str) or not label for label in labels):
        raise ValueError("zone_labels must be a tuple of three strings")
    if len(set(labels)) != len(labels):
        raise ValueError("zone_labels must contain distinct labels")
    return labels[0], labels[1], labels[2]


def ks_statistic(hpl: FloatVector, rtpl: FloatVector) -> float:
    """
    Compute the two-sample Kolmogorov-Smirnov statistic between HPL and RTPL.

    KS = max|F_HPL(x) - F_RTPL(x)| over all x.

    Args:
        hpl:  Hypothetical P&L vector (sign convention: positive = profit).
        rtpl: Risk-Theoretical P&L vector (same convention).

    Returns:
        KS statistic in [0, 1].

    Raises:
        ValueError: if either vector is empty.
    """
    return _ks_statistic_arrays(
        np.sort(_as_finite_1d_array(hpl, "hpl")),
        np.sort(_as_finite_1d_array(rtpl, "rtpl")),
    )


def _ks_statistic_arrays(
    hpl_arr: npt.NDArray[np.float64],
    rtpl_arr: npt.NDArray[np.float64],
) -> float:
    """Compute KS for already validated, sorted arrays."""

    # Merge all unique values for evaluation points
    all_values = np.unique(np.concatenate([hpl_arr, rtpl_arr]))

    n_hpl = len(hpl_arr)
    n_rtpl = len(rtpl_arr)

    # Empirical CDFs evaluated at each merged point
    cdf_hpl = np.searchsorted(hpl_arr, all_values, side="right") / n_hpl
    cdf_rtpl = np.searchsorted(rtpl_arr, all_values, side="right") / n_rtpl

    return float(np.max(np.abs(cdf_hpl - cdf_rtpl)))


def _average_ranks(arr: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    n = len(arr)
    order = np.argsort(arr, kind="stable")
    sorted_arr = arr[order]
    is_new_group = np.concatenate([[True], sorted_arr[1:] != sorted_arr[:-1]])
    group_labels = np.cumsum(is_new_group) - 1
    sequential_ranks = np.arange(1, n + 1, dtype=float)
    group_sum = np.bincount(group_labels, weights=sequential_ranks)
    group_count = np.bincount(group_labels)
    avg_rank_per_group = group_sum / group_count
    result = np.empty(n, dtype=float)
    result[order] = avg_rank_per_group[group_labels]
    return result


def spearman_correlation(hpl: FloatVector, rtpl: FloatVector) -> float:
    """
    Compute Spearman rank correlation between HPL and RTPL vectors.

    Args:
        hpl:  Hypothetical P&L vector (sign convention: positive = profit).
        rtpl: Risk-Theoretical P&L vector (same convention).

    Returns:
        Pearson correlation of average ranks in [-1, 1].
    """
    hpl_arr = _as_finite_1d_array(hpl, "hpl")
    rtpl_arr = _as_finite_1d_array(rtpl, "rtpl")
    if len(hpl_arr) != len(rtpl_arr):
        raise ValueError("HPL and RTPL must have equal length for Spearman correlation")
    if len(hpl_arr) < 2:
        raise ValueError("Spearman correlation requires at least two observations")

    hpl_ranks = _average_ranks(hpl_arr)
    rtpl_ranks = _average_ranks(rtpl_arr)
    hpl_c = hpl_ranks - hpl_ranks.mean()
    rtpl_c = rtpl_ranks - rtpl_ranks.mean()
    denom = np.sqrt(np.dot(hpl_c, hpl_c) * np.dot(rtpl_c, rtpl_c))
    if denom == 0.0:
        raise ValueError("Spearman correlation is undefined: all HPL or RTPL values are identical")
    return float(np.dot(hpl_c, rtpl_c) / denom)


def pla_assessment(
    hpl: FloatVector,
    rtpl: FloatVector,
    green_threshold: float,
    amber_threshold: float,
    zone_labels: tuple[str, str, str] = DEFAULT_ZONE_LABELS,
) -> PlaResult:
    """
    Run PLA assessment and return the KS statistic with zone classification.

    Args:
        hpl:              Hypothetical P&L vector.
        rtpl:             Risk-Theoretical P&L vector.
        green_threshold:  KS <= this -> GREEN.
        amber_threshold:  green < KS <= this -> AMBER; above -> RED.
        zone_labels:      Labels for green, amber, and red zones.

    Returns:
        PlaResult with ks_statistic, zone, and vector lengths.
    """
    green_threshold = _validate_unit_threshold(green_threshold, "green_threshold")
    amber_threshold = _validate_unit_threshold(amber_threshold, "amber_threshold")
    if not (0.0 <= green_threshold <= amber_threshold <= 1.0):
        raise ValueError("PLA thresholds must satisfy 0 <= green_threshold <= amber_threshold <= 1")

    green_label, amber_label, red_label = _validate_zone_labels(zone_labels)
    hpl_arr = _as_finite_1d_array(hpl, "hpl")
    rtpl_arr = _as_finite_1d_array(rtpl, "rtpl")
    ks = _ks_statistic_arrays(np.sort(hpl_arr), np.sort(rtpl_arr))

    if ks <= green_threshold:
        zone = green_label
    elif ks <= amber_threshold:
        zone = amber_label
    else:
        zone = red_label

    return PlaResult(
        ks_statistic=ks,
        zone=zone,
        n_hpl=len(hpl_arr),
        n_rtpl=len(rtpl_arr),
    )


def spearman_pla_assessment(
    hpl: FloatVector,
    rtpl: FloatVector,
    green_threshold: float,
    amber_threshold: float,
    zone_labels: tuple[str, str, str] = DEFAULT_ZONE_LABELS,
) -> SpearmanPlaResult:
    """
    Run PLA Spearman assessment and return rank correlation zone classification.

    Higher Spearman correlation is better:
        rho >= green_threshold -> GREEN
        rho >= amber_threshold -> AMBER
        otherwise -> RED
    """
    green_threshold = _validate_unit_threshold(green_threshold, "green_threshold")
    amber_threshold = _validate_unit_threshold(amber_threshold, "amber_threshold")
    green_label, amber_label, red_label = _validate_zone_labels(zone_labels)
    if not (0.0 <= amber_threshold <= green_threshold <= 1.0):
        raise ValueError(
            "Spearman PLA thresholds must satisfy 0 <= amber_threshold <= green_threshold <= 1"
        )

    hpl_arr = _as_finite_1d_array(hpl, "hpl")
    rtpl_arr = _as_finite_1d_array(rtpl, "rtpl")
    rho = spearman_correlation(hpl_arr, rtpl_arr)

    if rho >= green_threshold:
        zone = green_label
    elif rho >= amber_threshold:
        zone = amber_label
    else:
        zone = red_label

    return SpearmanPlaResult(
        spearman_correlation=rho,
        zone=zone,
        n_hpl=len(hpl_arr),
        n_rtpl=len(rtpl_arr),
    )


def _worse_zone(zone1: str, zone2: str, zone_labels: Sequence[str]) -> str:
    labels = _validate_zone_labels(zone_labels)
    severity = {label: idx for idx, label in enumerate(labels)}
    if zone1 not in severity:
        raise ValueError(f"zone1 must be one of {', '.join(labels)}, got {zone1!r}")
    if zone2 not in severity:
        raise ValueError(f"zone2 must be one of {', '.join(labels)}, got {zone2!r}")
    return zone1 if severity[zone1] >= severity[zone2] else zone2


def pla_assessment_for_policy(
    hpl: FloatVector,
    rtpl: FloatVector,
    policy: RegulatoryPolicy,
    observation_dates: Sequence[date] | None = None,
    calendar: BusinessCalendar | None = None,
    *,
    run_id: str | None = None,
    desk_id: str | None = None,
) -> PlaResult:
    """
    Run PLA using policy thresholds and required metrics.

    FED NPR 2.0 uses KS only. ECB/PRA profiles compute both KS and Spearman;
    the returned compatibility PlaResult carries the authoritative policy zone.
    Use pla_assessment_for_policy_with_diagnostics for the full decomposition.
    """
    result = pla_assessment_for_policy_with_diagnostics(
        hpl,
        rtpl,
        policy,
        observation_dates=observation_dates,
        calendar=calendar,
        run_id=run_id,
        desk_id=desk_id,
    )
    if result.spearman is None:
        return result.pla
    return PlaResult(
        ks_statistic=result.pla.ks_statistic,
        zone=result.zone,
        n_hpl=result.pla.n_hpl,
        n_rtpl=result.pla.n_rtpl,
    )


def pla_assessment_for_policy_with_diagnostics(
    hpl: FloatVector,
    rtpl: FloatVector,
    policy: RegulatoryPolicy,
    observation_dates: Sequence[date] | None = None,
    calendar: BusinessCalendar | None = None,
    *,
    run_id: str | None = None,
    desk_id: str | None = None,
) -> PlaPolicyAssessmentResult:
    """
    Run policy PLA and return window diagnostics.

    Policy PLA requires HPL and RTPL to be aligned one-to-one before the most
    recent policy window is selected. Optional dates provide an auditable window
    start/end without introducing a full business-calendar dependency.
    """
    if policy.pla_window_days <= 0:
        raise ValueError(f"pla_window_days must be positive, got {policy.pla_window_days}")
    if policy.pla_minimum_history_days <= 0:
        raise ValueError(
            f"pla_minimum_history_days must be positive, got {policy.pla_minimum_history_days}"
        )

    hpl_arr = _as_finite_1d_array(hpl, "hpl")
    rtpl_arr = _as_finite_1d_array(rtpl, "rtpl")
    if len(hpl_arr) != len(rtpl_arr):
        raise ValueError("HPL and RTPL must have equal length for policy PLA")
    dates = _validate_observation_dates(
        observation_dates,
        len(hpl_arr),
        length_label="HPL/RTPL",
    )

    available_observations = len(hpl_arr)
    if available_observations < policy.pla_minimum_history_days:
        raise ValueError(
            "HPL and RTPL must contain at least "
            f"{policy.pla_minimum_history_days} observations for policy PLA"
        )
    window_size = min(policy.pla_window_days, available_observations)
    start_index = available_observations - window_size
    end_index_exclusive = available_observations
    hpl_w = hpl_arr[start_index:end_index_exclusive]
    rtpl_w = rtpl_arr[start_index:end_index_exclusive]
    date_window = _select_recent_observation_window(
        dates,
        window_size,
        calendar=calendar,
        validation_label="PLA",
    )
    dates_w = date_window.observation_dates

    pla = pla_assessment(
        hpl_w,
        rtpl_w,
        green_threshold=policy.pla_green_threshold,
        amber_threshold=policy.pla_amber_threshold,
        zone_labels=policy.pla_zone_labels,
    )
    spearman_result: SpearmanPlaResult | None = None
    if policy.pla_metrics_required == PLAMetricsRequired.KS_AND_SPEARMAN:
        spearman_result = spearman_pla_assessment(
            hpl_w,
            rtpl_w,
            green_threshold=policy.pla_spearman_green_threshold,
            amber_threshold=policy.pla_spearman_amber_threshold,
            zone_labels=policy.pla_zone_labels,
        )
    result = PlaPolicyAssessmentResult(
        pla=pla,
        diagnostics=PlaWindowDiagnostics(
            available_observations=available_observations,
            minimum_history=policy.pla_minimum_history_days,
            window_size=window_size,
            start_index=start_index,
            end_index_exclusive=end_index_exclusive,
            start_date=dates_w[0] if dates_w else None,
            end_date=dates_w[-1] if dates_w else None,
            calendar_source=date_window.calendar_source,
            calendar_version=date_window.calendar_version,
            calendar_basis=date_window.calendar_basis,
            official_holiday_count=date_window.official_holiday_count,
            missing_business_dates=date_window.missing_business_dates,
        ),
        spearman=spearman_result,
        zone_labels=policy.pla_zone_labels,
    )
    log_fields = calculation_log_extra(
        run_id=run_id,
        desk_id=desk_id,
        regime=policy.regime.value,
        ks_statistic=result.ks_statistic,
        zone=result.zone,
        window_size=result.diagnostics.window_size,
        available_observations=result.diagnostics.available_observations,
    )
    if spearman_result is not None:
        log_fields["spearman_correlation"] = spearman_result.spearman_correlation
        log_fields["joint_zone"] = result.zone
    logger.info(
        "pla_complete",
        extra=log_fields,
    )
    return result
