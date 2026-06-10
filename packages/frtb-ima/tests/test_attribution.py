"""Tests for IMA DeskAuditRecord attribution projection."""

from __future__ import annotations

import pytest
from frtb_common.attribution import AttributionMethod, CapitalContribution, ReconciliationStatus

from frtb_ima.attribution import desk_contributions
from frtb_ima.audit import DeskAuditRecord

TEST_INPUTS_HASH = "1" * 64


def test_desk_contributions_reconcile_standard_path() -> None:
    record = _desk_record(
        imcc={"imcc": 100.0},
        ses={"total_ses": 25.0},
        capital={"total": 125.0, "binding_term": "SPOT"},
    )

    contributions = desk_contributions(record)

    assert _total(contributions) == pytest.approx(record.capital["total"])
    assert {item.category for item in contributions} == {"IMCC", "SES"}
    assert all(isinstance(item, CapitalContribution) for item in contributions)
    assert all(item.input_hash == record.inputs_hash for item in contributions)
    assert all(item.profile_hash == record.policy_hash for item in contributions)
    assert all(
        item.reconciliation_status is ReconciliationStatus.RECONCILED for item in contributions
    )
    assert all(item.method is AttributionMethod.ANALYTICAL_EULER for item in contributions)


def test_desk_contributions_use_capital_breakdown_when_present() -> None:
    record = _desk_record(
        imcc={"imcc": 999.0},
        ses={"total_ses": 999.0},
        capital={
            "total": 140.0,
            "imcc_t_minus_1": 100.0,
            "ses_t_minus_1": 25.0,
            "pla_addon": 15.0,
            "binding_term": "SPOT",
        },
    )

    contributions = desk_contributions(record)

    assert [(item.category, item.contribution) for item in contributions] == [
        ("IMCC", 100.0),
        ("SES", 25.0),
        ("PLA_ADDON", 15.0),
    ]
    assert _total(contributions) == pytest.approx(140.0)
    assert all(
        item.reconciliation_status is ReconciliationStatus.RECONCILED for item in contributions
    )


def test_desk_contributions_use_reconciling_detail_breakdowns() -> None:
    record = _desk_record(
        imcc={
            "components": {
                "current_es": 70.0,
                "stress_scaling": {"capital": 30.0},
            }
        },
        ses={"risk_class_components": {"rates": 10.0, "credit_spread": 15.0}},
        pla={"components": {"amber_shortfall": 5.0, "capital_benefit_reversal": 10.0}},
        capital={
            "total": 140.0,
            "imcc_t_minus_1": 100.0,
            "ses_t_minus_1": 25.0,
            "pla_addon": 15.0,
            "binding_term": "SPOT",
        },
    )

    contributions = desk_contributions(record)

    assert [(item.category, item.contribution) for item in contributions] == [
        ("IMCC_CURRENT_ES", 70.0),
        ("IMCC_STRESS_SCALING", 30.0),
        ("SES_RATES", 10.0),
        ("SES_CREDIT_SPREAD", 15.0),
        ("PLA_ADDON_AMBER_SHORTFALL", 5.0),
        ("PLA_ADDON_CAPITAL_BENEFIT_REVERSAL", 10.0),
    ]
    assert _total(contributions) == pytest.approx(140.0)
    assert all(
        item.reconciliation_status is ReconciliationStatus.RECONCILED for item in contributions
    )
    assert all(item.method is AttributionMethod.ANALYTICAL_EULER for item in contributions)


