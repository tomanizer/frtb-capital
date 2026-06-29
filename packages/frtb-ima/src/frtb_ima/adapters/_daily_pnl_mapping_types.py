"""Types for v1 daily P&L mapping adapters."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt
from frtb_common import ColumnSpec, NullPolicy, TabularLogicalType

from frtb_ima.adapters._mapping_hash import stable_mapping_hash
from frtb_ima.audit_inputs import compute_inputs_hash

if TYPE_CHECKING:
    from frtb_ima.adapters._rfet_observation_mapping_types import RfetObservationTableMapping

IMA_DAILY_PNL_VECTOR_TARGET = "ima_daily_pnl_vectors"
IMA_MAPPING_SPEC_VERSION = 1

IMA_DAILY_PNL_VECTOR_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("desk_id", logical_type=TabularLogicalType.STRING),
    ColumnSpec("business_date", logical_type=TabularLogicalType.DATE),
    ColumnSpec("apl", logical_type=TabularLogicalType.FLOAT),
    ColumnSpec("hpl", logical_type=TabularLogicalType.FLOAT),
    ColumnSpec("rtpl", logical_type=TabularLogicalType.FLOAT),
    ColumnSpec(
        "var_975",
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "var_99",
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "source_row_id",
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)

REQUIRED_DAILY_PNL_FIELDS = frozenset({"desk_id", "business_date", "apl", "hpl", "rtpl"})
DAILY_PNL_TARGET_FIELDS = frozenset(spec.name for spec in IMA_DAILY_PNL_VECTOR_ARROW_COLUMN_SPECS)


class MappingSpecError(ValueError):
    """Raised when a v1 IMA mapping spec is invalid."""


@dataclass(frozen=True)
class FieldMapping:
    """One target-field mapping from a source column or constant value."""

    source: str | None = None
    constant: str | None = None
    values: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if bool(self.source) == bool(self.constant):
            raise MappingSpecError("field mapping requires exactly one of source or constant")
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


@dataclass(frozen=True)
class DailyPnlTableMapping:
    """Mapping configuration for the v1 daily P&L vector table."""

    source: str
    target: str
    fields: Mapping[str, FieldMapping]

    def __post_init__(self) -> None:
        if not self.source:
            raise MappingSpecError("daily_pnl_vectors.source must be non-empty")
        if self.target != IMA_DAILY_PNL_VECTOR_TARGET:
            raise MappingSpecError(
                "daily_pnl_vectors.target must be "
                f"{IMA_DAILY_PNL_VECTOR_TARGET!r}, got {self.target!r}"
            )
        unknown = sorted(set(self.fields) - DAILY_PNL_TARGET_FIELDS)
        if unknown:
            raise MappingSpecError("unknown daily_pnl_vectors target fields: " + ", ".join(unknown))
        missing = sorted(REQUIRED_DAILY_PNL_FIELDS - set(self.fields))
        if missing:
            raise MappingSpecError(
                "missing daily_pnl_vectors required fields: " + ", ".join(missing)
            )
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))


@dataclass(frozen=True)
class ImaMappingSpec:
    """Versioned v1 IMA mapping spec for canonical adapter targets."""

    mapping_spec_version: int
    target_schema: str
    source_system: str
    base_currency: str
    timezone: str
    pnl_positive_means: str
    daily_pnl_vectors: DailyPnlTableMapping | None = None
    rfet_observations: RfetObservationTableMapping | None = None
    risk_factor_aliases: Mapping[str, str] = field(default_factory=dict)
    spec_hash: str = ""

    def __post_init__(self) -> None:
        if self.mapping_spec_version != IMA_MAPPING_SPEC_VERSION:
            raise MappingSpecError(
                f"mapping_spec_version must be {IMA_MAPPING_SPEC_VERSION}, "
                f"got {self.mapping_spec_version!r}"
            )
        for field_name in ("target_schema", "source_system", "base_currency", "timezone"):
            if not str(getattr(self, field_name)):
                raise MappingSpecError(f"{field_name} must be non-empty")
        if self.daily_pnl_vectors is None and self.rfet_observations is None:
            raise MappingSpecError("tables must define at least one supported IMA target")
        object.__setattr__(
            self, "pnl_positive_means", _normalize_pnl_sign_convention(self.pnl_positive_means)
        )
        object.__setattr__(
            self, "risk_factor_aliases", MappingProxyType(dict(self.risk_factor_aliases))
        )
        if not self.spec_hash:
            object.__setattr__(
                self,
                "spec_hash",
                stable_mapping_hash({"mapping_spec": _mapping_spec_payload(self)}),
            )


@dataclass(frozen=True)
class MappingFinding:
    """One mapping validation finding tied to a target field or source row."""

    severity: str
    code: str
    message: str
    row_id: str = ""
    field: str = ""

    def as_dict(self) -> dict[str, str]:
        """Return a JSON-serializable finding payload.

        Returns
        -------
        dict[str, str]
            Finding fields suitable for JSON serialization.
        """
        payload = {"severity": self.severity, "code": self.code, "message": self.message}
        if self.row_id:
            payload["row_id"] = self.row_id
        if self.field:
            payload["field"] = self.field
        return payload


@dataclass(frozen=True)
class DailyPnlValidationReport:
    """Generated validation and reconciliation report for one mapping run."""

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


@dataclass(frozen=True)
class DailyPnlVectorBatch:
    """Accepted daily P&L vectors for PLA and backtesting adapters."""

    desk_ids: npt.NDArray[np.str_]
    business_dates: npt.NDArray[np.datetime64]
    apl: npt.NDArray[np.float64]
    hpl: npt.NDArray[np.float64]
    rtpl: npt.NDArray[np.float64]
    var_975: npt.NDArray[np.float64]
    var_99: npt.NDArray[np.float64]
    var_975_present: npt.NDArray[np.bool_]
    var_99_present: npt.NDArray[np.bool_]
    source_row_ids: npt.NDArray[np.str_]
    source_hash: str
    mapping_hash: str
    input_hash: str = ""

    def __post_init__(self) -> None:
        arrays = _coerce_batch_arrays(self)
        if len({array.size for array in arrays.values()}) != 1:
            raise ValueError("daily P&L vector columns must have equal length")
        if arrays["desk_ids"].size == 0:
            raise ValueError("daily P&L vector batch must be non-empty")
        if bool(np.any(arrays["desk_ids"] == "")):
            raise ValueError("desk_ids cannot contain empty values")
        if bool(np.any(arrays["source_row_ids"] == "")):
            raise ValueError("source_row_ids cannot contain empty values")
        for name, array in arrays.items():
            object.__setattr__(self, name, array)
        if not self.input_hash:
            object.__setattr__(self, "input_hash", input_hash_for_daily_pnl_vector_batch(self))

    @property
    def observation_count(self) -> int:
        """Return the number of accepted daily P&L observations.

        Returns
        -------
        int
            Count of accepted rows in the batch.
        """
        return int(self.desk_ids.size)

    def observation_dates_for_desk(self, desk_id: str) -> tuple[date, ...]:
        """Return accepted business dates for one desk in ascending order.

        Parameters
        ----------
        desk_id : str
            Desk identifier to filter accepted observations.

        Returns
        -------
        tuple[date, ...]
            Business dates accepted for ``desk_id``.
        """
        selected = self.business_dates[self.desk_ids == desk_id].astype("datetime64[D]").astype(str)
        return tuple(date.fromisoformat(str(value)) for value in selected)


@dataclass(frozen=True)
class DailyPnlMappingResult:
    """Materialized daily P&L vectors plus generated validation report."""

    batch: DailyPnlVectorBatch
    report: DailyPnlValidationReport


def input_hash_for_daily_pnl_vector_batch(batch: DailyPnlVectorBatch) -> str:
    """Return a stable input hash for a daily P&L vector batch.

    Parameters
    ----------
    batch : DailyPnlVectorBatch
        Accepted daily P&L vectors plus source and mapping provenance.

    Returns
    -------
    str
        Deterministic SHA-256 hash over the batch arrays and provenance fields.
    """

    return compute_inputs_hash(
        desk_ids=batch.desk_ids,
        business_dates=batch.business_dates,
        apl=batch.apl,
        hpl=batch.hpl,
        rtpl=batch.rtpl,
        var_975=batch.var_975,
        var_99=batch.var_99,
        var_975_present=batch.var_975_present,
        var_99_present=batch.var_99_present,
        source_row_ids=batch.source_row_ids,
        source_hash=batch.source_hash,
        mapping_hash=batch.mapping_hash,
    )


def _coerce_batch_arrays(batch: DailyPnlVectorBatch) -> dict[str, npt.NDArray[Any]]:
    return {
        "desk_ids": _readonly_string_array(batch.desk_ids, "desk_ids"),
        "business_dates": _readonly_date_array(batch.business_dates, "business_dates"),
        "apl": _readonly_float_array(batch.apl, "apl"),
        "hpl": _readonly_float_array(batch.hpl, "hpl"),
        "rtpl": _readonly_float_array(batch.rtpl, "rtpl"),
        "var_975": _readonly_float_array(batch.var_975, "var_975"),
        "var_99": _readonly_float_array(batch.var_99, "var_99"),
        "var_975_present": _readonly_bool_array(batch.var_975_present, "var_975_present"),
        "var_99_present": _readonly_bool_array(batch.var_99_present, "var_99_present"),
        "source_row_ids": _readonly_string_array(batch.source_row_ids, "source_row_ids"),
    }


def _normalize_pnl_sign_convention(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"profit", "gain", "positive_profit", "positive_gain"}:
        return "profit"
    if normalized in {"loss", "positive_loss"}:
        return "loss"
    raise MappingSpecError(
        "sign_convention.pnl_positive_means must be one of profit, gain, or loss"
    )


def _mapping_spec_payload(spec: ImaMappingSpec) -> dict[str, object]:
    return {
        "mapping_spec_version": spec.mapping_spec_version,
        "target_schema": spec.target_schema,
        "source_system": spec.source_system,
        "base_currency": spec.base_currency,
        "timezone": spec.timezone,
        "pnl_positive_means": spec.pnl_positive_means,
        "daily_pnl_vectors": (
            None if spec.daily_pnl_vectors is None else spec.daily_pnl_vectors.source
        ),
        "rfet_observations": (
            None if spec.rfet_observations is None else spec.rfet_observations.source
        ),
        "risk_factor_aliases": dict(spec.risk_factor_aliases),
    }


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


def _readonly_bool_array(values: npt.ArrayLike, name: str) -> npt.NDArray[np.bool_]:
    arr = np.asarray(values, dtype=np.bool_)
    return _readonly_1d(arr, name)


def _readonly_1d(array: npt.NDArray[Any], name: str) -> npt.NDArray[Any]:
    if array.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    result = array.copy()
    result.flags.writeable = False
    return result
