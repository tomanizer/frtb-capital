"""
Equity delta reference data for BASEL_MAR21.

Regulatory traceability:
    Basel MAR21.12 — equity delta and vega risk factors.
    Basel MAR21.71-MAR21.80 — buckets (Table 9), weights (Table 10), correlations.
"""

from __future__ import annotations

from dataclasses import dataclass

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.data_models import SbmRegulatoryProfile
from frtb_sbm.validation import SbmInputError, ensure_sbm_profile_known

BASEL_MAR21_URL = "https://www.bis.org/basel_framework/chapter/MAR/21.htm"

EQUITY_SPOT_RISK_FACTOR = "SPOT"
EQUITY_REPO_RISK_FACTOR = "REPO"
EQUITY_SAME_ISSUER_SPOT_REPO_CORRELATION = 0.999
EQUITY_CROSS_ISSUER_SPOT_REPO_FACTOR = 0.999
EQUITY_OTHER_SECTOR_BUCKET = "11"

_EQUITY_BUCKET_CITATION = "basel_mar21_72"
_EQUITY_WEIGHT_CITATION = "basel_mar21_77"
_EQUITY_INTRA_CITATION = "basel_mar21_78"
_EQUITY_OTHER_SECTOR_CITATION = "basel_mar21_79"
_EQUITY_INTER_CITATION = "basel_mar21_80"


@dataclass(frozen=True)
class SbmEquityBucketDefinition:
    """Profile-specific equity bucket metadata."""

    bucket_id: str
    label: str
    citation_id: str


@dataclass(frozen=True)
class SbmEquityRiskWeightRule:
    """Spot and repo delta risk weights for one equity bucket."""

    bucket_id: str
    spot_risk_weight: float
    repo_risk_weight: float
    citation_id: str


_BASEL_EQUITY_BUCKETS: tuple[SbmEquityBucketDefinition, ...] = (
    SbmEquityBucketDefinition("1", "large_emerging_consumer", _EQUITY_BUCKET_CITATION),
    SbmEquityBucketDefinition("2", "large_emerging_telecom_industrial", _EQUITY_BUCKET_CITATION),
    SbmEquityBucketDefinition("3", "large_emerging_energy_agri_mfg", _EQUITY_BUCKET_CITATION),
    SbmEquityBucketDefinition("4", "large_emerging_financial_tech", _EQUITY_BUCKET_CITATION),
    SbmEquityBucketDefinition("5", "large_advanced_consumer", _EQUITY_BUCKET_CITATION),
    SbmEquityBucketDefinition("6", "large_advanced_telecom_industrial", _EQUITY_BUCKET_CITATION),
    SbmEquityBucketDefinition("7", "large_advanced_energy_agri_mfg", _EQUITY_BUCKET_CITATION),
    SbmEquityBucketDefinition("8", "large_advanced_financial_tech", _EQUITY_BUCKET_CITATION),
    SbmEquityBucketDefinition("9", "small_emerging_all_sectors", _EQUITY_BUCKET_CITATION),
    SbmEquityBucketDefinition("10", "small_advanced_all_sectors", _EQUITY_BUCKET_CITATION),
    SbmEquityBucketDefinition("11", "other_sector", _EQUITY_BUCKET_CITATION),
    SbmEquityBucketDefinition("12", "large_advanced_index", _EQUITY_BUCKET_CITATION),
    SbmEquityBucketDefinition("13", "other_index", _EQUITY_BUCKET_CITATION),
)

_BASEL_EQUITY_RISK_WEIGHTS: tuple[SbmEquityRiskWeightRule, ...] = (
    SbmEquityRiskWeightRule("1", 0.55, 0.0055, _EQUITY_WEIGHT_CITATION),
    SbmEquityRiskWeightRule("2", 0.60, 0.0060, _EQUITY_WEIGHT_CITATION),
    SbmEquityRiskWeightRule("3", 0.45, 0.0045, _EQUITY_WEIGHT_CITATION),
    SbmEquityRiskWeightRule("4", 0.55, 0.0055, _EQUITY_WEIGHT_CITATION),
    SbmEquityRiskWeightRule("5", 0.30, 0.0030, _EQUITY_WEIGHT_CITATION),
    SbmEquityRiskWeightRule("6", 0.35, 0.0035, _EQUITY_WEIGHT_CITATION),
    SbmEquityRiskWeightRule("7", 0.40, 0.0040, _EQUITY_WEIGHT_CITATION),
    SbmEquityRiskWeightRule("8", 0.50, 0.0050, _EQUITY_WEIGHT_CITATION),
    SbmEquityRiskWeightRule("9", 0.70, 0.0070, _EQUITY_WEIGHT_CITATION),
    SbmEquityRiskWeightRule("10", 0.50, 0.0050, _EQUITY_WEIGHT_CITATION),
    SbmEquityRiskWeightRule("11", 0.70, 0.0070, _EQUITY_WEIGHT_CITATION),
    SbmEquityRiskWeightRule("12", 0.15, 0.0015, _EQUITY_WEIGHT_CITATION),
    SbmEquityRiskWeightRule("13", 0.25, 0.0025, _EQUITY_WEIGHT_CITATION),
)

