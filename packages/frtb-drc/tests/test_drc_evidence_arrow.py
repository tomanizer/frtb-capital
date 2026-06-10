from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest
from frtb_drc import (
    DrcCalculationContext,
    DrcFairValueCapEvidence,
    DrcInputError,
    DrcPosition,
    DrcRiskWeightEvidence,
    DrcSourceLineage,
    calculate_drc_capital,
    calculate_drc_capital_from_batch,
    fair_value_cap_evidence_by_position,
    risk_weight_evidence_by_position,
    validate_reconciliation,
)
from frtb_drc.arrow_batch import (
    build_drc_ctp_batch_from_arrow,
    build_drc_ctp_risk_weight_evidence_from_arrow,
    build_drc_fair_value_cap_evidence_from_arrow,
    build_drc_securitisation_non_ctp_batch_from_arrow,
    build_drc_securitisation_non_ctp_risk_weight_evidence_from_arrow,
    normalize_drc_ctp_arrow_table,
    normalize_drc_fair_value_cap_evidence_arrow_table,
    normalize_drc_risk_weight_evidence_arrow_table,
    normalize_drc_securitisation_non_ctp_arrow_table,
)


def test_drc_risk_weight_evidence_arrow_replays_basel_securitisation_non_ctp() -> None:
    fixture = _load_fixture("drc_basel_sec_nonctp_v1")
    context = fixture["context"]
    evidence_records = tuple(context.securitisation_non_ctp_risk_weight_evidence.values())
    evidence = build_drc_securitisation_non_ctp_risk_weight_evidence_from_arrow(
        normalize_drc_risk_weight_evidence_arrow_table(
            _risk_weight_evidence_arrow_table(evidence_records)
        )
    )
    batch = build_drc_securitisation_non_ctp_batch_from_arrow(
        normalize_drc_securitisation_non_ctp_arrow_table(_arrow_table(fixture["positions"]))
    )

    row_result = calculate_drc_capital(fixture["positions"], context=context)
    calculation = calculate_drc_capital_from_batch(
        batch,
        context=replace(context, securitisation_non_ctp_risk_weight_evidence=evidence),
    )

    validate_reconciliation(calculation.result)
    assert calculation.result.total_drc == pytest.approx(row_result.total_drc)
    assert calculation.result.risk_weight_evidence == row_result.risk_weight_evidence

    mutated_evidence = _replace_first_risk_weight_source(evidence_records)
    mutated = build_drc_securitisation_non_ctp_risk_weight_evidence_from_arrow(
        normalize_drc_risk_weight_evidence_arrow_table(
            _risk_weight_evidence_arrow_table(mutated_evidence)
        )
    )
    mutated_calculation = calculate_drc_capital_from_batch(
        batch,
        context=replace(context, securitisation_non_ctp_risk_weight_evidence=mutated),
    )
    assert mutated_calculation.result.total_drc == pytest.approx(calculation.result.total_drc)
    assert mutated_calculation.result.input_hash != calculation.result.input_hash


def test_drc_risk_weight_evidence_arrow_replays_basel_ctp() -> None:
    fixture = _load_fixture("drc_basel_ctp_v1")
    context = fixture["context"]
    evidence = build_drc_ctp_risk_weight_evidence_from_arrow(
        normalize_drc_risk_weight_evidence_arrow_table(
            _risk_weight_evidence_arrow_table(tuple(context.ctp_risk_weight_evidence.values()))
        )
    )
    batch = build_drc_ctp_batch_from_arrow(
        normalize_drc_ctp_arrow_table(_arrow_table(fixture["positions"]))
    )

    row_result = calculate_drc_capital(fixture["positions"], context=context)
    calculation = calculate_drc_capital_from_batch(
        batch,
        context=replace(context, ctp_risk_weight_evidence=evidence),
    )

    validate_reconciliation(calculation.result)
    assert calculation.result.total_drc == pytest.approx(row_result.total_drc)
    assert calculation.result.risk_weight_evidence == row_result.risk_weight_evidence


