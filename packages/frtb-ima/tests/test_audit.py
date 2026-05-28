"""Tests for post-run audit records."""

import json
from datetime import date
from pathlib import Path
from types import MappingProxyType

import pytest

from frtb_ima import __version__
from frtb_ima.audit import (
    CapitalRunAuditLog,
    DeskAuditRecord,
    audit_records_to_ndjson,
    render_capital_run_audit_report,
    write_audit_records_ndjson,
    write_capital_run_audit_report,
)
from frtb_ima.regimes import DEFAULT_MODEL_VERSION, DeskEligibilityStatus, get_policy

TEST_INPUTS_HASH = "1" * 64
ALT_INPUTS_HASH = "2" * 64


def _desk_record(desk_id: str = "desk-1") -> DeskAuditRecord:
    return DeskAuditRecord(
        run_id="run-1",
        desk_id=desk_id,
        regime="FED_NPR_2_0",
        inputs_hash=TEST_INPUTS_HASH,
        as_of_date=date(2026, 5, 27),
        imcc={"imcc": 100.0},
        ses={"total_ses": 40.0},
        pla={"pla": {"zone": "GREEN"}},
        backtesting={"model_eligible": True},
        capital={"models_based_capital": 190.0},
        nmrf_valuation={"passed": True, "artifact_count": 2},
        elapsed_seconds=0.25,
        metadata={"source": "unit-test"},
    )


def test_desk_audit_record_serializes_to_json_line() -> None:
    record = _desk_record()

    payload = json.loads(record.to_json_line())

    assert payload["run_id"] == "run-1"
    assert payload["desk_id"] == "desk-1"
    assert payload["desk_eligibility"] == "IMA_ELIGIBLE"
    assert payload["model_version"] == DEFAULT_MODEL_VERSION.as_dict()
    assert payload["code_version"] == __version__
    assert payload["policy_hash"] == get_policy().policy_hash
    assert payload["inputs_hash"] == TEST_INPUTS_HASH
    assert payload["as_of_date"] == "2026-05-27"
    assert payload["imcc"]["imcc"] == pytest.approx(100.0)
    assert payload["nmrf_valuation"]["passed"] is True
    assert payload["metadata"]["source"] == "unit-test"


def test_desk_audit_record_canonicalizes_desk_eligibility_enum() -> None:
    record = DeskAuditRecord(
        run_id="run-1",
        desk_id="desk-1",
        regime="FED_NPR_2_0",
        desk_eligibility=DeskEligibilityStatus.SA_FALLBACK,
        imcc={},
        ses={},
        pla={},
        backtesting={},
        capital={},
        inputs_hash=TEST_INPUTS_HASH,
        elapsed_seconds=0.0,
    )

    assert record.desk_eligibility == "SA_FALLBACK"
    assert record.as_dict()["desk_eligibility"] == "SA_FALLBACK"


def test_desk_audit_record_rejects_invalid_desk_eligibility() -> None:
    with pytest.raises(ValueError, match="DeskEligibilityStatus"):
        DeskAuditRecord(
            run_id="run-1",
            desk_id="desk-1",
            regime="FED_NPR_2_0",
            desk_eligibility="BREACH",
            imcc={},
            ses={},
            pla={},
            backtesting={},
            capital={},
            inputs_hash=TEST_INPUTS_HASH,
            elapsed_seconds=0.0,
        )


def test_capital_run_audit_log_serializes_records_to_ndjson() -> None:
    log = CapitalRunAuditLog(
        run_id="run-1",
        regime="FED_NPR_2_0",
        as_of_date=date(2026, 5, 27),
        desk_records=(_desk_record("desk-1"), _desk_record("desk-2")),
    )

    lines = log.to_ndjson().splitlines()

    assert log.desk_count == 2
    assert log.as_dict()["model_version"] == DEFAULT_MODEL_VERSION.as_dict()
    assert log.as_dict()["code_version"] == __version__
    assert log.as_dict()["policy_hash"] == get_policy().policy_hash
    assert log.as_dict()["inputs_hash"] != TEST_INPUTS_HASH
    assert len(lines) == 2
    assert json.loads(lines[1])["desk_id"] == "desk-2"
    assert json.loads(lines[1])["inputs_hash"] == TEST_INPUTS_HASH


