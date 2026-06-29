"""U.S. NPR 2.0 SBM citation fragments.

Regulatory traceability:
    U.S. NPR 2.0 section V.A.7.a citation ids used by SBM comparison-profile payloads.
"""

from __future__ import annotations

from frtb_sbm.data_models import SbmCitation
from frtb_sbm.us_npr_citation_map import BASEL_TO_US_NPR_CITATION_IDS
from frtb_sbm.reference_citations_basel_core import BASEL_CORE_CITATIONS
from frtb_sbm.reference_citations_basel_risk_classes import BASEL_RISK_CLASS_CITATIONS

US_NPR_2_0_URL = "https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959"
_US_NPR_SOURCE_ID = "us_npr_2_0_91_fr_14952"
_US_NPR_LOCATION = "91 FR 14952, section V.A.7.a"

_BASEL_CITATIONS = {**BASEL_CORE_CITATIONS, **BASEL_RISK_CLASS_CITATIONS}


def _npr_citation_from_basel(basel_citation_id: str, npr_citation_id: str) -> SbmCitation:
    basel = _BASEL_CITATIONS[basel_citation_id]
    return SbmCitation(
        source_id=_US_NPR_SOURCE_ID,
        location=_US_NPR_LOCATION,
        url=US_NPR_2_0_URL,
        note=(
            "U.S. NPR comparison slice — Basel-mirrored numerics with profile-owned "
            f"citation routing; {basel.note}"
        ),
    )


US_NPR_2_0_CITATIONS: dict[str, SbmCitation] = {
    "us_npr_91_fr_14952_va7a_sbm_scope": SbmCitation(
        source_id=_US_NPR_SOURCE_ID,
        location=_US_NPR_LOCATION,
        url=US_NPR_2_0_URL,
        note=(
            "Standardized non-default capital requirement scope: sensitivities-based "
            "method capital plus residual risk add-on for comparison-profile runs."
        ),
    ),
    "us_npr_91_fr_14952_va7a_girr_buckets": SbmCitation(
        source_id=_US_NPR_SOURCE_ID,
        location=_US_NPR_LOCATION,
        url=US_NPR_2_0_URL,
        note="GIRR delta currency bucket mapping for the NPR comparison slice.",
    ),
    "us_npr_91_fr_14952_va7a_girr_delta_weights": SbmCitation(
        source_id=_US_NPR_SOURCE_ID,
        location=_US_NPR_LOCATION,
        url=US_NPR_2_0_URL,
        note="GIRR delta tenor risk weights used by the NPR comparison slice.",
    ),
    "us_npr_91_fr_14952_va7a_girr_special_factors": SbmCitation(
        source_id=_US_NPR_SOURCE_ID,
        location=_US_NPR_LOCATION,
        url=US_NPR_2_0_URL,
        note="GIRR inflation and cross-currency-basis special risk-factor weights.",
    ),
    "us_npr_91_fr_14952_va7a_girr_sqrt2": SbmCitation(
        source_id=_US_NPR_SOURCE_ID,
        location=_US_NPR_LOCATION,
        url=US_NPR_2_0_URL,
        note="Specified-currency square-root-of-two GIRR risk-weight adjustment.",
    ),
    "us_npr_91_fr_14952_va7a_girr_intra": SbmCitation(
        source_id=_US_NPR_SOURCE_ID,
        location=_US_NPR_LOCATION,
        url=US_NPR_2_0_URL,
        note="GIRR delta intra-bucket tenor, curve, inflation, and XCCY correlations.",
    ),
    "us_npr_91_fr_14952_va7a_girr_inter": SbmCitation(
        source_id=_US_NPR_SOURCE_ID,
        location=_US_NPR_LOCATION,
        url=US_NPR_2_0_URL,
        note="GIRR delta inter-bucket correlation used in the NPR comparison slice.",
    ),
    "us_npr_91_fr_14952_va7a_correlation_scenarios": SbmCitation(
        source_id=_US_NPR_SOURCE_ID,
        location=_US_NPR_LOCATION,
        url=US_NPR_2_0_URL,
        note="Low, medium, and high correlation scenario aggregation.",
    ),
}

for _basel_id, _npr_id in BASEL_TO_US_NPR_CITATION_IDS.items():
    if _npr_id in US_NPR_2_0_CITATIONS:
        continue
    if _basel_id in _BASEL_CITATIONS:
        US_NPR_2_0_CITATIONS[_npr_id] = _npr_citation_from_basel(_basel_id, _npr_id)

__all__ = ["US_NPR_2_0_CITATIONS"]