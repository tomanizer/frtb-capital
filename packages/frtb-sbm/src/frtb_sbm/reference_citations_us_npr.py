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
