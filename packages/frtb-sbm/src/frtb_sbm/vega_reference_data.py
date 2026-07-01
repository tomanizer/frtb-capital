"""Vega liquidity-horizon and tenor reference-data lookups for SBM.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for reference_data.py, Basel
    MAR21.91-MAR21.95, and SBM-REF-001.
"""

from __future__ import annotations

import math

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm._text import require_text as _require_text
from frtb_sbm.data_models import SbmRegulatoryProfile, SbmRiskClass
from frtb_sbm.equity_reference_data import equity_bucket_definition
from frtb_sbm.girr_reference_correlations import _exponential_tenor_correlation
from frtb_sbm.girr_reference_data import (
    BASEL_GIRR_TENORS,
    girr_tenor_definition,
)
from frtb_sbm.reference_profiles import _coerce_risk_class, _resolve_supported_profile
from frtb_sbm.reference_types import SbmGirrTenorDefinition
from frtb_sbm.validation import SbmInputError, require_positive_int

GIRR_VEGA_INTRA_BUCKET_CONSTANT = 0.01
GIRR_VEGA_RISK_WEIGHT_FACTOR = 0.55
GIRR_VEGA_RISK_WEIGHT_CAP = 1.0

PROFILE_GIRR_VEGA_LIQUIDITY_HORIZON_DAYS: dict[SbmRegulatoryProfile, int] = {
    SbmRegulatoryProfile.BASEL_MAR21: 60,
    SbmRegulatoryProfile.US_NPR_2_0: 60,
}

PROFILE_VEGA_LIQUIDITY_HORIZON_DAYS: dict[
    SbmRegulatoryProfile,
    dict[SbmRiskClass, int],
] = {
    SbmRegulatoryProfile.BASEL_MAR21: {
        SbmRiskClass.GIRR: 60,
        SbmRiskClass.CSR_NONSEC: 120,
        SbmRiskClass.CSR_SEC_CTP: 120,
        SbmRiskClass.CSR_SEC_NONCTP: 120,
        SbmRiskClass.COMMODITY: 120,
        SbmRiskClass.FX: 40,
    },
    SbmRegulatoryProfile.US_NPR_2_0: {
        SbmRiskClass.GIRR: 60,
        SbmRiskClass.FX: 40,
    },
}

EQUITY_VEGA_LARGE_CAP_INDEX_LIQUIDITY_HORIZON_DAYS = 20
EQUITY_VEGA_SMALL_CAP_OTHER_LIQUIDITY_HORIZON_DAYS = 60
EQUITY_VEGA_LARGE_CAP_INDEX_BUCKETS = frozenset(
    {"1", "2", "3", "4", "5", "6", "7", "8", "12", "13"}
)
EQUITY_VEGA_SMALL_CAP_OTHER_BUCKETS = frozenset({"9", "10", "11"})

PROFILE_GIRR_VEGA_OPTION_TENORS: dict[
    SbmRegulatoryProfile,
    tuple[SbmGirrTenorDefinition, ...],
] = {
    SbmRegulatoryProfile.BASEL_MAR21: BASEL_GIRR_TENORS,
    SbmRegulatoryProfile.US_NPR_2_0: tuple(
        SbmGirrTenorDefinition(
            tenor.tenor,
            tenor.maturity_years,
            "us_npr_91_fr_14952_va7a_girr_vega_option_tenors",
        )
        for tenor in BASEL_GIRR_TENORS
    ),
}

PROFILE_GIRR_VEGA_LIQUIDITY_HORIZON_CITATION_IDS: dict[SbmRegulatoryProfile, str] = {
    SbmRegulatoryProfile.BASEL_MAR21: "basel_mar21_92",
    SbmRegulatoryProfile.US_NPR_2_0: "us_npr_91_fr_14952_va7a_girr_vega_lh_rw",
}

PROFILE_GIRR_VEGA_INTRA_BUCKET_CITATION_IDS: dict[SbmRegulatoryProfile, str] = {
    SbmRegulatoryProfile.BASEL_MAR21: "basel_mar21_93",
    SbmRegulatoryProfile.US_NPR_2_0: "us_npr_91_fr_14952_va7a_girr_vega_intra",
}

