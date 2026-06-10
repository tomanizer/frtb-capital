from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

import pyarrow as pa
import pytest
from frtb_drc import (
    DrcFairValueCapEvidence,
    DrcInputError,
    DrcRiskWeightEvidence,
    calculate_drc_capital,
    calculate_drc_capital_from_batch,
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
from test_drc_arrow_batch import _arrow_table, _load_fixture


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
    assert _risk_weight_summary(calculation.result.risk_weight_evidence) == _risk_weight_summary(
        row_result.risk_weight_evidence
    )

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
    assert _risk_weight_summary(calculation.result.risk_weight_evidence) == _risk_weight_summary(
        row_result.risk_weight_evidence
    )


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
    actual = _fair_value_cap_summary(calculation.result.fair_value_cap_evidence)
    expected = _fair_value_cap_summary(row_result.fair_value_cap_evidence)
    assert actual == expected


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
    records = tuple(context.securitisation_non_ctp_risk_weight_evidence.values())
    evidence = build_drc_securitisation_non_ctp_risk_weight_evidence_from_arrow(
        normalize_drc_risk_weight_evidence_arrow_table(
            _risk_weight_evidence_arrow_table(records, overrides=overrides)
        )
    )
    batch = build_drc_securitisation_non_ctp_batch_from_arrow(
        normalize_drc_securitisation_non_ctp_arrow_table(_arrow_table(fixture["positions"]))
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


def _risk_weight_summary(
    records: tuple[DrcRiskWeightEvidence, ...],
) -> dict[str, tuple[object, ...]]:
    return {
        record.position_id: (
            _enum_value(record.risk_class),
            record.source_profile_id,
            record.source_table,
            record.source_method,
            record.effective_risk_weight,
            record.as_of_date,
            record.source_id,
            record.lineage.source_system,
            record.lineage.source_file,
            record.lineage.source_row_id,
            record.citation_ids,
            record.validation_flags,
        )
        for record in records
    }


def _fair_value_cap_summary(
    records: tuple[DrcFairValueCapEvidence, ...],
) -> dict[str, tuple[object, ...]]:
    return {
        record.position_id: (
            record.source_profile_id,
            record.eligible,
            record.fair_value_cap_amount,
            record.eligibility_reason,
            record.as_of_date,
            record.source_id,
            record.lineage.source_system,
            record.lineage.source_file,
            record.lineage.source_row_id,
            record.citation_ids,
            record.validation_flags,
        )
        for record in records
    }


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


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)