def test_drc_fair_value_cap_evidence_arrow_replays_basel_securitisation_non_ctp() -> None:
    fixture = _load_fixture("drc_basel_sec_nonctp_v1")
    context = fixture["context"]
    evidence = build_drc_fair_value_cap_evidence_from_arrow(
        normalize_drc_fair_value_cap_evidence_arrow_table(
            _fair_value_cap_evidence_arrow_table(
                tuple(context.securitisation_non_ctp_fair_value_cap_evidence.values())
            )
        )
    )
    batch = build_drc_securitisation_non_ctp_batch_from_arrow(
        normalize_drc_securitisation_non_ctp_arrow_table(_arrow_table(fixture["positions"]))
    )

    row_result = calculate_drc_capital(fixture["positions"], context=context)
    calculation = calculate_drc_capital_from_batch(
        batch,
        context=replace(context, securitisation_non_ctp_fair_value_cap_evidence=evidence),
    )

    validate_reconciliation(calculation.result)
    assert calculation.result.total_drc == pytest.approx(row_result.total_drc)
    assert calculation.result.fair_value_cap_evidence == row_result.fair_value_cap_evidence


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"position_id": ["duplicate", "duplicate"]}, "duplicate"),
        ({"risk_class": ["CORRELATION_TRADING_PORTFOLIO"]}, "expected"),
        ({"effective_risk_weight": [-0.1]}, "non-negative"),
        ({"effective_risk_weight": [float("inf")]}, "finite"),
        ({"citation_ids": [""]}, "citation_ids"),
        ({"is_stale": [True]}, "stale"),
    ],
)
def test_drc_risk_weight_evidence_arrow_rejects_invalid_structural_rows(
    overrides: dict[str, list[object]],
    match: str,
) -> None:
    fixture = _load_fixture("drc_basel_sec_nonctp_v1")
    records = tuple(fixture["context"].securitisation_non_ctp_risk_weight_evidence.values())
    selected = records[:2] if "position_id" in overrides else records[:1]

    with pytest.raises(DrcInputError, match=match):
        build_drc_securitisation_non_ctp_risk_weight_evidence_from_arrow(
            normalize_drc_risk_weight_evidence_arrow_table(
                _risk_weight_evidence_arrow_table(selected, overrides=overrides)
            )
        )


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"source_profile_id": ["WRONG_PROFILE"]}, "source_profile_id|profile"),
        ({"as_of_date": [date(2099, 1, 1)]}, "future"),
    ],
)
def test_drc_risk_weight_evidence_arrow_fails_closed_in_context_validation(
    overrides: dict[str, list[object]],
    match: str,
) -> None:
    fixture = _load_fixture("drc_basel_sec_nonctp_v1")
    context = fixture["context"]
    records = tuple(context.securitisation_non_ctp_risk_weight_evidence.values())[:1]
    evidence = build_drc_securitisation_non_ctp_risk_weight_evidence_from_arrow(
        normalize_drc_risk_weight_evidence_arrow_table(
            _risk_weight_evidence_arrow_table(records, overrides=overrides)
        )
    )
    batch = build_drc_securitisation_non_ctp_batch_from_arrow(
        normalize_drc_securitisation_non_ctp_arrow_table(_arrow_table(fixture["positions"][:1]))
    )

    with pytest.raises(DrcInputError, match=match):
        calculate_drc_capital_from_batch(
            batch,
            context=replace(context, securitisation_non_ctp_risk_weight_evidence=evidence),
        )


def test_drc_fair_value_cap_evidence_arrow_rejects_duplicate_positions() -> None:
    fixture = _load_fixture("drc_basel_sec_nonctp_v1")
    records = tuple(fixture["context"].securitisation_non_ctp_fair_value_cap_evidence.values())

    with pytest.raises(DrcInputError, match="duplicate"):
        build_drc_fair_value_cap_evidence_from_arrow(
            normalize_drc_fair_value_cap_evidence_arrow_table(
                _fair_value_cap_evidence_arrow_table(records + records)
            )
        )


def _replace_first_risk_weight_source(
    records: tuple[DrcRiskWeightEvidence, ...],
) -> tuple[DrcRiskWeightEvidence, ...]:
    first = replace(records[0], source_id=f"{records[0].source_id}-replay")
    return (first, *records[1:])


def _risk_weight_evidence_arrow_table(
    records: tuple[DrcRiskWeightEvidence, ...],
    *,
    overrides: dict[str, list[object]] | None = None,
) -> pa.Table:
    columns: dict[str, list[object]] = {
        "position_id": [record.position_id for record in records],
        "risk_class": [_enum_value(record.risk_class) for record in records],
        "source_profile_id": [record.source_profile_id for record in records],
        "source_table": [record.source_table for record in records],
        "source_method": [record.source_method for record in records],
        "effective_risk_weight": [record.effective_risk_weight for record in records],
        "as_of_date": [record.as_of_date for record in records],
        "source_id": [record.source_id for record in records],
        "lineage_source_system": [record.lineage.source_system for record in records],
        "lineage_source_file": [record.lineage.source_file for record in records],
        "lineage_source_row_id": [record.lineage.source_row_id for record in records],
        "citation_ids": [",".join(record.citation_ids) for record in records],
        "is_stale": [record.is_stale for record in records],
        "validation_flags": [",".join(record.validation_flags) for record in records],
    }
    _apply_overrides(columns, overrides, len(records))
    return pa.table(columns)