def test_desk_contributions_emit_nmrf_branch_local_explain_records() -> None:
    record = _desk_record(
        imcc={"imcc": 100.0},
        ses={
            "total_ses": 25.0,
            "type_a_results": [
                {
                    "risk_factor": {"name": "csr.alpha"},
                    "ses": 9.0,
                    "method": "DIRECT",
                    "source": "risk-engine",
                }
            ],
            "type_b_results": [
                {
                    "risk_factor_name": "fx.beta",
                    "ses": 16.0,
                    "method": "FULL_REVALUATION",
                    "source": "risk-engine",
                }
            ],
        },
        capital={"total": 125.0, "binding_term": "SPOT"},
    )

    contributions = desk_contributions(record)

    additive = [item for item in contributions if item.method is not AttributionMethod.UNSUPPORTED]
    explain = [item for item in contributions if item.method is AttributionMethod.UNSUPPORTED]
    assert [(item.category, item.contribution) for item in additive] == [
        ("IMCC", 100.0),
        ("SES", 25.0),
    ]
    assert [
        (item.category, item.source_level, item.source_id, item.base_amount, item.contribution)
        for item in explain
    ] == [
        ("SES_NMRF_TYPE_A", "risk_factor", "csr.alpha", 9.0, None),
        ("SES_NMRF_TYPE_B", "risk_factor", "fx.beta", 16.0, None),
    ]
    assert all(item.input_hash == record.inputs_hash for item in explain)
    assert all(item.profile_hash == record.policy_hash for item in explain)
    assert all(item.reconciliation_status is ReconciliationStatus.UNKNOWN for item in explain)
    assert _total(contributions) == pytest.approx(125.0)


def test_desk_contributions_emit_lha_branch_local_explain_records() -> None:
    record = _desk_record(
        imcc={
            "imcc": 100.0,
            "unconstrained": {
                "components": [
                    {
                        "liquidity_horizon": "LH10",
                        "expected_shortfall": 60.0,
                        "weighted_square": 3600.0,
                        "present": True,
                    }
                ]
            },
            "constrained_components": [
                {
                    "risk_class": "RATES",
                    "lha_es_result": {
                        "components": [
                            {
                                "liquidity_horizon": "LH20",
                                "expected_shortfall": 30.0,
                                "weighted_square": 900.0,
                                "present": True,
                            },
                            {
                                "liquidity_horizon": "LH40",
                                "expected_shortfall": 0.0,
                                "weighted_square": 0.0,
                                "present": False,
                            },
                        ]
                    },
                }
            ],
        },
        ses={"total_ses": 25.0},
        capital={"total": 125.0, "binding_term": "SPOT"},
    )

    contributions = desk_contributions(record)

    explain = [item for item in contributions if item.method is AttributionMethod.UNSUPPORTED]
    assert [(item.category, item.source_id, item.base_amount) for item in explain] == [
        ("IMCC_LH_UNCONSTRAINED", "UNCONSTRAINED:LH10", 60.0),
        ("IMCC_LH_CONSTRAINED", "CONSTRAINED:RATES:LH20", 30.0),
    ]
    assert all(item.source_level == "liquidity_horizon" for item in explain)
    assert all(item.contribution is None and item.residual == 0.0 for item in explain)
    assert _total(contributions) == pytest.approx(125.0)


def test_desk_contributions_fall_back_when_detail_breakdown_does_not_reconcile() -> None:
    record = _desk_record(
        imcc={"components": {"current_es": 60.0, "stress_scaling": 30.0}},
        ses={"risk_class_components": {"rates": 10.0, "credit_spread": 15.0}},
        capital={
            "total": 125.0,
            "imcc_t_minus_1": 100.0,
            "ses_t_minus_1": 25.0,
            "binding_term": "SPOT",
        },
    )

    contributions = desk_contributions(record)

    assert [(item.category, item.contribution) for item in contributions] == [
        ("IMCC", 100.0),
        ("SES_RATES", 10.0),
        ("SES_CREDIT_SPREAD", 15.0),
    ]
    assert _total(contributions) == pytest.approx(125.0)


