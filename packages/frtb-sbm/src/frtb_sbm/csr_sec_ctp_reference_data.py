"""
CSR securitisation CTP delta reference data for BASEL_MAR21.

Regulatory traceability:
    Basel MAR21.11 — underlying-name credit-spread delta risk factors.
    Basel MAR21.58-MAR21.60 — buckets (Table 6), weights, intra-bucket rules.
    Basel MAR21.57 — inter-bucket gamma reused from CSR non-securitisation.
"""

from __future__ import annotations

from dataclasses import dataclass

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.csr_nonsec_reference_data import (
    CSR_BOND_RISK_FACTOR,
    CSR_CDS_RISK_FACTOR,
    CSR_CROSS_RATING_GAMMA,
    CSR_NAME_CORRELATION,
    CSR_TENOR_CORRELATION,
    csr_nonsec_inter_bucket_correlation,
)
from frtb_sbm.data_models import SbmRegulatoryProfile, SbmSensitivity
from frtb_sbm.validation import SbmInputError, ensure_sbm_profile_known

CSR_SEC_CTP_DECOMPOSITION_REQUIRED_FLAG = "index_ctp_decomposition_required"
CSR_SEC_CTP_DECOMPOSITION_EVIDENCE_FLAG = "index_ctp_decomposition_evidence"

CSR_CTP_SAME_BASIS_CORRELATION = 1.0
CSR_CTP_DIFFERENT_BASIS_CORRELATION = 0.99

_WEIGHT_CITATION = "basel_mar21_59"
_INTRA_CITATION = "basel_mar21_58"
_INTER_CITATION = "basel_mar21_57"

_CSR_CTP_PRESCRIBED_TENORS: frozenset[str] = frozenset({"6m", "1y", "3y", "5y", "10y"})

_CSR_CTP_FORBIDDEN_BUCKETS = frozenset({"17", "18"})


@dataclass(frozen=True)
class SbmCsrSecCtpBucketDefinition:
    """Profile-specific CSR securitisation CTP bucket metadata."""

    bucket_id: str
    label: str
    risk_weight: float
    investment_grade: bool
    citation_id: str


_BASEL_CSR_CTP_BUCKETS: tuple[SbmCsrSecCtpBucketDefinition, ...] = (
    SbmCsrSecCtpBucketDefinition("1", "ig_sovereign", 0.040, True, _WEIGHT_CITATION),
    SbmCsrSecCtpBucketDefinition("2", "ig_local_government", 0.040, True, _WEIGHT_CITATION),
    SbmCsrSecCtpBucketDefinition("3", "ig_financials", 0.080, True, _WEIGHT_CITATION),
    SbmCsrSecCtpBucketDefinition("4", "ig_basic_materials_energy", 0.050, True, _WEIGHT_CITATION),
    SbmCsrSecCtpBucketDefinition("5", "ig_consumer_transport", 0.040, True, _WEIGHT_CITATION),
    SbmCsrSecCtpBucketDefinition("6", "ig_technology", 0.030, True, _WEIGHT_CITATION),
    SbmCsrSecCtpBucketDefinition("7", "ig_healthcare_utilities", 0.020, True, _WEIGHT_CITATION),
    SbmCsrSecCtpBucketDefinition("8", "ig_covered_bonds", 0.060, True, _WEIGHT_CITATION),
    SbmCsrSecCtpBucketDefinition("9", "hy_sovereign", 0.130, False, _WEIGHT_CITATION),
    SbmCsrSecCtpBucketDefinition("10", "hy_local_government", 0.130, False, _WEIGHT_CITATION),
    SbmCsrSecCtpBucketDefinition("11", "hy_financials", 0.160, False, _WEIGHT_CITATION),
    SbmCsrSecCtpBucketDefinition("12", "hy_basic_materials_energy", 0.100, False, _WEIGHT_CITATION),
    SbmCsrSecCtpBucketDefinition("13", "hy_consumer_transport", 0.120, False, _WEIGHT_CITATION),
    SbmCsrSecCtpBucketDefinition("14", "hy_technology", 0.120, False, _WEIGHT_CITATION),
    SbmCsrSecCtpBucketDefinition("15", "hy_healthcare_utilities", 0.120, False, _WEIGHT_CITATION),
    SbmCsrSecCtpBucketDefinition("16", "hy_other_sector", 0.130, False, _WEIGHT_CITATION),
)

