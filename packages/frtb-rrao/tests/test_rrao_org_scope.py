from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from frtb_common import CalculationScope, CalculationScopeLevel

from frtb_rrao import (
    RraoCalculationContext,
    RraoClassification,
    RraoEvidenceType,
    RraoInputError,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    build_rrao_batch_from_columns,
    build_rrao_batch_from_positions,
    calculate_rrao_capital,
    calculate_rrao_capital_from_batch,
    serialize_rrao_result,
)


def _scope(*, desk_id: str = "DESK-ALPHA", book_id: str = "BOOK-ALPHA") -> CalculationScope:
    return CalculationScope(
        level=CalculationScopeLevel.BOOK,
        legal_entity_id="LE-001",
        desk_id=desk_id,
        book_id=book_id,
        metadata={"source_system": "synthetic-org-master"},
    )


def _lineage(row_id: str) -> RraoSourceLineage:
    return RraoSourceLineage(
        source_system="synthetic-risk",
        source_file="rrao.csv",
        source_row_id=row_id,
        source_column_map=(("RiskType", "evidence_type"),),
    )


def _position(*, org_scope: CalculationScope | None = None) -> RraoPosition:
    return RraoPosition(
        position_id="rrao-pos-001",
        source_row_id="rrao-row-001",
        desk_id="desk-alpha",
        legal_entity="LE-001",
        gross_effective_notional=1_000_000.0,
        currency="USD",
        evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
        evidence_label="synthetic exotic underlying",
        classification_hint=RraoClassification.EXOTIC,
        lineage=_lineage("rrao-row-001"),
        org_scope=org_scope,
    )


def _context(*, calculation_scope: CalculationScope | None = None) -> RraoCalculationContext:
    return RraoCalculationContext(
        run_id="rrao-run-001",
        calculation_date=date(2026, 3, 31),
        base_currency="USD",
        profile=RraoRegulatoryProfile.US_NPR_2_0,
        calculation_scope=calculation_scope,
    )


def test_rrao_preserves_scope_metadata_without_changing_capital() -> None:
    unscoped = calculate_rrao_capital((_position(),), context=_context())
    scoped_position = replace(_position(), org_scope=_scope())
    scoped_context = _context(calculation_scope=_scope(desk_id="DESK-TOH", book_id="BOOK-TOH"))

    scoped = calculate_rrao_capital((scoped_position,), context=scoped_context)
    payload = serialize_rrao_result(scoped)

    assert scoped.total_rrao == unscoped.total_rrao == 10_000.0
    assert scoped.lines[0].org_scope == scoped_position.org_scope
    assert scoped.calculation_scope == scoped_context.calculation_scope
    assert payload["calculation_scope"]["desk_id"] == "DESK-TOH"
    assert payload["lines"][0]["org_scope"]["book_id"] == "BOOK-ALPHA"
    assert scoped.input_hash != unscoped.input_hash


def test_missing_scope_metadata_stays_absent_from_audit_payload() -> None:
    result = calculate_rrao_capital((_position(),), context=_context())
    payload = serialize_rrao_result(result)

    assert result.calculation_scope is None
    assert result.lines[0].org_scope is None
    assert "calculation_scope" not in payload
    assert "org_scope" not in payload["lines"][0]


def test_batch_columns_preserve_row_scope_metadata() -> None:
    scope = _scope(book_id="BOOK-BETA")
    batch = build_rrao_batch_from_columns(
        position_ids=["rrao-pos-001"],
        source_row_ids=["rrao-row-001"],
        desk_ids=["desk-alpha"],
        legal_entities=["LE-001"],
        gross_effective_notionals=[1_000_000.0],
        currencies=["USD"],
        evidence_types=[RraoEvidenceType.EXOTIC_UNDERLYING.value],
        evidence_labels=["synthetic exotic underlying"],
        classification_hints=[RraoClassification.EXOTIC.value],
        lineage_source_systems=["synthetic-risk"],
        lineage_source_files=["rrao.csv"],
        lineage_source_row_ids=["rrao-row-001"],
        lineage_present=[True],
        org_scopes=[scope],
    )

    result = calculate_rrao_capital_from_batch(batch, context=_context()).result

    assert batch.org_scopes == (scope,)
    assert result.lines[0].org_scope == scope
    assert serialize_rrao_result(result)["lines"][0]["org_scope"]["book_id"] == "BOOK-BETA"


def test_invalid_scope_metadata_fails_validation() -> None:
    with pytest.raises(RraoInputError, match="org_scopes\\[0\\] must be CalculationScope"):
        build_rrao_batch_from_positions((replace(_position(), org_scope="desk-alpha"),))

    with pytest.raises(RraoInputError, match="calculation_scope must be CalculationScope"):
        calculate_rrao_capital((_position(),), context=replace(_context(), calculation_scope="bad"))
