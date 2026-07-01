"""Deterministic SBM reference-data payload assembly for hashing.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for reference_data.py and SBM-REF-001.
"""

from __future__ import annotations

from frtb_sbm.curvature_reference_data import (
    PROFILE_CURVATURE_CITATION_IDS,
    PROFILE_CURVATURE_RISK_WEIGHT_CITATION_IDS,
    curvature_citation_ids,
)
from frtb_sbm.data_models import SbmRegulatoryProfile, SbmRiskClass
from frtb_sbm.fx_reference_data import (
    FX_DELTA_RISK_WEIGHT,
    FX_INTER_BUCKET_CORRELATION,
    FX_INTRA_BUCKET_CORRELATION,
    PROFILE_FX_BUCKETS,
    PROFILE_FX_DELTA_INTER_BUCKET_CITATION_IDS,
    PROFILE_FX_DELTA_INTRA_BUCKET_CITATION_IDS,
    PROFILE_FX_DELTA_RISK_WEIGHT_CITATION_IDS,
    PROFILE_FX_DELTA_SQRT2_CITATION_IDS,
    fx_buckets_for_profile,
    fx_specified_currencies_for_profile,
)
from frtb_sbm.girr_reference_data import girr_buckets_for_profile, girr_tenors_for_profile
from frtb_sbm.girr_reference_tables import (
    GIRR_DELTA_INTRA_BUCKET_CONSTANT,
    GIRR_INTER_BUCKET_CORRELATION,
    GIRR_INTRA_BUCKET_CORRELATION_FLOOR,
    PROFILE_GIRR_CURVATURE_CITATION_IDS,
    PROFILE_GIRR_CURVATURE_INTER_BUCKET_CITATION_IDS,
    PROFILE_GIRR_CURVATURE_INTRA_BUCKET_CITATION_IDS,
    PROFILE_GIRR_CURVATURE_RISK_WEIGHT_CITATION_IDS,
    PROFILE_GIRR_CURVATURE_SCENARIO_CITATION_IDS,
    PROFILE_GIRR_DELTA_INTER_BUCKET_CITATION_IDS,
    PROFILE_GIRR_DELTA_INTRA_BUCKET_CITATION_IDS,
    PROFILE_GIRR_DELTA_RISK_WEIGHTS,
    PROFILE_GIRR_SPECIAL_RISK_FACTORS,
)
from frtb_sbm.reference_citations_eu_crr3 import eu_crr3_citation_id_for_basel
from frtb_sbm.reference_profiles import (
    _resolve_supported_profile,
    citations_for_profile,
    correlation_scenarios_for_profile,
)
from frtb_sbm.vega_reference_data import (
    EQUITY_VEGA_LARGE_CAP_INDEX_BUCKETS,
    EQUITY_VEGA_LARGE_CAP_INDEX_LIQUIDITY_HORIZON_DAYS,
    EQUITY_VEGA_SMALL_CAP_OTHER_BUCKETS,
    EQUITY_VEGA_SMALL_CAP_OTHER_LIQUIDITY_HORIZON_DAYS,
    GIRR_VEGA_INTRA_BUCKET_CONSTANT,
    GIRR_VEGA_RISK_WEIGHT_CAP,
    GIRR_VEGA_RISK_WEIGHT_FACTOR,
    PROFILE_GIRR_VEGA_INTRA_BUCKET_CITATION_IDS,
    PROFILE_GIRR_VEGA_LIQUIDITY_HORIZON_CITATION_IDS,
    PROFILE_GIRR_VEGA_LIQUIDITY_HORIZON_DAYS,
    PROFILE_VEGA_INTER_BUCKET_CITATION_IDS,
    PROFILE_VEGA_INTRA_BUCKET_CITATION_IDS,
    PROFILE_VEGA_LIQUIDITY_HORIZON_DAYS,
    PROFILE_VEGA_OPTION_TENOR_CITATION_IDS,
    PROFILE_VEGA_RISK_WEIGHT_CITATION_IDS,
    girr_vega_option_tenors,
)


