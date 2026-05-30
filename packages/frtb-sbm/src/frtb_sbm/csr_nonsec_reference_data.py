"""
CSR non-securitisation delta reference data for BASEL_MAR21.

Regulatory traceability:
    Basel MAR21.9 — CSR non-securitisation delta risk factors (bond vs CDS).
    Basel MAR21.51-MAR21.57 — buckets (Table 3), weights (Table 4),
    intra-bucket correlations, other-sector rule, inter-bucket gamma (Table 5).
"""

from __future__ import annotations

from dataclasses import dataclass

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.data_models import SbmRegulatoryProfile
from frtb_sbm.validation import SbmInputError, ensure_sbm_profile_known

BASEL_MAR21_URL = "https://www.bis.org/basel_framework/chapter/MAR/21.htm"

CSR_BOND_RISK_FACTOR = "BOND"
CSR_CDS_RISK_FACTOR = "CDS"
CSR_OTHER_SECTOR_BUCKET = "16"
CSR_IG_INDEX_BUCKET = "17"
CSR_HY_INDEX_BUCKET = "18"

CSR_NAME_CORRELATION = 0.35
CSR_INDEX_NAME_CORRELATION = 0.80
CSR_TENOR_CORRELATION = 0.65
CSR_SAME_CURVE_CORRELATION = 1.0
CSR_DIFFERENT_CURVE_CORRELATION = 0.999
CSR_CROSS_RATING_GAMMA = 0.50

_CSR_BUCKET_CITATION = "basel_mar21_51"
_CSR_WEIGHT_CITATION = "basel_mar21_53"
_CSR_INTRA_CITATION = "basel_mar21_54"
_CSR_INDEX_INTRA_CITATION = "basel_mar21_55"
_CSR_OTHER_SECTOR_CITATION = "basel_mar21_56"
_CSR_INTER_CITATION = "basel_mar21_57"

_CSR_PRESCRIBED_TENORS: frozenset[str] = frozenset({"6m", "1y", "3y", "5y", "10y"})

# MAR21.57 Table 5 lower-triangle sector gammas (sectors 0..10 map to 1/9 .. 18).
# Row i stores gamma(sector i, sector j) for j = i+1 .. 10.
_CSR_SECTOR_GAMMA_ROWS: tuple[tuple[float, ...], ...] = (
    (0.75, 0.10, 0.20, 0.25, 0.20, 0.15, 0.10, 0.00, 0.45, 0.45),
    (0.05, 0.15, 0.20, 0.15, 0.10, 0.10, 0.00, 0.45, 0.45),
    (0.05, 0.15, 0.20, 0.05, 0.20, 0.00, 0.45, 0.45),
    (0.20, 0.25, 0.05, 0.05, 0.00, 0.45, 0.45),
    (0.25, 0.05, 0.15, 0.00, 0.45, 0.45),
    (0.05, 0.20, 0.00, 0.45, 0.45),
    (0.05, 0.00, 0.45, 0.45),
    (0.00, 0.45, 0.45),
    (0.00, 0.00),
    (0.75,),
    (),
)

_BUCKET_TO_SECTOR_INDEX: dict[str, int] = {
    "1": 0,
    "9": 0,
    "2": 1,
    "10": 1,
    "3": 2,
    "11": 2,
    "4": 3,
    "12": 3,
    "5": 4,
    "13": 4,
    "6": 5,
    "14": 5,
    "7": 6,
    "15": 6,
    "8": 7,
    "16": 8,
    "17": 9,
    "18": 10,
}


@dataclass(frozen=True)
class SbmCsrNonsecBucketDefinition:
    """Profile-specific CSR non-securitisation bucket metadata."""

    bucket_id: str
    label: str
    risk_weight: float
    investment_grade: bool
    is_index_bucket: bool
    citation_id: str


