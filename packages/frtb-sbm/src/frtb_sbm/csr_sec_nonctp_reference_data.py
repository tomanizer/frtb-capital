"""
CSR securitisation non-CTP delta reference data for BASEL_MAR21.

Regulatory traceability:
    Basel MAR21.10 — tranche credit-spread delta risk factors.
    Basel MAR21.61-MAR21.70 — buckets (Table 7), weights (Table 8),
    intra-bucket correlations, other-sector rule, zero inter-bucket gamma.
"""

from __future__ import annotations

from dataclasses import dataclass

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.data_models import SbmRegulatoryProfile
from frtb_sbm.validation import SbmInputError, ensure_sbm_profile_known

CSR_SEC_BOND_RISK_FACTOR = "BOND"
CSR_SEC_CDS_RISK_FACTOR = "CDS"
CSR_SEC_OTHER_SECTOR_BUCKET = "25"

CSR_SEC_TRANCHE_SAME_CORRELATION = 1.0
CSR_SEC_TRANCHE_DIFFERENT_CORRELATION = 0.40
CSR_SEC_TENOR_SAME_CORRELATION = 1.0
CSR_SEC_TENOR_DIFFERENT_CORRELATION = 0.80
CSR_SEC_SAME_BASIS_CORRELATION = 1.0
CSR_SEC_DIFFERENT_BASIS_CORRELATION = 0.999
CSR_SEC_INTER_BUCKET_CORRELATION = 0.0

_NON_SENIOR_MULTIPLIER = 1.25
_HIGH_YIELD_MULTIPLIER = 1.75
_OTHER_SECTOR_RISK_WEIGHT = 0.035

_WEIGHT_CITATION = "basel_mar21_65"
_INTRA_CITATION = "basel_mar21_67"
_OTHER_SECTOR_CITATION = "basel_mar21_68"
_INTER_CITATION = "basel_mar21_70"

_CSR_SEC_PRESCRIBED_TENORS: frozenset[str] = frozenset({"6m", "1y", "3y", "5y", "10y"})

_SENIOR_IG_BASE_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("senior_ig_rmbs_prime", 0.009),
    ("senior_ig_rmbs_mid_prime", 0.015),
    ("senior_ig_rmbs_sub_prime", 0.020),
    ("senior_ig_cmbs", 0.020),
    ("senior_ig_abs_student", 0.008),
    ("senior_ig_abs_credit_cards", 0.012),
    ("senior_ig_abs_auto", 0.012),
    ("senior_ig_clo_non_ctp", 0.014),
)


@dataclass(frozen=True)
class SbmCsrSecNonctpBucketDefinition:
    """Profile-specific CSR securitisation non-CTP bucket metadata."""

    bucket_id: str
    label: str
    credit_quality: str
    sector: str
    risk_weight: float
    is_other_sector: bool
    citation_id: str


def _build_basel_csr_sec_nonctp_buckets() -> tuple[SbmCsrSecNonctpBucketDefinition, ...]:
    buckets: list[SbmCsrSecNonctpBucketDefinition] = []
    bucket_number = 1
    for label, base_weight in _SENIOR_IG_BASE_WEIGHTS:
        buckets.append(
            SbmCsrSecNonctpBucketDefinition(
                bucket_id=str(bucket_number),
                label=label,
                credit_quality="SENIOR_IG",
                sector=label,
                risk_weight=base_weight,
                is_other_sector=False,
                citation_id=_WEIGHT_CITATION,
            )
        )
        bucket_number += 1
    for label, base_weight in _SENIOR_IG_BASE_WEIGHTS:
        buckets.append(
            SbmCsrSecNonctpBucketDefinition(
                bucket_id=str(bucket_number),
                label=f"non_senior_{label}",
                credit_quality="NON_SENIOR_IG",
                sector=label,
                risk_weight=base_weight * _NON_SENIOR_MULTIPLIER,
                is_other_sector=False,
                citation_id=_WEIGHT_CITATION,
            )
        )
        bucket_number += 1
    for label, base_weight in _SENIOR_IG_BASE_WEIGHTS:
        buckets.append(
            SbmCsrSecNonctpBucketDefinition(
                bucket_id=str(bucket_number),
                label=f"high_yield_{label}",
                credit_quality="HIGH_YIELD",
                sector=label,
                risk_weight=base_weight * _HIGH_YIELD_MULTIPLIER,
                is_other_sector=False,
                citation_id=_WEIGHT_CITATION,
            )
        )
        bucket_number += 1
    buckets.append(
        SbmCsrSecNonctpBucketDefinition(
            bucket_id=CSR_SEC_OTHER_SECTOR_BUCKET,
            label="other_sector",
            credit_quality="OTHER",
            sector="other_sector",
            risk_weight=_OTHER_SECTOR_RISK_WEIGHT,
            is_other_sector=True,
            citation_id="basel_mar21_66",
        )
    )
    return tuple(buckets)


