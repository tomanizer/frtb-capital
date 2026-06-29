from __future__ import annotations

from pathlib import Path

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_sbm import (
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    ensure_sbm_risk_class_measure_supported,
    phase1_capital_supported_paths,
)

BASEL_EXPECTED_PATHS = frozenset(
    (risk_class, risk_measure) for risk_class in SbmRiskClass for risk_measure in SbmRiskMeasure
)

NON_BASEL_PROFILES = (
    SbmRegulatoryProfile.US_NPR_2_0,
    SbmRegulatoryProfile.EU_CRR3,
    SbmRegulatoryProfile.PRA_UK_CRR,
)

US_NPR_EXPECTED_PATHS = BASEL_EXPECTED_PATHS
EU_CRR3_EXPECTED_PATHS = BASEL_EXPECTED_PATHS
PRA_UK_CRR_EXPECTED_PATHS = BASEL_EXPECTED_PATHS

RISK_CLASS_LABELS = {
    SbmRiskClass.GIRR: "GIRR",
    SbmRiskClass.FX: "FX",
    SbmRiskClass.EQUITY: "Equity",
    SbmRiskClass.COMMODITY: "Commodity",
    SbmRiskClass.CSR_NONSEC: "CSR non-securitisation",
    SbmRiskClass.CSR_SEC_NONCTP: "CSR securitisation non-CTP",
    SbmRiskClass.CSR_SEC_CTP: "CSR securitisation CTP",
}


def test_basel_phase1_support_matrix_covers_every_risk_class_measure() -> None:
    supported = phase1_capital_supported_paths(SbmRegulatoryProfile.BASEL_MAR21.value)

    assert supported == BASEL_EXPECTED_PATHS
    for risk_class, risk_measure in BASEL_EXPECTED_PATHS:
        ensure_sbm_risk_class_measure_supported(
            SbmRegulatoryProfile.BASEL_MAR21.value,
            risk_class,
            risk_measure,
        )


def test_us_npr_profile_supports_full_risk_class_measure_matrix() -> None:
    supported = phase1_capital_supported_paths(SbmRegulatoryProfile.US_NPR_2_0.value)

    assert supported == US_NPR_EXPECTED_PATHS
    for risk_class, risk_measure in US_NPR_EXPECTED_PATHS:
        ensure_sbm_risk_class_measure_supported(
            SbmRegulatoryProfile.US_NPR_2_0.value,
            risk_class,
            risk_measure,
        )


def test_eu_crr3_profile_supports_full_risk_class_measure_matrix() -> None:
    supported = phase1_capital_supported_paths(SbmRegulatoryProfile.EU_CRR3.value)

    assert supported == EU_CRR3_EXPECTED_PATHS
    for risk_class, risk_measure in EU_CRR3_EXPECTED_PATHS:
        ensure_sbm_risk_class_measure_supported(
            SbmRegulatoryProfile.EU_CRR3.value,
            risk_class,
            risk_measure,
        )


def test_pra_uk_crr_profile_supports_full_risk_class_measure_matrix() -> None:
    supported = phase1_capital_supported_paths(SbmRegulatoryProfile.PRA_UK_CRR.value)

    assert supported == PRA_UK_CRR_EXPECTED_PATHS
    for risk_class, risk_measure in PRA_UK_CRR_EXPECTED_PATHS:
        ensure_sbm_risk_class_measure_supported(
            SbmRegulatoryProfile.PRA_UK_CRR.value,
            risk_class,
            risk_measure,
        )


def test_traceability_support_matrix_lists_every_basel_path() -> None:
    traceability_path = Path(__file__).resolve().parents[1] / "docs" / "REGULATORY_TRACEABILITY.md"
    if not traceability_path.exists():
        pytest.skip("REGULATORY_TRACEABILITY.md not found")
    traceability = traceability_path.read_text(encoding="utf-8")
    implemented = "implemented but under audit"

    for label in RISK_CLASS_LABELS.values():
        row = f"| {label} | {implemented} | {implemented} | {implemented} |"
        assert row in traceability

    assert "| `US_NPR_2_0` | implemented under audit (21 / 21 cells) |" in traceability
    assert "| `EU_CRR3` | implemented under audit (21 / 21 cells) |" in traceability
    assert "| `PRA_UK_CRR` | implemented under audit (21 / 21 cells) |" in traceability

    for issue_number in ("#160", "#161", "#166", "#169", "#226", "#244"):
        assert issue_number in traceability

    assert "NON_BASEL_PROFILE_DESIGN.md" in traceability
    assert "NON_BASEL_PROFILE_REQUIREMENTS.md" in traceability