_BASEL_CSR_BUCKETS: tuple[SbmCsrNonsecBucketDefinition, ...] = (
    SbmCsrNonsecBucketDefinition("1", "ig_sovereign", 0.005, True, False, _CSR_BUCKET_CITATION),
    SbmCsrNonsecBucketDefinition(
        "2", "ig_local_government", 0.010, True, False, _CSR_BUCKET_CITATION
    ),
    SbmCsrNonsecBucketDefinition("3", "ig_financials", 0.050, True, False, _CSR_BUCKET_CITATION),
    SbmCsrNonsecBucketDefinition(
        "4", "ig_basic_materials_energy", 0.030, True, False, _CSR_BUCKET_CITATION
    ),
    SbmCsrNonsecBucketDefinition(
        "5", "ig_consumer_transport", 0.030, True, False, _CSR_BUCKET_CITATION
    ),
    SbmCsrNonsecBucketDefinition("6", "ig_technology", 0.020, True, False, _CSR_BUCKET_CITATION),
    SbmCsrNonsecBucketDefinition(
        "7", "ig_healthcare_utilities", 0.015, True, False, _CSR_BUCKET_CITATION
    ),
    SbmCsrNonsecBucketDefinition("8", "ig_covered_bonds", 0.025, True, False, _CSR_BUCKET_CITATION),
    SbmCsrNonsecBucketDefinition("9", "hy_sovereign", 0.020, False, False, _CSR_BUCKET_CITATION),
    SbmCsrNonsecBucketDefinition(
        "10", "hy_local_government", 0.040, False, False, _CSR_BUCKET_CITATION
    ),
    SbmCsrNonsecBucketDefinition("11", "hy_financials", 0.120, False, False, _CSR_BUCKET_CITATION),
    SbmCsrNonsecBucketDefinition(
        "12", "hy_basic_materials_energy", 0.070, False, False, _CSR_BUCKET_CITATION
    ),
    SbmCsrNonsecBucketDefinition(
        "13", "hy_consumer_transport", 0.085, False, False, _CSR_BUCKET_CITATION
    ),
    SbmCsrNonsecBucketDefinition("14", "hy_technology", 0.055, False, False, _CSR_BUCKET_CITATION),
    SbmCsrNonsecBucketDefinition(
        "15", "hy_healthcare_utilities", 0.050, False, False, _CSR_BUCKET_CITATION
    ),
    SbmCsrNonsecBucketDefinition("16", "other_sector", 0.120, False, False, _CSR_BUCKET_CITATION),
    SbmCsrNonsecBucketDefinition("17", "ig_index", 0.015, True, True, _CSR_BUCKET_CITATION),
    SbmCsrNonsecBucketDefinition("18", "hy_index", 0.050, False, True, _CSR_BUCKET_CITATION),
)

