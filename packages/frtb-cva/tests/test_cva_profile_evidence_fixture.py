from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from frtb_cva import (
    CvaMethod,
    CvaRegulatoryProfile,
    CvaSupportStatus,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    cva_profile_support_matrix,
    get_cva_rule_profile,
    profile_content_hash,
)
from frtb_cva.reference_data import citations_for_profile, profile_reference_payload

_REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "profile_comparison_v1" / "expected_profiles.json"
CROSSWALK_PATH = _REPO_ROOT / "docs" / "regulatory" / "crosswalk" / "frtb-cva.yml"


def _load_fixture() -> dict[str, Any]:
    with FIXTURE_PATH.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload["schema_version"] == 1
    return payload


def _load_crosswalk_requirements() -> dict[str, dict[str, Any]]:
    with CROSSWALK_PATH.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    return {str(requirement["id"]): requirement for requirement in payload["requirements"]}


@pytest.mark.parametrize("profile_id", sorted(_load_fixture()["profiles"]))
def test_profile_fixture_matches_runtime_hashes_and_reference_payloads(profile_id: str) -> None:
    fixture = _load_fixture()["profiles"][profile_id]
    profile = CvaRegulatoryProfile(profile_id)
    rule_profile = get_cva_rule_profile(profile)

    assert rule_profile.profile is profile
    assert rule_profile.content_hash == profile_content_hash(profile)
    assert len(rule_profile.content_hash) == 64
    int(rule_profile.content_hash, 16)
    assert rule_profile.content_hash != profile_content_hash(CvaRegulatoryProfile.BASEL_MAR50_2020)

    reference_payload = profile_reference_payload(profile)
    assert reference_payload["profile"] == profile.value
    for citation_id in _fixture_citation_ids(fixture):
        assert citation_id in reference_payload["citations"]


def test_profile_fixture_hashes_are_distinct_across_comparison_profiles() -> None:
    profiles = [CvaRegulatoryProfile(profile_id) for profile_id in _load_fixture()["profiles"]]
    hashes = {profile_content_hash(profile) for profile in profiles}
    assert len(hashes) == len(profiles)


@pytest.mark.parametrize("profile_id", sorted(_load_fixture()["profiles"]))
def test_profile_fixture_matches_citation_source_ids(profile_id: str) -> None:
    fixture = _load_fixture()["profiles"][profile_id]
    profile = CvaRegulatoryProfile(profile_id)
    citations = citations_for_profile(profile)

    source_ids = {citations[citation_id].source_id for citation_id in _fixture_citation_ids(fixture)}
    assert source_ids <= set(fixture["citation_source_ids"])


@pytest.mark.parametrize("profile_id", sorted(_load_fixture()["profiles"]))
def test_profile_fixture_matches_crosswalk_source_refs(profile_id: str) -> None:
    fixture = _load_fixture()["profiles"][profile_id]
    requirements = _load_crosswalk_requirements()
    requirement = requirements[fixture["requirement_id"]]

    assert set(fixture["crosswalk_source_refs"]) <= set(requirement["source_refs"])
    assert requirement["coverage_status"] == "implemented_under_audit"
    assert "comparison" in requirement["notes"]


@pytest.mark.parametrize("profile_id", sorted(_load_fixture()["profiles"]))
def test_profile_fixture_matches_support_matrix_rows(profile_id: str) -> None:
    fixture = _load_fixture()["profiles"][profile_id]
    profile = CvaRegulatoryProfile(profile_id)
    matrix = [cell for cell in cva_profile_support_matrix() if cell.profile is profile]

    for method_id, expected_citation in fixture["method_citations"].items():
        cell = _method_cell(matrix, CvaMethod(method_id))
        assert cell.status is CvaSupportStatus.IMPLEMENTED_UNDER_AUDIT
        assert cell.blocker == "none"
        assert cell.citation == expected_citation

    girr_delta = _sa_cva_cell(matrix, SaCvaRiskClass.GIRR, SaCvaRiskMeasure.DELTA)
    assert girr_delta.status is CvaSupportStatus.IMPLEMENTED_UNDER_AUDIT
    assert girr_delta.blocker == "none"
    assert girr_delta.citation == fixture["sa_cva_path_citation"]

    ccs_vega = _sa_cva_cell(
        matrix,
        SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
        SaCvaRiskMeasure.VEGA,
    )
    assert ccs_vega.status is CvaSupportStatus.REGULATORY_ABSENCE
    assert ccs_vega.blocker == "regulatory_absence"

    materiality = next(cell for cell in matrix if cell.method.startswith("MAR50.9"))
    assert materiality.status is CvaSupportStatus.UNSUPPORTED_FAIL_CLOSED
    assert materiality.blocker == "ccr_boundary"


def _fixture_citation_ids(fixture: dict[str, Any]) -> tuple[str, ...]:
    return (
        str(fixture["ba_cva_citation_id"]),
        str(fixture["sa_cva_citation_id"]),
        str(fixture["hedge_citation_id"]),
        str(fixture["materiality_citation_id"]),
    )


def _method_cell(matrix: list[Any], method: CvaMethod) -> Any:
    return next(cell for cell in matrix if cell.method == method.value and cell.risk_class is None)


def _sa_cva_cell(
    matrix: list[Any],
    risk_class: SaCvaRiskClass,
    risk_measure: SaCvaRiskMeasure,
) -> Any:
    return next(
        cell
        for cell in matrix
        if cell.method == CvaMethod.SA_CVA.value
        and cell.risk_class is risk_class
        and cell.risk_measure is risk_measure
    )
