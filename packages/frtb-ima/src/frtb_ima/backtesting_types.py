"""
Backtesting result and trace records.

This module owns immutable records and vector aliases for IMA backtesting. The
scalar kernels, trace assembly, and policy wrappers live in adjacent
``backtesting_*`` modules.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
import numpy.typing as npt
from frtb_common import CalculationScope

from frtb_ima.calendar import ObservationWindowBasis
from frtb_ima.org_scope import add_scope_payload, validate_scope_metadata

FloatVector = Sequence[float] | npt.NDArray[np.float64]
BoolVector = Sequence[bool] | npt.NDArray[np.bool_]


@dataclass(frozen=True)
class BacktestResult:
    """Basic APL/HPL backtesting result for one VaR vector."""

    apl_exceptions: int
    hpl_exceptions: int
    apl_zone: str  # "GREEN", "AMBER", "RED"
    hpl_zone: str
    window_size: int

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails.
        Returns
        -------
        dict[str, object]
            Result of the operation.
        """
        return {
            "apl_exceptions": self.apl_exceptions,
            "hpl_exceptions": self.hpl_exceptions,
            "apl_zone": self.apl_zone,
            "hpl_zone": self.hpl_zone,
            "window_size": self.window_size,
        }


@dataclass(frozen=True)
class BacktestLevelResult:
    """Backtesting result for one VaR confidence level."""

    confidence_level: float
    apl_exceptions: int
    hpl_exceptions: int
    exception_limit: float
    apl_passed: bool
    hpl_passed: bool
    level_passed: bool
    window_size: int

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails.
        Returns
        -------
        dict[str, object]
            Result of the operation.
        """
        return {
            "confidence_level": self.confidence_level,
            "apl_exceptions": self.apl_exceptions,
            "hpl_exceptions": self.hpl_exceptions,
            "exception_limit": self.exception_limit,
            "apl_passed": self.apl_passed,
            "hpl_passed": self.hpl_passed,
            "level_passed": self.level_passed,
            "window_size": self.window_size,
        }


@dataclass(frozen=True)
class TradingDeskBacktestResult:
    """NPR 2.0 trading-desk backtesting assessment across VaR levels."""

    levels: tuple[BacktestLevelResult, ...]
    window_size: int
    model_eligible: bool
    start_date: date | None = None
    end_date: date | None = None
    calendar_source: str = ""
    calendar_version: str = ""
    calendar_basis: str = ObservationWindowBasis.OBSERVATION_COUNT_PROXY.value
    official_holiday_count: int = 0
    missing_business_dates: tuple[date, ...] = ()
    org_scope: CalculationScope | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "org_scope",
            validate_scope_metadata(
                self.org_scope,
                field="TradingDeskBacktestResult.org_scope",
            ),
        )

    def level(self, confidence_level: float) -> BacktestLevelResult:
        """Return the result for one configured VaR confidence level.
        Parameters
        ----------
        confidence_level : float
            Confidence level.

        Returns
        -------
        BacktestLevelResult
            Result of the operation.
        """
        for result in self.levels:
            if result.confidence_level == confidence_level:
                return result
        raise KeyError(f"No backtesting result for confidence level {confidence_level}")

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails.
        Returns
        -------
        dict[str, object]
            Result of the operation.
        """
        return add_scope_payload(
            {
                "window_size": self.window_size,
                "model_eligible": self.model_eligible,
                "start_date": self.start_date.isoformat() if self.start_date is not None else None,
                "end_date": self.end_date.isoformat() if self.end_date is not None else None,
                "calendar_source": self.calendar_source,
                "calendar_version": self.calendar_version,
                "calendar_basis": self.calendar_basis,
                "official_holiday_count": self.official_holiday_count,
                "missing_business_dates": [
                    item.isoformat() for item in self.missing_business_dates
                ],
                "levels": [level.as_dict() for level in self.levels],
            },
            self.org_scope,
        )


