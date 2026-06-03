from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import cast

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_drc import (
    BASEL_MAR22_PROFILE_ID,
    EU_CRR3_PROFILE_ID,
    PRA_UK_CRR_PROFILE_ID,
    US_NPR_2_0_PROFILE_ID,
    DrcInputError,
    DrcRiskClass,
    DrcRuleProfile,
    drc_profile_support_matrix,
    ensure_risk_class_supported,
    get_rule_profile,
    profile_content_hash,
    regimes,
)


def test_us_npr_profile_supports_row_drc_risk_classes() -> None:
    profile = get_rule_profile(US_NPR_2_0_PROFILE_ID)

    assert DrcRiskClass.NON_SECURITISATION in profile.supported_risk_classes
    assert DrcRiskClass.SECURITISATION_NON_CTP in profile.supported_risk_classes
    assert DrcRiskClass.CORRELATION_TRADING_PORTFOLIO in profile.supported_risk_classes
    assert profile.securitisation_non_ctp_fair_value_cap_allowed is True
    assert "US_NPR_210_C_3_III" in profile.securitisation_non_ctp_fair_value_cap_citation_ids
    assert "BASEL_MAR22_34" in profile.securitisation_non_ctp_fair_value_cap_citation_ids


def test_basel_profile_supports_nonsec_and_securitisation_non_ctp() -> None:
    profile = get_rule_profile(BASEL_MAR22_PROFILE_ID)

    assert profile.supported_risk_classes == frozenset(
        {
            DrcRiskClass.NON_SECURITISATION,
            DrcRiskClass.SECURITISATION_NON_CTP,
        }
    )
    assert "BASEL_MAR22_24" in profile.citations
    assert "BASEL_MAR22_34" in profile.citations
    assert profile.securitisation_non_ctp_fair_value_cap_allowed is True
    assert profile.securitisation_non_ctp_fair_value_cap_citation_ids == ("BASEL_MAR22_34",)
    ensure_risk_class_supported(profile, DrcRiskClass.NON_SECURITISATION)
    ensure_risk_class_supported(profile, DrcRiskClass.SECURITISATION_NON_CTP)
    with pytest.raises(UnsupportedRegulatoryFeatureError, match=r"MAR22\.42"):
        ensure_risk_class_supported(profile, DrcRiskClass.CORRELATION_TRADING_PORTFOLIO)


@pytest.mark.parametrize("profile_id", [EU_CRR3_PROFILE_ID, PRA_UK_CRR_PROFILE_ID])
def test_comparison_profiles_are_known_and_fail_closed(profile_id: str) -> None:
    profile = get_rule_profile(profile_id)

    assert profile.supported_risk_classes == frozenset()
    with pytest.raises(UnsupportedRegulatoryFeatureError, match=profile_id):
        ensure_risk_class_supported(profile, DrcRiskClass.NON_SECURITISATION)


def test_unsupported_risk_classes_fail_closed() -> None:
    profile = DrcRuleProfile(
        profile_id="TEST",
        regulator="Test",
        version="test",
        publication_date=date(2026, 1, 1),
        effective_date=None,
        status="test",
        supported_risk_classes=frozenset({DrcRiskClass.NON_SECURITISATION}),
        unsupported_features={
            DrcRiskClass.SECURITISATION_NON_CTP: "test securitisation non-CTP gap"
        },
        content_hash="test",
    )

    with pytest.raises(UnsupportedRegulatoryFeatureError, match="test securitisation non-CTP gap"):
        ensure_risk_class_supported(profile, DrcRiskClass.SECURITISATION_NON_CTP)


def test_supported_risk_class_passes_gate() -> None:
    profile = get_rule_profile(US_NPR_2_0_PROFILE_ID)

    ensure_risk_class_supported(profile, DrcRiskClass.NON_SECURITISATION)
    ensure_risk_class_supported(profile, DrcRiskClass.SECURITISATION_NON_CTP)
    ensure_risk_class_supported(profile, DrcRiskClass.CORRELATION_TRADING_PORTFOLIO)


