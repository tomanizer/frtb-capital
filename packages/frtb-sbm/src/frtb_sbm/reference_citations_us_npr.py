"""U.S. NPR 2.0 SBM citation fragments.

Regulatory traceability:
    U.S. NPR 2.0 section V.A.7.a citation ids used by SBM comparison-profile payloads.
"""

from __future__ import annotations

from frtb_sbm.data_models import SbmCitation

US_NPR_2_0_URL = "https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959"

US_NPR_2_0_CITATIONS: dict[str, SbmCitation] = {
    "us_npr_91_fr_14952_va7a_sbm_scope": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note=(
            "Standardized non-default capital requirement scope: sensitivities-based "
            "method capital plus residual risk add-on for comparison-profile runs."
        ),
    ),
    "us_npr_91_fr_14952_va7a_girr_buckets": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note="GIRR delta currency bucket mapping for the NPR comparison slice.",
    ),
    "us_npr_91_fr_14952_va7a_girr_delta_weights": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note="GIRR delta tenor risk weights used by the NPR comparison slice.",
    ),
    "us_npr_91_fr_14952_va7a_girr_vega_option_tenors": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a, footnote 256",
        url=US_NPR_2_0_URL,
        note="GIRR vega option- and underlying-tenor axes used by the NPR comparison slice.",
    ),
    "us_npr_91_fr_14952_va7a_girr_vega_lh_rw": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a, footnote 256",
        url=US_NPR_2_0_URL,
        note="GIRR vega liquidity-horizon scaling and risk-weight treatment.",
    ),
    "us_npr_91_fr_14952_va7a_girr_vega_intra": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a, footnote 256",
        url=US_NPR_2_0_URL,
        note="GIRR vega same-bucket option-tenor and underlying-tenor correlation treatment.",
    ),
    "us_npr_91_fr_14952_va7a_girr_vega_inter": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a, footnote 256",
        url=US_NPR_2_0_URL,
        note="GIRR vega cross-bucket correlation treatment used by the NPR comparison slice.",
    ),
    "us_npr_91_fr_14952_va7a_girr_curvature_factors": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15037-15038, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note="GIRR curvature sensitivity and risk-factor treatment for the NPR comparison slice.",
    ),
    "us_npr_91_fr_14952_va7a_girr_curvature_shocks": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15037-15038, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note="GIRR curvature upward/downward shock and risk-weight treatment.",
    ),
    "us_npr_91_fr_14952_va7a_girr_curvature_intra": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15038, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note="GIRR curvature intra-bucket aggregation and correlation treatment.",
    ),
    "us_npr_91_fr_14952_va7a_girr_curvature_inter": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15038, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note="GIRR curvature inter-bucket aggregation and correlation treatment.",
    ),
    "us_npr_91_fr_14952_va7a_girr_curvature_scenarios": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15038, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note="GIRR curvature low, medium, and high correlation scenario selection.",
    ),
    "us_npr_91_fr_14952_va7a_fx_reporting_currency": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note=(
            "FX risk factors are treated as reporting-currency currency-pair "
            "sensitivities for the initial NPR comparison-profile FX slice."
        ),
    ),
    "us_npr_91_fr_14952_va7a_fx_base_currency_approval": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note=(
            "FX base-currency treatment requires prior supervisory approval and "
            "explicit translation-risk evidence before runtime support can open."
        ),
    ),
    "us_npr_91_fr_14952_va7a_girr_special_factors": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note="GIRR inflation and cross-currency-basis special risk-factor weights.",
    ),
    "us_npr_91_fr_14952_va7a_girr_sqrt2": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note="Specified-currency square-root-of-two GIRR risk-weight adjustment.",
    ),
    "us_npr_91_fr_14952_va7a_girr_intra": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note="GIRR delta intra-bucket tenor, curve, inflation, and XCCY correlations.",
    ),
    "us_npr_91_fr_14952_va7a_girr_inter": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note="GIRR delta inter-bucket correlation used in the NPR comparison slice.",
    ),
    "us_npr_91_fr_14952_va7a_correlation_scenarios": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note="Low, medium, and high correlation scenario aggregation.",
    ),
}

__all__ = ["US_NPR_2_0_CITATIONS"]
