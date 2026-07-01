"""Curvature reference-data lookups for SBM.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for reference_data.py, Basel
    MAR21.5 and MAR21.96-MAR21.101.
"""

from __future__ import annotations

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm._citations import merge_citation_ids as _merge_citation_ids
from frtb_sbm.commodity_reference_data import commodity_delta_risk_weight
from frtb_sbm.csr_nonsec_reference_data import csr_nonsec_delta_risk_weight
from frtb_sbm.data_models import SbmRegulatoryProfile, SbmRiskClass
from frtb_sbm.equity_reference_data import equity_delta_risk_weight
from frtb_sbm.fx_reference_data import fx_delta_risk_weight
from frtb_sbm.girr_reference_data import (
    PROFILE_GIRR_DELTA_RISK_WEIGHTS,
    _ensure_girr_delta_supported,
)
from frtb_sbm.reference_citations_eu_crr3 import translate_basel_citation_ids_to_eu
from frtb_sbm.reference_profiles import (
    _coerce_risk_class,
    _resolve_supported_profile,
    citations_for_profile,
)

PROFILE_CURVATURE_CITATION_IDS: dict[SbmRegulatoryProfile, tuple[str, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21: (
        "basel_mar21_curvature",
        "basel_mar21_96",
        "basel_mar21_97",
        "basel_mar21_98",
        "basel_mar21_99",
        "basel_mar21_100",
        "basel_mar21_101",
    ),
    SbmRegulatoryProfile.EU_CRR3: translate_basel_citation_ids_to_eu(
        (
            "basel_mar21_curvature",
            "basel_mar21_96",
            "basel_mar21_97",
            "basel_mar21_98",
            "basel_mar21_99",
            "basel_mar21_100",
            "basel_mar21_101",
        )
    ),
    SbmRegulatoryProfile.PRA_UK_CRR: (
        "pra_uk_crr_325e_components",
        "pra_uk_crr_325g_curvature_aggregation",
        "pra_uk_crr_325h_correlation_scenarios",
        "pra_uk_crr_325l_girr_risk_factors",
        "pra_uk_crr_325ax_curvature_risk_weights",
        "pra_uk_crr_325ay_curvature_correlations",
    ),
}

PROFILE_GIRR_CURVATURE_RISK_WEIGHT_CITATION_IDS: dict[SbmRegulatoryProfile, str] = {
    SbmRegulatoryProfile.BASEL_MAR21: "basel_mar21_99",
    SbmRegulatoryProfile.EU_CRR3: translate_basel_citation_ids_to_eu(("basel_mar21_99",))[0],
    SbmRegulatoryProfile.PRA_UK_CRR: "pra_uk_crr_325ax_curvature_risk_weights",
}


def curvature_citation_ids(profile: SbmRegulatoryProfile | str) -> tuple[str, ...]:
    """Return ordered citation ids for curvature contract validation.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.

    Returns
    -------
    tuple[str, ...]
    """

    resolved = _resolve_supported_profile(profile)
    citations = citations_for_profile(resolved)
    required = PROFILE_CURVATURE_CITATION_IDS.get(resolved)
    if required is None:
        raise UnsupportedRegulatoryFeatureError(
            f"curvature citations are unavailable for profile={profile!r}"
        )
    missing = [citation_id for citation_id in required if citation_id not in citations]
    if missing:
        raise UnsupportedRegulatoryFeatureError(
            f"curvature citations are unavailable for profile={profile!r}"
        )
    return required


def curvature_risk_weight(
    profile: SbmRegulatoryProfile | str,
    *,
    risk_class: SbmRiskClass | str,
    bucket_id: str = "",
    risk_factor: str = "",
    currency: str = "",
    reporting_currency: str = "",
) -> tuple[float, tuple[str, ...]]:
    """Return the cited MAR21.98/MAR21.99 curvature shock size for one factor.
    Parameters
    ----------
    profile, risk_class, bucket_id, risk_factor, currency, reporting_currency :
        See function signature for types and defaults.

    Returns
    -------
    tuple[float, tuple[str, ...]]
    """

    resolved_class = _coerce_risk_class(risk_class)
    if resolved_class is SbmRiskClass.GIRR:
        _ensure_girr_delta_supported(profile)
        resolved = _resolve_supported_profile(profile)
        rule = max(
            PROFILE_GIRR_DELTA_RISK_WEIGHTS[resolved],
            key=lambda item: item.risk_weight,
        )
        citation_id = PROFILE_GIRR_CURVATURE_RISK_WEIGHT_CITATION_IDS.get(resolved)
        if citation_id is None:
            raise UnsupportedRegulatoryFeatureError(
                f"GIRR curvature risk weights are unsupported for profile {resolved.value}"
            )
        return rule.risk_weight, (citation_id, rule.citation_id)
    if resolved_class is SbmRiskClass.FX:
        weight, citations = fx_delta_risk_weight(
            profile,
            currency=currency or risk_factor or bucket_id,
            reporting_currency=reporting_currency,
        )
        resolved = _resolve_supported_profile(profile)
        return weight, _merge_citation_ids(
            (_profile_citation_id(resolved, "basel_mar21_98"),), citations
        )
    if resolved_class is SbmRiskClass.EQUITY:
        from frtb_sbm.equity_reference_data import EQUITY_SPOT_RISK_FACTOR

        factor = risk_factor or EQUITY_SPOT_RISK_FACTOR
        if factor.strip().upper() != EQUITY_SPOT_RISK_FACTOR:
            raise UnsupportedRegulatoryFeatureError(
                "equity curvature has no capital requirement for equity repo rates (MAR21.12(3))"
            )
        weight, citations = equity_delta_risk_weight(
            profile,
            bucket_id=bucket_id,
            risk_factor=EQUITY_SPOT_RISK_FACTOR,
        )
        resolved = _resolve_supported_profile(profile)
        return weight, _merge_citation_ids(
            (_profile_citation_id(resolved, "basel_mar21_98"),), citations
        )
    if resolved_class is SbmRiskClass.COMMODITY:
        weight, citations = commodity_delta_risk_weight(profile, bucket_id=bucket_id)
        resolved = _resolve_supported_profile(profile)
        return weight, _merge_citation_ids(
            (_profile_citation_id(resolved, "basel_mar21_99"),), citations
        )
    if resolved_class is SbmRiskClass.CSR_NONSEC:
        weight, citations = csr_nonsec_delta_risk_weight(profile, bucket_id=bucket_id)
        return weight, _merge_citation_ids(("basel_mar21_99",), citations)
    if resolved_class is SbmRiskClass.CSR_SEC_CTP:
        from frtb_sbm.csr_sec_ctp_reference_data import csr_sec_ctp_delta_risk_weight

        weight, citations = csr_sec_ctp_delta_risk_weight(profile, bucket_id=bucket_id)
        return weight, _merge_citation_ids(("basel_mar21_99",), citations)
    if resolved_class is SbmRiskClass.CSR_SEC_NONCTP:
        from frtb_sbm.csr_sec_nonctp_reference_data import csr_sec_nonctp_delta_risk_weight

        weight, citations = csr_sec_nonctp_delta_risk_weight(profile, bucket_id=bucket_id)
        return weight, _merge_citation_ids(("basel_mar21_99",), citations)
    raise UnsupportedRegulatoryFeatureError(
        f"curvature risk weights are unsupported for risk_class={resolved_class.value}"
    )


def _profile_citation_id(profile: SbmRegulatoryProfile, basel_id: str) -> str:
    if profile is SbmRegulatoryProfile.EU_CRR3:
        return translate_basel_citation_ids_to_eu((basel_id,))[0]
    if profile is not SbmRegulatoryProfile.BASEL_MAR21:
        raise UnsupportedRegulatoryFeatureError(
            f"curvature citation {basel_id} is unsupported for profile {profile.value}"
        )
    return basel_id


__all__ = [
    "PROFILE_CURVATURE_CITATION_IDS",
    "PROFILE_GIRR_CURVATURE_RISK_WEIGHT_CITATION_IDS",
    "curvature_citation_ids",
    "curvature_risk_weight",
]
