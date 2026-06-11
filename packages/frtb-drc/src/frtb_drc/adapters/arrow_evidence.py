"""Arrow evidence adapters for DRC context-map handoffs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, cast

import numpy as np
import numpy.typing as npt
import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import (
    AdapterDiagnostic,
    ColumnSpec,
    NormalizedArrowTable,
    normalize_arrow_table,
    read_arrow_columns,
)

from frtb_drc.adapters.arrow_evidence_specs import (
    DRC_FAIR_VALUE_CAP_EVIDENCE_ARROW_COLUMN_SPECS,
    DRC_RISK_WEIGHT_EVIDENCE_ARROW_COLUMN_SPECS,
)
from frtb_drc.data_models import (
    DrcFairValueCapEvidence,
    DrcRiskClass,
    DrcRiskWeightEvidence,
    DrcSourceLineage,
)
from frtb_drc.fair_value_cap import fair_value_cap_evidence_by_position
from frtb_drc.risk_weight_evidence import risk_weight_evidence_by_position
from frtb_drc.validation import DrcInputError


def normalize_drc_risk_weight_evidence_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize Arrow risk-weight evidence for DRC securitisation and CTP.

    Parameters
    ----------
    table : pa.Table
        Raw client evidence table.

    Returns
    -------
    NormalizedArrowTable
        Canonical evidence handoff for context-map construction.
    """

    return _normalize_drc_evidence_arrow_table(
        table,
        DRC_RISK_WEIGHT_EVIDENCE_ARROW_COLUMN_SPECS,
        diagnostics,
        metadata,
        rejected,
        source_hash,
    )


