from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from frtb_common import StandardisedComponent, UnsupportedRegulatoryFeatureError
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
)
from frtb_sbm.csr_sec_ctp_reference_data import (
    CSR_SEC_CTP_DECOMPOSITION_EVIDENCE_FLAG,
    CSR_SEC_CTP_DECOMPOSITION_REQUIRED_FLAG,
)
from frtb_sbm.handoff import to_component_summary


def sample_lineage(row_id: str = "row-001") -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-sbm-fixture",
        source_file="sensitivities.json",
        source_row_id=row_id,
    )


def sample_nonctp_sensitivity(**overrides: object) -> SbmSensitivity:
    fields = {
        "sensitivity_id": "sec-nctp-001",
        "source_row_id": "row-sec-nctp-001",
        "desk_id": "credit-desk",
        "legal_entity": "LE-001",
        "risk_class": SbmRiskClass.CSR_SEC_NONCTP,
        "risk_measure": SbmRiskMeasure.DELTA,
        "bucket": "1",
        "risk_factor": "BOND",
        "amount": 1_000_000.0,
        "amount_currency": "USD",
        "qualifier": "TR-A",
        "tenor": "5y",
        "sign_convention": SbmSignConvention.RECEIVE,
        "lineage": sample_lineage("row-sec-nctp-001"),
    }
    fields.update(overrides)
    return SbmSensitivity(**fields)  # type: ignore[arg-type]


def sample_ctp_sensitivity(**overrides: object) -> SbmSensitivity:
    fields = {
        "sensitivity_id": "sec-ctp-001",
        "source_row_id": "row-sec-ctp-001",
        "desk_id": "credit-desk",
        "legal_entity": "LE-001",
        "risk_class": SbmRiskClass.CSR_SEC_CTP,
        "risk_measure": SbmRiskMeasure.DELTA,
        "bucket": "3",
        "risk_factor": "BOND",
        "amount": 500_000.0,
        "amount_currency": "USD",
        "qualifier": "UND-A",
        "tenor": "5y",
        "sign_convention": SbmSignConvention.RECEIVE,
        "lineage": sample_lineage("row-sec-ctp-001"),
    }
    fields.update(overrides)
    return SbmSensitivity(**fields)  # type: ignore[arg-type]


def sample_context() -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id="run-csr-sec-001",
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )


def test_csr_sec_nonctp_delta_capital_reconciles() -> None:
    result = calculate_sbm_capital(
        (
            sample_nonctp_sensitivity(),
            sample_nonctp_sensitivity(
                sensitivity_id="sec-nctp-002",
                source_row_id="row-sec-nctp-002",
                qualifier="TR-B",
                lineage=sample_lineage("row-sec-nctp-002"),
            ),
        ),
        context=sample_context(),
    )

    assert result.total_capital > 0.0
    risk_class = result.risk_classes[0]
    assert risk_class.risk_class is SbmRiskClass.CSR_SEC_NONCTP
    assert len(risk_class.scenario_details) == 3


def test_csr_sec_nonctp_rejects_missing_qualifier() -> None:
    with pytest.raises(Exception, match="qualifier"):
        calculate_sbm_capital(
            (sample_nonctp_sensitivity(qualifier=""),),
            context=sample_context(),
        )


def test_csr_sec_ctp_delta_capital_reconciles() -> None:
    result = calculate_sbm_capital(
        (sample_ctp_sensitivity(),),
        context=sample_context(),
    )

    assert result.total_capital > 0.0
    assert result.risk_classes[0].risk_class is SbmRiskClass.CSR_SEC_CTP


def test_csr_sec_ctp_rejects_index_buckets() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="excludes index buckets"):
        calculate_sbm_capital(
            (sample_ctp_sensitivity(bucket="17"),),
            context=sample_context(),
        )


def test_csr_sec_ctp_requires_decomposition_evidence_when_flagged() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="decomposition evidence"):
        calculate_sbm_capital(
            (
                sample_ctp_sensitivity(
                    mapping_citation_ids=(CSR_SEC_CTP_DECOMPOSITION_REQUIRED_FLAG,),
                ),
            ),
            context=sample_context(),
        )


def test_csr_sec_ctp_accepts_decomposition_evidence_flag() -> None:
    result = calculate_sbm_capital(
        (
            sample_ctp_sensitivity(
                mapping_citation_ids=(
                    CSR_SEC_CTP_DECOMPOSITION_REQUIRED_FLAG,
                    CSR_SEC_CTP_DECOMPOSITION_EVIDENCE_FLAG,
                ),
            ),
        ),
        context=sample_context(),
    )
    assert result.total_capital > 0.0


def test_orchestration_handoff_view_exposes_shared_contract() -> None:
    result = calculate_sbm_capital(
        (sample_nonctp_sensitivity(),),
        context=sample_context(),
    )
    handoff = to_component_summary(result)

    assert handoff.component is StandardisedComponent.SBM
    assert handoff.package_name == "frtb-sbm"
    assert handoff.total_capital == result.total_capital
    assert handoff.run_id == "run-csr-sec-001"
    assert handoff.subtotal_count == len(result.risk_classes)


def test_orchestration_handoff_requires_run_context() -> None:
    result = calculate_sbm_capital(
        (sample_nonctp_sensitivity(),),
        context=sample_context(),
    )
    without_context = replace(result, run_context=None)

    with pytest.raises(SbmInputError, match="run_context is required"):
        to_component_summary(without_context)
