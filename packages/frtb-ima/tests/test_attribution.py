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
) -> DeskAuditRecord:
    return DeskAuditRecord(
        run_id="run-1",
        desk_id="desk-1",
        regime="FED_NPR_2_0",
        inputs_hash=TEST_INPUTS_HASH,
        imcc=imcc,
        ses=ses,
        pla={"zone": "GREEN"},
        backtesting={"model_eligible": True},
        capital=capital,
        elapsed_seconds=0.0,
    )


def _total(records: tuple[CapitalContribution, ...]) -> float:
    return sum((item.contribution or 0.0) + item.residual for item in records)
