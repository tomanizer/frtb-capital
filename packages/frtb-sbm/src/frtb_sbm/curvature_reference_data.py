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
from frtb_sbm.girr_reference_tables import (
    PROFILE_GIRR_CURVATURE_CITATION_IDS,
    PROFILE_GIRR_CURVATURE_RISK_WEIGHT_CITATION_IDS,
)
from frtb_sbm.reference_citations_eu_crr3 import translate_basel_citation_ids_to_eu
from frtb_sbm.reference_profiles import (
    _coerce_risk_class,
    _resolve_supported_profile,
    citations_for_profile,
)

_BASEL_CURVATURE_REQUIRED_CITATIONS = (
    "basel_mar21_curvature",
    "basel_mar21_96",
    "basel_mar21_97",
    "basel_mar21_98",
    "basel_mar21_99",
    "basel_mar21_100",
    "basel_mar21_101",
)

_BASEL_CURVATURE_RISK_CLASSES = (
    SbmRiskClass.GIRR,
    SbmRiskClass.FX,
    SbmRiskClass.EQUITY,
    SbmRiskClass.COMMODITY,
    SbmRiskClass.CSR_NONSEC,
    SbmRiskClass.CSR_SEC_CTP,
    SbmRiskClass.CSR_SEC_NONCTP,
)

PROFILE_CURVATURE_CITATION_IDS: dict[
    SbmRegulatoryProfile,
    dict[SbmRiskClass, tuple[str, ...]],
] = {
    SbmRegulatoryProfile.BASEL_MAR21: {
        risk_class: _BASEL_CURVATURE_REQUIRED_CITATIONS
        for risk_class in _BASEL_CURVATURE_RISK_CLASSES
    },
    SbmRegulatoryProfile.US_NPR_2_0: {
        SbmRiskClass.GIRR: PROFILE_GIRR_CURVATURE_CITATION_IDS[SbmRegulatoryProfile.US_NPR_2_0],
        SbmRiskClass.FX: (
            "us_npr_91_fr_14952_va7a_fx_curvature_factors",
            "us_npr_91_fr_14952_va7a_fx_curvature_shocks",
            "us_npr_91_fr_14952_va7a_fx_curvature_intra",
            "us_npr_91_fr_14952_va7a_fx_curvature_inter",
            "us_npr_91_fr_14952_va7a_fx_curvature_scenarios",
        ),
    },
    SbmRegulatoryProfile.EU_CRR3: {
        risk_class: translate_basel_citation_ids_to_eu(_BASEL_CURVATURE_REQUIRED_CITATIONS)
        for risk_class in (
            SbmRiskClass.GIRR,
            SbmRiskClass.FX,
            SbmRiskClass.EQUITY,
            SbmRiskClass.COMMODITY,
        )
    },
    SbmRegulatoryProfile.PRA_UK_CRR: {
        SbmRiskClass.GIRR: (
            "pra_uk_crr_325e_components",
            "pra_uk_crr_325g_curvature_aggregation",
            "pra_uk_crr_325h_correlation_scenarios",
            "pra_uk_crr_325l_girr_risk_factors",
            "pra_uk_crr_325ax_curvature_risk_weights",
            "pra_uk_crr_325ay_curvature_correlations",
        ),
        SbmRiskClass.FX: (
            "pra_uk_crr_325e_components",
            "pra_uk_crr_325g_curvature_aggregation",
            "pra_uk_crr_325h_correlation_scenarios",
            "pra_uk_crr_325q_fx_risk_factors",
            "pra_uk_crr_325ax_fx_curvature_risk_weights",
            "pra_uk_crr_325ay_curvature_correlations",
            "pra_uk_crr_325av_fx_delta_weights",
            "pra_uk_crr_325aw_fx_delta_inter",
        ),
    },
}

