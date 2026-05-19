"""
Canonical scenario metadata and vector containers for the FRTB IMA prototype.

This module defines the lightweight scenario representation used at the boundary
between upstream scenario generation and downstream capital calculations.

Scenario values remain sign-convention-specific to the consuming calculation:
- ES/LHA vectors generally use positive values as losses.
- PLA/backtesting vectors may use positive values as profits where stated.

The structures here intentionally do not generate scenarios. They only identify,
order, and carry already prepared scenario vectors.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from types import MappingProxyType

import numpy as np
import numpy.typing as npt

from frtb_ima.data_models import LiquidityHorizon, RiskClass


class ScenarioSetType(str, Enum):
    """Classification of the scenario set supplied by upstream systems."""

    CURRENT = "CURRENT"
    STRESS = "STRESS"
    BACKTEST = "BACKTEST"
    PLA = "PLA"


@dataclass(frozen=True)
class ScenarioMetadata:
    """
    Metadata identifying one scenario observation.

    The metadata is deliberately small. It is enough to validate deterministic
    ordering and scenario alignment without modelling upstream market-data
    generation, stress-window governance, or RFET evidence workflows.
    """

    scenario_id: str
    scenario_date: date
    scenario_set: ScenarioSetType = ScenarioSetType.CURRENT
    calibration_window: str = ""
    source: str = ""
    provenance: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("scenario_id must be non-empty")
        if not isinstance(self.scenario_date, date):
            raise TypeError("scenario_date must be a datetime.date")
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))


@dataclass(frozen=True)
class ScenarioVector:
    """
    A one-dimensional vector of scenario values with optional scenario metadata.

    The vector is stored as a NumPy float64 array for efficient downstream
    calculation. Metadata, if supplied, must be aligned one-to-one with values.
    """

    values: npt.NDArray[np.float64]
    metadata: tuple[ScenarioMetadata, ...] = ()
    risk_class: RiskClass | None = None
    liquidity_horizon: LiquidityHorizon | None = None
    name: str = ""

    def __post_init__(self) -> None:
        arr = np.asarray(self.values, dtype=float)
        if arr.ndim != 1:
            raise ValueError("ScenarioVector values must be one-dimensional")
        if arr.size == 0:
            raise ValueError("ScenarioVector values must be non-empty")
        if self.metadata and len(self.metadata) != arr.size:
            raise ValueError(
                f"metadata length ({len(self.metadata)}) != values length ({arr.size})"
            )
        object.__setattr__(self, "values", arr.astype(np.float64, copy=False))
        object.__setattr__(self, "metadata", tuple(self.metadata))

    @property
    def scenario_ids(self) -> tuple[str, ...]:
        """Scenario IDs in vector order, or an empty tuple if metadata is absent."""
        return tuple(item.scenario_id for item in self.metadata)

    @property
    def scenario_dates(self) -> tuple[date, ...]:
        """Scenario dates in vector order, or an empty tuple if metadata is absent."""
        return tuple(item.scenario_date for item in self.metadata)

    def tolist(self) -> list[float]:
        """Return values as a plain list for compatibility with existing APIs."""
        return self.values.tolist()


def make_scenario_metadata(
    scenario_dates: Sequence[date],
    *,
    prefix: str = "scenario",
    scenario_set: ScenarioSetType = ScenarioSetType.CURRENT,
    calibration_window: str = "",
    source: str = "",
) -> tuple[ScenarioMetadata, ...]:
    """
    Create deterministic scenario metadata from ordered scenario dates.

    Scenario IDs are stable and position-based: ``{prefix}-{index:05d}``.
    """
    return tuple(
        ScenarioMetadata(
            scenario_id=f"{prefix}-{idx:05d}",
            scenario_date=scenario_date,
            scenario_set=scenario_set,
            calibration_window=calibration_window,
            source=source,
        )
        for idx, scenario_date in enumerate(scenario_dates)
    )


def validate_unique_scenarios(metadata: Sequence[ScenarioMetadata]) -> None:
    """Validate that scenario IDs and dates are unique within a metadata sequence."""
    ids = [item.scenario_id for item in metadata]
    dates = [item.scenario_date for item in metadata]
    if len(ids) != len(set(ids)):
        raise ValueError("scenario metadata contains duplicate scenario_id values")
    if len(dates) != len(set(dates)):
        raise ValueError("scenario metadata contains duplicate scenario_date values")


def validate_aligned_metadata(vectors: Mapping[str, ScenarioVector]) -> None:
    """
    Validate that all vectors with metadata share identical scenario ordering.

    Vectors without metadata are ignored by this function; length checks for
    metadata-free vectors belong in the nested-vector validator introduced by
    the next workstream issue.
    """
    reference_name: str | None = None
    reference_ids: tuple[str, ...] | None = None
    reference_dates: tuple[date, ...] | None = None

    for name, vector in vectors.items():
        if not vector.metadata:
            continue
        validate_unique_scenarios(vector.metadata)
        if reference_ids is None:
            reference_name = name
            reference_ids = vector.scenario_ids
            reference_dates = vector.scenario_dates
            continue
        if vector.scenario_ids != reference_ids or vector.scenario_dates != reference_dates:
            raise ValueError(
                f"scenario metadata for vector '{name}' is not aligned with '{reference_name}'"
            )
