from __future__ import annotations

from datetime import date

import pytest
from frtb_sbm import (
    SbmCalculationContext,
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


def sample_ctp_sensitivity(**overrides: object) -> SbmSensitivity:
    fields = {
        "sensitivity_id": "sec-ctp-001",
        "source_row_id": "row-sec-ctp-001",
        "desk_id": "credit-desk",
        "legal_entity": "LE-001",
        "risk_class": SbmRiskClass.CSR_SEC_CTP,
        "risk_measure": SbmRiskMeasure.DELTA,
        "bucket": "10",
        "risk_factor": "BOND",
        "amount": 750_000.0,
        "amount_currency": "USD",
        "qualifier": "UND-A",
        "tenor": "3y",
        "sign_convention": SbmSignConvention.RECEIVE,
        "lineage": SbmSourceLineage(
            source_system="synthetic-sbm-fixture",
            source_file="sensitivities.json",
            source_row_id="row-sec-ctp-001",
        ),
    }
    fields.update(overrides)
    return SbmSensitivity(**fields)  # type: ignore[arg-type]


def test_csr_sec_ctp_fixture_reconciles() -> None:
    result = calculate_sbm_capital(
        (
            sample_ctp_sensitivity(),
            sample_ctp_sensitivity(
                sensitivity_id="sec-ctp-002",
                source_row_id="row-sec-ctp-002",
                bucket="3",
                qualifier="UND-B",
                lineage=SbmSourceLineage(
                    source_system="synthetic-sbm-fixture",
                    source_file="sensitivities.json",
                    source_row_id="row-sec-ctp-002",
                ),
            ),
        ),
        context=SbmCalculationContext(
            run_id="run-csr-sec-ctp-001",
            calculation_date=date(2026, 5, 30),
            base_currency="USD",
            reporting_currency="USD",
            profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        ),
    )

    assert result.total_capital > 0.0
    assert len(result.risk_classes) == 1
    assert result.risk_classes[0].selected_scenario is not None


def test_csr_sec_ctp_missing_decomposition_fails_closed() -> None:
    with pytest.raises(Exception, match="decomposition evidence"):
        calculate_sbm_capital(
            (
                sample_ctp_sensitivity(
                    mapping_citation_ids=(CSR_SEC_CTP_DECOMPOSITION_REQUIRED_FLAG,),
                ),
            ),
            context=SbmCalculationContext(
                run_id="run-csr-sec-ctp-bad",
                calculation_date=date(2026, 5, 30),
                base_currency="USD",
                reporting_currency="USD",
                profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
            ),
        )
