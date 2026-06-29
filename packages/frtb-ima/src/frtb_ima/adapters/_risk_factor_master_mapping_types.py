"""Types for v1 risk-factor master mapping adapters."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, TYPE_CHECKING

import numpy as np
import numpy.typing as npt
from frtb_common import ColumnSpec, TabularLogicalType

from frtb_ima.adapters._mapping_hash import stable_mapping_hash
from frtb_ima.data_models import LiquidityHorizon, RiskClass

if TYPE_CHECKING:
    from frtb_ima.adapters._daily_pnl_mapping_types import FieldMapping, MappingFinding

IMA_RISK_FACTOR_MASTER_TARGET = "ima_risk_factor_master"
IMA_RISK_FACTOR_MASTER_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("risk_factor_name", logical_type=TabularLogicalType.STRING),
    ColumnSpec("risk_class", logical_type=TabularLogicalType.STRING),
    ColumnSpec("liquidity_horizon", logical_type=TabularLogicalType.INTEGER),
    ColumnSpec("bucket", logical_type=TabularLogicalType.STRING, required=False),
    ColumnSpec("effective_date", logical_type=TabularLogicalType.DATE),
    ColumnSpec("source_row_id", logical_type=TabularLogicalType.STRING),
)
RISK_FACTOR_MASTER_TARGET_FIELDS = frozenset(
    spec.name for spec in IMA_RISK_FACTOR_MASTER_ARROW_COLUMN_SPECS
)
REQUIRED_RISK_FACTOR_MASTER_FIELDS = frozenset(
    {"risk_factor_name", "risk_class", "liquidity_horizon", "effective_date"}
)


@dataclass(frozen=True)
class RiskFactorMasterTableMapping:
    """Mapping configuration for v1 risk-factor master source rows."""

    source: str
    target: str
    fields: Mapping[str, FieldMapping]

    def __post_init__(self) -> None:
        from frtb_ima.adapters._daily_pnl_mapping_types import MappingSpecError

        if not self.source:
            raise MappingSpecError("risk_factor_master.source must be non-empty")
        if self.target != IMA_RISK_FACTOR_MASTER_TARGET:
            raise MappingSpecError(
                "risk_factor_master.target must be "
                f"{IMA_RISK_FACTOR_MASTER_TARGET!r}, got {self.target!r}"
            )
        unknown = sorted(set(self.fields) - RISK_FACTOR_MASTER_TARGET_FIELDS)
        if unknown:
            raise MappingSpecError(
                "unknown risk_factor_master target fields: " + ", ".join(unknown)
            )
        missing = sorted(REQUIRED_RISK_FACTOR_MASTER_FIELDS - set(self.fields))
        if missing:
            raise MappingSpecError(
                "missing risk_factor_master required fields: " + ", ".join(missing)
            )
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))


@dataclass(frozen=True)
class RiskFactorMasterBatch:
    """Accepted canonical risk-factor master rows with lineage and hashes."""

    risk_factor_names: npt.NDArray[np.str_]
    risk_classes: npt.NDArray[np.str_]
    liquidity_horizons: npt.NDArray[np.int64]
    buckets: npt.NDArray[np.str_]
    effective_dates: npt.NDArray[np.datetime64]
    source_row_ids: npt.NDArray[np.str_]
    source_hash: str | None = None
    mapping_hash: str | None = None
    table_hash: str | None = None
    input_hash: str = ""

    def __post_init__(self) -> None:
        arrays = {
            "risk_factor_names": _readonly_string_array(
                self.risk_factor_names, "risk_factor_names"
            ),
            "risk_classes": _readonly_string_array(self.risk_classes, "risk_classes"),
            "liquidity_horizons": _readonly_int_array(
                self.liquidity_horizons, "liquidity_horizons"
            ),
            "buckets": _readonly_string_array(self.buckets, "buckets"),
            "effective_dates": _readonly_date_array(self.effective_dates, "effective_dates"),
            "source_row_ids": _readonly_string_array(self.source_row_ids, "source_row_ids"),
        }
        lengths = {array.size for array in arrays.values()}
        if len(lengths) != 1:
            raise ValueError("risk-factor master arrays must have equal lengths")
        if not lengths or next(iter(lengths)) == 0:
            raise ValueError("risk-factor master batch must be non-empty")
        if bool(np.any(arrays["risk_factor_names"] == "")):
            raise ValueError("risk_factor_names cannot contain empty values")
        if bool(np.any(arrays["source_row_ids"] == "")):
            raise ValueError("source_row_ids cannot contain empty values")
        for name, array in arrays.items():
            object.__setattr__(self, name, array)
        if not self.input_hash:
            object.__setattr__(self, "input_hash", input_hash_for_risk_factor_master_batch(self))

    @property
    def row_count(self) -> int:
        """Number of accepted risk-factor master rows.

        Returns
        -------
        int
            Accepted row count.
        """

        return int(self.risk_factor_names.size)

    def liquidity_horizon_by_name(self) -> dict[str, LiquidityHorizon]:
        """Return latest liquidity horizon keyed by risk-factor name.

        Returns
        -------
        dict[str, LiquidityHorizon]
            Risk-factor name to liquidity-horizon enum.
        """

        result: dict[str, LiquidityHorizon] = {}
        for name, liquidity_horizon in zip(
            self.risk_factor_names, self.liquidity_horizons, strict=True
        ):
            result[str(name)] = LiquidityHorizon(int(liquidity_horizon))
        return result

    def risk_class_by_name(self) -> dict[str, RiskClass]:
        """Return latest risk class keyed by risk-factor name.

        Returns
        -------
        dict[str, RiskClass]
            Risk-factor name to risk-class enum.
        """

        result: dict[str, RiskClass] = {}
        for name, risk_class in zip(self.risk_factor_names, self.risk_classes, strict=True):
            result[str(name)] = RiskClass(str(risk_class))
        return result


@dataclass(frozen=True)
class RiskFactorMasterValidationReport:
    """Generated validation and reconciliation report for risk-factor master mapping."""

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


def input_hash_for_risk_factor_master_batch(batch: RiskFactorMasterBatch) -> str:
    """Return stable hash of accepted risk-factor master batch contents.

    Parameters
    ----------
    batch : RiskFactorMasterBatch
        Accepted risk-factor master batch.

    Returns
    -------
    str
        Stable SHA-256 input hash.
    """

    return stable_mapping_hash(
        {
            "risk_factor_names": batch.risk_factor_names.tolist(),
            "risk_classes": batch.risk_classes.tolist(),
            "liquidity_horizons": batch.liquidity_horizons.tolist(),
            "buckets": batch.buckets.tolist(),
            "effective_dates": batch.effective_dates.astype("datetime64[D]").astype(str).tolist(),
            "source_row_ids": batch.source_row_ids.tolist(),
            "source_hash": batch.source_hash,
            "mapping_hash": batch.mapping_hash,
            "table_hash": batch.table_hash,
        }
    )


def _readonly_string_array(values: npt.ArrayLike, name: str) -> npt.NDArray[np.str_]:
    return _readonly_1d(np.asarray(values, dtype=np.str_), name)


def _readonly_int_array(values: npt.ArrayLike, name: str) -> npt.NDArray[np.int64]:
    return _readonly_1d(np.asarray(values, dtype=np.int64), name)


def _readonly_date_array(values: npt.ArrayLike, name: str) -> npt.NDArray[np.datetime64]:
    return _readonly_1d(np.asarray(values, dtype="datetime64[D]"), name)


def _readonly_1d(arr: npt.NDArray[Any], name: str) -> npt.NDArray[Any]:
    if arr.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if arr.size and bool(np.any(arr.astype(str) == "NaT")):
        raise ValueError(f"{name} cannot contain NaT")
    arr = arr.copy()
    arr.flags.writeable = False
    return arr
