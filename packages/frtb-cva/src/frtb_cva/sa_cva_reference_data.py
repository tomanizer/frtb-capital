"""
SA-CVA risk-class reference tables for Basel MAR50.54–MAR50.77.

Regulatory traceability: Basel MAR50.59–MAR50.77 (FX through commodity),
MAR50.58 (GIRR vega), MAR50.45 (no CCS vega).
"""

from __future__ import annotations

from frtb_cva.data_models import CreditQuality, CvaRegulatoryProfile
from frtb_cva.validation import CvaInputError

SA_CVA_VEGA_RW_SIGMA = 0.55

FX_DELTA_RISK_WEIGHT = 0.11
FX_INTER_BUCKET_CORRELATION = 0.6

GIRR_VEGA_INFLATION_FACTOR = "INFL_VOL"
GIRR_VEGA_RATE_FACTOR = "IR_VOL"

CCS_DELTA_TENORS: tuple[str, ...] = ("0.5y", "1y", "3y", "5y", "10y")
CCS_QUALIFIED_INDEX_BUCKET = "8"

CCS_DELTA_RISK_WEIGHTS: dict[tuple[str, CreditQuality], float] = {
    ("1a", CreditQuality.INVESTMENT_GRADE): 0.005,
    ("1b", CreditQuality.INVESTMENT_GRADE): 0.01,
    ("2", CreditQuality.INVESTMENT_GRADE): 0.05,
    ("3", CreditQuality.INVESTMENT_GRADE): 0.03,
    ("4", CreditQuality.INVESTMENT_GRADE): 0.03,
    ("5", CreditQuality.INVESTMENT_GRADE): 0.02,
    ("6", CreditQuality.INVESTMENT_GRADE): 0.015,
    ("7", CreditQuality.INVESTMENT_GRADE): 0.05,
    ("8", CreditQuality.INVESTMENT_GRADE): 0.015,
    ("1a", CreditQuality.HIGH_YIELD): 0.02,
    ("1b", CreditQuality.HIGH_YIELD): 0.04,
    ("2", CreditQuality.HIGH_YIELD): 0.12,
    ("3", CreditQuality.HIGH_YIELD): 0.07,
    ("4", CreditQuality.HIGH_YIELD): 0.085,
    ("5", CreditQuality.HIGH_YIELD): 0.055,
    ("6", CreditQuality.HIGH_YIELD): 0.05,
    ("7", CreditQuality.HIGH_YIELD): 0.05,
    ("8", CreditQuality.HIGH_YIELD): 0.05,
    ("1a", CreditQuality.NOT_RATED): 0.02,
    ("1b", CreditQuality.NOT_RATED): 0.04,
    ("2", CreditQuality.NOT_RATED): 0.12,
    ("3", CreditQuality.NOT_RATED): 0.07,
    ("4", CreditQuality.NOT_RATED): 0.085,
    ("5", CreditQuality.NOT_RATED): 0.055,
    ("6", CreditQuality.NOT_RATED): 0.05,
    ("7", CreditQuality.NOT_RATED): 0.05,
    ("8", CreditQuality.NOT_RATED): 0.05,
}

CCS_GAMMA_BC: dict[tuple[str, str], float] = {
    ("1", "1"): 1.0,
    ("1", "2"): 0.10,
    ("1", "3"): 0.20,
    ("1", "4"): 0.25,
    ("1", "5"): 0.20,
    ("1", "6"): 0.15,
    ("1", "7"): 0.0,
    ("1", "8"): 0.45,
    ("2", "2"): 1.0,
    ("2", "3"): 0.15,
    ("2", "4"): 0.20,
    ("2", "5"): 0.05,
    ("2", "6"): 0.0,
    ("2", "7"): 0.0,
    ("2", "8"): 0.45,
    ("3", "3"): 1.0,
    ("3", "4"): 0.25,
    ("3", "5"): 0.05,
    ("3", "6"): 0.0,
    ("3", "7"): 0.0,
    ("3", "8"): 0.45,
    ("4", "4"): 1.0,
    ("4", "5"): 0.05,
    ("4", "6"): 0.0,
    ("4", "7"): 0.0,
    ("4", "8"): 0.45,
    ("5", "5"): 1.0,
    ("5", "6"): 0.0,
    ("5", "7"): 0.0,
    ("5", "8"): 0.45,
    ("6", "6"): 1.0,
    ("6", "7"): 0.0,
    ("6", "8"): 0.45,
    ("7", "7"): 1.0,
    ("7", "8"): 0.0,
    ("8", "8"): 1.0,
}

