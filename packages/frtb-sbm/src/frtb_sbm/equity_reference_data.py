"""
Equity delta reference data for BASEL_MAR21.

Regulatory traceability:
    Basel MAR21.12 — equity delta and vega risk factors.
    Basel MAR21.71-MAR21.80 — buckets (Table 9), weights (Table 10), correlations.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm._text import require_text as _require_text
from frtb_sbm.data_models import SbmRegulatoryProfile
from frtb_sbm.reference_citations_eu_crr3 import eu_crr3_citation_id_for_basel
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

_US_NPR_EQUITY_BUCKET_CITATION = "us_npr_91_fr_14952_va7a_equity_delta_buckets"
_US_NPR_EQUITY_WEIGHT_CITATION = "us_npr_91_fr_14952_va7a_equity_delta_weights"
_US_NPR_EQUITY_INTRA_CITATION = "us_npr_91_fr_14952_va7a_equity_delta_intra"
_US_NPR_EQUITY_OTHER_SECTOR_CITATION = "us_npr_91_fr_14952_va7a_equity_delta_other_sector"
_US_NPR_EQUITY_INTER_CITATION = "us_npr_91_fr_14952_va7a_equity_delta_inter"

_PRA_UK_CRR_EQUITY_BUCKET_CITATION = "pra_uk_crr_325ap_equity_buckets"
_PRA_UK_CRR_EQUITY_WEIGHT_CITATION = "pra_uk_crr_325ap_equity_weights"
_PRA_UK_CRR_EQUITY_INTRA_CITATION = "pra_uk_crr_325aq_equity_intra"
_PRA_UK_CRR_EQUITY_OTHER_SECTOR_CITATION = "pra_uk_crr_325aq_equity_other_sector"
_PRA_UK_CRR_EQUITY_INTER_CITATION = "pra_uk_crr_325ar_equity_inter"


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

_EU_CRR3_EQUITY_BUCKETS: tuple[SbmEquityBucketDefinition, ...] = tuple(
    replace(bucket, citation_id=eu_crr3_citation_id_for_basel(bucket.citation_id))
    for bucket in _BASEL_EQUITY_BUCKETS
)

_US_NPR_EQUITY_BUCKETS: tuple[SbmEquityBucketDefinition, ...] = tuple(
    replace(bucket, citation_id=_US_NPR_EQUITY_BUCKET_CITATION) for bucket in _BASEL_EQUITY_BUCKETS
)

_PRA_UK_CRR_EQUITY_BUCKETS: tuple[SbmEquityBucketDefinition, ...] = tuple(
    replace(bucket, citation_id=_PRA_UK_CRR_EQUITY_BUCKET_CITATION)
    for bucket in _BASEL_EQUITY_BUCKETS
)

_EU_CRR3_EQUITY_RISK_WEIGHTS: tuple[SbmEquityRiskWeightRule, ...] = tuple(
    replace(rule, citation_id=eu_crr3_citation_id_for_basel(rule.citation_id))
    for rule in _BASEL_EQUITY_RISK_WEIGHTS
)

_US_NPR_EQUITY_RISK_WEIGHTS: tuple[SbmEquityRiskWeightRule, ...] = tuple(
    replace(rule, citation_id=_US_NPR_EQUITY_WEIGHT_CITATION) for rule in _BASEL_EQUITY_RISK_WEIGHTS
)

_PRA_UK_CRR_EQUITY_RISK_WEIGHTS: tuple[SbmEquityRiskWeightRule, ...] = tuple(
    replace(rule, citation_id=_PRA_UK_CRR_EQUITY_WEIGHT_CITATION)
    for rule in _BASEL_EQUITY_RISK_WEIGHTS
)

_PROFILE_EQUITY_BUCKETS: dict[SbmRegulatoryProfile, tuple[SbmEquityBucketDefinition, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21: _BASEL_EQUITY_BUCKETS,
    SbmRegulatoryProfile.US_NPR_2_0: _US_NPR_EQUITY_BUCKETS,
    SbmRegulatoryProfile.EU_CRR3: _EU_CRR3_EQUITY_BUCKETS,
    SbmRegulatoryProfile.PRA_UK_CRR: _PRA_UK_CRR_EQUITY_BUCKETS,
}

_PROFILE_EQUITY_RISK_WEIGHTS: dict[SbmRegulatoryProfile, tuple[SbmEquityRiskWeightRule, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21: _BASEL_EQUITY_RISK_WEIGHTS,
    SbmRegulatoryProfile.US_NPR_2_0: _US_NPR_EQUITY_RISK_WEIGHTS,
    SbmRegulatoryProfile.EU_CRR3: _EU_CRR3_EQUITY_RISK_WEIGHTS,
    SbmRegulatoryProfile.PRA_UK_CRR: _PRA_UK_CRR_EQUITY_RISK_WEIGHTS,
}

_PROFILE_EQUITY_INTRA_CITATIONS: dict[SbmRegulatoryProfile, str] = {
    SbmRegulatoryProfile.BASEL_MAR21: _EQUITY_INTRA_CITATION,
    SbmRegulatoryProfile.US_NPR_2_0: _US_NPR_EQUITY_INTRA_CITATION,
    SbmRegulatoryProfile.EU_CRR3: eu_crr3_citation_id_for_basel(_EQUITY_INTRA_CITATION),
    SbmRegulatoryProfile.PRA_UK_CRR: _PRA_UK_CRR_EQUITY_INTRA_CITATION,
}

_PROFILE_EQUITY_OTHER_SECTOR_CITATIONS: dict[SbmRegulatoryProfile, str] = {
    SbmRegulatoryProfile.BASEL_MAR21: _EQUITY_OTHER_SECTOR_CITATION,
    SbmRegulatoryProfile.US_NPR_2_0: _US_NPR_EQUITY_OTHER_SECTOR_CITATION,
    SbmRegulatoryProfile.EU_CRR3: eu_crr3_citation_id_for_basel(_EQUITY_OTHER_SECTOR_CITATION),
    SbmRegulatoryProfile.PRA_UK_CRR: _PRA_UK_CRR_EQUITY_OTHER_SECTOR_CITATION,
}

_PROFILE_EQUITY_INTER_CITATIONS: dict[SbmRegulatoryProfile, str] = {
    SbmRegulatoryProfile.BASEL_MAR21: _EQUITY_INTER_CITATION,
    SbmRegulatoryProfile.US_NPR_2_0: _US_NPR_EQUITY_INTER_CITATION,
    SbmRegulatoryProfile.EU_CRR3: eu_crr3_citation_id_for_basel(_EQUITY_INTER_CITATION),
    SbmRegulatoryProfile.PRA_UK_CRR: _PRA_UK_CRR_EQUITY_INTER_CITATION,
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
    """Return cited equity bucket definitions for a supported profile.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.

    Returns
    -------
    tuple[SbmEquityBucketDefinition, ...]
    """

    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    _ensure_equity_delta_supported(profile)
    return _PROFILE_EQUITY_BUCKETS[resolved]


def equity_bucket_definition(
    profile: SbmRegulatoryProfile | str,
    bucket_id: str,
) -> SbmEquityBucketDefinition:
    """Return the equity bucket definition for a canonical bucket id.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    bucket_id : str
        See signature.

    Returns
    -------
    SbmEquityBucketDefinition
    """

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
    """Return the cited equity delta risk weight for spot or repo sensitivities.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    bucket_id : str
        See signature.
    risk_factor : str
        See signature.

    Returns
    -------
    tuple[float, tuple[str, ...]]
    """

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
    """Return MAR21.78 intra-bucket correlation for two weighted equity sensitivities.
    Parameters
    ----------
    profile, bucket_id, risk_factor_a, risk_factor_b, issuer_a, issuer_b :
        See function signature for types and defaults.

    Returns
    -------
    tuple[float, tuple[str, ...]]
    """

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
            return 1.0, (_equity_intra_citation(profile),)
        return _EQUITY_SPOT_SPOT_CORRELATIONS[normalised_bucket], (_equity_intra_citation(profile),)

    if issuer_a_norm == issuer_b_norm:
        return EQUITY_SAME_ISSUER_SPOT_REPO_CORRELATION, (_equity_intra_citation(profile),)

    base = _EQUITY_SPOT_SPOT_CORRELATIONS[normalised_bucket]
    return base * EQUITY_CROSS_ISSUER_SPOT_REPO_FACTOR, (_equity_intra_citation(profile),)


def equity_inter_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket1: str,
    bucket2: str,
) -> tuple[float, tuple[str, ...]]:
    """Return MAR21.80 inter-bucket gamma for two equity buckets.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    bucket1 : str
        See signature.
    bucket2 : str
        See signature.

    Returns
    -------
    tuple[float, tuple[str, ...]]
    """

    _ensure_equity_delta_supported(profile)
    b1 = _require_equity_bucket_number(bucket1)
    b2 = _require_equity_bucket_number(bucket2)
    equity_bucket_definition(profile, str(b1))
    equity_bucket_definition(profile, str(b2))
    if b1 == b2:
        return 1.0, (_equity_inter_citation(profile),)
    if b1 == 11 or b2 == 11:
        return 0.0, (_equity_inter_citation(profile),)
    if {b1, b2} == {12, 13}:
        return 0.75, (_equity_inter_citation(profile),)
    if b1 <= 10 and b2 <= 10:
        return 0.15, (_equity_inter_citation(profile),)
    return 0.45, (_equity_inter_citation(profile),)


def equity_delta_intra_bucket_citation_ids(
    profile: SbmRegulatoryProfile | str,
) -> tuple[str, ...]:
    """Return profile-owned equity delta intra-bucket correlation citation ids.

    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        Regulatory profile that owns the equity delta correlation rule.

    Returns
    -------
    tuple[str, ...]
        Citation identifiers for equity delta intra-bucket correlation.
    """

    _ensure_equity_delta_supported(profile)
    return (_equity_intra_citation(profile),)


def equity_inter_bucket_citation_ids(profile: SbmRegulatoryProfile | str) -> tuple[str, ...]:
    """Return profile-owned equity delta inter-bucket correlation citation ids.

    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        Regulatory profile that owns the equity delta correlation rule.

    Returns
    -------
    tuple[str, ...]
        Citation identifiers for equity delta inter-bucket correlation.
    """

    _ensure_equity_delta_supported(profile)
    return (_equity_inter_citation(profile),)


def equity_other_sector_citation_ids(profile: SbmRegulatoryProfile | str) -> tuple[str, ...]:
    """Return profile-owned equity bucket 11 absolute-weight citation ids.

    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        Regulatory profile that owns the equity bucket 11 absolute-weight rule.

    Returns
    -------
    tuple[str, ...]
        Citation identifiers for the equity other-sector bucket treatment.
    """

    _ensure_equity_delta_supported(profile)
    return (_equity_other_sector_citation(profile),)


def equity_reference_payload(profile: SbmRegulatoryProfile | str) -> dict[str, object]:
    """Return equity tables for profile hashing.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.

    Returns
    -------
    dict[str, object]
    """

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
        "equity_other_sector_citation_id": _equity_other_sector_citation(profile),
    }


def _ensure_equity_delta_supported(profile: SbmRegulatoryProfile | str) -> None:
    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    if resolved not in _PROFILE_EQUITY_BUCKETS:
        raise UnsupportedRegulatoryFeatureError(
            f"equity delta reference data is unsupported for profile {resolved.value}"
        )


def _equity_intra_citation(profile: SbmRegulatoryProfile | str) -> str:
    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    citation = _PROFILE_EQUITY_INTRA_CITATIONS.get(resolved)
    if citation is None:
        raise UnsupportedRegulatoryFeatureError(
            f"Profile {resolved.value} is not supported for equity intra citations."
        )
    return citation


def _equity_other_sector_citation(profile: SbmRegulatoryProfile | str) -> str:
    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    citation = _PROFILE_EQUITY_OTHER_SECTOR_CITATIONS.get(resolved)
    if citation is None:
        raise UnsupportedRegulatoryFeatureError(
            f"Profile {resolved.value} is not supported for equity other sector citations."
        )
    return citation


def _equity_inter_citation(profile: SbmRegulatoryProfile | str) -> str:
    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    citation = _PROFILE_EQUITY_INTER_CITATIONS.get(resolved)
    if citation is None:
        raise UnsupportedRegulatoryFeatureError(
            f"Profile {resolved.value} is not supported for equity inter citations."
        )
    return citation


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
    "equity_delta_intra_bucket_citation_ids",
    "equity_delta_intra_bucket_correlation",
    "equity_delta_risk_weight",
    "equity_inter_bucket_citation_ids",
    "equity_inter_bucket_correlation",
    "equity_other_sector_citation_ids",
    "equity_reference_payload",
]