def _fair_value_cap_evidence_arrow_table(
    records: tuple[DrcFairValueCapEvidence, ...],
) -> pa.Table:
    return pa.table(
        {
            "position_id": [record.position_id for record in records],
            "source_profile_id": [record.source_profile_id for record in records],
            "eligible": [record.eligible for record in records],
            "fair_value_cap_amount": pa.array(
                [record.fair_value_cap_amount for record in records], type=pa.float64()
            ),
            "eligibility_reason": [record.eligibility_reason for record in records],
            "as_of_date": [record.as_of_date for record in records],
            "source_id": [record.source_id for record in records],
            "lineage_source_system": [record.lineage.source_system for record in records],
            "lineage_source_file": [record.lineage.source_file for record in records],
            "lineage_source_row_id": [record.lineage.source_row_id for record in records],
            "citation_ids": [",".join(record.citation_ids) for record in records],
            "is_stale": [record.is_stale for record in records],
            "validation_flags": [",".join(record.validation_flags) for record in records],
        }
    )


def _apply_overrides(
    columns: dict[str, list[object]],
    overrides: dict[str, list[object]] | None,
    row_count: int,
) -> None:
    if overrides is None:
        return
    for column_name, values in overrides.items():
        if len(values) == row_count:
            columns[column_name] = values
        elif len(values) == 1:
            columns[column_name] = values * row_count
        else:
            raise AssertionError(f"override {column_name} must have 1 or {row_count} values")


def _load_fixture(fixture_name: str) -> dict[str, Any]:
    fixture_dir = Path(__file__).resolve().parent / "fixtures" / fixture_name
    payload = json.loads((fixture_dir / "positions.json").read_text(encoding="utf-8"))
    context_raw = payload["context"]
    positions = tuple(_position_from_dict(raw) for raw in payload["positions"])
    return {
        "positions": positions,
        "context": DrcCalculationContext(
            run_id=context_raw["run_id"],
            calculation_date=date.fromisoformat(context_raw["calculation_date"]),
            base_currency=context_raw["base_currency"],
            profile_id=context_raw["profile_id"],
            securitisation_non_ctp_risk_weights=context_raw.get(
                "securitisation_non_ctp_risk_weights",
                {},
            ),
            securitisation_non_ctp_offset_groups=context_raw.get(
                "securitisation_non_ctp_offset_groups",
                {},
            ),
            ctp_risk_weights=context_raw.get("ctp_risk_weights", {}),
            ctp_risk_weight_evidence=risk_weight_evidence_by_position(
                _risk_weight_evidence_from_dict(raw)
                for raw in context_raw.get("ctp_risk_weight_evidence", ())
            ),
            securitisation_non_ctp_risk_weight_evidence=risk_weight_evidence_by_position(
                _risk_weight_evidence_from_dict(raw)
                for raw in context_raw.get("securitisation_non_ctp_risk_weight_evidence", ())
            ),
            securitisation_non_ctp_fair_value_cap_evidence=fair_value_cap_evidence_by_position(
                _fair_value_cap_evidence_from_dict(raw)
                for raw in context_raw.get("securitisation_non_ctp_fair_value_cap_evidence", ())
            ),
            ctp_offset_groups=context_raw.get("ctp_offset_groups", {}),
        ),
    }


def _risk_weight_evidence_from_dict(raw: dict[str, Any]) -> DrcRiskWeightEvidence:
    lineage = raw["lineage"]
    return DrcRiskWeightEvidence(
        position_id=raw["position_id"],
        risk_class=raw["risk_class"],
        source_profile_id=raw["source_profile_id"],
        source_table=raw["source_table"],
        source_method=raw["source_method"],
        effective_risk_weight=float(raw["effective_risk_weight"]),
        as_of_date=date.fromisoformat(raw["as_of_date"]),
        source_id=raw["source_id"],
        lineage=DrcSourceLineage(
            source_system=lineage["source_system"],
            source_file=lineage["source_file"],
            source_row_id=lineage["source_row_id"],
            source_column_map=dict(lineage.get("source_column_map") or {}),
        ),
        citation_ids=tuple(raw["citation_ids"]),
        is_stale=bool(raw.get("is_stale", False)),
        validation_flags=tuple(raw.get("validation_flags", ())),
    )


