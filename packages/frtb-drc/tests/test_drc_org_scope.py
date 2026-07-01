from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import cast

import pytest
from frtb_common import CalculationScope, CalculationScopeLevel
from frtb_drc import (
    CreditQuality,
    DefaultDirection,
    DrcCalculationContext,
    DrcInputError,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    DrcSourceLineage,
    calculate_drc_capital,
    calculate_drc_capital_from_batch,
    validate_reconciliation,
)
from frtb_drc.adapters.positions import build_drc_nonsec_batch_from_positions
from frtb_drc.audit import input_snapshot_hash, serialize_result


def test_row_api_preserves_scope_metadata_without_changing_capital() -> None:
    scope = _scope("desk-a", book_id="book-rates")
    context_scope = _scope("desk-a")
    scoped_positions = (
        _position("long-a", DefaultDirection.LONG, 100.0, org_scope=scope),
        _position("long-b", DefaultDirection.LONG, 40.0, org_scope=scope),
    )
    unscoped_positions = tuple(replace(position, org_scope=None) for position in scoped_positions)

    scoped = calculate_drc_capital(
        scoped_positions,
        context=_context(calculation_scope=context_scope),
    )
    unscoped = calculate_drc_capital(unscoped_positions, context=_context())

    assert scoped.total_drc == pytest.approx(unscoped.total_drc)
    assert scoped.calculation_scope == context_scope
    assert scoped.input_positions[0].org_scope == scope
    assert scoped.gross_jtds[0].org_scope == scope
    assert scoped.maturity_scaled_jtds[0].org_scope == scope
    assert scoped.net_jtds[0].org_scope == scope
    assert scoped.net_jtds[0].contributing_org_scopes == (scope,)
    assert input_snapshot_hash(scoped_positions) != input_snapshot_hash(unscoped_positions)
    validate_reconciliation(scoped)


def test_batch_api_projects_mixed_scope_net_jtd_contributors() -> None:
    desk_scope = _scope("desk-a", book_id="book-rates")
    credit_scope = _scope("desk-b", book_id="book-credit")
    positions = (
        _position("long-a", DefaultDirection.LONG, 100.0, org_scope=desk_scope),
        _position("long-b", DefaultDirection.LONG, 40.0, org_scope=credit_scope),
    )
    unscoped_batch = build_drc_nonsec_batch_from_positions(
        tuple(replace(position, org_scope=None) for position in positions)
    )
    scoped_batch = build_drc_nonsec_batch_from_positions(positions)

    calculation = calculate_drc_capital_from_batch(
        scoped_batch,
        context=_context(calculation_scope=_scope("desk-a")),
    )
    unscoped_calculation = calculate_drc_capital_from_batch(unscoped_batch, context=_context())

    assert scoped_batch.org_scopes == (desk_scope, credit_scope)
    assert scoped_batch.input_hash != unscoped_batch.input_hash
    assert calculation.result.total_drc == pytest.approx(unscoped_calculation.result.total_drc)
    assert calculation.result.calculation_scope == _scope("desk-a")
    assert calculation.result.net_jtds[0].org_scope is None
    assert {scope.desk_id for scope in calculation.result.net_jtds[0].contributing_org_scopes} == {
        "desk-a",
        "desk-b",
    }
    validate_reconciliation(calculation.result)


def test_missing_scope_metadata_remains_explicit_on_result_records() -> None:
    result = calculate_drc_capital(
        (_position("unscoped", DefaultDirection.LONG, 100.0),),
        context=_context(),
    )
    serialized = serialize_result(result)

    assert result.calculation_scope is None
    assert result.input_positions[0].org_scope is None
    assert result.gross_jtds[0].org_scope is None
    assert result.maturity_scaled_jtds[0].org_scope is None
    assert result.net_jtds[0].org_scope is None
    assert result.net_jtds[0].contributing_org_scopes == ()
    assert serialized["calculation_scope"] is None


def test_invalid_scope_metadata_fails_validation() -> None:
    position = replace(
        _position("bad", DefaultDirection.LONG, 100.0),
        org_scope=cast(CalculationScope, "desk-a"),
    )

    with pytest.raises(DrcInputError, match="org_scope must be CalculationScope"):
        calculate_drc_capital((position,), context=_context())


def _scope(desk_id: str, *, book_id: str | None = None) -> CalculationScope:
    return CalculationScope(
        level=CalculationScopeLevel.DESK,
        legal_entity_id="bank-na",
        business_line_id="markets",
        desk_id=desk_id,
        book_id=book_id,
    )


def _context(
    *,
    calculation_scope: CalculationScope | None = None,
) -> DrcCalculationContext:
    return DrcCalculationContext(
        run_id="run-org-scope",
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile_id="US_NPR_2_0",
        calculation_scope=calculation_scope,
    )


def _position(
    position_id: str,
    direction: DefaultDirection,
    notional: float,
    *,
    org_scope: CalculationScope | None = None,
) -> DrcPosition:
    return DrcPosition(
        position_id=position_id,
        source_row_id=f"row-{position_id}",
        desk_id="desk-a",
        legal_entity="bank-na",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        instrument_type=DrcInstrumentType.BOND,
        default_direction=direction,
        issuer_id="issuer-a",
        tranche_id=None,
        index_series_id=None,
        bucket_key="CORPORATE",
        seniority=DrcSeniority.SENIOR_DEBT,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        notional=notional,
        market_value=notional,
        cumulative_pnl=0.0,
        maturity_years=1.0,
        currency="USD",
        lineage=DrcSourceLineage(
            source_system="synthetic",
            source_file="org-scope.csv",
            source_row_id=f"row-{position_id}",
            source_column_map={"position_id": "position_id", "issuer_id": "issuer_id"},
        ),
        citation_ids=("US_NPR_210_SCOPE",),
        org_scope=org_scope,
    )