def test_profile_support_matrix_marks_basel_securitisation_non_ctp_supported() -> None:
    cells = {(cell.profile_id, cell.risk_class): cell for cell in drc_profile_support_matrix()}

    basel_sec = cells[(BASEL_MAR22_PROFILE_ID, DrcRiskClass.SECURITISATION_NON_CTP)]
    basel_ctp = cells[(BASEL_MAR22_PROFILE_ID, DrcRiskClass.CORRELATION_TRADING_PORTFOLIO)]

    assert basel_sec.status == "SUPPORTED"
    assert "BASEL_MAR22_34" in basel_sec.citation_ids
    assert basel_sec.next_step == "Maintain Basel-specific typed evidence fixtures."
    assert basel_ctp.status == "FAIL_CLOSED"
    assert "BASEL_MAR22_42" in basel_ctp.citation_ids


def test_profile_support_matrix_covers_every_known_profile_path() -> None:
    cells = drc_profile_support_matrix()
    expected = {
        (profile_id, risk_class)
        for profile_id in (
            US_NPR_2_0_PROFILE_ID,
            BASEL_MAR22_PROFILE_ID,
            EU_CRR3_PROFILE_ID,
            PRA_UK_CRR_PROFILE_ID,
        )
        for risk_class in DrcRiskClass
    }

    assert {(cell.profile_id, cell.risk_class) for cell in cells} == expected
    for cell in cells:
        profile = get_rule_profile(cell.profile_id)
        assert cell.status in {"SUPPORTED", "FAIL_CLOSED"}
        assert cell.reason
        assert cell.citation_ids
        assert cell.next_step
        if cell.status == "SUPPORTED":
            ensure_risk_class_supported(profile, cell.risk_class)
        else:
            with pytest.raises(UnsupportedRegulatoryFeatureError):
                ensure_risk_class_supported(profile, cell.risk_class)


def test_profile_support_matrix_cells_are_json_serialisable() -> None:
    payload = tuple(cell.as_dict() for cell in drc_profile_support_matrix())

    assert payload[0]["profile_id"] == US_NPR_2_0_PROFILE_ID
    json.dumps(payload, sort_keys=True)


def test_profile_support_matrix_doc_matches_public_api() -> None:
    docs_path = (
        Path(__file__).resolve().parents[3] / "docs/modules/frtb-drc/PROFILE_SUPPORT_MATRIX.md"
    )
    documented = _profile_support_doc_rows(docs_path)
    actual = {
        (cell.profile_id, cell.risk_class.value): {
            "status": cell.status,
            "reason": cell.reason,
            "citation_ids": cell.citation_ids,
            "next_step": cell.next_step,
        }
        for cell in drc_profile_support_matrix()
    }

    assert documented == actual


def test_unknown_profile_is_input_error() -> None:
    with pytest.raises(DrcInputError, match="unknown DRC rule profile"):
        get_rule_profile("UNKNOWN")


def test_profile_hash_is_deterministic_sha256() -> None:
    profile = get_rule_profile(US_NPR_2_0_PROFILE_ID)

    assert profile.content_hash == profile_content_hash(profile)
    assert re.fullmatch(r"[0-9a-f]{64}", profile.content_hash)


def _profile_support_doc_rows(path: Path) -> dict[tuple[str, str], dict[str, object]]:
    rows: dict[tuple[str, str], dict[str, object]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        profile_id, risk_class, status, reason, citation_ids, next_step = cells
        rows[(_unquote(profile_id), _unquote(risk_class))] = {
            "status": _unquote(status),
            "reason": reason,
            "citation_ids": tuple(_unquote(item.strip()) for item in citation_ids.split(",")),
            "next_step": next_step,
        }
    return rows


def _unquote(value: str) -> str:
    return value.removeprefix("`").removesuffix("`")


def test_profile_hash_changes_when_reference_data_payload_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = get_rule_profile(US_NPR_2_0_PROFILE_ID)
    baseline_hash = profile_content_hash(profile)
    original_payload = regimes.profile_reference_data_payload

    monkeypatch.setattr(
        regimes,
        "profile_reference_data_payload",
        lambda profile_id: {
            **original_payload(profile_id),
            "risk_weight_rules": [
                {
                    "bucket_key": "CORPORATE",
                    "credit_quality": "INVESTMENT_GRADE",
                    "risk_weight": 0.5,
                }
            ],
        },
    )

    assert profile_content_hash(profile) != baseline_hash


def test_profile_as_dict_is_json_serialisable() -> None:
    profile = get_rule_profile(US_NPR_2_0_PROFILE_ID)

    as_dict = profile.as_dict()
    citations = cast(dict[str, object], as_dict["citations"])

    assert as_dict["profile_id"] == US_NPR_2_0_PROFILE_ID
    assert "US_NPR_210_B_1_IV" in citations
    json.dumps(as_dict, sort_keys=True)