RCS_DELTA_RISK_WEIGHTS: dict[str, float] = {
    "1": 0.005,
    "2": 0.01,
    "3": 0.05,
    "4": 0.03,
    "5": 0.03,
    "6": 0.02,
    "7": 0.015,
    "8": 0.12,
    "9": 0.07,
    "10": 0.085,
    "11": 0.055,
    "12": 0.05,
    "13": 0.12,
    "14": 0.05,
    "15": 0.12,
    "16": 0.015,
    "17": 0.05,
}

RCS_IG_BUCKETS = frozenset({"1", "2", "3", "4", "5", "6", "7", "16"})
RCS_HY_NR_BUCKETS = frozenset({"8", "9", "10", "11", "12", "13", "14", "15", "17"})

# Maps bucket ids to MAR50.67 Table 9 row/column labels.
RCS_TABLE_COORDINATES: dict[str, str] = {
    "1": "1/8",
    "8": "1/8",
    "2": "2/9",
    "9": "2/9",
    "3": "3/10",
    "10": "3/10",
    "4": "4/11",
    "11": "4/11",
    "5": "5/12",
    "12": "5/12",
    "6": "6/13",
    "13": "6/13",
    "7": "7/14",
    "14": "7/14",
    "15": "15",
    "16": "16",
    "17": "17",
}

RCS_GAMMA_BY_COORDINATE: dict[tuple[str, str], float] = {
    ("1/8", "1/8"): 1.0,
    ("1/8", "2/9"): 0.75,
    ("1/8", "3/10"): 0.10,
    ("1/8", "4/11"): 0.20,
    ("1/8", "5/12"): 0.25,
    ("1/8", "6/13"): 0.20,
    ("1/8", "7/14"): 0.15,
    ("1/8", "15"): 0.0,
    ("1/8", "16"): 0.45,
    ("1/8", "17"): 0.45,
    ("2/9", "2/9"): 1.0,
    ("2/9", "3/10"): 0.05,
    ("2/9", "4/11"): 0.15,
    ("2/9", "5/12"): 0.20,
    ("2/9", "6/13"): 0.15,
    ("2/9", "7/14"): 0.10,
    ("2/9", "15"): 0.0,
    ("2/9", "16"): 0.45,
    ("2/9", "17"): 0.45,
    ("3/10", "3/10"): 1.0,
    ("3/10", "4/11"): 0.05,
    ("3/10", "5/12"): 0.15,
    ("3/10", "6/13"): 0.20,
    ("3/10", "7/14"): 0.05,
    ("3/10", "15"): 0.0,
    ("3/10", "16"): 0.45,
    ("3/10", "17"): 0.45,
    ("4/11", "4/11"): 1.0,
    ("4/11", "5/12"): 0.20,
    ("4/11", "6/13"): 0.25,
    ("4/11", "7/14"): 0.05,
    ("4/11", "15"): 0.0,
    ("4/11", "16"): 0.45,
    ("4/11", "17"): 0.45,
    ("5/12", "5/12"): 1.0,
    ("5/12", "6/13"): 0.25,
    ("5/12", "7/14"): 0.05,
    ("5/12", "15"): 0.0,
    ("5/12", "16"): 0.45,
    ("5/12", "17"): 0.45,
    ("6/13", "6/13"): 1.0,
    ("6/13", "7/14"): 0.05,
    ("6/13", "15"): 0.0,
    ("6/13", "16"): 0.45,
    ("6/13", "17"): 0.45,
    ("7/14", "7/14"): 1.0,
    ("7/14", "15"): 0.0,
    ("7/14", "16"): 0.45,
    ("7/14", "17"): 0.45,
    ("15", "15"): 1.0,
    ("15", "16"): 0.0,
    ("15", "17"): 0.0,
    ("16", "16"): 1.0,
    ("16", "17"): 0.75,
    ("17", "17"): 1.0,
}

