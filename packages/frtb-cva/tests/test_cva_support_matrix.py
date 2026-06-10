from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_cva import (
    CvaCalculationContext,
    CvaMethod,
    CvaProfileSupportStatus,
    CvaRegulatoryProfile,
    CvaSupportStatus,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    cva_capital_supported_methods,
    cva_profile_support_matrix,
    cva_profile_support_status,
    cva_sa_cva_supported_paths,
    ensure_cva_profile_method_supported,
    ensure_cva_sa_cva_path_supported,
    get_cva_rule_profile,
    resolve_calculation_method,
)
from frtb_cva.sa_cva import SA_CVA_PATH_REGISTRY
from frtb_cva.support_matrix import (
    EXPOSURE_SENSITIVITY_GENERATION_POLICY,
    SA_CVA_APPROVAL_GOVERNANCE_POLICY,
)
from frtb_cva.validation import CvaInputError

_SUPPORTED_PATHS = frozenset(
    key for key, spec in SA_CVA_PATH_REGISTRY.items() if spec.unsupported_message is None
)
_COMPARISON_PROFILES = (
    CvaRegulatoryProfile.US_NPR20_VB,
    CvaRegulatoryProfile.EU_CRR3_CVA,
    CvaRegulatoryProfile.UK_PRA_CVA,
)


def test_basel_methods_match_supported_set() -> None:
    methods = cva_capital_supported_methods(CvaRegulatoryProfile.BASEL_MAR50_2020)
    assert methods == frozenset(CvaMethod)
    assert get_cva_rule_profile(CvaRegulatoryProfile.BASEL_MAR50_2020).supported_methods == methods


def test_basel_sa_paths_match_sa_cva_module() -> None:
    paths = cva_sa_cva_supported_paths(CvaRegulatoryProfile.BASEL_MAR50_2020)
    assert paths == frozenset(_SUPPORTED_PATHS)
    assert len(paths) == 11
    assert (SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD, SaCvaRiskMeasure.VEGA) not in paths


@pytest.mark.parametrize("profile", _COMPARISON_PROFILES)
def test_non_basel_profiles_are_supported_comparison_profiles(
    profile: CvaRegulatoryProfile,
) -> None:
    assert cva_profile_support_status(profile) is CvaProfileSupportStatus.CAPITAL_PRODUCING
    assert cva_capital_supported_methods(profile) == frozenset(CvaMethod)
    assert cva_sa_cva_supported_paths(profile) == frozenset(_SUPPORTED_PATHS)
    ensure_cva_profile_method_supported(profile, CvaMethod.BA_CVA_REDUCED)
    ensure_cva_sa_cva_path_supported(
        profile,
        SaCvaRiskClass.GIRR,
        SaCvaRiskMeasure.DELTA,
    )


@pytest.mark.parametrize("profile", _COMPARISON_PROFILES)
def test_non_basel_matrix_cells_record_evidenced_support(
    profile: CvaRegulatoryProfile,
) -> None:
    method_ids = {method.value for method in CvaMethod}
    cells = [
        cell
        for cell in cva_profile_support_matrix()
        if cell.profile is profile
        and cell.method in method_ids
        and not _is_ccs_vega_cell(cell)
    ]
    assert cells
    assert {cell.status for cell in cells} == {CvaSupportStatus.IMPLEMENTED_UNDER_AUDIT}
    assert {cell.blocker for cell in cells} == {"none"}
    assert all("test_cva_profile_evidence_fixture.py" in " ".join(cell.tests) for cell in cells)


def _is_ccs_vega_cell(cell: object) -> bool:
    return (
        getattr(cell, "risk_measure", None) is SaCvaRiskMeasure.VEGA
        and getattr(cell, "risk_class", None) is SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD
    )


