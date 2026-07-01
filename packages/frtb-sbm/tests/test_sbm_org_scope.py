from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from frtb_common import CalculationScope, CalculationScopeLevel
from frtb_sbm import (
    SbmCalculationContext,
    SbmInputError,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    calculate_sbm_capital,
    calculate_sbm_capital_from_batch,
    input_hash_for_sensitivities,
    serialize_sbm_result,
    validate_sbm_sensitivities,
)
from frtb_sbm.batch import build_sbm_batch_from_sensitivities
from frtb_sbm.factor_grid import net_girr_delta_weighted_sensitivities
from frtb_sbm.weighted_sensitivity import weight_girr_delta_sensitivities


def _scope(*, desk_id: str, book_id: str) -> CalculationScope:
    return CalculationScope(
        level=CalculationScopeLevel.BOOK,
        legal_entity_id="LE-001",
        business_division_id="markets",
        business_line_id="rates",
        desk_id=desk_id,
        volcker_desk_id=f"volcker-{desk_id}",
        book_id=book_id,
        metadata={"fixture": "sbm-org-scope"},
    )


def _context(*, calculation_scope: CalculationScope | None = None) -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id="sbm-org-scope-run",
        calculation_date=date(2026, 6, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        calculation_scope=calculation_scope,
    )


def _sensitivity(
    sensitivity_id: str,
    *,
    source_row_id: str,
    amount: float = 1_000_000.0,
    risk_factor: str = "USD-OIS",
    tenor: str = "5y",
    org_scope: CalculationScope | None = None,
) -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id=sensitivity_id,
        source_row_id=source_row_id,
        desk_id="rates-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket="2",
        risk_factor=risk_factor,
        amount=amount,
        amount_currency="USD",
        tenor=tenor,
        sign_convention=SbmSignConvention.RECEIVE,
        lineage=SbmSourceLineage(
            source_system="synthetic-risk",
            source_file="sbm-org-scope.csv",
            source_row_id=source_row_id,
        ),
        org_scope=org_scope,
    )


def test_sbm_preserves_scope_metadata_without_changing_capital() -> None:
    run_scope = _scope(desk_id="rates-desk", book_id="book-run")
    row_scope = _scope(desk_id="rates-desk", book_id="book-001")
    scoped = (_sensitivity("sens-001", source_row_id="row-001", org_scope=row_scope),)
    unscoped = (replace(scoped[0], org_scope=None),)

    scoped_result = calculate_sbm_capital(scoped, context=_context(calculation_scope=run_scope))
    unscoped_result = calculate_sbm_capital(unscoped, context=_context())

    assert scoped_result.total_capital == pytest.approx(unscoped_result.total_capital)
    payload = serialize_sbm_result(scoped_result)
    assert payload["run_context"]["calculation_scope"]["book_id"] == "book-run"
    weighted = payload["risk_classes"][0]["buckets"][0]["weighted_sensitivities"][0]
    assert weighted["org_scope"]["book_id"] == "book-001"
    assert weighted["org_scope"]["desk_id"] == "rates-desk"
    assert input_hash_for_sensitivities(scoped) != input_hash_for_sensitivities(unscoped)


def test_missing_scope_metadata_stays_absent_from_audit_payload() -> None:
    result = calculate_sbm_capital(
        (_sensitivity("sens-001", source_row_id="row-001"),),
        context=_context(),
    )

    payload = serialize_sbm_result(result)
    assert "calculation_scope" not in payload["run_context"]
    weighted = payload["risk_classes"][0]["buckets"][0]["weighted_sensitivities"][0]
    assert "org_scope" not in weighted
    assert "contributing_org_scopes" not in weighted


def test_batch_builder_preserves_row_scope_metadata() -> None:
    row_scope = _scope(desk_id="rates-desk", book_id="book-batch")
    sensitivities = (_sensitivity("sens-001", source_row_id="row-001", org_scope=row_scope),)

    batch = build_sbm_batch_from_sensitivities(sensitivities)
    result = calculate_sbm_capital_from_batch(batch, context=_context())
    payload = serialize_sbm_result(result)

    assert batch.org_scopes == (row_scope,)
    assert batch.input_hash == input_hash_for_sensitivities(sensitivities)
    weighted = payload["risk_classes"][0]["buckets"][0]["weighted_sensitivities"][0]
    assert weighted["org_scope"]["book_id"] == "book-batch"


def test_girr_factor_grid_retains_contributing_scopes_for_netted_rows() -> None:
    scope_a = _scope(desk_id="rates-desk", book_id="book-a")
    scope_b = _scope(desk_id="rates-desk", book_id="book-b")
    sensitivities = (
        _sensitivity("sens-001", source_row_id="row-001", amount=100.0, org_scope=scope_b),
        _sensitivity("sens-002", source_row_id="row-002", amount=200.0, org_scope=scope_a),
    )
    weighted = weight_girr_delta_sensitivities(
        sensitivities,
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        reporting_currency="USD",
    )

    grid = net_girr_delta_weighted_sensitivities(sensitivities, weighted)
    netted = grid.weighted_sensitivities[0]

    assert netted.org_scope is None
    assert [scope.book_id for scope in netted.contributing_org_scopes] == ["book-a", "book-b"]
    payload = serialize_sbm_result(calculate_sbm_capital(sensitivities, context=_context()))
    weighted_payload = payload["risk_classes"][0]["buckets"][0]["weighted_sensitivities"][0]
    assert [scope["book_id"] for scope in weighted_payload["contributing_org_scopes"]] == [
        "book-a",
        "book-b",
    ]


def test_scope_metadata_validation_is_explicit() -> None:
    sensitivity = replace(
        _sensitivity("sens-001", source_row_id="row-001"),
        org_scope={"book_id": "book-001"},  # type: ignore[arg-type]
    )

    with pytest.raises(SbmInputError, match="org_scope must be CalculationScope"):
        validate_sbm_sensitivities((sensitivity,))