RCS_GAMMA_BC_SAME_QUALITY: dict[tuple[str, str], float] = {
    ("1", "1"): 1.0,
    ("1", "2"): 0.75,
    ("1", "3"): 0.10,
    ("1", "4"): 0.20,
    ("1", "5"): 0.25,
    ("1", "6"): 0.20,
    ("1", "7"): 0.15,
    ("1", "8"): 0.0,
    ("1", "15"): 0.0,
    ("1", "16"): 0.45,
    ("1", "17"): 0.45,
    ("2", "2"): 1.0,
    ("2", "3"): 0.05,
    ("2", "4"): 0.15,
    ("2", "5"): 0.20,
    ("2", "6"): 0.15,
    ("2", "7"): 0.10,
    ("2", "8"): 0.0,
    ("2", "15"): 0.0,
    ("2", "16"): 0.45,
    ("2", "17"): 0.45,
    ("3", "3"): 1.0,
    ("3", "4"): 0.05,
    ("3", "5"): 0.15,
    ("3", "6"): 0.20,
    ("3", "7"): 0.05,
    ("3", "8"): 0.0,
    ("3", "15"): 0.0,
    ("3", "16"): 0.45,
    ("3", "17"): 0.45,
    ("4", "4"): 1.0,
    ("4", "5"): 0.20,
    ("4", "6"): 0.25,
    ("4", "7"): 0.05,
    ("4", "8"): 0.0,
    ("4", "15"): 0.0,
    ("4", "16"): 0.45,
    ("4", "17"): 0.45,
    ("5", "5"): 1.0,
    ("5", "6"): 0.25,
    ("5", "7"): 0.05,
    ("5", "8"): 0.0,
    ("5", "15"): 0.0,
    ("5", "16"): 0.45,
    ("5", "17"): 0.45,
    ("6", "6"): 1.0,
    ("6", "7"): 0.05,
    ("6", "8"): 0.0,
    ("6", "15"): 0.0,
    ("6", "16"): 0.45,
    ("6", "17"): 0.45,
    ("7", "7"): 1.0,
    ("7", "8"): 0.0,
    ("7", "15"): 0.0,
    ("7", "16"): 0.45,
    ("7", "17"): 0.45,
    ("8", "8"): 1.0,
    ("8", "15"): 0.0,
    ("8", "16"): 0.45,
    ("8", "17"): 0.45,
    ("9", "9"): 1.0,
    ("9", "10"): 0.75,
    ("9", "11"): 0.10,
    ("9", "12"): 0.20,
    ("9", "13"): 0.25,
    ("9", "14"): 0.20,
    ("9", "15"): 0.0,
    ("9", "16"): 0.45,
    ("9", "17"): 0.45,
    ("10", "10"): 1.0,
    ("10", "11"): 0.05,
    ("10", "12"): 0.15,
    ("10", "13"): 0.20,
    ("10", "14"): 0.15,
    ("10", "15"): 0.0,
    ("10", "16"): 0.45,
    ("10", "17"): 0.45,
    ("11", "11"): 1.0,
    ("11", "12"): 0.05,
    ("11", "13"): 0.15,
    ("11", "14"): 0.20,
    ("11", "15"): 0.0,
    ("11", "16"): 0.45,
    ("11", "17"): 0.45,
    ("12", "12"): 1.0,
    ("12", "13"): 0.20,
    ("12", "14"): 0.25,
    ("12", "15"): 0.0,
    ("12", "16"): 0.45,
    ("12", "17"): 0.45,
    ("13", "13"): 1.0,
    ("13", "14"): 0.05,
    ("13", "15"): 0.0,
    ("13", "16"): 0.45,
    ("13", "17"): 0.45,
    ("14", "14"): 1.0,
    ("14", "15"): 0.0,
    ("14", "16"): 0.45,
    ("14", "17"): 0.45,
    ("15", "15"): 1.0,
    ("15", "16"): 0.0,
    ("15", "17"): 0.0,
    ("16", "16"): 1.0,
    ("16", "17"): 0.75,
    ("17", "17"): 1.0,
}

EQUITY_DELTA_RISK_WEIGHTS: dict[str, float] = {
    "1": 0.55,
    "2": 0.60,
    "3": 0.45,
    "4": 0.55,
    "5": 0.30,
    "6": 0.35,
    "7": 0.40,
    "8": 0.50,
    "9": 0.70,
    "10": 0.50,
    "11": 0.70,
    "12": 0.15,
    "13": 0.25,
}