def profile_reference_payload(profile: SbmRegulatoryProfile | str) -> dict[str, object]:
    """Return a deterministic, JSON-serialisable payload for profile hashing.

    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        Supported SBM regulatory profile identifier.

    Returns
    -------
    dict[str, object]
        Stable profile reference-data payload used by profile hash assembly.
    """

    resolved = _resolve_supported_profile(profile)
    payload = _base_payload(resolved)
    _add_girr_delta_payload(payload, resolved)
    _add_girr_vega_payload(payload, resolved)
    _add_girr_curvature_payload(payload, resolved)
    _add_non_girr_vega_payload(payload, resolved)
    _add_fx_payload(payload, resolved)
    _add_fx_curvature_payload(payload, resolved)
    _add_basel_curvature_and_non_girr_payloads(payload, resolved)
    return payload


def _base_payload(profile: SbmRegulatoryProfile) -> dict[str, object]:
    citations = citations_for_profile(profile)
    return {
        "profile": profile.value,
        "citations": {
            citation_id: {
                "source_id": citation.source_id,
                "location": citation.location,
                "url": citation.url,
                "note": citation.note,
            }
            for citation_id, citation in sorted(citations.items())
        },
    }


def _add_girr_delta_payload(payload: dict[str, object], profile: SbmRegulatoryProfile) -> None:
    if profile not in PROFILE_GIRR_DELTA_RISK_WEIGHTS:
        return
    payload.update(
        {
            "girr_buckets": [
                {
                    "bucket_id": bucket.bucket_id,
                    "currency": bucket.currency,
                    "citation_id": bucket.citation_id,
                }
                for bucket in girr_buckets_for_profile(profile)
            ],
            "girr_tenors": [
                {
                    "tenor": tenor.tenor,
                    "maturity_years": tenor.maturity_years,
                    "citation_id": tenor.citation_id,
                }
                for tenor in girr_tenors_for_profile(profile)
            ],
            "girr_delta_risk_weights": [
                {
                    "tenor": rule.tenor,
                    "risk_weight": rule.risk_weight,
                    "citation_id": rule.citation_id,
                }
                for rule in sorted(
                    PROFILE_GIRR_DELTA_RISK_WEIGHTS[profile],
                    key=lambda item: item.tenor,
                )
            ],
            "girr_special_risk_factors": [
                {
                    "risk_factor": rule.risk_factor,
                    "risk_weight": rule.risk_weight,
                    "citation_id": rule.citation_id,
                }
                for rule in PROFILE_GIRR_SPECIAL_RISK_FACTORS[profile]
            ],
            "correlation_scenarios": [
                {
                    "scenario": definition.scenario.value,
                    "multiplier": definition.multiplier,
                    "floor_factor": definition.floor_factor,
                    "cap": definition.cap,
                    "citation_id": definition.citation_id,
                }
                for definition in correlation_scenarios_for_profile(profile)
            ],
            "girr_delta_parameters": {
                "intra_bucket_constant": GIRR_DELTA_INTRA_BUCKET_CONSTANT,
                "intra_bucket_floor": GIRR_INTRA_BUCKET_CORRELATION_FLOOR,
                "inter_bucket_correlation": GIRR_INTER_BUCKET_CORRELATION,
                "intra_bucket_citation_id": PROFILE_GIRR_DELTA_INTRA_BUCKET_CITATION_IDS[profile],
                "inter_bucket_citation_id": PROFILE_GIRR_DELTA_INTER_BUCKET_CITATION_IDS[profile],
            },
        }
    )