_PROFILE_CSR_BUCKETS: dict[SbmRegulatoryProfile, tuple[SbmCsrNonsecBucketDefinition, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21: _BASEL_CSR_BUCKETS,
}


def csr_nonsec_buckets_for_profile(
    profile: SbmRegulatoryProfile | str,
) -> tuple[SbmCsrNonsecBucketDefinition, ...]:
    """Return cited CSR non-securitisation bucket definitions."""

    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    _ensure_csr_nonsec_delta_supported(profile)
    return _PROFILE_CSR_BUCKETS[resolved]


def csr_nonsec_bucket_definition(
    profile: SbmRegulatoryProfile | str,
    bucket_id: str,
) -> SbmCsrNonsecBucketDefinition:
    """Return the CSR non-securitisation bucket definition for a bucket id."""

    _ensure_csr_nonsec_delta_supported(profile)
    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    normalised = _require_text(bucket_id, "bucket_id")
    for bucket in _PROFILE_CSR_BUCKETS[resolved]:
        if bucket.bucket_id == normalised:
            return bucket
    raise SbmInputError(
        f"no CSR non-securitisation bucket definition for bucket_id {normalised}",
        field="bucket_id",
    )


def csr_nonsec_prescribed_tenors(
    profile: SbmRegulatoryProfile | str,
) -> frozenset[str]:
    """Return prescribed CSR non-securitisation delta tenors for a profile."""

    _ensure_csr_nonsec_delta_supported(profile)
    del profile
    return _CSR_PRESCRIBED_TENORS


def csr_nonsec_validate_delta_inputs(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket_id: str,
    risk_factor: str,
    tenor: str,
    qualifier: str,
) -> None:
    """Validate cited CSR non-securitisation delta inputs at the weighting boundary."""

    csr_nonsec_bucket_definition(profile, bucket_id)
    _normalise_csr_risk_factor(risk_factor)
    _require_csr_tenor(profile, tenor)
    _require_text(qualifier, "qualifier")


def csr_nonsec_delta_risk_weight(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket_id: str,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited CSR non-securitisation delta risk weight for one bucket."""

    bucket = csr_nonsec_bucket_definition(profile, bucket_id)
    return bucket.risk_weight, (_CSR_WEIGHT_CITATION,)


def csr_nonsec_delta_intra_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket_id: str,
    risk_factor_a: str,
    risk_factor_b: str,
    issuer_a: str,
    issuer_b: str,
    tenor_a: str,
    tenor_b: str,
) -> tuple[float, tuple[str, ...]]:
    """Return MAR21.54/MAR21.55 intra-bucket rho as rho_name * rho_tenor * rho_basis."""

    _ensure_csr_nonsec_delta_supported(profile)
    normalised_bucket = _require_text(bucket_id, "bucket_id")
    bucket = csr_nonsec_bucket_definition(profile, normalised_bucket)
    if normalised_bucket == CSR_OTHER_SECTOR_BUCKET:
        raise UnsupportedRegulatoryFeatureError(
            "CSR non-securitisation bucket 16 uses absolute-weight aggregation; "
            "pairwise correlations do not apply"
        )

    factor_a = _normalise_csr_risk_factor(risk_factor_a)
    factor_b = _normalise_csr_risk_factor(risk_factor_b)
    issuer_a_norm = _require_text(issuer_a, "qualifier")
    issuer_b_norm = _require_text(issuer_b, "qualifier")
    tenor_a_norm = _require_csr_tenor(profile, tenor_a)
    tenor_b_norm = _require_csr_tenor(profile, tenor_b)

    name_rho = (
        1.0
        if issuer_a_norm == issuer_b_norm
        else (CSR_INDEX_NAME_CORRELATION if bucket.is_index_bucket else CSR_NAME_CORRELATION)
    )
    tenor_rho = 1.0 if tenor_a_norm == tenor_b_norm else CSR_TENOR_CORRELATION
    basis_rho = (
        CSR_SAME_CURVE_CORRELATION if factor_a == factor_b else CSR_DIFFERENT_CURVE_CORRELATION
    )
    citation = _CSR_INDEX_INTRA_CITATION if bucket.is_index_bucket else _CSR_INTRA_CITATION
    return name_rho * tenor_rho * basis_rho, (citation,)


def csr_nonsec_inter_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket1: str,
    bucket2: str,
) -> tuple[float, tuple[str, ...]]:
    """Return MAR21.57 inter-bucket gamma for two CSR non-securitisation buckets."""

    _ensure_csr_nonsec_delta_supported(profile)
    b1 = _require_csr_bucket_number(bucket1)
    b2 = _require_csr_bucket_number(bucket2)
    bucket_a = csr_nonsec_bucket_definition(profile, str(b1))
    bucket_b = csr_nonsec_bucket_definition(profile, str(b2))
    if b1 == b2:
        return 1.0, (_CSR_INTER_CITATION,)

    gamma = _sector_gamma_from_table(b1, b2)
    if (
        1 <= b1 <= 15
        and 1 <= b2 <= 15
        and bucket_a.investment_grade is not bucket_b.investment_grade
    ):
        gamma *= CSR_CROSS_RATING_GAMMA
    return gamma, (_CSR_INTER_CITATION,)


def csr_nonsec_reference_payload(profile: SbmRegulatoryProfile | str) -> dict[str, object]:
    """Return CSR non-securitisation tables for profile hashing."""

    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    _ensure_csr_nonsec_delta_supported(profile)
    return {
        "csr_nonsec_buckets": [
            {
                "bucket_id": bucket.bucket_id,
                "label": bucket.label,
                "risk_weight": bucket.risk_weight,
                "investment_grade": bucket.investment_grade,
                "is_index_bucket": bucket.is_index_bucket,
                "citation_id": bucket.citation_id,
            }
            for bucket in _PROFILE_CSR_BUCKETS[resolved]
        ],
        "csr_nonsec_prescribed_tenors": sorted(_CSR_PRESCRIBED_TENORS),
        "csr_nonsec_intra_parameters": {
            "name_correlation": CSR_NAME_CORRELATION,
            "index_name_correlation": CSR_INDEX_NAME_CORRELATION,
            "tenor_correlation": CSR_TENOR_CORRELATION,
            "same_curve_correlation": CSR_SAME_CURVE_CORRELATION,
            "different_curve_correlation": CSR_DIFFERENT_CURVE_CORRELATION,
        },
        "csr_nonsec_inter_parameters": {
            "cross_rating_gamma": CSR_CROSS_RATING_GAMMA,
            "sector_gamma_rows": [list(row) for row in _CSR_SECTOR_GAMMA_ROWS],
        },
    }


def _sector_gamma_from_table(bucket_a: int, bucket_b: int) -> float:
    sector_a = _BUCKET_TO_SECTOR_INDEX[str(bucket_a)]
    sector_b = _BUCKET_TO_SECTOR_INDEX[str(bucket_b)]
    if sector_a == sector_b:
        return 1.0
    row = min(sector_a, sector_b)
    col = max(sector_a, sector_b)
    offset = col - row - 1
    return _CSR_SECTOR_GAMMA_ROWS[row][offset]


def _normalise_csr_risk_factor(risk_factor: str) -> str:
    normalised = _require_text(risk_factor, "risk_factor").upper()
    if normalised not in {CSR_BOND_RISK_FACTOR, CSR_CDS_RISK_FACTOR}:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm CSR non-securitisation delta supports BOND and CDS risk factors only; "
            f"received risk_factor={normalised!r}"
        )
    return normalised


def _require_csr_tenor(profile: SbmRegulatoryProfile | str, tenor: str) -> str:
    normalised = _require_text(tenor, "tenor")
    prescribed = csr_nonsec_prescribed_tenors(profile)
    if normalised not in prescribed:
        allowed = ", ".join(sorted(prescribed))
        raise SbmInputError(
            f"tenor must be one of the prescribed CSR non-securitisation tenors: {allowed}",
            field="tenor",
        )
    return normalised


def _ensure_csr_nonsec_delta_supported(profile: SbmRegulatoryProfile | str) -> None:
    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    if resolved is not SbmRegulatoryProfile.BASEL_MAR21:
        raise UnsupportedRegulatoryFeatureError(
            f"CSR non-securitisation delta reference data is unsupported for profile "
            f"{resolved.value}"
        )


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SbmInputError("non-empty text is required", field=field)
    return value.strip()


def _require_csr_bucket_number(bucket_id: str) -> int:
    normalised = _require_text(bucket_id, "bucket_id")
    try:
        bucket_number = int(normalised)
    except ValueError as exc:
        raise SbmInputError(
            "CSR non-securitisation bucket_id must be a numeric bucket label",
            field="bucket_id",
        ) from exc
    if bucket_number < 1 or bucket_number > 18:
        raise SbmInputError(
            "CSR non-securitisation bucket_id must be between 1 and 18",
            field="bucket_id",
        )
    return bucket_number


CSR_NONSEC_BASEL_CITATIONS = {
    "basel_mar21_9": {
        "source_id": "basel_mar21_sensitivities_based_method",
        "location": "MAR21.9",
        "url": BASEL_MAR21_URL,
        "note": "CSR non-securitisation delta risk factors (bond and CDS credit spreads).",
    },
    "basel_mar21_51": {
        "source_id": "basel_mar21_sensitivities_based_method",
        "location": "MAR21.51",
        "url": BASEL_MAR21_URL,
        "note": "CSR non-securitisation delta bucket assignment (Table 3).",
    },
    "basel_mar21_53": {
        "source_id": "basel_mar21_sensitivities_based_method",
        "location": "MAR21.53",
        "url": BASEL_MAR21_URL,
        "note": "CSR non-securitisation delta risk weights (Table 4).",
    },
    "basel_mar21_54": {
        "source_id": "basel_mar21_sensitivities_based_method",
        "location": "MAR21.54",
        "url": BASEL_MAR21_URL,
        "note": "CSR non-securitisation delta intra-bucket correlations for buckets 1-15.",
    },
    "basel_mar21_55": {
        "source_id": "basel_mar21_sensitivities_based_method",
        "location": "MAR21.55",
        "url": BASEL_MAR21_URL,
        "note": "CSR non-securitisation delta intra-bucket correlations for index buckets 17-18.",
    },
    "basel_mar21_56": {
        "source_id": "basel_mar21_sensitivities_based_method",
        "location": "MAR21.56",
        "url": BASEL_MAR21_URL,
        "note": "CSR non-securitisation other-sector bucket absolute-weight aggregation.",
    },
    "basel_mar21_57": {
        "source_id": "basel_mar21_sensitivities_based_method",
        "location": "MAR21.57",
        "url": BASEL_MAR21_URL,
        "note": "CSR non-securitisation delta inter-bucket gamma (Table 5).",
    },
}


__all__ = [
    "CSR_BOND_RISK_FACTOR",
    "CSR_CDS_RISK_FACTOR",
    "CSR_DIFFERENT_CURVE_CORRELATION",
    "CSR_INDEX_NAME_CORRELATION",
    "CSR_NAME_CORRELATION",
    "CSR_OTHER_SECTOR_BUCKET",
    "CSR_SAME_CURVE_CORRELATION",
    "CSR_TENOR_CORRELATION",
    "SbmCsrNonsecBucketDefinition",
    "csr_nonsec_bucket_definition",
    "csr_nonsec_buckets_for_profile",
    "csr_nonsec_delta_intra_bucket_correlation",
    "csr_nonsec_delta_risk_weight",
    "csr_nonsec_inter_bucket_correlation",
    "csr_nonsec_prescribed_tenors",
    "csr_nonsec_reference_payload",
    "csr_nonsec_validate_delta_inputs",
]