EQUITY_VEGA_RW_SCALAR: dict[str, float] = {
    "1": 0.78,
    "2": 0.78,
    "3": 0.78,
    "4": 0.78,
    "5": 0.78,
    "6": 0.78,
    "7": 0.78,
    "8": 0.78,
    "9": 1.0,
    "10": 1.0,
    "11": 1.0,
    "12": 0.78,
    "13": 1.0,
}

EQUITY_LARGE_CAP_BUCKETS = frozenset({"1", "2", "3", "4", "5", "6", "7", "8", "12"})
EQUITY_OTHER_BUCKET = "11"
EQUITY_QUALIFIED_INDEX_BUCKETS = frozenset({"12", "13"})

COMMODITY_DELTA_RISK_WEIGHTS: dict[str, float] = {
    "1": 0.30,
    "2": 0.35,
    "3": 0.60,
    "4": 0.80,
    "5": 0.40,
    "6": 0.45,
    "7": 0.20,
    "8": 0.35,
    "9": 0.25,
    "10": 0.35,
    "11": 0.50,
}

COMMODITY_MAIN_BUCKETS = frozenset({"1", "2", "3", "4", "5", "6", "7", "8", "9", "10"})
COMMODITY_OTHER_BUCKET = "11"


def _resolve_profile(profile: CvaRegulatoryProfile | str) -> CvaRegulatoryProfile:
    from frtb_cva.reference_data import _resolve_supported_profile

    return _resolve_supported_profile(profile)


def _symmetric_gamma_lookup(
    table: dict[tuple[str, str], float],
    left_bucket: str,
    right_bucket: str,
) -> float:
    left = _normalise_bucket(left_bucket)
    right = _normalise_bucket(right_bucket)
    key = (left, right)
    if key in table:
        return table[key]
    key = (right, left)
    if key in table:
        return table[key]
    raise CvaInputError(
        f"no cross-bucket correlation for buckets {left_bucket}/{right_bucket}",
        field="gamma_bc",
    )


def _normalise_bucket(bucket_id: str) -> str:
    normalised = bucket_id.strip()
    if not normalised:
        raise CvaInputError("bucket id is required", field="bucket_id")
    return normalised