PROFILE_CURVATURE_RISK_WEIGHT_CITATION_IDS: dict[
    SbmRegulatoryProfile,
    dict[SbmRiskClass, str],
] = {
    SbmRegulatoryProfile.BASEL_MAR21: {
        SbmRiskClass.GIRR: PROFILE_GIRR_CURVATURE_RISK_WEIGHT_CITATION_IDS[
            SbmRegulatoryProfile.BASEL_MAR21
        ],
        SbmRiskClass.FX: "basel_mar21_98",
        SbmRiskClass.EQUITY: "basel_mar21_98",
        SbmRiskClass.COMMODITY: "basel_mar21_99",
        SbmRiskClass.CSR_NONSEC: "basel_mar21_99",
        SbmRiskClass.CSR_SEC_CTP: "basel_mar21_99",
        SbmRiskClass.CSR_SEC_NONCTP: "basel_mar21_99",
    },
    SbmRegulatoryProfile.US_NPR_2_0: {
        SbmRiskClass.GIRR: PROFILE_GIRR_CURVATURE_RISK_WEIGHT_CITATION_IDS[
            SbmRegulatoryProfile.US_NPR_2_0
        ],
        SbmRiskClass.FX: "us_npr_91_fr_14952_va7a_fx_curvature_shocks",
    },
    SbmRegulatoryProfile.EU_CRR3: {
        SbmRiskClass.GIRR: translate_basel_citation_ids_to_eu(("basel_mar21_99",))[0],
        SbmRiskClass.FX: translate_basel_citation_ids_to_eu(("basel_mar21_98",))[0],
        SbmRiskClass.EQUITY: translate_basel_citation_ids_to_eu(("basel_mar21_98",))[0],
        SbmRiskClass.COMMODITY: translate_basel_citation_ids_to_eu(("basel_mar21_99",))[0],
    },
    SbmRegulatoryProfile.PRA_UK_CRR: {
        SbmRiskClass.GIRR: "pra_uk_crr_325ax_curvature_risk_weights",
        SbmRiskClass.FX: "pra_uk_crr_325ax_fx_curvature_risk_weights",
    },
}


def curvature_citation_ids(
    profile: SbmRegulatoryProfile | str,
    risk_class: SbmRiskClass | str = SbmRiskClass.GIRR,
) -> tuple[str, ...]:
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
    resolved_class = _coerce_risk_class(risk_class)
    citations = citations_for_profile(resolved)
    required = PROFILE_CURVATURE_CITATION_IDS.get(resolved, {}).get(resolved_class)
    if required is None:
        raise UnsupportedRegulatoryFeatureError(
            "curvature citations are unavailable for "
            f"profile={profile!r} risk_class={resolved_class.value}"
        )
    missing = [citation_id for citation_id in required if citation_id not in citations]
    if missing:
        raise UnsupportedRegulatoryFeatureError(
            "curvature citations are unavailable for "
            f"profile={profile!r} risk_class={resolved_class.value}"
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
        citation_id = _curvature_risk_weight_citation_id(profile, resolved_class)
        return rule.risk_weight, (citation_id, rule.citation_id)
    if resolved_class is SbmRiskClass.FX:
        weight, citations = fx_delta_risk_weight(
            profile,
            currency=currency or risk_factor or bucket_id,
            reporting_currency=reporting_currency,
        )
        return weight, _merge_citation_ids(
            (_curvature_risk_weight_citation_id(profile, resolved_class),), citations
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
        return weight, _merge_citation_ids(
            (_curvature_risk_weight_citation_id(profile, resolved_class),), citations
        )
    if resolved_class is SbmRiskClass.COMMODITY:
        weight, citations = commodity_delta_risk_weight(profile, bucket_id=bucket_id)
        return weight, _merge_citation_ids(
            (_curvature_risk_weight_citation_id(profile, resolved_class),), citations
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


def _curvature_risk_weight_citation_id(
    profile: SbmRegulatoryProfile | str,
    risk_class: SbmRiskClass,
) -> str:
    resolved = _resolve_supported_profile(profile)
    try:
        return PROFILE_CURVATURE_RISK_WEIGHT_CITATION_IDS[resolved][risk_class]
    except KeyError as exc:
        raise UnsupportedRegulatoryFeatureError(
            "curvature risk-weight citation is unavailable for "
            f"profile={resolved.value} risk_class={risk_class.value}"
        ) from exc


__all__ = [
    "PROFILE_CURVATURE_CITATION_IDS",
    "PROFILE_CURVATURE_RISK_WEIGHT_CITATION_IDS",
    "curvature_citation_ids",
    "curvature_risk_weight",
]
