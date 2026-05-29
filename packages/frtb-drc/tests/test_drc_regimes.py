from __future__ import annotations

import json
import re
from typing import cast

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_drc import (
    US_NPR_2_0_PROFILE_ID,
    DrcInputError,
    DrcRiskClass,
    ensure_risk_class_supported,
    get_rule_profile,
    profile_content_hash,
    regimes,
)


def test_us_npr_profile_supports_only_non_securitisation_initially() -> None:
    profile = get_rule_profile(US_NPR_2_0_PROFILE_ID)

    assert DrcRiskClass.NON_SECURITISATION in profile.supported_risk_classes
    assert DrcRiskClass.SECURITISATION_NON_CTP not in profile.supported_risk_classes
    assert DrcRiskClass.CORRELATION_TRADING_PORTFOLIO not in profile.supported_risk_classes


def test_unsupported_risk_classes_fail_closed() -> None:
    profile = get_rule_profile(US_NPR_2_0_PROFILE_ID)

    with pytest.raises(UnsupportedRegulatoryFeatureError, match="securitisation non-CTP"):
        ensure_risk_class_supported(profile, DrcRiskClass.SECURITISATION_NON_CTP)

    with pytest.raises(UnsupportedRegulatoryFeatureError, match="CTP DRC"):
        ensure_risk_class_supported(profile, DrcRiskClass.CORRELATION_TRADING_PORTFOLIO)


def test_supported_risk_class_passes_gate() -> None:
    profile = get_rule_profile(US_NPR_2_0_PROFILE_ID)

    ensure_risk_class_supported(profile, DrcRiskClass.NON_SECURITISATION)


def test_unknown_profile_is_input_error() -> None:
    with pytest.raises(DrcInputError, match="unknown DRC rule profile"):
        get_rule_profile("UNKNOWN")


def test_profile_hash_is_deterministic_sha256() -> None:
    profile = get_rule_profile(US_NPR_2_0_PROFILE_ID)

    assert profile.content_hash == profile_content_hash(profile)
    assert re.fullmatch(r"[0-9a-f]{64}", profile.content_hash)


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