def test_capital_run_audit_log_rejects_duplicate_desks() -> None:
    with pytest.raises(ValueError, match="duplicate desk_id"):
        CapitalRunAuditLog(
            run_id="run-1",
            regime="FED_NPR_2_0",
            desk_records=(_desk_record("desk-1"), _desk_record("desk-1")),
        )


def test_capital_run_audit_log_requires_consistent_identity_fields() -> None:
    with pytest.raises(ValueError, match="same run_id"):
        CapitalRunAuditLog(
            run_id="run-2",
            regime="FED_NPR_2_0",
            desk_records=(_desk_record("desk-1"),),
        )

    with pytest.raises(ValueError, match="same regime"):
        CapitalRunAuditLog(
            run_id="run-1",
            regime="ECB_CRR3",
            policy_hash="0" * 64,
            desk_records=(_desk_record("desk-1"),),
        )

    with pytest.raises(ValueError, match="same policy_hash"):
        CapitalRunAuditLog(
            run_id="run-1",
            regime="FED_NPR_2_0",
            policy_hash=get_policy().policy_hash,
            desk_records=(
                _desk_record("desk-1"),
                DeskAuditRecord(
                    run_id="run-1",
                    desk_id="desk-2",
                    regime="FED_NPR_2_0",
                    policy_hash="0" * 64,
                    imcc={},
                    ses={},
                    pla={},
                    backtesting={},
                    capital={},
                    inputs_hash=TEST_INPUTS_HASH,
                    elapsed_seconds=0.0,
                ),
            ),
        )


def test_audit_record_rejects_invalid_policy_hash() -> None:
    with pytest.raises(ValueError, match="policy_hash"):
        DeskAuditRecord(
            run_id="run-1",
            desk_id="desk-1",
            regime="FED_NPR_2_0",
            policy_hash="not-a-sha",
            imcc={},
            ses={},
            pla={},
            backtesting={},
            capital={},
            inputs_hash=TEST_INPUTS_HASH,
            elapsed_seconds=0.0,
        )


def test_audit_record_rejects_invalid_inputs_hash() -> None:
    with pytest.raises(ValueError, match="inputs_hash"):
        DeskAuditRecord(
            run_id="run-1",
            desk_id="desk-1",
            regime="FED_NPR_2_0",
            inputs_hash="not-a-sha",
            imcc={},
            ses={},
            pla={},
            backtesting={},
            capital={},
            elapsed_seconds=0.0,
        )


def test_audit_records_validate_identity_and_version_fields() -> None:
    with pytest.raises(ValueError, match="run_id"):
        DeskAuditRecord(
            run_id="",
            desk_id="desk-1",
            regime="FED_NPR_2_0",
            imcc={},
            ses={},
            pla={},
            backtesting={},
            capital={},
            inputs_hash=TEST_INPUTS_HASH,
            elapsed_seconds=0.0,
        )
    with pytest.raises(ValueError, match="code_version"):
        DeskAuditRecord(
            run_id="run-1",
            desk_id="desk-1",
            regime="FED_NPR_2_0",
            code_version="",
            imcc={},
            ses={},
            pla={},
            backtesting={},
            capital={},
            inputs_hash=TEST_INPUTS_HASH,
            elapsed_seconds=0.0,
        )
    with pytest.raises(ValueError, match="policy_hash"):
        DeskAuditRecord(
            run_id="run-1",
            desk_id="desk-1",
            regime="UNKNOWN_REGIME",
            imcc={},
            ses={},
            pla={},
            backtesting={},
            capital={},
            inputs_hash=TEST_INPUTS_HASH,
            elapsed_seconds=0.0,
        )
    with pytest.raises(ValueError, match="elapsed_seconds"):
        DeskAuditRecord(
            run_id="run-1",
            desk_id="desk-1",
            regime="FED_NPR_2_0",
            imcc={},
            ses={},
            pla={},
            backtesting={},
            capital={},
            inputs_hash=TEST_INPUTS_HASH,
            elapsed_seconds=-0.1,
        )


