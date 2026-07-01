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

US_NPR_EXPECTED_PATHS = frozenset(
    {
        (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
        (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
        (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
    }
)
PRA_UK_CRR_EXPECTED_PATHS = frozenset({(SbmRiskClass.GIRR, SbmRiskMeasure.DELTA)})
COMPARISON_PROFILE_EXPECTED_PATHS = {
    SbmRegulatoryProfile.US_NPR_2_0: US_NPR_EXPECTED_PATHS,
    SbmRegulatoryProfile.EU_CRR3: frozenset(),
    SbmRegulatoryProfile.PRA_UK_CRR: PRA_UK_CRR_EXPECTED_PATHS,
}

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


def test_us_npr_profile_supports_only_girr_delta_vega_and_curvature() -> None:
    assert phase1_capital_supported_paths(SbmRegulatoryProfile.US_NPR_2_0.value) == (
        US_NPR_EXPECTED_PATHS
    )
    ensure_sbm_risk_class_measure_supported(
        SbmRegulatoryProfile.US_NPR_2_0.value,
        SbmRiskClass.GIRR,
        SbmRiskMeasure.DELTA,
    )
    ensure_sbm_risk_class_measure_supported(
        SbmRegulatoryProfile.US_NPR_2_0.value,
        SbmRiskClass.GIRR,
        SbmRiskMeasure.VEGA,
    )
    ensure_sbm_risk_class_measure_supported(
        SbmRegulatoryProfile.US_NPR_2_0.value,
        SbmRiskClass.GIRR,
        SbmRiskMeasure.CURVATURE,
    )

    for risk_class in SbmRiskClass:
        for risk_measure in SbmRiskMeasure:
            if (risk_class, risk_measure) in US_NPR_EXPECTED_PATHS:
                continue
            with pytest.raises(UnsupportedRegulatoryFeatureError, match="US_NPR_2_0"):
                ensure_sbm_risk_class_measure_supported(
                    SbmRegulatoryProfile.US_NPR_2_0.value,
                    risk_class,
                    risk_measure,
                )


def test_pra_uk_crr_profile_supports_only_girr_delta() -> None:
    assert phase1_capital_supported_paths(SbmRegulatoryProfile.PRA_UK_CRR.value) == (
        PRA_UK_CRR_EXPECTED_PATHS
    )
    ensure_sbm_risk_class_measure_supported(
        SbmRegulatoryProfile.PRA_UK_CRR.value,
        SbmRiskClass.GIRR,
        SbmRiskMeasure.DELTA,
    )

    for risk_class in SbmRiskClass:
        for risk_measure in SbmRiskMeasure:
            if (risk_class, risk_measure) in PRA_UK_CRR_EXPECTED_PATHS:
                continue
            with pytest.raises(UnsupportedRegulatoryFeatureError, match="PRA_UK_CRR"):
                ensure_sbm_risk_class_measure_supported(
                    SbmRegulatoryProfile.PRA_UK_CRR.value,
                    risk_class,
                    risk_measure,
                )


@pytest.mark.parametrize("profile", NON_BASEL_PROFILES)
def test_comparison_profile_support_matrix_classifies_every_cell(
    profile: SbmRegulatoryProfile,
) -> None:
    supported = phase1_capital_supported_paths(profile.value)
    expected_supported = COMPARISON_PROFILE_EXPECTED_PATHS[profile]

    assert supported == expected_supported
    for risk_class in SbmRiskClass:
        for risk_measure in SbmRiskMeasure:
            if (risk_class, risk_measure) in expected_supported:
                ensure_sbm_risk_class_measure_supported(
                    profile.value,
                    risk_class,
                    risk_measure,
                )
                continue
            with pytest.raises(UnsupportedRegulatoryFeatureError, match=profile.value):
                ensure_sbm_risk_class_measure_supported(
                    profile.value,
                    risk_class,
                    risk_measure,
                )


@pytest.mark.parametrize(
    "profile",
    (SbmRegulatoryProfile.EU_CRR3,),
)
def test_comparison_profiles_without_implemented_cells_fail_closed(
    profile: SbmRegulatoryProfile,
) -> None:
    assert phase1_capital_supported_paths(profile.value) == frozenset()

    with pytest.raises(UnsupportedRegulatoryFeatureError, match="unsupported"):
        ensure_sbm_risk_class_measure_supported(
            profile.value,
            SbmRiskClass.GIRR,
            SbmRiskMeasure.DELTA,
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

    assert "| `US_NPR_2_0` | partial (3 / 21 cells) |" in traceability
    assert "| `PRA_UK_CRR` | partial (1 / 21 cells) |" in traceability
    assert f"| `{SbmRegulatoryProfile.EU_CRR3.value}` | unsupported fail-closed" in traceability
    assert (
        "| GIRR | implemented under audit | implemented under audit | implemented under audit |"
        " unsupported fail-closed | unsupported fail-closed | unsupported fail-closed |"
        " implemented under audit | unsupported fail-closed | unsupported fail-closed |"
        in traceability
    )
    assert (
        "| FX | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed |"
        in traceability
    )
    assert "ADR 0048" in traceability
    assert "girr_delta_us_npr_v1" in traceability
    assert "girr_vega_us_npr_v1" in traceability
    assert "girr_curvature_us_npr_v1" in traceability
    assert "girr_delta_pra_uk_crr_v1" in traceability

    for issue_number in ("#160", "#161", "#166", "#169", "#226", "#244"):
        assert issue_number in traceability

    assert "NON_BASEL_PROFILE_DESIGN.md" in traceability
    assert "NON_BASEL_PROFILE_REQUIREMENTS.md" in traceability
    assert "SBM-NBP-020" in traceability


def test_pra_source_map_is_final_rule_reference_not_runtime_support() -> None:
    docs_root = Path(__file__).resolve().parents[1] / "docs"
    source_manifest_path = docs_root / "regulatory_sources.yml"
    traceability_path = docs_root / "REGULATORY_TRACEABILITY.md"
    if not source_manifest_path.exists() or not traceability_path.exists():
        pytest.skip("SBM documentation files not found")

    source_manifest = source_manifest_path.read_text(encoding="utf-8")
    traceability = traceability_path.read_text(encoding="utf-8")

    assert "pra_uk_crr_sbm_mapping_tbd" not in source_manifest
    assert "uk_pra_ps1_26_sbm_asa" in source_manifest
    assert "status: final_rule_reference" in source_manifest
    assert "Articles 325c-325h" in source_manifest
    assert "Articles 325l-325u" in source_manifest
    assert "Articles 325ae-325ay" in source_manifest
    assert "runtime cells still need profile-owned citation ids" in source_manifest

    assert "source-mapped under SBM-NBP-020" in traceability
    assert "PRA PS1/26 Appendix 1" in traceability
    assert "PRA mirroring policy" in traceability
    assert "numerical identity is not implementation" in traceability
    assert "2027-01-01 effective date" in traceability
    assert "partial (1 / 21 cells)" in traceability
    assert "PRA_UK_CRR` GIRR delta" in traceability
