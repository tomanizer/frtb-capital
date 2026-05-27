"""
Profit and Loss Attribution (PLA) prototype.

Working assumption: use Kolmogorov-Smirnov (KS) statistic to compare
Hypothetical P&L (HPL) and Risk-Theoretical P&L (RTPL) vectors.

A large KS statistic indicates the two distributions differ significantly,
which under NPR 2.0 / Basel FRTB IMA would trigger a PLA add-on or
model failure.

Zone thresholds:
    Green (pass):  KS <= GREEN_THRESHOLD
    Amber:         GREEN_THRESHOLD < KS <= AMBER_THRESHOLD
    Red (fail):    KS > AMBER_THRESHOLD

Thresholds are placeholders — NPR 2.0 working assumption only.

Regulatory traceability:
    Basel MAR32 PLA; U.S. NPR 2.0 KS-based PLA proposal; EU CRR Article 325bg
    and Delegated Regulation (EU) 2022/2059. See
    docs/REGULATORY_TRACEABILITY.md.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
import numpy.typing as npt

from frtb_ima.logging import calculation_log_extra
from frtb_ima.regimes import (
    PLAMetricsRequired,
    RegulatoryPolicy,
    UnsupportedRegulatoryFeature,
)

# Placeholder zone thresholds — replace with final NPR 2.0 values when published
GREEN_THRESHOLD: float = 0.09
AMBER_THRESHOLD: float = 0.12
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
class PlaWindowDiagnostics:
    """Policy-window diagnostics for a PLA assessment."""

    available_observations: int
    minimum_history: int
    window_size: int
    start_index: int
    end_index_exclusive: int
    start_date: date | None = None
    end_date: date | None = None

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
        }


@dataclass(frozen=True)
class PlaPolicyAssessmentResult:
    """Policy PLA result with explicit window diagnostics."""

    pla: PlaResult
    diagnostics: PlaWindowDiagnostics

    @property
    def ks_statistic(self) -> float:
        """PLA KS statistic."""
        return self.pla.ks_statistic

    @property
    def zone(self) -> str:
        """Policy PLA zone label."""
        return self.pla.zone

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and notebooks."""
        return {
            "pla": self.pla.as_dict(),
            "diagnostics": self.diagnostics.as_dict(),
        }


FloatVector = Sequence[float] | npt.NDArray[np.float64]


def _as_finite_1d_array(values: FloatVector, name: str) -> npt.NDArray[np.float64]:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} vector must be one-dimensional")
    if arr.size == 0:
        raise ValueError(f"{name} vector is empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} vector must contain only finite values")
    return arr.astype(np.float64, copy=False)


def _validate_observation_dates(
    observation_dates: Sequence[date] | None,
    expected_length: int,
) -> tuple[date, ...] | None:
    if observation_dates is None:
        return None
    dates = tuple(observation_dates)
    if len(dates) != expected_length:
        raise ValueError("observation_dates length must match HPL/RTPL")
    if not all(isinstance(item, date) for item in dates):
        raise TypeError("observation_dates must contain datetime.date values")
    return dates


def _require_supported_policy_metrics(policy: RegulatoryPolicy) -> None:
    if policy.pla_metrics_required == PLAMetricsRequired.KS_AND_SPEARMAN:
        feature = policy.unsupported_feature("spearman_pla")
        if feature is not None:
            raise UnsupportedRegulatoryFeature(
                policy.regime,
                feature.feature_name,
                feature.source_topic,
            )
        raise UnsupportedRegulatoryFeature(
            policy.regime,
            "spearman_pla",
            "PLA Spearman metric",
        )


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


def pla_assessment(
    hpl: FloatVector,
    rtpl: FloatVector,
    green_threshold: float = GREEN_THRESHOLD,
    amber_threshold: float = AMBER_THRESHOLD,
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
    if not (0.0 <= green_threshold <= amber_threshold <= 1.0):
        raise ValueError("PLA thresholds must satisfy 0 <= green_threshold <= amber_threshold <= 1")

    green_label, amber_label, red_label = zone_labels
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


def pla_assessment_for_policy(
    hpl: FloatVector,
    rtpl: FloatVector,
    policy: RegulatoryPolicy,
    *,
    run_id: str | None = None,
    desk_id: str | None = None,
) -> PlaResult:
    """
    Run PLA using policy thresholds and required metrics.

    The prototype currently implements KS only. Policies requiring Spearman
    raise an explicit unsupported-feature error.
    """
    return pla_assessment_for_policy_with_diagnostics(
        hpl,
        rtpl,
        policy,
        run_id=run_id,
        desk_id=desk_id,
    ).pla


def pla_assessment_for_policy_with_diagnostics(
    hpl: FloatVector,
    rtpl: FloatVector,
    policy: RegulatoryPolicy,
    observation_dates: Sequence[date] | None = None,
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
    _require_supported_policy_metrics(policy)

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
    dates = _validate_observation_dates(observation_dates, len(hpl_arr))

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
    dates_w = dates[start_index:end_index_exclusive] if dates is not None else None

    pla = pla_assessment(
        hpl_w,
        rtpl_w,
        green_threshold=policy.pla_green_threshold,
        amber_threshold=policy.pla_amber_threshold,
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
        ),
    )
    logger.info(
        "pla_complete",
        extra=calculation_log_extra(
            run_id=run_id,
            desk_id=desk_id,
            regime=policy.regime.value,
            ks_statistic=result.ks_statistic,
            zone=result.zone,
            window_size=result.diagnostics.window_size,
            available_observations=result.diagnostics.available_observations,
        ),
    )
    return result