def _add_girr_vega_payload(payload: dict[str, object], profile: SbmRegulatoryProfile) -> None:
    if profile not in PROFILE_GIRR_VEGA_LIQUIDITY_HORIZON_DAYS:
        return
    payload.update(
        {
            "girr_vega_parameters": {
                "liquidity_horizon_days": PROFILE_GIRR_VEGA_LIQUIDITY_HORIZON_DAYS[profile],
                "risk_weight_factor": GIRR_VEGA_RISK_WEIGHT_FACTOR,
                "risk_weight_cap": GIRR_VEGA_RISK_WEIGHT_CAP,
                "intra_bucket_constant": GIRR_VEGA_INTRA_BUCKET_CONSTANT,
                "liquidity_horizon_citation_id": (
                    PROFILE_GIRR_VEGA_LIQUIDITY_HORIZON_CITATION_IDS[profile]
                ),
                "intra_bucket_citation_id": PROFILE_GIRR_VEGA_INTRA_BUCKET_CITATION_IDS[profile],
            },
            "girr_vega_option_tenors": [
                {
                    "tenor": tenor.tenor,
                    "maturity_years": tenor.maturity_years,
                    "citation_id": tenor.citation_id,
                }
                for tenor in girr_vega_option_tenors(profile)
            ],
        }
    )


def _add_girr_curvature_payload(payload: dict[str, object], profile: SbmRegulatoryProfile) -> None:
    if profile is not SbmRegulatoryProfile.US_NPR_2_0:
        return
    if profile not in PROFILE_GIRR_CURVATURE_CITATION_IDS:
        return
    payload["girr_curvature_parameters"] = {
        "citation_ids": list(PROFILE_GIRR_CURVATURE_CITATION_IDS[profile]),
        "parallel_shift_risk_weight": max(
            rule.risk_weight for rule in PROFILE_GIRR_DELTA_RISK_WEIGHTS[profile]
        ),
        "risk_weight_citation_id": PROFILE_GIRR_CURVATURE_RISK_WEIGHT_CITATION_IDS[profile],
        "intra_bucket_citation_ids": list(
            PROFILE_GIRR_CURVATURE_INTRA_BUCKET_CITATION_IDS[profile]
        ),
        "inter_bucket_citation_ids": list(
            PROFILE_GIRR_CURVATURE_INTER_BUCKET_CITATION_IDS[profile]
        ),
        "scenario_citation_ids": list(PROFILE_GIRR_CURVATURE_SCENARIO_CITATION_IDS[profile]),
    }


