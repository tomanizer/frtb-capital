"""IMA contribution bundle compatibility tests for orchestration."""

from __future__ import annotations

from datetime import date

import pytest
from frtb_common import (
    CapitalContribution,
    ComponentCapitalSummary,
    StandardisedComponent,
)
from frtb_common.attribution import AttributionMethod, ReconciliationStatus
from frtb_common.contribution_bundle import ComponentContributionBundle
from frtb_ima import DeskAuditRecord, build_ima_contribution_bundle
from frtb_orchestration import (
    CvaCapitalSummary,
    ImaCapitalSummary,
    StandardisedApproachCapitalResult,
    SuiteAttributionResult,
    calculate_suite_capital,
    compose_standardised_approach_capital,
)

_CALCULATION_DATE = date(2026, 3, 31)
_INPUT_HASH = "1" * 64
_POLICY_HASH = "2" * 64
_ZERO_INPUT_HASH = "3" * 64
_ZERO_PROFILE_HASH = "4" * 64
_CVA_INPUT_HASH = "5" * 64
_CVA_PROFILE_HASH = "6" * 64


def test_orchestration_consumes_public_ima_contribution_bundle() -> None:
    """IMA bundles should work through public package imports only."""

    ima_summary = ImaCapitalSummary(
        package_name="frtb-ima",
        run_id="ima-run",
        calculation_date=_CALCULATION_DATE,
        base_currency="USD",
        profile_id="FED_NPR_2_0",
        total_ima_capital=125.0,
        ima_eligible_desk_count=1,
        sa_fallback_desk_count=0,
        policy_hash=_POLICY_HASH,
        input_hash=_INPUT_HASH,
        citations=("adr_0038",),
    )
    ima_record = DeskAuditRecord(
        run_id="ima-run",
        desk_id="desk-1",
        regime="FED_NPR_2_0",
        inputs_hash=_INPUT_HASH,
        imcc={"imcc": 100.0},
        ses={"total_ses": 25.0},
        pla={"zone": "GREEN"},
        backtesting={"model_eligible": True},
        capital={"total": 125.0, "binding_term": "SPOT"},
        elapsed_seconds=0.0,
        policy_hash=_POLICY_HASH,
    )
    ima_bundle = build_ima_contribution_bundle(
        ima_record,
        total_ima_capital=ima_summary.total_ima_capital,
    )

    result = calculate_suite_capital(
        ima_summary=ima_summary,
        sa_result=_zero_sa_result(),
        cva_summary=_zero_cva_summary(),
        component_contribution_bundles=(
            ima_bundle,
            _zero_component_bundle("frtb_sa"),
            _zero_component_bundle("frtb_cva"),
        ),
    )

    assert isinstance(result.attribution_result, SuiteAttributionResult)
    assert result.attribution_result.component_bundles[0] is ima_bundle
    assert result.attribution_result.suite_residual.residual == pytest.approx(0.0)
    assert (
        result.attribution_result.suite_residual.reconciliation_status
        is ReconciliationStatus.RECONCILED
    )
    assert [item.category for item in ima_bundle.contributions] == ["IMCC", "SES"]
    assert all(
        item.method is AttributionMethod.ANALYTICAL_EULER for item in ima_bundle.contributions
    )


def _zero_component_bundle(component: str) -> ComponentContributionBundle:
    record = CapitalContribution(
        contribution_id=f"{component}:zero",
        source_id=component,
        source_level="component",
        bucket_key=None,
        category=component.upper(),
        base_amount=0.0,
        marginal_multiplier=1.0,
        contribution=0.0,
        method=AttributionMethod.ANALYTICAL_EULER,
        citations=("adr_0038",),
        input_hash=_ZERO_INPUT_HASH,
        profile_hash=_ZERO_PROFILE_HASH,
        reconciliation_status=ReconciliationStatus.RECONCILED,
    )
    return ComponentContributionBundle(
        component=component,
        contributions=(record,),
        component_total=0.0,
        component_input_hash=record.input_hash,
        component_profile_hash=record.profile_hash,
    )


def _zero_sa_result() -> StandardisedApproachCapitalResult:
    return compose_standardised_approach_capital(
        sbm_summary=_component_summary(StandardisedComponent.SBM, "frtb-sbm"),
        drc_summary=_component_summary(StandardisedComponent.DRC, "frtb-drc"),
        rrao_summary=_component_summary(StandardisedComponent.RRAO, "frtb-rrao"),
        run_id="sa-run",
    )


def _component_summary(
    component: StandardisedComponent,
    package_name: str,
) -> ComponentCapitalSummary:
    return ComponentCapitalSummary(
        component=component,
        package_name=package_name,
        run_id=f"{component.value}-run",
        calculation_date=_CALCULATION_DATE,
        base_currency="USD",
        profile_id="US_NPR_2_0",
        total_capital=0.0,
        profile_hash=_ZERO_PROFILE_HASH,
        input_hash=_ZERO_INPUT_HASH,
        line_count=0,
        excluded_line_count=0,
        subtotal_count=0,
        citations=("adr_0038",),
    )


def _zero_cva_summary() -> CvaCapitalSummary:
    return CvaCapitalSummary(
        package_name="frtb-cva",
        run_id="cva-run",
        calculation_date=_CALCULATION_DATE,
        base_currency="USD",
        profile_id="US_NPR20_VB",
        method="BA_CVA_REDUCED",
        total_cva_capital=0.0,
        ba_cva_reduced_total=0.0,
        ba_cva_full_total=None,
        sa_cva_total=None,
        profile_hash=_CVA_PROFILE_HASH,
        input_hash=_CVA_INPUT_HASH,
        risk_class_count=0,
        counterparty_count=0,
        citations=("adr_0038",),
    )