def _fair_value_cap_evidence_from_dict(raw: dict[str, Any]) -> DrcFairValueCapEvidence:
    lineage = raw["lineage"]
    return DrcFairValueCapEvidence(
        position_id=raw["position_id"],
        source_profile_id=raw["source_profile_id"],
        eligible=bool(raw["eligible"]),
        fair_value_cap_amount=(
            None
            if raw.get("fair_value_cap_amount") is None
            else float(raw["fair_value_cap_amount"])
        ),
        eligibility_reason=raw["eligibility_reason"],
        as_of_date=date.fromisoformat(raw["as_of_date"]),
        source_id=raw["source_id"],
        lineage=DrcSourceLineage(
            source_system=lineage["source_system"],
            source_file=lineage["source_file"],
            source_row_id=lineage["source_row_id"],
            source_column_map=dict(lineage.get("source_column_map") or {}),
        ),
        citation_ids=tuple(raw["citation_ids"]),
        is_stale=bool(raw.get("is_stale", False)),
        validation_flags=tuple(raw.get("validation_flags", ())),
    )


def _position_from_dict(raw: dict[str, Any]) -> DrcPosition:
    lineage = raw["lineage"]
    return DrcPosition(
        position_id=raw["position_id"],
        source_row_id=raw["source_row_id"],
        desk_id=raw["desk_id"],
        legal_entity=raw["legal_entity"],
        risk_class=raw["risk_class"],
        instrument_type=raw["instrument_type"],
        default_direction=raw["default_direction"],
        issuer_id=raw.get("issuer_id"),
        tranche_id=raw.get("tranche_id"),
        index_series_id=raw.get("index_series_id"),
        bucket_key=raw["bucket_key"],
        seniority=raw.get("seniority"),
        credit_quality=raw.get("credit_quality"),
        notional=float(raw["notional"]),
        market_value=None if raw.get("market_value") is None else float(raw["market_value"]),
        cumulative_pnl=raw.get("cumulative_pnl"),
        maturity_years=float(raw["maturity_years"]),
        currency=raw["currency"],
        lineage=DrcSourceLineage(
            source_system=lineage["source_system"],
            source_file=lineage["source_file"],
            source_row_id=lineage["source_row_id"],
            source_column_map=dict(lineage.get("source_column_map") or {}),
        ),
        citation_ids=tuple(raw["citation_ids"]),
    )


def _arrow_table(positions: tuple[DrcPosition, ...]) -> pa.Table:
    return pa.table(
        {
            "position_id": [position.position_id for position in positions],
            "source_row_id": [position.source_row_id for position in positions],
            "desk_id": [position.desk_id for position in positions],
            "legal_entity": [position.legal_entity for position in positions],
            "risk_class": [_enum_value(position.risk_class) for position in positions],
            "instrument_type": [_enum_value(position.instrument_type) for position in positions],
            "default_direction": [_enum_value(position.default_direction) for position in positions],
            "issuer_id": [position.issuer_id for position in positions],
            "tranche_id": [position.tranche_id for position in positions],
            "index_series_id": [position.index_series_id for position in positions],
            "bucket_key": [position.bucket_key for position in positions],
            "seniority": [
                None if position.seniority is None else _enum_value(position.seniority)
                for position in positions
            ],
            "credit_quality": [
                None if position.credit_quality is None else _enum_value(position.credit_quality)
                for position in positions
            ],
            "notional": pa.array([position.notional for position in positions], type=pa.float64()),
            "market_value": pa.array(
                [position.market_value for position in positions], type=pa.float64()
            ),
            "cumulative_pnl": pa.array(
                [position.cumulative_pnl for position in positions], type=pa.float64()
            ),
            "maturity_years": pa.array(
                [position.maturity_years for position in positions], type=pa.float64()
            ),
            "currency": [position.currency for position in positions],
            "lgd_override": pa.array(
                [position.lgd_override for position in positions], type=pa.float64()
            ),
            "is_defaulted": [position.is_defaulted for position in positions],
            "is_gse": [position.is_gse for position in positions],
            "is_pse": [position.is_pse for position in positions],
            "is_covered_bond": [position.is_covered_bond for position in positions],
            "lineage_source_system": [position.lineage.source_system for position in positions],
            "lineage_source_file": [position.lineage.source_file for position in positions],
            "citation_ids": [",".join(position.citation_ids) for position in positions],
        }
    )


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)