PROFILE_VEGA_RISK_WEIGHT_CITATION_IDS: dict[
    SbmRegulatoryProfile,
    dict[SbmRiskClass, str],
] = {
    SbmRegulatoryProfile.BASEL_MAR21: {
        risk_class: "basel_mar21_92"
        for risk_class in (
            SbmRiskClass.GIRR,
            SbmRiskClass.CSR_NONSEC,
            SbmRiskClass.CSR_SEC_CTP,
            SbmRiskClass.CSR_SEC_NONCTP,
            SbmRiskClass.COMMODITY,
            SbmRiskClass.EQUITY,
            SbmRiskClass.FX,
        )
    },
    SbmRegulatoryProfile.US_NPR_2_0: {
        SbmRiskClass.GIRR: "us_npr_91_fr_14952_va7a_girr_vega_lh_rw",
        SbmRiskClass.FX: "us_npr_91_fr_14952_va7a_fx_vega_lh_rw",
    },
}

PROFILE_VEGA_OPTION_TENOR_CITATION_IDS: dict[
    SbmRegulatoryProfile,
    dict[SbmRiskClass, str],
] = {
    SbmRegulatoryProfile.BASEL_MAR21: {
        risk_class: "basel_mar21_93"
        for risk_class in (
            SbmRiskClass.GIRR,
            SbmRiskClass.CSR_NONSEC,
            SbmRiskClass.CSR_SEC_CTP,
            SbmRiskClass.CSR_SEC_NONCTP,
            SbmRiskClass.COMMODITY,
            SbmRiskClass.EQUITY,
            SbmRiskClass.FX,
        )
    },
    SbmRegulatoryProfile.US_NPR_2_0: {
        SbmRiskClass.GIRR: "us_npr_91_fr_14952_va7a_girr_vega_intra",
        SbmRiskClass.FX: "us_npr_91_fr_14952_va7a_fx_vega_option_tenors",
    },
}

PROFILE_VEGA_INTRA_BUCKET_CITATION_IDS: dict[
    SbmRegulatoryProfile,
    dict[SbmRiskClass, tuple[str, ...]],
] = {
    SbmRegulatoryProfile.BASEL_MAR21: {
        SbmRiskClass.FX: ("basel_mar21_4_intra_bucket", "basel_mar21_94", "basel_mar21_86"),
        SbmRiskClass.EQUITY: (
            "basel_mar21_4_intra_bucket",
            "basel_mar21_94",
            "basel_mar21_78",
            "basel_mar21_79",
        ),
        SbmRiskClass.COMMODITY: (
            "basel_mar21_4_intra_bucket",
            "basel_mar21_94",
            "basel_mar21_83",
        ),
        SbmRiskClass.CSR_NONSEC: (
            "basel_mar21_4_intra_bucket",
            "basel_mar21_94",
            "basel_mar21_54",
            "basel_mar21_55",
            "basel_mar21_56",
        ),
        SbmRiskClass.CSR_SEC_NONCTP: (
            "basel_mar21_4_intra_bucket",
            "basel_mar21_94",
            "basel_mar21_67",
            "basel_mar21_68",
        ),
        SbmRiskClass.CSR_SEC_CTP: (
            "basel_mar21_4_intra_bucket",
            "basel_mar21_94",
            "basel_mar21_58",
        ),
    },
    SbmRegulatoryProfile.US_NPR_2_0: {
        SbmRiskClass.FX: (
            "us_npr_91_fr_14952_va7a_sbm_scope",
            "us_npr_91_fr_14952_va7a_fx_vega_intra",
            "us_npr_91_fr_14952_va7a_fx_delta_intra",
        ),
    },
}

PROFILE_VEGA_INTER_BUCKET_CITATION_IDS: dict[
    SbmRegulatoryProfile,
    dict[SbmRiskClass, tuple[str, ...]],
] = {
    SbmRegulatoryProfile.BASEL_MAR21: {
        SbmRiskClass.FX: ("basel_mar21_4_inter_bucket", "basel_mar21_95", "basel_mar21_89"),
        SbmRiskClass.EQUITY: ("basel_mar21_4_inter_bucket", "basel_mar21_95", "basel_mar21_80"),
        SbmRiskClass.COMMODITY: (
            "basel_mar21_4_inter_bucket",
            "basel_mar21_95",
            "basel_mar21_85",
        ),
        SbmRiskClass.CSR_NONSEC: (
            "basel_mar21_4_inter_bucket",
            "basel_mar21_95",
            "basel_mar21_57",
        ),
        SbmRiskClass.CSR_SEC_NONCTP: (
            "basel_mar21_4_inter_bucket",
            "basel_mar21_95",
            "basel_mar21_70",
        ),
        SbmRiskClass.CSR_SEC_CTP: (
            "basel_mar21_4_inter_bucket",
            "basel_mar21_95",
            "basel_mar21_57",
        ),
    },
    SbmRegulatoryProfile.US_NPR_2_0: {
        SbmRiskClass.FX: (
            "us_npr_91_fr_14952_va7a_sbm_scope",
            "us_npr_91_fr_14952_va7a_fx_vega_inter",
            "us_npr_91_fr_14952_va7a_fx_delta_inter",
        ),
    },
}

