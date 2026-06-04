"""
SA-CVA risk-class reference tables for Basel MAR50.54-MAR50.77.

Regulatory traceability: Basel MAR50.59-MAR50.77 (FX through commodity),
MAR50.58 (GIRR vega), MAR50.45 (no CCS vega).
"""

from __future__ import annotations

from functools import cache

from frtb_cva.data_models import CreditQuality, CvaRegulatoryProfile, CvaSector
from frtb_cva.validation import CvaInputError

CCS_SINGLE_NAME_BUCKETS = frozenset({"1a", "1b", "2", "3", "4", "5", "6", "7"})

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


def _cite(citation_id: str, profile: CvaRegulatoryProfile | str) -> str:
    from frtb_cva.reference_data import profile_citation_id

    return profile_citation_id(citation_id, profile)


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
    """MAR50.61(3): FX delta risk weight vs reporting currency.

Parameters
----------
profile, optional :
    Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

Returns
-------
tuple[float, str]
    Result of ``fx_delta_risk_weight`` for audit replay."""

    resolved_profile = _resolve_profile(profile)
    return FX_DELTA_RISK_WEIGHT, _cite("basel_mar50_61", resolved_profile)


def fx_inter_bucket_correlation(
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.60: FX cross-bucket gamma_bc.

Parameters
----------
profile, optional :
    Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

Returns
-------
tuple[float, str]
    Result of ``fx_inter_bucket_correlation`` for audit replay."""

    resolved_profile = _resolve_profile(profile)
    return FX_INTER_BUCKET_CORRELATION, _cite("basel_mar50_60", resolved_profile)


def sa_cva_vega_risk_weight(
    volatility_input: float,
    *,
    rw_sigma: float = SA_CVA_VEGA_RW_SIGMA,
    rw_scalar: float = 1.0,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.58/62/69/73/77: RW_k = rw_scalar · RW_sigma · sigma_k.

Parameters
----------
volatility_input :
    Input for ``sa_cva_vega_risk_weight`` used in the CVA capital path.

rw_sigma, optional :
    Input for ``sa_cva_vega_risk_weight`` used in the CVA capital path.

rw_scalar, optional :
    Input for ``sa_cva_vega_risk_weight`` used in the CVA capital path.

profile, optional :
    Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

Returns
-------
tuple[float, str]
    Result of ``sa_cva_vega_risk_weight`` for audit replay."""

    resolved_profile = _resolve_profile(profile)
    if volatility_input < 0:
        raise CvaInputError("volatility input must be non-negative", field="volatility_input")
    return rw_scalar * rw_sigma * volatility_input, _cite("basel_mar50_58", resolved_profile)


def girr_vega_intra_bucket_correlation(
    factor1: str,
    factor2: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.58(4): inflation vs rate vol correlation.

Parameters
----------
factor1 :
    Input for ``girr_vega_intra_bucket_correlation`` used in the CVA capital path.

factor2 :
    Input for ``girr_vega_intra_bucket_correlation`` used in the CVA capital path.

profile, optional :
    Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

Returns
-------
tuple[float, str]
    Result of ``girr_vega_intra_bucket_correlation`` for audit replay."""

    resolved_profile = _resolve_profile(profile)
    if factor1 == factor2:
        return 1.0, _cite("basel_mar50_58", resolved_profile)
    factors = {factor1, factor2}
    if factors == {GIRR_VEGA_INFLATION_FACTOR, GIRR_VEGA_RATE_FACTOR}:
        return 0.4, _cite("basel_mar50_58", resolved_profile)
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
    """MAR50.65(3): CCS delta risk weight by bucket and credit quality.

Parameters
----------
bucket_id :
    SA-CVA bucket identifier stored on the bucket capital result.

credit_quality :
    Counterparty credit-quality bucket for BA-CVA Table 1.

profile, optional :
    Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

Returns
-------
tuple[float, str]
    Result of ``ccs_delta_risk_weight`` for audit replay."""

    resolved_profile = _resolve_profile(profile)
    bucket = _normalise_bucket(bucket_id)
    quality = _resolve_credit_quality(credit_quality)
    key = (bucket, quality)
    if key not in CCS_DELTA_RISK_WEIGHTS:
        raise CvaInputError(
            f"no CCS delta risk weight for bucket {bucket} and {quality.value}",
            field="risk_weight",
        )
    return CCS_DELTA_RISK_WEIGHTS[key], _cite("basel_mar50_65", resolved_profile)


def ccs_inter_bucket_correlation(
    bucket1: str,
    bucket2: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.64: CCS cross-bucket gamma_bc.

Parameters
----------
bucket1 :
    Input for ``ccs_inter_bucket_correlation`` used in the CVA capital path.

bucket2 :
    Input for ``ccs_inter_bucket_correlation`` used in the CVA capital path.

profile, optional :
    Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

Returns
-------
tuple[float, str]
    Result of ``ccs_inter_bucket_correlation`` for audit replay."""

    resolved_profile = _resolve_profile(profile)
    return _symmetric_gamma_lookup(CCS_GAMMA_BC, bucket1, bucket2), _cite(
        "basel_mar50_64",
        resolved_profile,
    )


def ccs_delta_intra_bucket_correlation(
    *,
    same_entity: bool,
    legally_related: bool,
    same_credit_quality: bool,
    same_tenor: bool,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.65(4)-(7): CCS intra-bucket rho.

Parameters
----------
same_entity :
    Input for ``ccs_delta_intra_bucket_correlation`` used in the CVA capital path.

legally_related :
    Input for ``ccs_delta_intra_bucket_correlation`` used in the CVA capital path.

same_credit_quality :
    Input for ``ccs_delta_intra_bucket_correlation`` used in the CVA capital path.

same_tenor :
    Input for ``ccs_delta_intra_bucket_correlation`` used in the CVA capital path.

profile, optional :
    Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

Returns
-------
tuple[float, str]
    Result of ``ccs_delta_intra_bucket_correlation`` for audit replay."""

    resolved_profile = _resolve_profile(profile)
    if same_entity:
        rho_tenor = 1.0 if same_tenor else 0.9
        return rho_tenor, _cite("basel_mar50_65", resolved_profile)
    if legally_related:
        rho = 0.9 if same_tenor else 0.81
        return rho, _cite("basel_mar50_65", resolved_profile)
    if same_credit_quality:
        rho = 0.5 if same_tenor else 0.45
        return rho, _cite("basel_mar50_65", resolved_profile)
    rho = 0.4 if same_tenor else 0.36
    return rho, _cite("basel_mar50_65", resolved_profile)


def rcs_delta_risk_weight(
    bucket_id: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.68(3): RCS delta risk weight by bucket.

Parameters
----------
bucket_id :
    SA-CVA bucket identifier stored on the bucket capital result.

profile, optional :
    Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

Returns
-------
tuple[float, str]
    Result of ``rcs_delta_risk_weight`` for audit replay."""

    resolved_profile = _resolve_profile(profile)
    bucket = _normalise_bucket(bucket_id)
    if bucket not in RCS_DELTA_RISK_WEIGHTS:
        raise CvaInputError(f"no RCS delta risk weight for bucket {bucket}", field="risk_weight")
    return RCS_DELTA_RISK_WEIGHTS[bucket], _cite("basel_mar50_68", resolved_profile)


def rcs_inter_bucket_correlation(
    bucket1: str,
    bucket2: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.67: RCS cross-bucket gamma_bc with cross-quality halving.

Parameters
----------
bucket1 :
    Input for ``rcs_inter_bucket_correlation`` used in the CVA capital path.

bucket2 :
    Input for ``rcs_inter_bucket_correlation`` used in the CVA capital path.

profile, optional :
    Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

Returns
-------
tuple[float, str]
    Result of ``rcs_inter_bucket_correlation`` for audit replay."""

    resolved_profile = _resolve_profile(profile)
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
    return gamma, _cite("basel_mar50_67", resolved_profile)


def equity_delta_risk_weight(
    bucket_id: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.72(3): equity delta risk weight.

Parameters
----------
bucket_id :
    SA-CVA bucket identifier stored on the bucket capital result.

profile, optional :
    Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

Returns
-------
tuple[float, str]
    Result of ``equity_delta_risk_weight`` for audit replay."""

    resolved_profile = _resolve_profile(profile)
    bucket = _normalise_bucket(bucket_id)
    if bucket not in EQUITY_DELTA_RISK_WEIGHTS:
        raise CvaInputError(f"no equity delta risk weight for bucket {bucket}", field="risk_weight")
    return EQUITY_DELTA_RISK_WEIGHTS[bucket], _cite("basel_mar50_72", resolved_profile)


def equity_vega_rw_scalar(
    bucket_id: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.73(3): equity vega RW scalar before RW_sigma · sigma_k.

Parameters
----------
bucket_id :
    SA-CVA bucket identifier stored on the bucket capital result.

profile, optional :
    Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

Returns
-------
tuple[float, str]
    Result of ``equity_vega_rw_scalar`` for audit replay."""

    resolved_profile = _resolve_profile(profile)
    bucket = _normalise_bucket(bucket_id)
    if bucket not in EQUITY_VEGA_RW_SCALAR:
        raise CvaInputError(f"no equity vega RW scalar for bucket {bucket}", field="risk_weight")
    return EQUITY_VEGA_RW_SCALAR[bucket], _cite("basel_mar50_73", resolved_profile)


def equity_inter_bucket_correlation(
    bucket1: str,
    bucket2: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.71: equity cross-bucket gamma_bc.

Parameters
----------
bucket1 :
    Input for ``equity_inter_bucket_correlation`` used in the CVA capital path.

bucket2 :
    Input for ``equity_inter_bucket_correlation`` used in the CVA capital path.

profile, optional :
    Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

Returns
-------
tuple[float, str]
    Result of ``equity_inter_bucket_correlation`` for audit replay."""

    resolved_profile = _resolve_profile(profile)
    left = _normalise_bucket(bucket1)
    right = _normalise_bucket(bucket2)
    if EQUITY_OTHER_BUCKET in {left, right}:
        return 0.0, _cite("basel_mar50_71", resolved_profile)
    pair = {left, right}
    if pair == {"12", "13"}:
        return 0.75, _cite("basel_mar50_71", resolved_profile)
    if "12" in pair or "13" in pair:
        return 0.45, _cite("basel_mar50_71", resolved_profile)
    return 0.15, _cite("basel_mar50_71", resolved_profile)


def commodity_delta_risk_weight(
    bucket_id: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.76(3): commodity delta risk weight.

Parameters
----------
bucket_id :
    SA-CVA bucket identifier stored on the bucket capital result.

profile, optional :
    Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

Returns
-------
tuple[float, str]
    Result of ``commodity_delta_risk_weight`` for audit replay."""

    resolved_profile = _resolve_profile(profile)
    bucket = _normalise_bucket(bucket_id)
    if bucket not in COMMODITY_DELTA_RISK_WEIGHTS:
        raise CvaInputError(
            f"no commodity delta risk weight for bucket {bucket}",
            field="risk_weight",
        )
    return COMMODITY_DELTA_RISK_WEIGHTS[bucket], _cite("basel_mar50_76", resolved_profile)


def commodity_inter_bucket_correlation(
    bucket1: str,
    bucket2: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """MAR50.75: commodity cross-bucket gamma_bc.

Parameters
----------
bucket1 :
    Input for ``commodity_inter_bucket_correlation`` used in the CVA capital path.

bucket2 :
    Input for ``commodity_inter_bucket_correlation`` used in the CVA capital path.

profile, optional :
    Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

Returns
-------
tuple[float, str]
    Result of ``commodity_inter_bucket_correlation`` for audit replay."""

    resolved_profile = _resolve_profile(profile)
    left = _normalise_bucket(bucket1)
    right = _normalise_bucket(bucket2)
    if COMMODITY_OTHER_BUCKET in {left, right}:
        return 0.0, _cite("basel_mar50_75", resolved_profile)
    return 0.2, _cite("basel_mar50_75", resolved_profile)


def ccs_single_name_bucket_for_sector(
    sector: CvaSector,
    credit_quality: CreditQuality,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[str, str]:
    """MAR50.63(2): map a dominant CCS sector to the single-name bucket id.

Parameters
----------
sector :
    Counterparty sector bucket for BA-CVA Table 1 risk weights.

credit_quality :
    Counterparty credit-quality bucket for BA-CVA Table 1.

profile, optional :
    Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

Returns
-------
tuple[str, str]
    Result of ``ccs_single_name_bucket_for_sector`` for audit replay."""

    resolved_profile = _resolve_profile(profile)
    if sector is CvaSector.SOVEREIGN:
        bucket = "1a" if credit_quality is CreditQuality.INVESTMENT_GRADE else "1b"
        return bucket, _cite("basel_mar50_63", resolved_profile)
    sector_buckets: dict[CvaSector, str] = {
        CvaSector.LOCAL_GOVERNMENT: "2",
        CvaSector.FINANCIALS: "3",
        CvaSector.BASIC_MATERIALS_ENERGY_INDUSTRIALS: "4",
        CvaSector.CONSUMER_TRANSPORT_ADMIN: "5",
        CvaSector.TECHNOLOGY_TELECOM: "6",
        CvaSector.HEALTH_UTILITIES_PROFESSIONAL: "7",
        CvaSector.OTHER: "7",
    }
    try:
        return sector_buckets[sector], _cite("basel_mar50_63", resolved_profile)
    except KeyError as exc:
        raise CvaInputError(
            f"no CCS single-name bucket for sector {sector.value}",
            field="index_dominant_sector",
        ) from exc


def sa_cva_reference_payload(profile: CvaRegulatoryProfile | str) -> dict[str, object]:
    """Return deterministic SA-CVA reference-table payload for profile hashing.

Parameters
----------
profile :
    Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

Returns
-------
dict[str, object]
    Result of ``sa_cva_reference_payload`` for audit replay."""

    resolved_profile = _resolve_profile(profile)
    return {
        "fx": _fx_reference_payload(resolved_profile),
        "vega": _vega_reference_payload(resolved_profile),
        "ccs": _ccs_reference_payload(resolved_profile),
        "rcs": _rcs_reference_payload(resolved_profile),
        "equity": _equity_reference_payload(resolved_profile),
        "commodity": _commodity_reference_payload(resolved_profile),
    }


def _fx_reference_payload(profile: CvaRegulatoryProfile) -> dict[str, object]:
    from frtb_cva.reference_data import profile_citation_id

    return {
        "delta_risk_weight": FX_DELTA_RISK_WEIGHT,
        "delta_risk_weight_citation_id": profile_citation_id("basel_mar50_61", profile),
        "inter_bucket_correlation": FX_INTER_BUCKET_CORRELATION,
        "inter_bucket_correlation_citation_id": profile_citation_id("basel_mar50_60", profile),
    }


def _vega_reference_payload(profile: CvaRegulatoryProfile) -> dict[str, object]:
    from frtb_cva.reference_data import profile_citation_ids

    return {
        "rw_sigma": SA_CVA_VEGA_RW_SIGMA,
        "rw_sigma_citation_ids": profile_citation_ids(
            (
                "basel_mar50_58",
                "basel_mar50_62",
                "basel_mar50_69",
                "basel_mar50_73",
                "basel_mar50_77",
            ),
            profile,
        ),
    }


def _ccs_reference_payload(profile: CvaRegulatoryProfile) -> dict[str, object]:
    from frtb_cva.reference_data import profile_citation_id

    return {
        "single_name_buckets": sorted(CCS_SINGLE_NAME_BUCKETS),
        "qualified_index_bucket": CCS_QUALIFIED_INDEX_BUCKET,
        "delta_tenors": CCS_DELTA_TENORS,
        "delta_risk_weights": [
            {
                "bucket": bucket,
                "credit_quality": credit_quality.value,
                "risk_weight": risk_weight,
                "citation_id": profile_citation_id("basel_mar50_65", profile),
            }
            for (bucket, credit_quality), risk_weight in sorted(
                CCS_DELTA_RISK_WEIGHTS.items(),
                key=lambda item: (item[0][0], item[0][1].value),
            )
        ],
        "gamma_bc": [
            {
                "bucket1": bucket1,
                "bucket2": bucket2,
                "correlation": correlation,
                "citation_id": profile_citation_id("basel_mar50_64", profile),
            }
            for (bucket1, bucket2), correlation in sorted(CCS_GAMMA_BC.items())
        ],
    }


def _rcs_reference_payload(profile: CvaRegulatoryProfile) -> dict[str, object]:
    from frtb_cva.reference_data import profile_citation_id

    return {
        "ig_buckets": sorted(RCS_IG_BUCKETS),
        "hy_nr_buckets": sorted(RCS_HY_NR_BUCKETS),
        "delta_risk_weights": [
            {
                "bucket": bucket,
                "risk_weight": risk_weight,
                "citation_id": profile_citation_id("basel_mar50_68", profile),
            }
            for bucket, risk_weight in sorted(RCS_DELTA_RISK_WEIGHTS.items())
        ],
        "gamma_coordinates": [
            {
                "coordinate1": coordinate1,
                "coordinate2": coordinate2,
                "correlation": correlation,
                "citation_id": profile_citation_id("basel_mar50_67", profile),
            }
            for (coordinate1, coordinate2), correlation in sorted(RCS_GAMMA_BY_COORDINATE.items())
        ],
    }


def _equity_reference_payload(profile: CvaRegulatoryProfile) -> dict[str, object]:
    from frtb_cva.reference_data import profile_citation_id

    return {
        "large_cap_buckets": sorted(EQUITY_LARGE_CAP_BUCKETS),
        "qualified_index_buckets": sorted(EQUITY_QUALIFIED_INDEX_BUCKETS),
        "delta_risk_weights": [
            {
                "bucket": bucket,
                "risk_weight": risk_weight,
                "citation_id": profile_citation_id("basel_mar50_72", profile),
            }
            for bucket, risk_weight in sorted(EQUITY_DELTA_RISK_WEIGHTS.items())
        ],
        "vega_rw_scalars": [
            {
                "bucket": bucket,
                "risk_weight_scalar": scalar,
                "citation_id": profile_citation_id("basel_mar50_73", profile),
            }
            for bucket, scalar in sorted(EQUITY_VEGA_RW_SCALAR.items())
        ],
    }


def _commodity_reference_payload(profile: CvaRegulatoryProfile) -> dict[str, object]:
    from frtb_cva.reference_data import profile_citation_id

    return {
        "main_buckets": sorted(COMMODITY_MAIN_BUCKETS),
        "other_bucket": COMMODITY_OTHER_BUCKET,
        "delta_risk_weights": [
            {
                "bucket": bucket,
                "risk_weight": risk_weight,
                "citation_id": profile_citation_id("basel_mar50_76", profile),
            }
            for bucket, risk_weight in sorted(COMMODITY_DELTA_RISK_WEIGHTS.items())
        ],
    }


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


@cache
def parse_ccs_entity_key(risk_factor_key: str) -> tuple[str, CreditQuality, str | None]:
    """Parse CCS risk_factor_key as ``entity|QUALITY`` with optional ``|legal:GROUP``.

Parameters
----------
risk_factor_key :
    Stable SA-CVA risk-factor key for weighting and bucket assignment.

Returns
-------
tuple[str, CreditQuality, str | None]
    Result of ``parse_ccs_entity_key`` for audit replay."""

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
    "CCS_SINGLE_NAME_BUCKETS",
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
    "RCS_HY_NR_BUCKETS",
    "RCS_IG_BUCKETS",
    "SA_CVA_VEGA_RW_SIGMA",
    "ccs_delta_intra_bucket_correlation",
    "ccs_delta_risk_weight",
    "ccs_inter_bucket_correlation",
    "ccs_single_name_bucket_for_sector",
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
    "sa_cva_reference_payload",
    "sa_cva_vega_risk_weight",
]
