"""Types for v1 scenario P&L vector mapping adapters."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import numpy as np
import numpy.typing as npt
from frtb_common import ColumnSpec, TabularLogicalType

from frtb_ima.adapters._daily_pnl_mapping_types import (
    FieldMapping,
    MappingFinding,
    MappingSpecError,
)
from frtb_ima.audit_inputs import compute_inputs_hash

IMA_SCENARIO_PNL_VECTOR_TARGET = "ima_scenario_pnl_vectors"
IMA_SCENARIO_PNL_VECTOR_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("scenario_id", logical_type=TabularLogicalType.STRING),
    ColumnSpec("scenario_date", logical_type=TabularLogicalType.DATE),
    ColumnSpec("scenario_set", logical_type=TabularLogicalType.STRING),
    ColumnSpec("position_id", logical_type=TabularLogicalType.STRING),
    ColumnSpec("risk_factor_name", logical_type=TabularLogicalType.STRING),
    ColumnSpec("pnl", logical_type=TabularLogicalType.FLOAT),
    ColumnSpec("source_row_id", logical_type=TabularLogicalType.STRING),
)
SCENARIO_PNL_TARGET_FIELDS = frozenset(
    spec.name for spec in IMA_SCENARIO_PNL_VECTOR_ARROW_COLUMN_SPECS
)
REQUIRED_SCENARIO_PNL_FIELDS = frozenset(
    {"scenario_id", "scenario_date", "position_id", "risk_factor_name", "pnl"}
)
SCENARIO_PNL_MISSING_CELL_POLICIES = frozenset({"reject", "zero"})


@dataclass(frozen=True)
class ScenarioPnlTableMapping:
    """Mapping configuration for v1 long-form scenario P&L source rows."""

    source: str
    target: str
    fields: Mapping[str, FieldMapping]
    missing_cells: str = "reject"

    def __post_init__(self) -> None:
        if not self.source:
            raise MappingSpecError("scenario_pnl_vectors.source must be non-empty")
        if self.target != IMA_SCENARIO_PNL_VECTOR_TARGET:
            raise MappingSpecError(
                "scenario_pnl_vectors.target must be "
                f"{IMA_SCENARIO_PNL_VECTOR_TARGET!r}, got {self.target!r}"
            )
        unknown = sorted(set(self.fields) - SCENARIO_PNL_TARGET_FIELDS)
        if unknown:
            raise MappingSpecError(
                "unknown scenario_pnl_vectors target fields: " + ", ".join(unknown)
            )
        missing = sorted(REQUIRED_SCENARIO_PNL_FIELDS - set(self.fields))
        if missing:
            raise MappingSpecError(
                "missing scenario_pnl_vectors required fields: " + ", ".join(missing)
            )
        missing_cells = self.missing_cells.strip().lower()
        if missing_cells not in SCENARIO_PNL_MISSING_CELL_POLICIES:
            raise MappingSpecError("scenario_pnl_vectors.missing_cells must be reject or zero")
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))
        object.__setattr__(self, "missing_cells", missing_cells)


@dataclass(frozen=True)
class ScenarioPnlVectorBatch:
    """Accepted canonical long-form scenario P&L rows plus source lineage."""

    scenario_ids: npt.NDArray[np.str_]
    scenario_dates: npt.NDArray[np.datetime64]
    scenario_sets: npt.NDArray[np.str_]
    position_ids: npt.NDArray[np.str_]
    risk_factor_names: npt.NDArray[np.str_]
    pnl: npt.NDArray[np.float64]
    source_row_ids: npt.NDArray[np.str_]
    source_hash: str
    handoff_hash: str
    input_hash: str = ""

    def __post_init__(self) -> None:
        arrays = {
            "scenario_ids": _readonly_string_array(self.scenario_ids, "scenario_ids"),
            "scenario_dates": _readonly_date_array(self.scenario_dates, "scenario_dates"),
            "scenario_sets": _readonly_string_array(self.scenario_sets, "scenario_sets"),
            "position_ids": _readonly_string_array(self.position_ids, "position_ids"),
            "risk_factor_names": _readonly_string_array(
                self.risk_factor_names, "risk_factor_names"
            ),
            "pnl": _readonly_float_array(self.pnl, "pnl"),
            "source_row_ids": _readonly_string_array(self.source_row_ids, "source_row_ids"),
        }
        if len({array.size for array in arrays.values()}) != 1:
            raise ValueError("scenario P&L vector columns must have equal length")
        if arrays["scenario_ids"].size == 0:
            raise ValueError("scenario P&L vector batch must be non-empty")
        for name in (
            "scenario_ids",
            "scenario_sets",
            "position_ids",
            "risk_factor_names",
            "source_row_ids",
        ):
            if bool(np.any(arrays[name] == "")):
                raise ValueError(f"{name} cannot contain empty values")
        for name, array in arrays.items():
            object.__setattr__(self, name, array)
        if not self.input_hash:
            object.__setattr__(self, "input_hash", input_hash_for_scenario_pnl_batch(self))

    @property
    def observation_count(self) -> int:
        """Return the number of accepted scenario P&L rows.

        Returns
        -------
        int
            Count of accepted long-form scenario P&L rows.
        """

        return int(self.scenario_ids.size)


@dataclass(frozen=True)
class ScenarioPnlValidationReport:
    """Generated validation and reconciliation report for scenario P&L mapping."""

    target_schema: str
    source_system: str
    source_file: str
    mapping_hash: str
    source_hash: str
    row_count_read: int
    row_count_mapped: int
    row_count_rejected: int
    findings: tuple[MappingFinding, ...] = ()

    @property
    def passed(self) -> bool:
        """Return ``True`` when no finding has severity ``ERROR``.

        Returns
        -------
        bool
            ``True`` when the report contains no error-severity findings.
        """

        return all(finding.severity != "ERROR" for finding in self.findings)

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable validation report payload.

        Returns
        -------
        dict[str, object]
            Validation report fields suitable for JSON serialization.
        """

        return {
            "target_schema": self.target_schema,
            "source_system": self.source_system,
            "source_file": self.source_file,
            "mapping_hash": self.mapping_hash,
            "source_hash": self.source_hash,
            "row_count_read": self.row_count_read,
            "row_count_mapped": self.row_count_mapped,
            "row_count_rejected": self.row_count_rejected,
            "passed": self.passed,
            "findings": [finding.as_dict() for finding in self.findings],
        }


