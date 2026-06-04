"""
Canonical scenario metadata and vector containers for FRTB IMA.

This module defines the lightweight scenario representation used at the boundary
between upstream scenario generation and downstream capital calculations.

Scenario values remain sign-convention-specific to the consuming calculation:
- ES/LHA vectors generally use positive values as losses.
- PLA/backtesting vectors may use positive values as profits where stated.

The structures here intentionally do not generate scenarios. They only identify,
order, and carry already prepared scenario vectors.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for scenario.py, scenario metadata,
    PLA, backtesting, expected shortfall, and liquidity-horizon vectors.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from types import MappingProxyType

import numpy as np
import numpy.typing as npt

from frtb_ima._array_utils import date_from_datetime64 as _date_from_datetime64
from frtb_ima._array_utils import readonly_date_array as _readonly_date_array
from frtb_ima._array_utils import readonly_string_array as _readonly_string_array
from frtb_ima._array_utils import validate_equal_lengths as _validate_equal_lengths
from frtb_ima.audit_inputs import compute_inputs_hash
from frtb_ima.data_models import LiquidityHorizon, RiskClass

DateArray = npt.NDArray[np.datetime64]
StringArray = npt.NDArray[np.str_]


class ScenarioSetType(StrEnum):
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
class ScenarioMetadataBatch:
    """
    Columnar scenario-axis metadata for high-volume IMA handoffs.

    Dense scenario P&L vectors remain NumPy arrays owned by ``ScenarioVector`` or
    ``ScenarioCube``. This batch carries the tabular scenario axis separately so
    Arrow ingestion paths can validate ordering, lineage, and hashes without
    constructing one ``ScenarioMetadata`` dataclass per accepted source row.
    """

    scenario_ids: StringArray
    scenario_dates: DateArray
    scenario_sets: StringArray
    calibration_windows: StringArray
    sources: StringArray
    provenance_json: StringArray
    source_row_ids: StringArray
    source_hash: str | None = None
    handoff_hash: str | None = None
    input_hash: str = ""

    def __post_init__(self) -> None:
        scenario_ids = _readonly_string_array(self.scenario_ids, "scenario_ids")
        scenario_dates = _readonly_date_array(self.scenario_dates, "scenario_dates")
        scenario_sets = _readonly_string_array(self.scenario_sets, "scenario_sets")
        calibration_windows = _readonly_string_array(
            self.calibration_windows,
            "calibration_windows",
        )
        sources = _readonly_string_array(self.sources, "sources")
        provenance_json = _readonly_string_array(self.provenance_json, "provenance_json")
        source_row_ids = _readonly_string_array(self.source_row_ids, "source_row_ids")
        _validate_equal_lengths(
            "scenario metadata batch",
            scenario_ids,
            scenario_dates,
            scenario_sets,
            calibration_windows,
            sources,
            provenance_json,
            source_row_ids,
        )
        if scenario_ids.size == 0:
            raise ValueError("scenario metadata batch must be non-empty")
        if bool(np.any(scenario_ids == "")):
            raise ValueError("scenario_ids cannot contain empty values")
        if np.unique(scenario_ids).size != scenario_ids.size:
            raise ValueError("scenario metadata contains duplicate scenario_id values")
        if np.unique(scenario_dates).size != scenario_dates.size:
            raise ValueError("scenario metadata contains duplicate scenario_date values")
        for scenario_set in scenario_sets:
            ScenarioSetType(str(scenario_set))
        for raw_json in provenance_json:
            _parse_provenance_json(str(raw_json))

        object.__setattr__(self, "scenario_ids", scenario_ids)
        object.__setattr__(self, "scenario_dates", scenario_dates)
        object.__setattr__(self, "scenario_sets", scenario_sets)
        object.__setattr__(self, "calibration_windows", calibration_windows)
        object.__setattr__(self, "sources", sources)
        object.__setattr__(self, "provenance_json", provenance_json)
        object.__setattr__(self, "source_row_ids", source_row_ids)
        if not self.input_hash:
            object.__setattr__(self, "input_hash", input_hash_for_scenario_metadata_batch(self))

    @property
    def scenario_count(self) -> int:
        """Number of scenario metadata rows carried by the batch.
        Returns
        -------
        int
            Result of the operation.
        """

        return int(self.scenario_ids.size)

    def to_metadata(self) -> tuple[ScenarioMetadata, ...]:
        """Materialize compatibility dataclasses in batch order.

        High-volume adapters should pass the batch itself through ingestion and
        audit checks. This method is for legacy APIs that still require
        ``ScenarioMetadata`` objects.
        Returns
        -------
        tuple[ScenarioMetadata, ...]
            Result of the operation.
        """

        return tuple(
            ScenarioMetadata(
                scenario_id=str(self.scenario_ids[index]),
                scenario_date=_date_from_datetime64(
                    self.scenario_dates[index],
                    "scenario date",
                ),
                scenario_set=ScenarioSetType(str(self.scenario_sets[index])),
                calibration_window=str(self.calibration_windows[index]),
                source=str(self.sources[index]),
                provenance=_parse_provenance_json(str(self.provenance_json[index])),
            )
            for index in range(self.scenario_count)
        )


def input_hash_for_scenario_metadata_batch(batch: ScenarioMetadataBatch) -> str:
    """Return a stable audit hash for a columnar scenario metadata batch.
    Parameters
    ----------
    batch : ScenarioMetadataBatch
        Batch.

    Returns
    -------
    str
        Result of the operation.
    """

    return compute_inputs_hash(
        scenario_ids=batch.scenario_ids,
        scenario_dates=batch.scenario_dates,
        scenario_sets=batch.scenario_sets,
        calibration_windows=batch.calibration_windows,
        sources=batch.sources,
        provenance_json=batch.provenance_json,
        source_row_ids=batch.source_row_ids,
        source_hash=batch.source_hash,
        handoff_hash=batch.handoff_hash,
    )


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
        if not np.all(np.isfinite(arr)):
            raise ValueError("ScenarioVector values must contain only finite values")
        if self.metadata and len(self.metadata) != arr.size:
            raise ValueError(
                f"metadata length ({len(self.metadata)}) != values length ({arr.size})"
            )
        object.__setattr__(self, "values", arr.astype(np.float64, copy=False))
        object.__setattr__(self, "metadata", tuple(self.metadata))

    @property
    def scenario_ids(self) -> tuple[str, ...]:
        """Scenario IDs in vector order, or an empty tuple if metadata is absent.
        Returns
        -------
        tuple[str, ...]
            Result of the operation.
        """
        return tuple(item.scenario_id for item in self.metadata)

    @property
    def scenario_dates(self) -> tuple[date, ...]:
        """Scenario dates in vector order, or an empty tuple if metadata is absent.
        Returns
        -------
        tuple[date, ...]
            Result of the operation.
        """
        return tuple(item.scenario_date for item in self.metadata)

    def tolist(self) -> list[float]:
        """Return values as a plain list for compatibility with existing APIs.
        Returns
        -------
        list[float]
            Result of the operation.
        """
        return [float(value) for value in self.values]


def make_scenario_metadata(
    scenario_dates: Sequence[date],
    *,
    prefix: str = "scenario",
    scenario_set: ScenarioSetType = ScenarioSetType.CURRENT,
    calibration_window: str = "",
    source: str = "",
) -> tuple[ScenarioMetadata, ...]:
    """Create deterministic scenario metadata from ordered scenario dates.

    Scenario IDs are stable and position-based: ``{prefix}-{index:05d}``.
    Parameters
    ----------
    scenario_dates : Sequence[date]
        Scenario dates.
    prefix : str, optional
        Prefix.
    scenario_set : ScenarioSetType, optional
        Scenario set.
    calibration_window : str, optional
        Calibration window.
    source : str, optional
        Source.

    Returns
    -------
    tuple[ScenarioMetadata, ...]
        Result of the operation.
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
    """Validate that scenario IDs and dates are unique within a metadata sequence.
    Parameters
    ----------
    metadata : Sequence[ScenarioMetadata]
        Metadata.
    """
    ids = [item.scenario_id for item in metadata]
    dates = [item.scenario_date for item in metadata]
    if len(ids) != len(set(ids)):
        raise ValueError("scenario metadata contains duplicate scenario_id values")
    if len(dates) != len(set(dates)):
        raise ValueError("scenario metadata contains duplicate scenario_date values")


def validate_aligned_metadata(vectors: Mapping[str, ScenarioVector]) -> None:
    """Validate that all vectors with metadata share identical scenario ordering.

    Vectors without metadata are ignored by this function; length checks for
    metadata-free vectors belong in the nested-vector validator introduced by
    the next workstream issue.
    Parameters
    ----------
    vectors : Mapping[str, ScenarioVector]
        Vectors.
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


def _parse_provenance_json(raw_json: str) -> Mapping[str, str]:
    if not raw_json:
        return {}
    import json

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as err:
        raise ValueError(f"provenance_json contains invalid JSON: {err}") from err
    if not isinstance(parsed, dict):
        raise ValueError("provenance_json must contain a JSON object")
    provenance: dict[str, str] = {}
    for key, value in parsed.items():
        if not isinstance(key, str) or not key:
            raise ValueError("provenance_json keys must be non-empty strings")
        if not isinstance(value, str):
            raise ValueError("provenance_json values must be strings")
        provenance[key] = value
    return provenance