def test_single_desk_audit_log_defaults_to_desk_inputs_hash() -> None:
    log = CapitalRunAuditLog(
        run_id="run-1",
        regime="FED_NPR_2_0",
        desk_records=(_desk_record(),),
    )

    assert log.inputs_hash == TEST_INPUTS_HASH


def test_multi_desk_audit_log_inputs_hash_is_deterministic_by_desk_id() -> None:
    first = _desk_record("desk-1")
    second = DeskAuditRecord(
        run_id="run-1",
        desk_id="desk-2",
        regime="FED_NPR_2_0",
        inputs_hash=ALT_INPUTS_HASH,
        imcc={},
        ses={},
        pla={},
        backtesting={},
        capital={},
        elapsed_seconds=0.0,
    )

    forward = CapitalRunAuditLog(
        run_id="run-1",
        regime="FED_NPR_2_0",
        desk_records=(first, second),
    )
    reverse = CapitalRunAuditLog(
        run_id="run-1",
        regime="FED_NPR_2_0",
        desk_records=(second, first),
    )

    assert forward.inputs_hash == reverse.inputs_hash
    assert forward.inputs_hash not in {TEST_INPUTS_HASH, ALT_INPUTS_HASH}


def test_audit_metadata_defaults_are_immutable_mappings() -> None:
    record = DeskAuditRecord(
        run_id="run-1",
        desk_id="desk-1",
        regime="FED_NPR_2_0",
        imcc={},
        ses={},
        pla={},
        backtesting={},
        capital={},
        inputs_hash=TEST_INPUTS_HASH,
        elapsed_seconds=0.0,
    )
    log = CapitalRunAuditLog(
        run_id="run-1",
        regime="FED_NPR_2_0",
        desk_records=(record,),
    )

    assert isinstance(record.metadata, MappingProxyType)
    assert isinstance(log.metadata, MappingProxyType)


def test_audit_records_to_ndjson_returns_empty_string_for_empty_input() -> None:
    assert audit_records_to_ndjson(()) == ""


def test_write_audit_records_ndjson(tmp_path: Path) -> None:
    path = tmp_path / "audit.ndjson"

    write_audit_records_ndjson([_desk_record()], path)

    assert audit_records_to_ndjson([_desk_record()]) == path.read_text()


def test_render_capital_run_audit_report_contains_summary_and_details() -> None:
    log = CapitalRunAuditLog(
        run_id="run-1",
        regime="FED_NPR_2_0",
        as_of_date=date(2026, 5, 27),
        desk_records=(_desk_record(),),
        metadata={"fixture": "capital_run_v1"},
    )

    report = render_capital_run_audit_report(log)

    assert "# FRTB IMA Capital Run Audit Report" in report
    assert "## Run identity" in report
    assert f"| Code version | {__version__} |" in report
    assert f"| Policy hash | {get_policy().policy_hash} |" in report
    assert f"| Inputs hash | {TEST_INPUTS_HASH} |" in report
    assert "| Run ID | run-1 |" in report
    assert "| desk-1 | 2026-05-27 | 100 | 40 | 190 |" in report
    assert "## Desk: desk-1" in report
    assert "### NMRF valuation" in report
    assert '"artifact_count": 2' in report
    assert "Prototype report only. Not for regulatory reporting." in report
    assert (
        "> NPR 2.0 values are proposed-rule parameters and are not final regulatory capital."
        in report
    )


def test_write_capital_run_audit_report(tmp_path: Path) -> None:
    log = CapitalRunAuditLog(
        run_id="run-1",
        regime="FED_NPR_2_0",
        desk_records=(_desk_record(),),
    )
    path = tmp_path / "reports" / "audit.md"

    write_capital_run_audit_report(log, path, title="Unit Test Audit")

    report = path.read_text()
    assert report.startswith("# Unit Test Audit")
    assert "## Desk summary" in report