@dataclass(frozen=True)
class BacktestObservationTrace:
    """One windowed backtesting observation for audit and exception review."""

    original_index: int
    observation_date: date | None
    apl: float | None
    hpl: float | None
    var_estimate: float | None
    official_holiday: bool
    apl_exception: bool
    hpl_exception: bool
    apl_reason: str
    hpl_reason: str

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and notebooks.
        Returns
        -------
        dict[str, object]
            Result of the operation.
        """
        return {
            "original_index": self.original_index,
            "observation_date": self.observation_date.isoformat()
            if self.observation_date is not None
            else None,
            "apl": self.apl,
            "hpl": self.hpl,
            "var_estimate": self.var_estimate,
            "official_holiday": self.official_holiday,
            "apl_exception": self.apl_exception,
            "hpl_exception": self.hpl_exception,
            "apl_reason": self.apl_reason,
            "hpl_reason": self.hpl_reason,
        }


@dataclass(frozen=True)
class BacktestLevelTrace:
    """Backtesting level result plus the dated observation trace."""

    result: BacktestLevelResult
    observations: tuple[BacktestObservationTrace, ...]

    @property
    def confidence_level(self) -> float:
        """VaR confidence level for this trace.
        Returns
        -------
        float
            Result of the operation.
        """
        return self.result.confidence_level

    def exception_observations(self) -> tuple[BacktestObservationTrace, ...]:
        """Return observations where either APL or HPL produced an exception.
        Returns
        -------
        tuple[BacktestObservationTrace, ...]
            Result of the operation.
        """
        return tuple(
            observation
            for observation in self.observations
            if observation.apl_exception or observation.hpl_exception
        )

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and notebooks.
        Returns
        -------
        dict[str, object]
            Result of the operation.
        """
        return {
            "result": self.result.as_dict(),
            "observations": [observation.as_dict() for observation in self.observations],
        }


@dataclass(frozen=True)
class TradingDeskBacktestTraceResult:
    """NPR backtesting result with per-level dated exception traces."""

    result: TradingDeskBacktestResult
    levels: tuple[BacktestLevelTrace, ...]

    @property
    def window_size(self) -> int:
        """Number of observations used after policy windowing.
        Returns
        -------
        int
            Result of the operation.
        """
        return self.result.window_size

    @property
    def model_eligible(self) -> bool:
        """Whether every configured APL/HPL VaR level passed.
        Returns
        -------
        bool
            Result of the operation.
        """
        return self.result.model_eligible

    def level(self, confidence_level: float) -> BacktestLevelTrace:
        """Return the trace for one configured VaR confidence level.
        Parameters
        ----------
        confidence_level : float
            Confidence level.

        Returns
        -------
        BacktestLevelTrace
            Result of the operation.
        """
        for trace in self.levels:
            if trace.confidence_level == confidence_level:
                return trace
        raise KeyError(f"No backtesting trace for confidence level {confidence_level}")

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and notebooks.
        Returns
        -------
        dict[str, object]
            Result of the operation.
        """
        return {
            "window_size": self.window_size,
            "model_eligible": self.model_eligible,
            "start_date": self.result.start_date.isoformat()
            if self.result.start_date is not None
            else None,
            "end_date": self.result.end_date.isoformat()
            if self.result.end_date is not None
            else None,
            "calendar_source": self.result.calendar_source,
            "calendar_version": self.result.calendar_version,
            "calendar_basis": self.result.calendar_basis,
            "official_holiday_count": self.result.official_holiday_count,
            "missing_business_dates": [
                item.isoformat() for item in self.result.missing_business_dates
            ],
            "levels": [level.as_dict() for level in self.levels],
        }


__all__ = (
    "BacktestLevelResult",
    "BacktestLevelTrace",
    "BacktestObservationTrace",
    "BacktestResult",
    "BoolVector",
    "FloatVector",
    "TradingDeskBacktestResult",
    "TradingDeskBacktestTraceResult",
)