def input_hash_for_scenario_pnl_batch(batch: ScenarioPnlVectorBatch) -> str:
    """Return a stable input hash for accepted scenario P&L rows.

    Parameters
    ----------
    batch : ScenarioPnlVectorBatch
        Accepted canonical scenario P&L rows and provenance identifiers.

    Returns
    -------
    str
        Deterministic SHA-256 hash over accepted rows and source lineage.
    """

    return compute_inputs_hash(
        scenario_ids=batch.scenario_ids,
        scenario_dates=batch.scenario_dates,
        scenario_sets=batch.scenario_sets,
        position_ids=batch.position_ids,
        risk_factor_names=batch.risk_factor_names,
        pnl=batch.pnl,
        source_row_ids=batch.source_row_ids,
        source_hash=batch.source_hash,
        handoff_hash=batch.handoff_hash,
    )


def _readonly_string_array(values: npt.ArrayLike, name: str) -> npt.NDArray[np.str_]:
    arr = np.asarray(values, dtype=np.str_)
    return _readonly_1d(arr, name)


def _readonly_date_array(values: npt.ArrayLike, name: str) -> npt.NDArray[np.datetime64]:
    arr = np.asarray(values, dtype="datetime64[D]")
    return _readonly_1d(arr, name)


def _readonly_float_array(values: npt.ArrayLike, name: str) -> npt.NDArray[np.float64]:
    arr = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return _readonly_1d(arr, name)


def _readonly_1d(arr: npt.NDArray[Any], name: str) -> npt.NDArray[Any]:
    if arr.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if not arr.flags.owndata:
        arr = arr.copy()
    arr.flags.writeable = False
    return arr