PROFILE_VEGA_SCENARIO_CITATION_IDS: dict[SbmRegulatoryProfile, tuple[str, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21: (
        "basel_mar21_6_correlation_scenarios",
        "basel_mar21_7_scenario_selection",
    ),
    SbmRegulatoryProfile.US_NPR_2_0: ("us_npr_91_fr_14952_va7a_correlation_scenarios",),
}


def girr_vega_liquidity_horizon_days(profile: SbmRegulatoryProfile | str) -> int:
    """Return the cited GIRR vega liquidity horizon in days for a profile.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.

    Returns
    -------
    int
    """

    return vega_liquidity_horizon_days(
        profile,
        risk_class=SbmRiskClass.GIRR,
    )


def vega_liquidity_horizon_days(
    profile: SbmRegulatoryProfile | str,
    *,
    risk_class: SbmRiskClass | str,
    bucket_id: str = "",
) -> int:
    """Return the cited MAR21.92 Table 13 vega liquidity horizon in days.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    risk_class : SbmRiskClass | str
        See signature.
    bucket_id : str, optional
        See signature.

    Returns
    -------
    int
    """

    resolved = _resolve_supported_profile(profile)
    _ensure_vega_supported(profile)
    resolved_class = _coerce_risk_class(risk_class)
    if resolved_class is SbmRiskClass.EQUITY:
        normalised_bucket = equity_bucket_definition(profile, bucket_id).bucket_id
        if normalised_bucket in EQUITY_VEGA_LARGE_CAP_INDEX_BUCKETS:
            return EQUITY_VEGA_LARGE_CAP_INDEX_LIQUIDITY_HORIZON_DAYS
        if normalised_bucket in EQUITY_VEGA_SMALL_CAP_OTHER_BUCKETS:
            return EQUITY_VEGA_SMALL_CAP_OTHER_LIQUIDITY_HORIZON_DAYS
        raise SbmInputError(
            f"no equity vega liquidity horizon for bucket_id {normalised_bucket}",
            field="bucket_id",
        )
    try:
        return PROFILE_VEGA_LIQUIDITY_HORIZON_DAYS[resolved][resolved_class]
    except KeyError as exc:
        raise UnsupportedRegulatoryFeatureError(
            f"vega liquidity horizon is unsupported for risk_class={resolved_class.value}"
        ) from exc


def vega_risk_weight(
    profile: SbmRegulatoryProfile | str,
    *,
    liquidity_horizon_days: int,
    risk_class: SbmRiskClass | str = SbmRiskClass.GIRR,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited vega risk weight min(100%, 55% * sqrt(LH/10)).
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    liquidity_horizon_days : int
        See signature.

    Returns
    -------
    tuple[float, tuple[str, ...]]
    """

    resolved = _resolve_supported_profile(profile)
    _ensure_vega_supported(profile)
    resolved_class = _coerce_risk_class(risk_class)
    horizon = require_positive_int(liquidity_horizon_days, "liquidity_horizon_days")
    risk_weight = min(
        GIRR_VEGA_RISK_WEIGHT_CAP,
        GIRR_VEGA_RISK_WEIGHT_FACTOR * math.sqrt(horizon / 10.0),
    )
    try:
        citation_id = PROFILE_VEGA_RISK_WEIGHT_CITATION_IDS[resolved][resolved_class]
    except KeyError as exc:
        raise UnsupportedRegulatoryFeatureError(
            f"vega risk-weight citation is unsupported for risk_class={resolved_class.value}"
        ) from exc
    return risk_weight, (citation_id,)


def girr_vega_option_tenors(
    profile: SbmRegulatoryProfile | str,
) -> tuple[SbmGirrTenorDefinition, ...]:
    """Return the prescribed GIRR vega option-tenor set for a supported profile.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.

    Returns
    -------
    tuple[SbmGirrTenorDefinition, ...]
    """

    resolved = _resolve_supported_profile(profile)
    _ensure_girr_vega_supported(profile)
    return PROFILE_GIRR_VEGA_OPTION_TENORS[resolved]


def girr_vega_option_tenor_definition(
    profile: SbmRegulatoryProfile | str,
    option_tenor: str,
) -> SbmGirrTenorDefinition:
    """Return the GIRR vega option-tenor definition for a canonical label.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    option_tenor : str
        See signature.

    Returns
    -------
    SbmGirrTenorDefinition
    """

    normalised = _require_text(option_tenor, "option_tenor")
    for tenor_definition in girr_vega_option_tenors(profile):
        if tenor_definition.tenor == normalised:
            return tenor_definition
    raise SbmInputError(
        f"no GIRR vega option tenor definition for option_tenor {normalised}",
        field="option_tenor",
    )


def girr_vega_intra_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    option_tenor1: str,
    option_tenor2: str,
    tenor1: str,
    tenor2: str,
) -> tuple[float, tuple[str, ...]]:
    """Return min(1, rho_opt * rho_ul) with 1% exponential tenor constants.
    Parameters
    ----------
    profile, option_tenor1, option_tenor2, tenor1, tenor2 :
        See function signature for types and defaults.

    Returns
    -------
    tuple[float, tuple[str, ...]]
    """

    _ensure_girr_vega_supported(profile)
    rho_opt, _ = vega_option_tenor_correlation(
        profile,
        option_tenor1=option_tenor1,
        option_tenor2=option_tenor2,
    )
    underlying_maturity1 = girr_tenor_definition(profile, tenor1).maturity_years
    underlying_maturity2 = girr_tenor_definition(profile, tenor2).maturity_years
    rho_ul = _exponential_tenor_correlation(
        underlying_maturity1,
        underlying_maturity2,
        constant=GIRR_VEGA_INTRA_BUCKET_CONSTANT,
        floor=None,
    )
    resolved = _resolve_supported_profile(profile)
    return min(1.0, rho_opt * rho_ul), (PROFILE_GIRR_VEGA_INTRA_BUCKET_CITATION_IDS[resolved],)


def vega_option_tenor_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    option_tenor1: str,
    option_tenor2: str,
    risk_class: SbmRiskClass | str = SbmRiskClass.GIRR,
) -> tuple[float, tuple[str, ...]]:
    """Return the MAR21.93 option-tenor correlation term used by vega paths.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    option_tenor1 : str
        See signature.
    option_tenor2 : str
        See signature.

    Returns
    -------
    tuple[float, tuple[str, ...]]
    """

    resolved = _resolve_supported_profile(profile)
    _ensure_vega_supported(profile)
    resolved_class = _coerce_risk_class(risk_class)
    option_maturity1 = girr_vega_option_tenor_definition(profile, option_tenor1).maturity_years
    option_maturity2 = girr_vega_option_tenor_definition(profile, option_tenor2).maturity_years
    try:
        citation_id = PROFILE_VEGA_OPTION_TENOR_CITATION_IDS[resolved][resolved_class]
    except KeyError as exc:
        raise UnsupportedRegulatoryFeatureError(
            f"vega option-tenor citation is unsupported for risk_class={resolved_class.value}"
        ) from exc
    return (
        _exponential_tenor_correlation(
            option_maturity1,
            option_maturity2,
            constant=GIRR_VEGA_INTRA_BUCKET_CONSTANT,
            floor=None,
        ),
        (citation_id,),
    )


def vega_intra_bucket_citation_ids(
    profile: SbmRegulatoryProfile | str,
    risk_class: SbmRiskClass | str,
) -> tuple[str, ...]:
    """Return profile-owned non-GIRR vega intra-bucket citation ids.

    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        Regulatory profile that owns the vega correlation rule citation.
    risk_class : SbmRiskClass | str
        Risk class for the non-GIRR vega branch.

    Returns
    -------
    tuple[str, ...]
        Citation identifiers used on the intra-bucket vega aggregation branch.

    Raises
    ------
    UnsupportedRegulatoryFeatureError
        If the profile/risk-class pair does not have implemented vega citations.
    """

    resolved = _resolve_supported_profile(profile)
    resolved_class = _coerce_risk_class(risk_class)
    try:
        return PROFILE_VEGA_INTRA_BUCKET_CITATION_IDS[resolved][resolved_class]
    except KeyError as exc:
        raise UnsupportedRegulatoryFeatureError(
            f"vega intra-bucket citations are unsupported for risk_class={resolved_class.value}"
        ) from exc


def vega_inter_bucket_citation_ids(
    profile: SbmRegulatoryProfile | str,
    risk_class: SbmRiskClass | str,
) -> tuple[str, ...]:
    """Return profile-owned non-GIRR vega inter-bucket citation ids.

    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        Regulatory profile that owns the vega correlation rule citation.
    risk_class : SbmRiskClass | str
        Risk class for the non-GIRR vega branch.

    Returns
    -------
    tuple[str, ...]
        Citation identifiers used on the inter-bucket vega aggregation branch.

    Raises
    ------
    UnsupportedRegulatoryFeatureError
        If the profile/risk-class pair does not have implemented vega citations.
    """

    resolved = _resolve_supported_profile(profile)
    resolved_class = _coerce_risk_class(risk_class)
    try:
        return PROFILE_VEGA_INTER_BUCKET_CITATION_IDS[resolved][resolved_class]
    except KeyError as exc:
        raise UnsupportedRegulatoryFeatureError(
            f"vega inter-bucket citations are unsupported for risk_class={resolved_class.value}"
        ) from exc


def vega_scenario_citation_ids(profile: SbmRegulatoryProfile | str) -> tuple[str, ...]:
    """Return profile-owned vega correlation-scenario citation ids.

    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        Regulatory profile that owns the vega correlation-scenario rule.

    Returns
    -------
    tuple[str, ...]
        Citation identifiers for high, medium, and low vega correlation scenarios.

    Raises
    ------
    UnsupportedRegulatoryFeatureError
        If the profile does not have implemented vega scenario citations.
    """

    resolved = _resolve_supported_profile(profile)
    try:
        return PROFILE_VEGA_SCENARIO_CITATION_IDS[resolved]
    except KeyError as exc:
        raise UnsupportedRegulatoryFeatureError(
            f"vega scenario citations are unsupported for profile={resolved.value}"
        ) from exc


def _ensure_vega_supported(profile: SbmRegulatoryProfile | str) -> None:
    resolved = _resolve_supported_profile(profile)
    if resolved not in PROFILE_VEGA_LIQUIDITY_HORIZON_DAYS:
        raise UnsupportedRegulatoryFeatureError(
            f"vega reference data is unsupported for profile {resolved.value}"
        )


def _ensure_girr_vega_supported(profile: SbmRegulatoryProfile | str) -> None:
    resolved = _resolve_supported_profile(profile)
    if (
        resolved not in PROFILE_GIRR_VEGA_LIQUIDITY_HORIZON_DAYS
        or resolved not in PROFILE_GIRR_VEGA_OPTION_TENORS
    ):
        raise UnsupportedRegulatoryFeatureError(
            f"GIRR vega reference data is unsupported for profile {resolved.value}"
        )


__all__ = [
    "EQUITY_VEGA_LARGE_CAP_INDEX_BUCKETS",
    "EQUITY_VEGA_LARGE_CAP_INDEX_LIQUIDITY_HORIZON_DAYS",
    "EQUITY_VEGA_SMALL_CAP_OTHER_BUCKETS",
    "EQUITY_VEGA_SMALL_CAP_OTHER_LIQUIDITY_HORIZON_DAYS",
    "GIRR_VEGA_INTRA_BUCKET_CONSTANT",
    "GIRR_VEGA_RISK_WEIGHT_CAP",
    "GIRR_VEGA_RISK_WEIGHT_FACTOR",
    "PROFILE_GIRR_VEGA_INTRA_BUCKET_CITATION_IDS",
    "PROFILE_GIRR_VEGA_LIQUIDITY_HORIZON_CITATION_IDS",
    "PROFILE_GIRR_VEGA_LIQUIDITY_HORIZON_DAYS",
    "PROFILE_GIRR_VEGA_OPTION_TENORS",
    "PROFILE_VEGA_INTER_BUCKET_CITATION_IDS",
    "PROFILE_VEGA_INTRA_BUCKET_CITATION_IDS",
    "PROFILE_VEGA_LIQUIDITY_HORIZON_DAYS",
    "PROFILE_VEGA_OPTION_TENOR_CITATION_IDS",
    "PROFILE_VEGA_RISK_WEIGHT_CITATION_IDS",
    "PROFILE_VEGA_SCENARIO_CITATION_IDS",
    "girr_vega_intra_bucket_correlation",
    "girr_vega_liquidity_horizon_days",
    "girr_vega_option_tenor_definition",
    "girr_vega_option_tenors",
    "vega_inter_bucket_citation_ids",
    "vega_intra_bucket_citation_ids",
    "vega_liquidity_horizon_days",
    "vega_option_tenor_correlation",
    "vega_risk_weight",
    "vega_scenario_citation_ids",
]