def fx_delta_risk_weight(
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.61(3): FX delta risk weight vs reporting currency."""

    _resolve_profile(profile)
    return FX_DELTA_RISK_WEIGHT, "basel_mar50_61"


def fx_inter_bucket_correlation(
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.60: FX cross-bucket gamma_bc."""

    _resolve_profile(profile)
    return FX_INTER_BUCKET_CORRELATION, "basel_mar50_60"


def sa_cva_vega_risk_weight(
    volatility_input: float,
    *,
    rw_sigma: float = SA_CVA_VEGA_RW_SIGMA,
    rw_scalar: float = 1.0,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.58/62/69/73/77: RW_k = rw_scalar · RW_sigma · sigma_k."""

    _resolve_profile(profile)
    if volatility_input < 0:
        raise CvaInputError("volatility input must be non-negative", field="volatility_input")
    return rw_scalar * rw_sigma * volatility_input, "basel_mar50_58"


def girr_vega_intra_bucket_correlation(
    factor1: str,
    factor2: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.58(4): inflation vs rate vol correlation."""

    _resolve_profile(profile)
    if factor1 == factor2:
        return 1.0, "basel_mar50_58"
    factors = {factor1, factor2}
    if factors == {GIRR_VEGA_INFLATION_FACTOR, GIRR_VEGA_RATE_FACTOR}:
        return 0.4, "basel_mar50_58"
    raise CvaInputError(
        f"no GIRR vega correlation for factors {factor1}/{factor2}",
        field="correlation",
    )


def ccs_delta_risk_weight(
    bucket_id: str,
    credit_quality: CreditQuality | str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.65(3): CCS delta risk weight by bucket and credit quality."""

    _resolve_profile(profile)
    bucket = _normalise_bucket(bucket_id)
    if bucket == CCS_QUALIFIED_INDEX_BUCKET:
        raise CvaInputError(
            "CCS qualified-index bucket 8 is unsupported until qualified-index mapping is delivered",
            field="bucket_id",
        )
    quality = _resolve_credit_quality(credit_quality)
    key = (bucket, quality)
    if key not in CCS_DELTA_RISK_WEIGHTS:
        raise CvaInputError(
            f"no CCS delta risk weight for bucket {bucket} and {quality.value}",
            field="risk_weight",
        )
    return CCS_DELTA_RISK_WEIGHTS[key], "basel_mar50_65"


def ccs_inter_bucket_correlation(
    bucket1: str,
    bucket2: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.64: CCS cross-bucket gamma_bc."""

    _resolve_profile(profile)
    if bucket1 == CCS_QUALIFIED_INDEX_BUCKET or bucket2 == CCS_QUALIFIED_INDEX_BUCKET:
        raise CvaInputError(
            "CCS qualified-index bucket 8 is unsupported until qualified-index mapping is delivered",
            field="bucket_id",
        )
    return _symmetric_gamma_lookup(CCS_GAMMA_BC, bucket1, bucket2), "basel_mar50_64"


def ccs_delta_intra_bucket_correlation(
    *,
    same_entity: bool,
    legally_related: bool,
    same_credit_quality: bool,
    same_tenor: bool,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.65(4)-(7): CCS intra-bucket rho."""

    _resolve_profile(profile)
    if same_entity:
        rho_tenor = 1.0 if same_tenor else 0.9
        return rho_tenor, "basel_mar50_65"
    if legally_related:
        rho = 0.9 if same_tenor else 0.81
        return rho, "basel_mar50_65"
    if same_credit_quality:
        rho = 0.5 if same_tenor else 0.45
        return rho, "basel_mar50_65"
    rho = 0.4 if same_tenor else 0.36
    return rho, "basel_mar50_65"


def rcs_delta_risk_weight(
    bucket_id: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.68(3): RCS delta risk weight by bucket."""

    _resolve_profile(profile)
    bucket = _normalise_bucket(bucket_id)
    if bucket not in RCS_DELTA_RISK_WEIGHTS:
        raise CvaInputError(f"no RCS delta risk weight for bucket {bucket}", field="risk_weight")
    return RCS_DELTA_RISK_WEIGHTS[bucket], "basel_mar50_68"


def rcs_inter_bucket_correlation(
    bucket1: str,
    bucket2: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.67: RCS cross-bucket gamma_bc with cross-quality halving."""

    _resolve_profile(profile)
    left = _normalise_bucket(bucket1)
    right = _normalise_bucket(bucket2)
    left_coord = RCS_TABLE_COORDINATES.get(left)
    right_coord = RCS_TABLE_COORDINATES.get(right)
    if left_coord is None or right_coord is None:
        raise CvaInputError(
            f"no RCS table coordinate for buckets {left}/{right}",
            field="gamma_bc",
        )
    gamma = _symmetric_gamma_lookup(RCS_GAMMA_BY_COORDINATE, left_coord, right_coord)
    left_ig = left in RCS_IG_BUCKETS
    right_ig = right in RCS_IG_BUCKETS
    if left_ig != right_ig:
        gamma *= 0.5
    return gamma, "basel_mar50_67"


def equity_delta_risk_weight(
    bucket_id: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.72(3): equity delta risk weight."""

    _resolve_profile(profile)
    bucket = _normalise_bucket(bucket_id)
    if bucket not in EQUITY_DELTA_RISK_WEIGHTS:
        raise CvaInputError(f"no equity delta risk weight for bucket {bucket}", field="risk_weight")
    return EQUITY_DELTA_RISK_WEIGHTS[bucket], "basel_mar50_72"


def equity_vega_rw_scalar(
    bucket_id: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.73(3): equity vega RW scalar before RW_sigma · sigma_k."""

    _resolve_profile(profile)
    bucket = _normalise_bucket(bucket_id)
    if bucket not in EQUITY_VEGA_RW_SCALAR:
        raise CvaInputError(f"no equity vega RW scalar for bucket {bucket}", field="risk_weight")
    return EQUITY_VEGA_RW_SCALAR[bucket], "basel_mar50_73"


def equity_inter_bucket_correlation(
    bucket1: str,
    bucket2: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.71: equity cross-bucket gamma_bc."""

    _resolve_profile(profile)
    left = _normalise_bucket(bucket1)
    right = _normalise_bucket(bucket2)
    if EQUITY_OTHER_BUCKET in {left, right}:
        return 0.0, "basel_mar50_71"
    pair = {left, right}
    if pair == {"12", "13"}:
        return 0.75, "basel_mar50_71"
    if "12" in pair or "13" in pair:
        return 0.45, "basel_mar50_71"
    return 0.15, "basel_mar50_71"


def commodity_delta_risk_weight(
    bucket_id: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.76(3): commodity delta risk weight."""

    _resolve_profile(profile)
    bucket = _normalise_bucket(bucket_id)
    if bucket not in COMMODITY_DELTA_RISK_WEIGHTS:
        raise CvaInputError(
            f"no commodity delta risk weight for bucket {bucket}",
            field="risk_weight",
        )
    return COMMODITY_DELTA_RISK_WEIGHTS[bucket], "basel_mar50_76"


def commodity_inter_bucket_correlation(
    bucket1: str,
    bucket2: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.75: commodity cross-bucket gamma_bc."""

    _resolve_profile(profile)
    left = _normalise_bucket(bucket1)
    right = _normalise_bucket(bucket2)
    if COMMODITY_OTHER_BUCKET in {left, right}:
        return 0.0, "basel_mar50_75"
    return 0.2, "basel_mar50_75"


def _resolve_credit_quality(credit_quality: CreditQuality | str) -> CreditQuality:
    if isinstance(credit_quality, CreditQuality):
        return credit_quality
    try:
        return CreditQuality(credit_quality)
    except ValueError as exc:
        raise CvaInputError(
            f"unknown credit quality: {credit_quality!r}",
            field="credit_quality",
        ) from exc


def parse_ccs_entity_key(risk_factor_key: str) -> tuple[str, CreditQuality, str | None]:
    """
    Parse CCS risk_factor_key as ``entity|QUALITY`` with optional ``|legal:GROUP``.
    """

    parts = risk_factor_key.split("|")
    if len(parts) < 2:
        raise CvaInputError(
            "CCS risk_factor_key must be entity|CREDIT_QUALITY[|legal:GROUP]",
            field="risk_factor_key",
        )
    entity_id = parts[0].strip()
    quality = _resolve_credit_quality(parts[1].strip())
    legal_group: str | None = None
    if len(parts) == 3:
        legal_token = parts[2].strip()
        if not legal_token.startswith("legal:"):
            raise CvaInputError(
                "CCS optional third segment must be legal:GROUP",
                field="risk_factor_key",
            )
        legal_group = legal_token.removeprefix("legal:").strip() or None
    elif len(parts) > 3:
        raise CvaInputError("CCS risk_factor_key has too many segments", field="risk_factor_key")
    if not entity_id:
        raise CvaInputError("CCS entity id is required", field="risk_factor_key")
    return entity_id, quality, legal_group


__all__ = [
    "CCS_DELTA_TENORS",
    "CCS_GAMMA_BC",
    "CCS_QUALIFIED_INDEX_BUCKET",
    "COMMODITY_DELTA_RISK_WEIGHTS",
    "COMMODITY_MAIN_BUCKETS",
    "COMMODITY_OTHER_BUCKET",
    "EQUITY_DELTA_RISK_WEIGHTS",
    "EQUITY_LARGE_CAP_BUCKETS",
    "EQUITY_OTHER_BUCKET",
    "EQUITY_QUALIFIED_INDEX_BUCKETS",
    "EQUITY_VEGA_RW_SCALAR",
    "FX_DELTA_RISK_WEIGHT",
    "FX_INTER_BUCKET_CORRELATION",
    "GIRR_VEGA_INFLATION_FACTOR",
    "GIRR_VEGA_RATE_FACTOR",
    "RCS_DELTA_RISK_WEIGHTS",
    "RCS_GAMMA_BC_SAME_QUALITY",
    "RCS_HY_NR_BUCKETS",
    "RCS_IG_BUCKETS",
    "SA_CVA_VEGA_RW_SIGMA",
    "ccs_delta_intra_bucket_correlation",
    "ccs_delta_risk_weight",
    "ccs_inter_bucket_correlation",
    "commodity_delta_risk_weight",
    "commodity_inter_bucket_correlation",
    "equity_delta_risk_weight",
    "equity_inter_bucket_correlation",
    "equity_vega_rw_scalar",
    "fx_delta_risk_weight",
    "fx_inter_bucket_correlation",
    "girr_vega_intra_bucket_correlation",
    "parse_ccs_entity_key",
    "rcs_delta_risk_weight",
    "rcs_inter_bucket_correlation",
    "sa_cva_vega_risk_weight",
]