@pytest.mark.parametrize("profile", list(CvaRegulatoryProfile))
def test_ccs_vega_matrix_row_is_regulatory_absence(profile: CvaRegulatoryProfile) -> None:
    cells = {
        (cell.profile, cell.method, cell.risk_class, cell.risk_measure): cell
        for cell in cva_profile_support_matrix()
    }
    cell = cells[
        (
            profile,
            CvaMethod.SA_CVA.value,
            SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
            SaCvaRiskMeasure.VEGA,
        )
    ]
    assert cell.status is CvaSupportStatus.REGULATORY_ABSENCE
    assert cell.blocker == "regulatory_absence"
    with pytest.raises(CvaInputError, match="CCS vega"):
        ensure_cva_sa_cva_path_supported(
            profile,
            SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
            SaCvaRiskMeasure.VEGA,
        )


def test_mar50_9_materiality_policy_unsupported() -> None:
    cells = [cell for cell in cva_profile_support_matrix() if cell.method.startswith("MAR50.9")]
    assert len(cells) == len(CvaRegulatoryProfile)
    assert {cell.profile for cell in cells} == set(CvaRegulatoryProfile)
    assert all(cell.status is CvaSupportStatus.UNSUPPORTED_FAIL_CLOSED for cell in cells)
    assert all(cell.blocker == "ccr_boundary" for cell in cells)
    context = CvaCalculationContext(
        run_id="run-mar50-9",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        materiality_threshold_elected=True,
    )
    with pytest.raises(UnsupportedRegulatoryFeatureError, match=r"MAR50\.9"):
        resolve_calculation_method(context)


def test_support_matrix_uses_every_status_taxonomy_value() -> None:
    statuses = {cell.status for cell in cva_profile_support_matrix()}
    assert statuses == {
        CvaSupportStatus.IMPLEMENTED_UNDER_AUDIT,
        CvaSupportStatus.UNSUPPORTED_FAIL_CLOSED,
        CvaSupportStatus.REGULATORY_ABSENCE,
        CvaSupportStatus.OUT_OF_SCOPE,
    }


@pytest.mark.parametrize("profile", list(CvaRegulatoryProfile))
def test_package_boundary_policies_are_out_of_scope(profile: CvaRegulatoryProfile) -> None:
    matrix = cva_profile_support_matrix()
    approval = next(
        cell
        for cell in matrix
        if cell.profile is profile and cell.method == SA_CVA_APPROVAL_GOVERNANCE_POLICY
    )
    generation = next(
        cell
        for cell in matrix
        if cell.profile is profile and cell.method == EXPOSURE_SENSITIVITY_GENERATION_POLICY
    )

    assert approval.status is CvaSupportStatus.OUT_OF_SCOPE
    assert approval.blocker == "supervisory_approval_boundary"
    assert approval.method not in {method.value for method in CvaMethod}

    assert generation.status is CvaSupportStatus.OUT_OF_SCOPE
    assert generation.blocker == "upstream_exposure_sensitivity_boundary"
    assert generation.method not in {method.value for method in CvaMethod}


def test_traceability_lists_all_basel_sa_rows() -> None:
    traceability = (
        Path(__file__).resolve().parents[1] / "docs" / "REGULATORY_TRACEABILITY.md"
    ).read_text()
    for risk_class, risk_measure in cva_sa_cva_supported_paths(
        CvaRegulatoryProfile.BASEL_MAR50_2020
    ):
        assert f"`{risk_class.value}` | `{risk_measure.value}`" in traceability


def test_traceability_documents_boundary_status_taxonomy() -> None:
    traceability = (
        Path(__file__).resolve().parents[1] / "docs" / "REGULATORY_TRACEABILITY.md"
    ).read_text()
    for status in CvaSupportStatus:
        assert f"`{status.value}`" in traceability
    assert SA_CVA_APPROVAL_GOVERNANCE_POLICY in traceability
    assert EXPOSURE_SENSITIVITY_GENERATION_POLICY in traceability
    assert "ccr_boundary" in traceability