_BASEL_CSR_SEC_NONCTP_BUCKETS = _build_basel_csr_sec_nonctp_buckets()

_PROFILE_BUCKETS: dict[SbmRegulatoryProfile, tuple[SbmCsrSecNonctpBucketDefinition, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21: _BASEL_CSR_SEC_NONCTP_BUCKETS,
}


def csr_sec_nonctp_buckets_for_profile(
    profile: SbmRegulatoryProfile | str,
) -> tuple[SbmCsrSecNonctpBucketDefinition, ...]:
    """Return cited CSR securitisation non-CTP bucket definitions."""

    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    _ensure_csr_sec_nonctp_delta_supported(profile)
    return _PROFILE_BUCKETS[resolved]


def csr_sec_nonctp_bucket_definition(
    profile: SbmRegulatoryProfile | str,
    bucket_id: str,
) -> SbmCsrSecNonctpBucketDefinition:
    """Return the CSR securitisation non-CTP bucket definition for a bucket id."""

    _ensure_csr_sec_nonctp_delta_supported(profile)
    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    normalised = _require_text(bucket_id, "bucket_id")
    for bucket in _PROFILE_BUCKETS[resolved]:
        if bucket.bucket_id == normalised:
            return bucket
    raise SbmInputError(
        f"no CSR securitisation non-CTP bucket definition for bucket_id {normalised}",
        field="bucket_id",
    )


def csr_sec_nonctp_prescribed_tenors(
    profile: SbmRegulatoryProfile | str,
) -> frozenset[str]:
    """Return prescribed CSR securitisation non-CTP delta tenors."""

    _ensure_csr_sec_nonctp_delta_supported(profile)
    del profile
    return _CSR_SEC_PRESCRIBED_TENORS


def csr_sec_nonctp_validate_delta_inputs(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket_id: str,
    risk_factor: str,
    tenor: str,
    qualifier: str,
) -> None:
    """Validate CSR securitisation non-CTP delta lookup inputs."""

    _ensure_csr_sec_nonctp_delta_supported(profile)
    csr_sec_nonctp_bucket_definition(profile, bucket_id)
    _normalise_csr_sec_risk_factor(risk_factor)
    _require_csr_sec_tenor(profile, tenor)
    if not _require_text(qualifier, "qualifier"):
        raise SbmInputError("qualifier must not be empty", field="qualifier")


def csr_sec_nonctp_validate_vega_inputs(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket_id: str,
    risk_factor: str,
    qualifier: str,
) -> None:
    """Validate CSR securitisation non-CTP vega lookup inputs."""

    _ensure_csr_sec_nonctp_delta_supported(profile)
    csr_sec_nonctp_bucket_definition(profile, bucket_id)
    _normalise_csr_sec_risk_factor(risk_factor)
    if not _require_text(qualifier, "qualifier"):
        raise SbmInputError("qualifier must not be empty", field="qualifier")


def csr_sec_nonctp_delta_risk_weight(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket_id: str,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited CSR securitisation non-CTP delta risk weight."""

    bucket = csr_sec_nonctp_bucket_definition(profile, bucket_id)
    return bucket.risk_weight, (bucket.citation_id, _WEIGHT_CITATION)


def csr_sec_nonctp_delta_intra_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket_id: str,
    tranche_a: str,
    tranche_b: str,
    tenor_a: str,
    tenor_b: str,
    risk_factor_a: str,
    risk_factor_b: str,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited CSR securitisation non-CTP intra-bucket correlation."""

    _ensure_csr_sec_nonctp_delta_supported(profile)
    bucket = csr_sec_nonctp_bucket_definition(profile, bucket_id)
    if bucket.is_other_sector:
        return 0.0, (_OTHER_SECTOR_CITATION,)

    tranche_factor = (
        CSR_SEC_TRANCHE_SAME_CORRELATION
        if tranche_a == tranche_b
        else CSR_SEC_TRANCHE_DIFFERENT_CORRELATION
    )
    tenor_factor = (
        CSR_SEC_TENOR_SAME_CORRELATION
        if tenor_a == tenor_b
        else CSR_SEC_TENOR_DIFFERENT_CORRELATION
    )
    basis_a = _normalise_csr_sec_risk_factor(risk_factor_a)
    basis_b = _normalise_csr_sec_risk_factor(risk_factor_b)
    basis_factor = (
        CSR_SEC_SAME_BASIS_CORRELATION
        if basis_a == basis_b
        else CSR_SEC_DIFFERENT_BASIS_CORRELATION
    )
    return tranche_factor * tenor_factor * basis_factor, (_INTRA_CITATION,)


def csr_sec_nonctp_inter_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket1: str,
    bucket2: str,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited CSR securitisation non-CTP inter-bucket correlation."""

    _ensure_csr_sec_nonctp_delta_supported(profile)
    del bucket1, bucket2
    return CSR_SEC_INTER_BUCKET_CORRELATION, (_INTER_CITATION,)


def csr_sec_nonctp_reference_payload(profile: SbmRegulatoryProfile | str) -> dict[str, object]:
    """Return CSR securitisation non-CTP tables for profile hashing."""

    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    _ensure_csr_sec_nonctp_delta_supported(profile)
    return {
        "csr_sec_nonctp_buckets": [
            {
                "bucket_id": bucket.bucket_id,
                "label": bucket.label,
                "credit_quality": bucket.credit_quality,
                "sector": bucket.sector,
                "risk_weight": bucket.risk_weight,
                "is_other_sector": bucket.is_other_sector,
                "citation_id": bucket.citation_id,
            }
            for bucket in _PROFILE_BUCKETS[resolved]
        ],
        "csr_sec_nonctp_prescribed_tenors": sorted(_CSR_SEC_PRESCRIBED_TENORS),
        "csr_sec_nonctp_intra_parameters": {
            "tranche_same_correlation": CSR_SEC_TRANCHE_SAME_CORRELATION,
            "tranche_different_correlation": CSR_SEC_TRANCHE_DIFFERENT_CORRELATION,
            "tenor_same_correlation": CSR_SEC_TENOR_SAME_CORRELATION,
            "tenor_different_correlation": CSR_SEC_TENOR_DIFFERENT_CORRELATION,
            "same_basis_correlation": CSR_SEC_SAME_BASIS_CORRELATION,
            "different_basis_correlation": CSR_SEC_DIFFERENT_BASIS_CORRELATION,
        },
        "csr_sec_nonctp_inter_parameters": {
            "inter_bucket_correlation": CSR_SEC_INTER_BUCKET_CORRELATION,
        },
    }


def _ensure_csr_sec_nonctp_delta_supported(profile: SbmRegulatoryProfile | str) -> None:
    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    if resolved is not SbmRegulatoryProfile.BASEL_MAR21:
        raise UnsupportedRegulatoryFeatureError(
            f"CSR securitisation non-CTP delta is unsupported for profile {resolved.value}"
        )


def _normalise_csr_sec_risk_factor(risk_factor: str) -> str:
    normalised = _require_text(risk_factor, "risk_factor").upper()
    if normalised not in {CSR_SEC_BOND_RISK_FACTOR, CSR_SEC_CDS_RISK_FACTOR}:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm CSR securitisation delta supports BOND and CDS risk factors only; "
            f"received risk_factor={normalised!r}"
        )
    return normalised


def _require_csr_sec_tenor(profile: SbmRegulatoryProfile | str, tenor: str) -> str:
    normalised = _require_text(tenor, "tenor")
    prescribed = csr_sec_nonctp_prescribed_tenors(profile)
    if normalised not in prescribed:
        allowed = ", ".join(sorted(prescribed))
        raise SbmInputError(
            f"tenor must be one of the prescribed CSR securitisation tenors: {allowed}",
            field="tenor",
        )
    return normalised


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SbmInputError("non-empty text is required", field=field)
    return value.strip()


__all__ = [
    "CSR_SEC_BOND_RISK_FACTOR",
    "CSR_SEC_CDS_RISK_FACTOR",
    "CSR_SEC_OTHER_SECTOR_BUCKET",
    "SbmCsrSecNonctpBucketDefinition",
    "csr_sec_nonctp_bucket_definition",
    "csr_sec_nonctp_buckets_for_profile",
    "csr_sec_nonctp_delta_intra_bucket_correlation",
    "csr_sec_nonctp_delta_risk_weight",
    "csr_sec_nonctp_inter_bucket_correlation",
    "csr_sec_nonctp_prescribed_tenors",
    "csr_sec_nonctp_reference_payload",
    "csr_sec_nonctp_validate_delta_inputs",
    "csr_sec_nonctp_validate_vega_inputs",
]