def test_desk_contributions_detail_breakdown_keeps_binding_term_residual_explicit() -> None:
    record = _desk_record(
        imcc={"imcc": 100.0, "components": {"current_es": 70.0, "stress_scaling": 30.0}},
        ses={"total_ses": 25.0, "components": {"nmrf_ses": 25.0}},
        capital={"total": 150.0, "binding_term": "AVERAGE"},
    )

    contributions = desk_contributions(record)

    assert [(item.category, item.contribution, item.residual) for item in contributions] == [
        ("IMCC_CURRENT_ES", 70.0, 0.0),
        ("IMCC_STRESS_SCALING", 30.0, 0.0),
        ("SES_NMRF_SES", 25.0, 0.0),
        ("IMA_RC_RESIDUAL", None, 25.0),
    ]
    assert _total(contributions) == pytest.approx(150.0)
    assert all(
        item.reconciliation_status is ReconciliationStatus.PARTIAL_RESIDUAL
        for item in contributions
    )


def test_desk_contributions_reject_non_finite_detail_breakdown() -> None:
    record = _desk_record(
        imcc={"components": {"current_es": float("inf")}},
        ses={"total_ses": 25.0},
        capital={"total": 125.0, "imcc_t_minus_1": 100.0, "binding_term": "SPOT"},
    )

    with pytest.raises(ValueError, match=r"components\.current_es must be finite"):
        desk_contributions(record)


def test_desk_contributions_ignore_explicit_none_breakdown_values() -> None:
    record = _desk_record(
        imcc={"imcc": 100.0},
        ses={"total_ses": 25.0},
        capital={
            "total": 125.0,
            "imcc_t_minus_1": None,
            "ses_t_minus_1": None,
            "pla_addon": None,
            "binding_term": "SPOT",
        },
    )

    contributions = desk_contributions(record)

    assert [(item.category, item.contribution) for item in contributions] == [
        ("IMCC", 100.0),
        ("SES", 25.0),
    ]
    assert _total(contributions) == pytest.approx(125.0)


def test_desk_contributions_emit_partial_residual_for_floor_branch() -> None:
    record = _desk_record(
        imcc={"imcc": 100.0},
        ses={"total_ses": 25.0},
        capital={"total": 150.0, "binding_term": "AVERAGE"},
    )

    contributions = desk_contributions(record)

    assert _total(contributions) == pytest.approx(150.0)
    assert contributions[-1].category == "IMA_RC_RESIDUAL"
    assert contributions[-1].method is AttributionMethod.RESIDUAL
    assert contributions[-1].residual == pytest.approx(25.0)
    assert all(
        item.reconciliation_status is ReconciliationStatus.PARTIAL_RESIDUAL
        for item in contributions
    )


def test_desk_contributions_report_unreconciled_without_floor_branch() -> None:
    record = _desk_record(
        imcc={"imcc": 100.0},
        ses={"total_ses": 25.0},
        capital={"total": 140.0, "binding_term": "SPOT"},
    )

    contributions = desk_contributions(record)

    assert _total(contributions) == pytest.approx(140.0)
    assert contributions[-1].category == "IMA_RC_RESIDUAL"
    assert all(
        item.reconciliation_status is ReconciliationStatus.UNRECONCILED for item in contributions
    )


def test_desk_contributions_require_desk_total() -> None:
    record = _desk_record(
        imcc={"imcc": 100.0},
        ses={"total_ses": 25.0},
        capital={"binding_term": "SPOT"},
    )

    with pytest.raises(ValueError, match="capital must include"):
        desk_contributions(record)


def _desk_record(
    *,
    imcc: dict[str, object],
    ses: dict[str, object],
    capital: dict[str, object],
    pla: dict[str, object] | None = None,
) -> DeskAuditRecord:
    return DeskAuditRecord(
        run_id="run-1",
        desk_id="desk-1",
        regime="FED_NPR_2_0",
        inputs_hash=TEST_INPUTS_HASH,
        imcc=imcc,
        ses=ses,
        pla=pla if pla is not None else {"zone": "GREEN"},
        backtesting={"model_eligible": True},
        capital=capital,
        elapsed_seconds=0.0,
    )


def _total(records: tuple[CapitalContribution, ...]) -> float:
    return sum((item.contribution or 0.0) + item.residual for item in records)
