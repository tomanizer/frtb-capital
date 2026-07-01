from __future__ import annotations

import pytest
from frtb_orchestration import (
    BindingCapitalSide,
    OrchestrationInputError,
    ScopeComponentCapital,
    ScopeViewStatus,
    compose_scope_capital_view,
)


def test_scope_view_composes_top_of_house_binding_floor() -> None:
    view = compose_scope_capital_view(
        run_id="run-001",
        node_id="GLOBAL_GROUP",
        node_label="Global Group",
        component_capitals=_scope_components(sbm=100.0, drc=40.0, rrao=10.0, ima=80.0, cva=7.0),
    )

    assert view.status == ScopeViewStatus.OK
    assert view.sa_capital == 150.0
    assert view.ima_capital == 80.0
    assert view.cva_capital == 7.0
    assert view.binding_capital.floor_value == pytest.approx(108.75)
    assert view.binding_capital.binding_side == BindingCapitalSide.SA_FLOOR
    assert view.binding_capital.binding_value == pytest.approx(108.75)
    assert view.total_capital == pytest.approx(115.75)
    assert [component.component for component in view.components] == [
        "SBM",
        "DRC",
        "RRAO",
        "IMA",
        "CVA",
    ]


def test_scope_view_composes_legal_entity_ima_binding() -> None:
    view = compose_scope_capital_view(
        run_id="run-001",
        node_id="US_BANK_NA",
        node_label="US Bank NA",
        component_capitals=_scope_components(sbm=30.0, drc=12.0, rrao=3.0, ima=90.0, cva=2.0),
    )

    assert view.sa_capital == 45.0
    assert view.binding_capital.floor_value == pytest.approx(32.625)
    assert view.binding_capital.binding_side == BindingCapitalSide.IMA
    assert view.total_capital == pytest.approx(92.0)


def test_scope_view_supports_desk_and_book_scopes() -> None:
    desk = compose_scope_capital_view(
        run_id="run-001",
        node_id="USD_RATES_VOLCKER",
        node_label="USD Rates Volcker",
        component_capitals=_scope_components(sbm=35.0, drc=0.0, rrao=0.0, ima=42.0),
    )
    book = compose_scope_capital_view(
        run_id="run-001",
        node_id="USD_SWAP_BOOK_01",
        node_label="USD Swap Book 01",
        component_capitals=_scope_components(sbm=35.0, drc=0.0, rrao=0.0, ima=0.0),
    )

    assert desk.binding_capital.binding_side == BindingCapitalSide.IMA
    assert desk.total_capital == 42.0
    assert book.binding_capital.binding_side == BindingCapitalSide.SA_FLOOR
    assert book.total_capital == pytest.approx(25.375)


def test_scope_view_reports_no_data_when_required_binding_inputs_are_missing() -> None:
    view = compose_scope_capital_view(
        run_id="run-001",
        node_id="UK_LIQUIDITY_DESK",
        node_label="UK Liquidity Desk",
        component_capitals=(
            ScopeComponentCapital("SBM", None, status=ScopeViewStatus.NO_DATA),
            ScopeComponentCapital("DRC", None, status=ScopeViewStatus.NO_DATA),
            ScopeComponentCapital("RRAO", None, status=ScopeViewStatus.NO_DATA),
            ScopeComponentCapital("IMA", None, status=ScopeViewStatus.NO_DATA),
            ScopeComponentCapital("CVA", 11.0),
        ),
    )

    assert view.status == ScopeViewStatus.NO_DATA
    assert view.sa_capital is None
    assert view.ima_capital is None
    assert view.cva_capital == 11.0
    assert view.binding_capital.status == ScopeViewStatus.NO_DATA
    assert view.binding_capital.binding_side == BindingCapitalSide.NO_DATA
    assert view.total_capital is None


def test_scope_view_preserves_unsupported_component_state() -> None:
    view = compose_scope_capital_view(
        run_id="run-001",
        node_id="G10_FX_SPOT",
        node_label="G10 FX Spot",
        component_capitals=(
            ScopeComponentCapital("SBM", 8.0),
            ScopeComponentCapital("DRC", 18.0),
            ScopeComponentCapital("RRAO", 0.0),
            ScopeComponentCapital("IMA", None, status=ScopeViewStatus.UNSUPPORTED),
            ScopeComponentCapital("CVA", None, status=ScopeViewStatus.NO_DATA),
        ),
    )

    assert view.status == ScopeViewStatus.NO_DATA
    assert view.sa_capital == 26.0
    assert view.ima_capital is None
    assert view.binding_capital.status == ScopeViewStatus.NO_DATA
    assert [component.status for component in view.components if component.component == "IMA"] == [
        ScopeViewStatus.UNSUPPORTED
    ]


def test_scope_view_rejects_duplicate_components() -> None:
    with pytest.raises(OrchestrationInputError, match="duplicate scope component"):
        compose_scope_capital_view(
            run_id="run-001",
            node_id="GLOBAL_GROUP",
            node_label="Global Group",
            component_capitals=(
                ScopeComponentCapital("SBM", 1.0),
                ScopeComponentCapital("SBM", 2.0),
            ),
        )


def test_scope_component_rejects_placeholder_success_without_capital() -> None:
    with pytest.raises(OrchestrationInputError, match="OK component capital"):
        ScopeComponentCapital("IMA", None)


def _scope_components(
    *,
    sbm: float,
    drc: float,
    rrao: float,
    ima: float,
    cva: float | None = None,
) -> tuple[ScopeComponentCapital, ...]:
    cva_component = (
        ScopeComponentCapital("CVA", cva)
        if cva is not None
        else ScopeComponentCapital("CVA", None, status=ScopeViewStatus.NO_DATA)
    )
    return (
        ScopeComponentCapital("SBM", sbm),
        ScopeComponentCapital("DRC", drc),
        ScopeComponentCapital("RRAO", rrao),
        ScopeComponentCapital("IMA", ima),
        cva_component,
    )
