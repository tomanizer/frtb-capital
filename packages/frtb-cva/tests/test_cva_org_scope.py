from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from frtb_common import CalculationScope, CalculationScopeLevel
from frtb_cva import (
    CreditQuality,
    CvaCalculationContext,
    CvaCounterparty,
    CvaInputError,
    CvaMethod,
    CvaNettingSet,
    CvaRegulatoryProfile,
    CvaSector,
    CvaSourceLineage,
    build_cva_counterparty_batch_from_columns,
    build_cva_counterparty_batch_from_counterparties,
    build_cva_netting_set_batch_from_columns,
    calculate_cva_capital,
    calculate_cva_capital_from_batches,
    serialize_cva_result,
)


def _scope(*, desk_id: str = "DESK-CVA", book_id: str = "BOOK-CVA") -> CalculationScope:
    return CalculationScope(
        level=CalculationScopeLevel.BOOK,
        legal_entity_id="LE-001",
        desk_id=desk_id,
        book_id=book_id,
        metadata={"source_system": "synthetic-org-master"},
    )


def _lineage(row_id: str) -> CvaSourceLineage:
    return CvaSourceLineage(
        source_system="synthetic-cva",
        source_file="cva.csv",
        source_row_id=row_id,
        source_column_map=(("CounterpartyID", "counterparty_id"),),
    )


def _counterparty(*, org_scope: CalculationScope | None = None) -> CvaCounterparty:
    return CvaCounterparty(
        counterparty_id="ctp-scope-001",
        desk_id="desk-cva",
        legal_entity="LE-001",
        sector=CvaSector.SOVEREIGN,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        region="EMEA",
        source_row_id="row-ctp-scope-001",
        lineage=_lineage("row-ctp-scope-001"),
        org_scope=org_scope,
    )


def _netting_set(*, org_scope: CalculationScope | None = None) -> CvaNettingSet:
    return CvaNettingSet(
        netting_set_id="ns-scope-001",
        counterparty_id="ctp-scope-001",
        ead=1_000_000.0,
        effective_maturity=2.5,
        discount_factor=0.9400247793232364,
        currency="USD",
        sign_convention="non_negative",
        uses_imm_ead=False,
        source_row_id="row-ns-scope-001",
        lineage=_lineage("row-ns-scope-001"),
        org_scope=org_scope,
    )


def _context(*, calculation_scope: CalculationScope | None = None) -> CvaCalculationContext:
    return CvaCalculationContext(
        run_id="cva-scope-run-001",
        calculation_date=date(2026, 3, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.BA_CVA_REDUCED,
        calculation_scope=calculation_scope,
    )


def test_cva_preserves_scope_metadata_without_changing_capital() -> None:
    unscoped = calculate_cva_capital(
        _context(),
        (_counterparty(),),
        (_netting_set(),),
    )
    scoped_counterparty = _counterparty(org_scope=_scope(book_id="BOOK-CTP"))
    scoped_netting_set = _netting_set(org_scope=_scope(book_id="BOOK-NS"))
    scoped_context = _context(calculation_scope=_scope(desk_id="DESK-TOH", book_id="BOOK-TOH"))

    scoped = calculate_cva_capital(
        scoped_context,
        (scoped_counterparty,),
        (scoped_netting_set,),
    )
    payload = serialize_cva_result(scoped)

    assert scoped.total_cva_capital == pytest.approx(unscoped.total_cva_capital)
    assert scoped.ba_cva_counterparty_capitals[0].org_scope == scoped_counterparty.org_scope
    assert scoped.ba_cva_netting_set_lines[0].org_scope == scoped_netting_set.org_scope
    assert scoped.calculation_scope == scoped_context.calculation_scope
    assert payload["calculation_scope"]["desk_id"] == "DESK-TOH"
    assert payload["ba_cva_counterparty_capitals"][0]["org_scope"]["book_id"] == "BOOK-CTP"
    assert payload["ba_cva_netting_set_lines"][0]["org_scope"]["book_id"] == "BOOK-NS"
    assert scoped.input_hash != unscoped.input_hash


def test_missing_scope_metadata_stays_absent_from_audit_payload() -> None:
    result = calculate_cva_capital(
        _context(),
        (_counterparty(),),
        (_netting_set(),),
    )
    payload = serialize_cva_result(result)

    assert result.calculation_scope is None
    assert result.ba_cva_counterparty_capitals[0].org_scope is None
    assert result.ba_cva_netting_set_lines[0].org_scope is None
    assert "calculation_scope" not in payload
    assert "org_scope" not in payload["ba_cva_counterparty_capitals"][0]
    assert "org_scope" not in payload["ba_cva_netting_set_lines"][0]


def test_batch_columns_preserve_scope_metadata() -> None:
    counterparty_scope = _scope(book_id="BOOK-CTP")
    netting_set_scope = _scope(book_id="BOOK-NS")
    counterparty_batch = build_cva_counterparty_batch_from_columns(
        counterparty_ids=["ctp-scope-001"],
        desk_ids=["desk-cva"],
        legal_entities=["LE-001"],
        sectors=[CvaSector.SOVEREIGN.value],
        credit_qualities=[CreditQuality.INVESTMENT_GRADE.value],
        regions=["EMEA"],
        source_row_ids=["row-ctp-scope-001"],
        lineage_source_systems=["synthetic-cva"],
        lineage_source_files=["cva.csv"],
        org_scopes=[counterparty_scope],
    )
    netting_set_batch = build_cva_netting_set_batch_from_columns(
        netting_set_ids=["ns-scope-001"],
        counterparty_ids=["ctp-scope-001"],
        eads=[1_000_000.0],
        effective_maturities=[2.5],
        discount_factors=[0.9400247793232364],
        currencies=["USD"],
        sign_conventions=["non_negative"],
        uses_imm_eads=[False],
        source_row_ids=["row-ns-scope-001"],
        org_scopes=[netting_set_scope],
    )

    result = calculate_cva_capital_from_batches(
        _context(),
        counterparty_batch,
        netting_set_batch,
    ).result

    assert counterparty_batch.org_scopes == (counterparty_scope,)
    assert netting_set_batch.org_scopes == (netting_set_scope,)
    assert result.ba_cva_counterparty_capitals[0].org_scope == counterparty_scope
    assert result.ba_cva_netting_set_lines[0].org_scope == netting_set_scope


def test_invalid_scope_metadata_fails_validation() -> None:
    with pytest.raises(CvaInputError, match="org_scope must be CalculationScope"):
        build_cva_counterparty_batch_from_counterparties(
            (replace(_counterparty(), org_scope="desk-cva"),),
        )

    with pytest.raises(CvaInputError, match="org_scopes\\[0\\] must be CalculationScope"):
        build_cva_netting_set_batch_from_columns(
            netting_set_ids=["ns-scope-001"],
            counterparty_ids=["ctp-scope-001"],
            eads=[1_000_000.0],
            effective_maturities=[2.5],
            discount_factors=[0.9400247793232364],
            currencies=["USD"],
            sign_conventions=["non_negative"],
            uses_imm_eads=[False],
            source_row_ids=["row-ns-scope-001"],
            org_scopes=["bad"],  # type: ignore[list-item]
        )

    with pytest.raises(CvaInputError, match="calculation_scope must be CalculationScope"):
        calculate_cva_capital(
            replace(_context(), calculation_scope="bad"),
            (_counterparty(),),
            (_netting_set(),),
        )
