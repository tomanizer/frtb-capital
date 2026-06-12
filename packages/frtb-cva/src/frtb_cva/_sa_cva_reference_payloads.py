"""SA-CVA deterministic reference payload assembly."""

from __future__ import annotations

from frtb_cva._sa_cva_reference_tables import (
    CCS_DELTA_RISK_WEIGHTS,
    CCS_DELTA_TENORS,
    CCS_GAMMA_BC,
    CCS_QUALIFIED_INDEX_BUCKET,
    CCS_SINGLE_NAME_BUCKETS,
    COMMODITY_DELTA_RISK_WEIGHTS,
    COMMODITY_MAIN_BUCKETS,
    COMMODITY_OTHER_BUCKET,
    EQUITY_DELTA_RISK_WEIGHTS,
    EQUITY_LARGE_CAP_BUCKETS,
    EQUITY_QUALIFIED_INDEX_BUCKETS,
    EQUITY_VEGA_RW_SCALAR,
    FX_DELTA_RISK_WEIGHT,
    FX_INTER_BUCKET_CORRELATION,
    RCS_DELTA_RISK_WEIGHTS,
    RCS_GAMMA_BY_COORDINATE,
    RCS_HY_NR_BUCKETS,
    RCS_IG_BUCKETS,
    SA_CVA_VEGA_RW_SIGMA,
)
from frtb_cva.data_models import CvaRegulatoryProfile


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

    from frtb_cva.reference_data import _resolve_supported_profile

    resolved_profile = _resolve_supported_profile(profile)
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


__all__ = ["sa_cva_reference_payload"]