_PROFILE_BUCKETS: dict[SbmRegulatoryProfile, tuple[SbmCsrSecCtpBucketDefinition, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21: _BASEL_CSR_CTP_BUCKETS,
}


def csr_sec_ctp_buckets_for_profile(
    profile: SbmRegulatoryProfile | str,
) -> tuple[SbmCsrSecCtpBucketDefinition, ...]:
    """Return cited CSR securitisation CTP bucket definitions."""

    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    _ensure_csr_sec_ctp_delta_supported(profile)
    return _PROFILE_BUCKETS[resolved]


def csr_sec_ctp_bucket_definition(
    profile: SbmRegulatoryProfile | str,
    bucket_id: str,
) -> SbmCsrSecCtpBucketDefinition:
    """Return the CSR securitisation CTP bucket definition for a bucket id."""

    _ensure_csr_sec_ctp_delta_supported(profile)
    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    normalised = _require_text(bucket_id, "bucket_id")
    if normalised in _CSR_CTP_FORBIDDEN_BUCKETS:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm CSR securitisation CTP excludes index buckets 17 and 18; "
            f"received bucket_id={normalised!r}"
        )
    for bucket in _PROFILE_BUCKETS[resolved]:
        if bucket.bucket_id == normalised:
            return bucket
    raise SbmInputError(
        f"no CSR securitisation CTP bucket definition for bucket_id {normalised}",
        field="bucket_id",
    )


def csr_sec_ctp_prescribed_tenors(
    profile: SbmRegulatoryProfile | str,
) -> frozenset[str]:
    """Return prescribed CSR securitisation CTP delta tenors."""

    _ensure_csr_sec_ctp_delta_supported(profile)
    del profile
    return _CSR_CTP_PRESCRIBED_TENORS


def csr_sec_ctp_validate_delta_inputs(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket_id: str,
    risk_factor: str,
    tenor: str,
    qualifier: str,
) -> None:
    """Validate CSR securitisation CTP delta lookup inputs."""

    _ensure_csr_sec_ctp_delta_supported(profile)
    csr_sec_ctp_bucket_definition(profile, bucket_id)
    _normalise_csr_sec_ctp_risk_factor(risk_factor)
    _require_csr_sec_ctp_tenor(profile, tenor)
    if not _require_text(qualifier, "qualifier"):
        raise SbmInputError("qualifier must not be empty", field="qualifier")


def ensure_csr_sec_ctp_decomposition_evidence(sensitivity: SbmSensitivity) -> None:
    """Fail closed when index CTP decomposition is required but evidence is missing."""

    flags = set(sensitivity.mapping_citation_ids)
    if CSR_SEC_CTP_DECOMPOSITION_REQUIRED_FLAG not in flags:
        return
    if CSR_SEC_CTP_DECOMPOSITION_EVIDENCE_FLAG in flags:
        return
    raise UnsupportedRegulatoryFeatureError(
        "frtb-sbm CSR securitisation CTP requires decomposition evidence when "
        "index constituent decomposition is requested; "
        f"sensitivity_id={sensitivity.sensitivity_id!r}"
    )


def csr_sec_ctp_delta_risk_weight(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket_id: str,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited CSR securitisation CTP delta risk weight."""

    bucket = csr_sec_ctp_bucket_definition(profile, bucket_id)
    return bucket.risk_weight, (bucket.citation_id, _WEIGHT_CITATION)


def csr_sec_ctp_delta_intra_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket_id: str,
    name_a: str,
    name_b: str,
    tenor_a: str,
    tenor_b: str,
    risk_factor_a: str,
    risk_factor_b: str,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited CSR securitisation CTP intra-bucket correlation."""

    _ensure_csr_sec_ctp_delta_supported(profile)
    del bucket_id
    name_factor = 1.0 if name_a == name_b else CSR_NAME_CORRELATION
    tenor_factor = 1.0 if tenor_a == tenor_b else CSR_TENOR_CORRELATION
    basis_a = _normalise_csr_sec_ctp_risk_factor(risk_factor_a)
    basis_b = _normalise_csr_sec_ctp_risk_factor(risk_factor_b)
    basis_factor = (
        CSR_CTP_SAME_BASIS_CORRELATION
        if basis_a == basis_b
        else CSR_CTP_DIFFERENT_BASIS_CORRELATION
    )
    return name_factor * tenor_factor * basis_factor, (_INTRA_CITATION,)


def csr_sec_ctp_inter_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket1: str,
    bucket2: str,
) -> tuple[float, tuple[str, ...]]:
    """Return cited CSR securitisation CTP inter-bucket correlation."""

    return csr_nonsec_inter_bucket_correlation(profile, bucket1=bucket1, bucket2=bucket2)