_PROFILE_EQUITY_BUCKETS: dict[SbmRegulatoryProfile, tuple[SbmEquityBucketDefinition, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21: _BASEL_EQUITY_BUCKETS,
}

_PROFILE_EQUITY_RISK_WEIGHTS: dict[SbmRegulatoryProfile, tuple[SbmEquityRiskWeightRule, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21: _BASEL_EQUITY_RISK_WEIGHTS,
}

_EQUITY_SPOT_SPOT_CORRELATIONS: dict[str, float] = {
    "1": 0.15,
    "2": 0.15,
    "3": 0.15,
    "4": 0.15,
    "5": 0.25,
    "6": 0.25,
    "7": 0.25,
    "8": 0.25,
    "9": 0.075,
    "10": 0.125,
    "12": 0.80,
    "13": 0.80,
}


def equity_buckets_for_profile(
    profile: SbmRegulatoryProfile | str,
) -> tuple[SbmEquityBucketDefinition, ...]:
    """Return cited equity bucket definitions for a supported profile."""

    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    _ensure_equity_delta_supported(profile)
    return _PROFILE_EQUITY_BUCKETS[resolved]


def equity_bucket_definition(
    profile: SbmRegulatoryProfile | str,
    bucket_id: str,
) -> SbmEquityBucketDefinition:
    """Return the equity bucket definition for a canonical bucket id."""

    _ensure_equity_delta_supported(profile)
    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    normalised = _require_text(bucket_id, "bucket_id")
    for bucket in _PROFILE_EQUITY_BUCKETS[resolved]:
        if bucket.bucket_id == normalised:
            return bucket
    raise SbmInputError(
        f"no equity bucket definition for bucket_id {normalised}",
        field="bucket_id",
    )


def equity_delta_risk_weight(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket_id: str,
    risk_factor: str,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited equity delta risk weight for spot or repo sensitivities."""

    _ensure_equity_delta_supported(profile)
    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    normalised_bucket = _require_text(bucket_id, "bucket_id")
    normalised_factor = _normalise_equity_risk_factor(risk_factor)
    equity_bucket_definition(profile, normalised_bucket)
    for rule in _PROFILE_EQUITY_RISK_WEIGHTS[resolved]:
        if rule.bucket_id != normalised_bucket:
            continue
        if normalised_factor == EQUITY_SPOT_RISK_FACTOR:
            return rule.spot_risk_weight, (rule.citation_id,)
        return rule.repo_risk_weight, (rule.citation_id,)
    raise SbmInputError(
        f"no equity risk weight for bucket_id {normalised_bucket}",
        field="bucket_id",
    )


def equity_delta_intra_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket_id: str,
    risk_factor_a: str,
    risk_factor_b: str,
    issuer_a: str,
    issuer_b: str,
) -> tuple[float, tuple[str, ...]]:
    """Return MAR21.78 intra-bucket correlation for two weighted equity sensitivities."""

    _ensure_equity_delta_supported(profile)
    normalised_bucket = _require_text(bucket_id, "bucket_id")
    equity_bucket_definition(profile, normalised_bucket)
    if normalised_bucket == EQUITY_OTHER_SECTOR_BUCKET:
        raise UnsupportedRegulatoryFeatureError(
            "equity bucket 11 uses absolute-weight aggregation; pairwise correlations do not apply"
        )

    factor_a = _normalise_equity_risk_factor(risk_factor_a)
    factor_b = _normalise_equity_risk_factor(risk_factor_b)
    issuer_a_norm = _require_text(issuer_a, "qualifier")
    issuer_b_norm = _require_text(issuer_b, "qualifier")

    if factor_a == factor_b:
        if issuer_a_norm == issuer_b_norm:
            return 1.0, (_EQUITY_INTRA_CITATION,)
        return _EQUITY_SPOT_SPOT_CORRELATIONS[normalised_bucket], (_EQUITY_INTRA_CITATION,)

    if issuer_a_norm == issuer_b_norm:
        return EQUITY_SAME_ISSUER_SPOT_REPO_CORRELATION, (_EQUITY_INTRA_CITATION,)

    base = _EQUITY_SPOT_SPOT_CORRELATIONS[normalised_bucket]
    return base * EQUITY_CROSS_ISSUER_SPOT_REPO_FACTOR, (_EQUITY_INTRA_CITATION,)


def equity_inter_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket1: str,
    bucket2: str,
) -> tuple[float, tuple[str, ...]]:
    """Return MAR21.80 inter-bucket gamma for two equity buckets."""

    _ensure_equity_delta_supported(profile)
    b1 = _require_equity_bucket_number(bucket1)
    b2 = _require_equity_bucket_number(bucket2)
    equity_bucket_definition(profile, str(b1))
    equity_bucket_definition(profile, str(b2))
    if b1 == b2:
        return 1.0, (_EQUITY_INTER_CITATION,)
    if b1 == 11 or b2 == 11:
        return 0.0, (_EQUITY_INTER_CITATION,)
    if {b1, b2} == {12, 13}:
        return 0.75, (_EQUITY_INTER_CITATION,)
    if b1 <= 10 and b2 <= 10:
        return 0.15, (_EQUITY_INTER_CITATION,)
    return 0.45, (_EQUITY_INTER_CITATION,)


def equity_reference_payload(profile: SbmRegulatoryProfile | str) -> dict[str, object]:
    """Return equity tables for profile hashing."""

    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    _ensure_equity_delta_supported(profile)
    return {
        "equity_buckets": [
            {
                "bucket_id": bucket.bucket_id,
                "label": bucket.label,
                "citation_id": bucket.citation_id,
            }
            for bucket in _PROFILE_EQUITY_BUCKETS[resolved]
        ],
        "equity_delta_risk_weights": [
            {
                "bucket_id": rule.bucket_id,
                "spot_risk_weight": rule.spot_risk_weight,
                "repo_risk_weight": rule.repo_risk_weight,
                "citation_id": rule.citation_id,
            }
            for rule in _PROFILE_EQUITY_RISK_WEIGHTS[resolved]
        ],
        "equity_other_sector_bucket": EQUITY_OTHER_SECTOR_BUCKET,
        "equity_other_sector_citation_id": _EQUITY_OTHER_SECTOR_CITATION,
    }


def _ensure_equity_delta_supported(profile: SbmRegulatoryProfile | str) -> None:
    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    if resolved is not SbmRegulatoryProfile.BASEL_MAR21:
        raise UnsupportedRegulatoryFeatureError(
            f"equity delta reference data is unsupported for profile {resolved.value}"
        )


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SbmInputError("non-empty text is required", field=field)
    return value.strip()


def _normalise_equity_risk_factor(risk_factor: str) -> str:
    normalised = _require_text(risk_factor, "risk_factor").upper()
    if normalised not in {EQUITY_SPOT_RISK_FACTOR, EQUITY_REPO_RISK_FACTOR}:
        raise SbmInputError(
            "equity delta risk_factor must be SPOT or REPO",
            field="risk_factor",
        )
    return normalised


def _require_equity_bucket_number(bucket_id: str) -> int:
    normalised = _require_text(bucket_id, "bucket_id")
    try:
        bucket_number = int(normalised)
    except ValueError as exc:
        raise SbmInputError(
            "equity bucket_id must be a numeric bucket label",
            field="bucket_id",
        ) from exc
    if bucket_number < 1 or bucket_number > 13:
        raise SbmInputError(
            "equity bucket_id must be between 1 and 13",
            field="bucket_id",
        )
    return bucket_number


EQUITY_BASEL_CITATIONS = {
    "basel_mar21_12": {
        "source_id": "basel_mar21_sensitivities_based_method",
        "location": "MAR21.12",
        "url": BASEL_MAR21_URL,
        "note": "Equity delta and vega risk-factor definitions.",
    },
    "basel_mar21_72": {
        "source_id": "basel_mar21_sensitivities_based_method",
        "location": "MAR21.72",
        "url": BASEL_MAR21_URL,
        "note": "Equity delta bucket assignment (Table 9).",
    },
    "basel_mar21_77": {
        "source_id": "basel_mar21_sensitivities_based_method",
        "location": "MAR21.77",
        "url": BASEL_MAR21_URL,
        "note": "Equity delta risk weights for spot and repo (Table 10).",
    },
    "basel_mar21_78": {
        "source_id": "basel_mar21_sensitivities_based_method",
        "location": "MAR21.78",
        "url": BASEL_MAR21_URL,
        "note": "Equity delta intra-bucket correlation parameters.",
    },
    "basel_mar21_79": {
        "source_id": "basel_mar21_sensitivities_based_method",
        "location": "MAR21.79",
        "url": BASEL_MAR21_URL,
        "note": "Equity other-sector bucket absolute-weight aggregation.",
    },
    "basel_mar21_80": {
        "source_id": "basel_mar21_sensitivities_based_method",
        "location": "MAR21.80",
        "url": BASEL_MAR21_URL,
        "note": "Equity delta inter-bucket correlation parameters.",
    },
}


__all__ = [
    "EQUITY_OTHER_SECTOR_BUCKET",
    "EQUITY_REPO_RISK_FACTOR",
    "EQUITY_SPOT_RISK_FACTOR",
    "SbmEquityBucketDefinition",
    "SbmEquityRiskWeightRule",
    "equity_bucket_definition",
    "equity_buckets_for_profile",
    "equity_delta_intra_bucket_correlation",
    "equity_delta_risk_weight",
    "equity_inter_bucket_correlation",
    "equity_reference_payload",
]