def _add_non_girr_vega_payload(payload: dict[str, object], profile: SbmRegulatoryProfile) -> None:
    if profile not in PROFILE_VEGA_LIQUIDITY_HORIZON_DAYS:
        return
    parameters: dict[str, object] = {
        "liquidity_horizon_days": {
            risk_class.value: horizon
            for risk_class, horizon in sorted(
                PROFILE_VEGA_LIQUIDITY_HORIZON_DAYS[profile].items(),
                key=lambda item: item[0].value,
            )
            if risk_class not in {SbmRiskClass.EQUITY, SbmRiskClass.GIRR}
        },
        "equity_large_cap_index_bucket_ids": sorted(EQUITY_VEGA_LARGE_CAP_INDEX_BUCKETS),
        "equity_large_cap_index_liquidity_horizon_days": (
            EQUITY_VEGA_LARGE_CAP_INDEX_LIQUIDITY_HORIZON_DAYS
        ),
        "equity_small_cap_other_bucket_ids": sorted(EQUITY_VEGA_SMALL_CAP_OTHER_BUCKETS),
        "equity_small_cap_other_liquidity_horizon_days": (
            EQUITY_VEGA_SMALL_CAP_OTHER_LIQUIDITY_HORIZON_DAYS
        ),
        "risk_weight_factor": GIRR_VEGA_RISK_WEIGHT_FACTOR,
        "risk_weight_cap": GIRR_VEGA_RISK_WEIGHT_CAP,
    }
    payload["non_girr_vega_parameters"] = parameters
    if profile is not SbmRegulatoryProfile.US_NPR_2_0:
        parameters.update(
            {
                "intra_bucket_citation_id": _profile_citation_id(profile, "basel_mar21_94"),
                "inter_bucket_citation_id": _profile_citation_id(profile, "basel_mar21_95"),
            }
        )
        return
    parameters.update(
        {
            "risk_weight_citation_ids": {
                risk_class.value: PROFILE_VEGA_RISK_WEIGHT_CITATION_IDS[profile][risk_class]
                for risk_class in sorted(
                    PROFILE_VEGA_LIQUIDITY_HORIZON_DAYS[profile],
                    key=lambda item: item.value,
                )
                if risk_class not in {SbmRiskClass.EQUITY, SbmRiskClass.GIRR}
            },
            "option_tenor_citation_ids": {
                risk_class.value: PROFILE_VEGA_OPTION_TENOR_CITATION_IDS[profile][risk_class]
                for risk_class in sorted(
                    PROFILE_VEGA_LIQUIDITY_HORIZON_DAYS[profile],
                    key=lambda item: item.value,
                )
                if risk_class not in {SbmRiskClass.EQUITY, SbmRiskClass.GIRR}
            },
            "intra_bucket_citation_ids": {
                risk_class.value: list(PROFILE_VEGA_INTRA_BUCKET_CITATION_IDS[profile][risk_class])
                for risk_class in sorted(
                    PROFILE_VEGA_LIQUIDITY_HORIZON_DAYS[profile],
                    key=lambda item: item.value,
                )
                if risk_class not in {SbmRiskClass.EQUITY, SbmRiskClass.GIRR}
            },
            "inter_bucket_citation_ids": {
                risk_class.value: list(PROFILE_VEGA_INTER_BUCKET_CITATION_IDS[profile][risk_class])
                for risk_class in sorted(
                    PROFILE_VEGA_LIQUIDITY_HORIZON_DAYS[profile],
                    key=lambda item: item.value,
                )
                if risk_class not in {SbmRiskClass.EQUITY, SbmRiskClass.GIRR}
            },
        }
    )


def _add_fx_payload(payload: dict[str, object], profile: SbmRegulatoryProfile) -> None:
    if profile not in PROFILE_FX_BUCKETS:
        return
    fx_delta_parameters = {
        "risk_weight": FX_DELTA_RISK_WEIGHT,
        "intra_bucket_correlation": FX_INTRA_BUCKET_CORRELATION,
        "inter_bucket_correlation": FX_INTER_BUCKET_CORRELATION,
    }
    if profile is SbmRegulatoryProfile.US_NPR_2_0:
        fx_delta_parameters.update(
            {
                "risk_weight_citation_id": PROFILE_FX_DELTA_RISK_WEIGHT_CITATION_IDS[profile],
                "sqrt2_citation_id": PROFILE_FX_DELTA_SQRT2_CITATION_IDS[profile],
                "intra_bucket_citation_id": PROFILE_FX_DELTA_INTRA_BUCKET_CITATION_IDS[profile],
                "inter_bucket_citation_id": PROFILE_FX_DELTA_INTER_BUCKET_CITATION_IDS[profile],
            }
        )
    else:
        fx_delta_parameters.update(
            {
                "risk_weight_citation_id": _profile_citation_id(profile, "basel_mar21_87"),
                "sqrt2_citation_id": _profile_citation_id(profile, "basel_mar21_88"),
                "inter_bucket_citation_id": _profile_citation_id(profile, "basel_mar21_89"),
            }
        )
    payload.update(
        {
            "fx_buckets": [
                {
                    "bucket_id": bucket.bucket_id,
                    "currency": bucket.currency,
                    "citation_id": bucket.citation_id,
                }
                for bucket in fx_buckets_for_profile(profile)
            ],
            "fx_delta_parameters": fx_delta_parameters,
            "fx_specified_currencies": sorted(fx_specified_currencies_for_profile(profile)),
        }
    )