def csr_sec_ctp_reference_payload(profile: SbmRegulatoryProfile | str) -> dict[str, object]:
    """Return CSR securitisation CTP tables for profile hashing."""

    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    _ensure_csr_sec_ctp_delta_supported(profile)
    return {
        "csr_sec_ctp_buckets": [
            {
                "bucket_id": bucket.bucket_id,
                "label": bucket.label,
                "risk_weight": bucket.risk_weight,
                "investment_grade": bucket.investment_grade,
                "citation_id": bucket.citation_id,
            }
            for bucket in _PROFILE_BUCKETS[resolved]
        ],
        "csr_sec_ctp_prescribed_tenors": sorted(_CSR_CTP_PRESCRIBED_TENORS),
        "csr_sec_ctp_intra_parameters": {
            "name_correlation": CSR_NAME_CORRELATION,
            "tenor_correlation": CSR_TENOR_CORRELATION,
            "same_basis_correlation": CSR_CTP_SAME_BASIS_CORRELATION,
            "different_basis_correlation": CSR_CTP_DIFFERENT_BASIS_CORRELATION,
        },
        "csr_sec_ctp_inter_parameters": {
            "cross_rating_gamma": CSR_CROSS_RATING_GAMMA,
            "inter_bucket_citation_id": _INTER_CITATION,
        },
    }


def _ensure_csr_sec_ctp_delta_supported(profile: SbmRegulatoryProfile | str) -> None:
    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    if resolved is not SbmRegulatoryProfile.BASEL_MAR21:
        raise UnsupportedRegulatoryFeatureError(
            f"CSR securitisation CTP delta is unsupported for profile {resolved.value}"
        )


def _normalise_csr_sec_ctp_risk_factor(risk_factor: str) -> str:
    normalised = _require_text(risk_factor, "risk_factor").upper()
    if normalised not in {CSR_BOND_RISK_FACTOR, CSR_CDS_RISK_FACTOR}:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm CSR securitisation CTP supports BOND and CDS risk factors only; "
            f"received risk_factor={normalised!r}"
        )
    return normalised


def _require_csr_sec_ctp_tenor(profile: SbmRegulatoryProfile | str, tenor: str) -> str:
    normalised = _require_text(tenor, "tenor")
    prescribed = csr_sec_ctp_prescribed_tenors(profile)
    if normalised not in prescribed:
        allowed = ", ".join(sorted(prescribed))
        raise SbmInputError(
            f"tenor must be one of the prescribed CSR securitisation CTP tenors: {allowed}",
            field="tenor",
        )
    return normalised


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SbmInputError("non-empty text is required", field=field)
    return value.strip()


__all__ = [
    "CSR_CTP_DIFFERENT_BASIS_CORRELATION",
    "CSR_SEC_CTP_DECOMPOSITION_EVIDENCE_FLAG",
    "CSR_SEC_CTP_DECOMPOSITION_REQUIRED_FLAG",
    "SbmCsrSecCtpBucketDefinition",
    "csr_sec_ctp_bucket_definition",
    "csr_sec_ctp_buckets_for_profile",
    "csr_sec_ctp_delta_intra_bucket_correlation",
    "csr_sec_ctp_delta_risk_weight",
    "csr_sec_ctp_inter_bucket_correlation",
    "csr_sec_ctp_prescribed_tenors",
    "csr_sec_ctp_reference_payload",
    "csr_sec_ctp_validate_delta_inputs",
    "ensure_csr_sec_ctp_decomposition_evidence",
]
