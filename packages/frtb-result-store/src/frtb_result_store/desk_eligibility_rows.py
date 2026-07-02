"""Desk eligibility mart row serialization helpers."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from frtb_common.hashing import stable_json_dumps

from frtb_result_store._model_desk_eligibility import (
    BacktestingState,
    DeskEligibilityRow,
    DeskEligibilityState,
    PLAState,
)
from frtb_result_store._row_codecs import (
    float_value as _float_value,
)
from frtb_result_store._row_codecs import (
    int_value as _int_value,
)
from frtb_result_store._row_codecs import (
    json_mapping as _json_mapping,
)
from frtb_result_store._row_codecs import (
    json_text_tuple as _json_text_tuple,
)
from frtb_result_store._row_codecs import (
    metadata_json as _metadata_json,
)
from frtb_result_store._row_codecs import (
    optional_text as _optional_text,
)
from frtb_result_store._row_codecs import (
    stored_value as _stored_value,
)

__all__ = [
    "_desk_eligibility_mart_from_row",
    "_desk_eligibility_mart_row",
]


def _desk_eligibility_mart_row(row: DeskEligibilityRow) -> dict[str, object]:
    """Serialize one desk eligibility read-model row."""
    return {
        "run_id": row.run_id,
        "desk_id": row.desk_id,
        "desk_node_id": row.desk_node_id,
        "label": row.label,
        "legal_entity_id": row.legal_entity_id,
        "division_id": row.division_id,
        "business_line_id": row.business_line_id,
        "volcker_desk_id": row.volcker_desk_id,
        "book_ids_json": str(stable_json_dumps(list(row.book_ids))),
        "eligibility_state": _stored_value(row.eligibility_state),
        "pla_state": _stored_value(row.pla_state),
        "pla_threshold_profile_id": row.pla_threshold_profile_id,
        "pla_metric_summary_json": _metadata_json(row.pla_metric_summary),
        "backtesting_state": _stored_value(row.backtesting_state),
        "backtesting_zone": row.backtesting_zone,
        "backtesting_exception_count": row.backtesting_exception_count,
        "backtesting_window": row.backtesting_window,
        "latest_exception_date": (
            None if row.latest_exception_date is None else row.latest_exception_date.isoformat()
        ),
        "rfet_modellable_count": row.rfet_modellable_count,
        "nmrf_count": row.nmrf_count,
        "ses_amount": row.ses_amount,
        "capital_consequence_amount": row.capital_consequence_amount,
        "capital_consequence_currency": row.capital_consequence_currency,
        "capital_node_id": row.capital_node_id,
        "pnl_artifact_id": row.pnl_artifact_id,
        "rfet_artifact_id": row.rfet_artifact_id,
        "source_artifact_id": row.source_artifact_id,
        "model_run_id": row.model_run_id,
        "profile_hash": row.profile_hash,
        "source_hashes_json": str(stable_json_dumps(list(row.source_hashes))),
        "calculation_timestamp": (
            None if row.calculation_timestamp is None else row.calculation_timestamp.isoformat()
        ),
        "metadata_json": _metadata_json(row.metadata),
    }


def _desk_eligibility_mart_from_row(row: Sequence[object]) -> DeskEligibilityRow:
    """Deserialize one storage-order desk eligibility mart row."""
    return DeskEligibilityRow(
        run_id=str(row[0]),
        desk_id=str(row[1]),
        desk_node_id=str(row[2]),
        label=str(row[3]),
        legal_entity_id=_optional_text(row[4]),
        division_id=_optional_text(row[5]),
        business_line_id=_optional_text(row[6]),
        volcker_desk_id=_optional_text(row[7]),
        book_ids=_json_text_tuple(row[8]),
        eligibility_state=DeskEligibilityState(str(row[9])),
        pla_state=PLAState(str(row[10])),
        pla_threshold_profile_id=_optional_text(row[11]),
        pla_metric_summary=_json_mapping(row[12]),
        backtesting_state=BacktestingState(str(row[13])),
        backtesting_zone=_optional_text(row[14]),
        backtesting_exception_count=None if row[15] is None else _int_value(row[15]),
        backtesting_window=_optional_text(row[16]),
        latest_exception_date=None if row[17] is None else date.fromisoformat(str(row[17])),
        rfet_modellable_count=None if row[18] is None else _int_value(row[18]),
        nmrf_count=None if row[19] is None else _int_value(row[19]),
        ses_amount=None if row[20] is None else _float_value(row[20]),
        capital_consequence_amount=None if row[21] is None else _float_value(row[21]),
        capital_consequence_currency=_optional_text(row[22]),
        capital_node_id=_optional_text(row[23]),
        pnl_artifact_id=_optional_text(row[24]),
        rfet_artifact_id=_optional_text(row[25]),
        source_artifact_id=_optional_text(row[26]),
        model_run_id=_optional_text(row[27]),
        profile_hash=_optional_text(row[28]),
        source_hashes=_json_text_tuple(row[29]),
        calculation_timestamp=None if row[30] is None else datetime.fromisoformat(str(row[30])),
        metadata=_json_mapping(row[31]),
    )