def normalize_drc_fair_value_cap_evidence_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize Arrow fair-value-cap evidence for DRC securitisation.

    Parameters
    ----------
    table : pa.Table
        Raw client evidence table.

    Returns
    -------
    NormalizedArrowTable
        Canonical evidence handoff for context-map construction.
    """

    return _normalize_drc_evidence_arrow_table(
        table,
        DRC_FAIR_VALUE_CAP_EVIDENCE_ARROW_COLUMN_SPECS,
        diagnostics,
        metadata,
        rejected,
        source_hash,
    )


def build_drc_risk_weight_evidence_from_arrow(
    handoff: NormalizedArrowTable,
) -> dict[str, DrcRiskWeightEvidence]:
    """Build typed DRC risk-weight evidence records from an Arrow handoff.

    Parameters
    ----------
    handoff : NormalizedArrowTable
        Canonical risk-weight evidence handoff.

    Returns
    -------
    dict[str, DrcRiskWeightEvidence]
        Evidence keyed by position id for context-map injection.
    """

    return _build_drc_risk_weight_evidence_from_arrow(handoff, expected_risk_class=None)


def build_drc_securitisation_non_ctp_risk_weight_evidence_from_arrow(
    handoff: NormalizedArrowTable,
) -> dict[str, DrcRiskWeightEvidence]:
    """Build securitisation non-CTP risk-weight evidence from Arrow.

    Parameters
    ----------
    handoff : NormalizedArrowTable
        Canonical risk-weight evidence handoff.

    Returns
    -------
    dict[str, DrcRiskWeightEvidence]
        Securitisation non-CTP evidence keyed by position id.
    """

    return _build_drc_risk_weight_evidence_from_arrow(
        handoff,
        expected_risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
    )


def build_drc_ctp_risk_weight_evidence_from_arrow(
    handoff: NormalizedArrowTable,
) -> dict[str, DrcRiskWeightEvidence]:
    """Build CTP risk-weight evidence from an Arrow handoff.

    Parameters
    ----------
    handoff : NormalizedArrowTable
        Canonical risk-weight evidence handoff.

    Returns
    -------
    dict[str, DrcRiskWeightEvidence]
        Correlation trading portfolio evidence keyed by position id.
    """

    return _build_drc_risk_weight_evidence_from_arrow(
        handoff,
        expected_risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
    )


def build_drc_fair_value_cap_evidence_from_arrow(
    handoff: NormalizedArrowTable,
) -> dict[str, DrcFairValueCapEvidence]:
    """Build typed DRC fair-value-cap evidence records from an Arrow handoff.

    Parameters
    ----------
    handoff : NormalizedArrowTable
        Canonical fair-value-cap evidence handoff.

    Returns
    -------
    dict[str, DrcFairValueCapEvidence]
        Fair-value-cap evidence keyed by position id for context-map injection.
    """

    table, columns = _read_evidence_columns(handoff, DRC_FAIR_VALUE_CAP_EVIDENCE_ARROW_COLUMN_SPECS)
    records: list[DrcFairValueCapEvidence] = []
    for index in range(table.num_rows):
        position_id = _required_text(columns, "position_id", index)
        eligible = _required_bool(columns, "eligible", index)
        fair_value_cap_amount = _optional_float(columns, "fair_value_cap_amount", index)
        _validate_fair_value_cap_amount(position_id, eligible, fair_value_cap_amount)
        if _optional_bool(columns, "is_stale", index):
            raise DrcInputError(f"fair-value-cap evidence for {position_id!r} is stale")
        records.append(
            DrcFairValueCapEvidence(
                position_id=position_id,
                source_profile_id=_required_text(columns, "source_profile_id", index),
                eligible=eligible,
                fair_value_cap_amount=fair_value_cap_amount,
                eligibility_reason=_required_text(columns, "eligibility_reason", index),
                as_of_date=_required_date(columns, "as_of_date", index),
                source_id=_required_text(columns, "source_id", index),
                lineage=_lineage_from_columns(columns, index),
                citation_ids=_required_ids(columns, "citation_ids", index),
                is_stale=False,
                validation_flags=_optional_ids(columns, "validation_flags", index),
            )
        )
    return fair_value_cap_evidence_by_position(records)


def _normalize_drc_evidence_arrow_table(
    table: pa.Table,
    column_specs: tuple[ColumnSpec, ...],
    diagnostics: Sequence[AdapterDiagnostic],
    metadata: Mapping[str, str] | None,
    rejected: pa.Table | None,
    source_hash: str | None,
) -> NormalizedArrowTable:
    return normalize_arrow_table(
        table,
        column_specs=column_specs,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def _build_drc_risk_weight_evidence_from_arrow(
    handoff: NormalizedArrowTable,
    *,
    expected_risk_class: DrcRiskClass | None,
) -> dict[str, DrcRiskWeightEvidence]:
    table, columns = _read_evidence_columns(handoff, DRC_RISK_WEIGHT_EVIDENCE_ARROW_COLUMN_SPECS)
    records: list[DrcRiskWeightEvidence] = []
    for index in range(table.num_rows):
        position_id = _required_text(columns, "position_id", index)
        risk_class = _risk_class(columns, index)
        if expected_risk_class is not None and risk_class is not expected_risk_class:
            raise DrcInputError(
                f"risk-weight evidence for {position_id!r} has risk_class "
                f"{risk_class.value!r}; expected {expected_risk_class.value!r}"
            )
        if _optional_bool(columns, "is_stale", index):
            raise DrcInputError(f"risk-weight evidence for {position_id!r} is stale")
        records.append(
            DrcRiskWeightEvidence(
                position_id=position_id,
                risk_class=risk_class,
                source_profile_id=_required_text(columns, "source_profile_id", index),
                source_table=_required_text(columns, "source_table", index),
                source_method=_required_text(columns, "source_method", index),
                effective_risk_weight=_required_non_negative_float(
                    columns,
                    "effective_risk_weight",
                    index,
                ),
                as_of_date=_required_date(columns, "as_of_date", index),
                source_id=_required_text(columns, "source_id", index),
                lineage=_lineage_from_columns(columns, index),
                citation_ids=_required_ids(columns, "citation_ids", index),
                is_stale=False,
                validation_flags=_optional_ids(columns, "validation_flags", index),
            )
        )
    return risk_weight_evidence_by_position(records)


def _read_evidence_columns(
    handoff: NormalizedArrowTable,
    specs: tuple[ColumnSpec, ...],
) -> tuple[pa.Table, dict[str, npt.NDArray[Any]]]:
    if not isinstance(handoff, NormalizedArrowTable):
        raise DrcInputError("handoff must be NormalizedArrowTable")
    table = handoff.accepted
    columns = read_arrow_columns(table, specs, error=_drc_error)
    return table, columns


def _drc_error(message: str, _field: str | None) -> DrcInputError:
    return DrcInputError(message)


def _lineage_from_columns(columns: Mapping[str, npt.NDArray[Any]], index: int) -> DrcSourceLineage:
    return DrcSourceLineage(
        source_system=_required_text(columns, "lineage_source_system", index),
        source_file=_required_text(columns, "lineage_source_file", index),
        source_row_id=_required_text(columns, "lineage_source_row_id", index),
        source_column_map={},
    )


def _risk_class(columns: Mapping[str, npt.NDArray[Any]], index: int) -> DrcRiskClass:
    raw = _required_text(columns, "risk_class", index)
    try:
        return DrcRiskClass(raw)
    except ValueError as exc:
        raise DrcInputError(f"risk_class must be a supported DRC risk class: {raw!r}") from exc


def _value(columns: Mapping[str, npt.NDArray[Any]], field: str, index: int) -> object:
    values = columns.get(field)
    if values is None:
        return None
    return values[index]


def _required_text(columns: Mapping[str, npt.NDArray[Any]], field: str, index: int) -> str:
    value = _value(columns, field, index)
    if value is None:
        raise DrcInputError(f"{field} is required")
    text = str(value).strip()
    if not text:
        raise DrcInputError(f"{field} must be non-empty")
    return text


def _required_bool(columns: Mapping[str, npt.NDArray[Any]], field: str, index: int) -> bool:
    value = _value(columns, field, index)
    if value is None:
        raise DrcInputError(f"{field} is required")
    return _coerce_bool(value, field)


def _optional_bool(columns: Mapping[str, npt.NDArray[Any]], field: str, index: int) -> bool:
    value = _value(columns, field, index)
    if value is None:
        return False
    return _coerce_bool(value, field)


def _coerce_bool(value: object, field: str) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n", ""}:
        return False
    raise DrcInputError(f"{field} must be boolean")


def _required_date(columns: Mapping[str, npt.NDArray[Any]], field: str, index: int) -> date:
    value = _value(columns, field, index)
    if value is None:
        raise DrcInputError(f"{field} is required")
    if isinstance(value, date):
        return value
    if isinstance(value, np.datetime64):
        if np.isnat(value):
            raise DrcInputError(f"{field} is required")
        return date.fromisoformat(np.datetime_as_string(value.astype("datetime64[D]"), unit="D"))
    text = str(value).strip()
    if not text:
        raise DrcInputError(f"{field} is required")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise DrcInputError(f"{field} must be an ISO date") from exc


def _required_non_negative_float(
    columns: Mapping[str, npt.NDArray[Any]],
    field: str,
    index: int,
) -> float:
    value = _float_value(_value(columns, field, index), field)
    if value is None:
        raise DrcInputError(f"{field} is required")
    if value < 0.0:
        raise DrcInputError(f"{field} must be non-negative")
    return value


def _optional_float(
    columns: Mapping[str, npt.NDArray[Any]],
    field: str,
    index: int,
) -> float | None:
    return _float_value(_value(columns, field, index), field)


def _float_value(value: object, field: str) -> float | None:
    if value is None:
        return None
    result = float(cast(Any, value))
    if np.isnan(result):
        return None
    if not np.isfinite(result):
        raise DrcInputError(f"{field} must be finite")
    return result


def _validate_fair_value_cap_amount(
    position_id: str,
    eligible: bool,
    fair_value_cap_amount: float | None,
) -> None:
    if eligible and fair_value_cap_amount is None:
        raise DrcInputError(
            f"fair_value_cap_amount is required for eligible evidence {position_id!r}"
        )
    if eligible and fair_value_cap_amount is not None and fair_value_cap_amount < 0.0:
        raise DrcInputError(f"fair_value_cap_amount must be non-negative for {position_id!r}")
    if not eligible and fair_value_cap_amount is not None:
        raise DrcInputError(
            f"fair_value_cap_amount must be empty for ineligible evidence {position_id!r}"
        )


def _required_ids(
    columns: Mapping[str, npt.NDArray[Any]],
    field: str,
    index: int,
) -> tuple[str, ...]:
    ids = _optional_ids(columns, field, index)
    if not ids:
        raise DrcInputError(f"{field} must contain at least one non-empty id")
    return ids


def _optional_ids(
    columns: Mapping[str, npt.NDArray[Any]],
    field: str,
    index: int,
) -> tuple[str, ...]:
    value = _value(columns, field, index)
    if value is None:
        return ()
    return tuple(item.strip() for item in str(value).split(",") if item.strip())
