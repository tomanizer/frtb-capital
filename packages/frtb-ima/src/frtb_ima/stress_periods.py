"""
Compatibility import surface for IMA stress-period calibration.

The physical implementation lives in ``stress_period_types``,
``stress_period_windows``, and ``stress_period_selection``. This module keeps
the historical ``frtb_ima.stress_periods`` public import path stable.
"""

from frtb_ima.stress_period_results import StressPeriodSelectionResult
from frtb_ima.stress_period_selection import (
    select_stress_periods_by_risk_class,
    select_stress_periods_for_policy,
    stress_period_specs_for_nmrf,
    validate_selected_stress_periods,
)
from frtb_ima.stress_period_types import (
    FloatVector,
    HistoricalStressSeries,
    StressPeriodCalibrationError,
    StressPeriodCandidate,
    StressPeriodTieBreak,
    StressSeverityMetric,
)
from frtb_ima.stress_period_windows import (
    rolling_window_severity_scores,
    select_stress_period_from_history,
    stress_period_candidates_from_history,
)

__all__ = (
    "FloatVector",
    "HistoricalStressSeries",
    "StressPeriodCalibrationError",
    "StressPeriodCandidate",
    "StressPeriodSelectionResult",
    "StressPeriodTieBreak",
    "StressSeverityMetric",
    "rolling_window_severity_scores",
    "select_stress_period_from_history",
    "select_stress_periods_by_risk_class",
    "select_stress_periods_for_policy",
    "stress_period_candidates_from_history",
    "stress_period_specs_for_nmrf",
    "validate_selected_stress_periods",
)