def _add_fx_curvature_payload(payload: dict[str, object], profile: SbmRegulatoryProfile) -> None:
    if profile is not SbmRegulatoryProfile.US_NPR_2_0:
        return
    if SbmRiskClass.FX not in PROFILE_CURVATURE_CITATION_IDS.get(profile, {}):
        return
    payload["fx_curvature_parameters"] = {
        "citation_ids": list(PROFILE_CURVATURE_CITATION_IDS[profile][SbmRiskClass.FX]),
        "risk_weight_citation_id": PROFILE_CURVATURE_RISK_WEIGHT_CITATION_IDS[profile][
            SbmRiskClass.FX
        ],
        "intra_bucket_citation_ids": [
            "us_npr_91_fr_14952_va7a_sbm_scope",
            "us_npr_91_fr_14952_va7a_fx_curvature_intra",
            "us_npr_91_fr_14952_va7a_fx_delta_intra",
        ],
        "inter_bucket_citation_ids": [
            "us_npr_91_fr_14952_va7a_sbm_scope",
            "us_npr_91_fr_14952_va7a_fx_curvature_inter",
            "us_npr_91_fr_14952_va7a_fx_delta_inter",
        ],
        "scenario_citation_ids": ["us_npr_91_fr_14952_va7a_fx_curvature_scenarios"],
    }


def _add_us_npr_equity_commodity_delta_payload(
    payload: dict[str, object],
    profile: SbmRegulatoryProfile,
) -> None:
    if profile is not SbmRegulatoryProfile.US_NPR_2_0:
        return
    from frtb_sbm.commodity_reference_data import commodity_reference_payload
    from frtb_sbm.equity_reference_data import equity_reference_payload

    payload.update(equity_reference_payload(profile))
    payload.update(commodity_reference_payload(profile))


def _add_basel_curvature_and_non_girr_payloads(
    payload: dict[str, object],
    profile: SbmRegulatoryProfile,
) -> None:
    if profile not in {SbmRegulatoryProfile.BASEL_MAR21, SbmRegulatoryProfile.EU_CRR3}:
        _add_us_npr_equity_commodity_delta_payload(payload, profile)
        return
    payload["curvature_parameters"] = {
        "citation_ids": list(curvature_citation_ids(profile)),
        "girr_parallel_shift_risk_weight": max(
            rule.risk_weight for rule in PROFILE_GIRR_DELTA_RISK_WEIGHTS[profile]
        ),
        "fx_equity_rule_citation_id": _profile_citation_id(profile, "basel_mar21_98"),
        "parallel_shift_rule_citation_id": _profile_citation_id(profile, "basel_mar21_99"),
        "intra_bucket_correlation_citation_id": _profile_citation_id(
            profile,
            "basel_mar21_100",
        ),
        "inter_bucket_correlation_citation_id": _profile_citation_id(
            profile,
            "basel_mar21_101",
        ),
    }
    _add_non_girr_reference_payloads(payload, profile)


def _add_non_girr_reference_payloads(
    payload: dict[str, object],
    profile: SbmRegulatoryProfile,
) -> None:
    from frtb_sbm.commodity_reference_data import commodity_reference_payload
    from frtb_sbm.equity_reference_data import equity_reference_payload

    payload.update(equity_reference_payload(profile))
    payload.update(commodity_reference_payload(profile))
    if profile is not SbmRegulatoryProfile.BASEL_MAR21:
        return
    from frtb_sbm.csr_nonsec_reference_data import csr_nonsec_reference_payload
    from frtb_sbm.csr_sec_ctp_reference_data import csr_sec_ctp_reference_payload
    from frtb_sbm.csr_sec_nonctp_reference_data import csr_sec_nonctp_reference_payload

    payload.update(csr_nonsec_reference_payload(profile))
    payload.update(csr_sec_nonctp_reference_payload(profile))
    payload.update(csr_sec_ctp_reference_payload(profile))


def _profile_citation_id(profile: SbmRegulatoryProfile, basel_id: str) -> str:
    if profile is SbmRegulatoryProfile.EU_CRR3:
        return eu_crr3_citation_id_for_basel(basel_id)
    return basel_id


__all__ = ["profile_reference_payload"]
