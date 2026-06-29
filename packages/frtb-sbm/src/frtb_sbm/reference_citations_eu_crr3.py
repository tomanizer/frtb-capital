"""EU CRR3 SBM citation fragments.

Regulatory traceability:
    Regulation (EU) 2024/1623 Articles 325e-325az citation ids used by the
    EU_CRR3 comparison-profile payloads.
"""

from __future__ import annotations

from frtb_sbm.data_models import SbmCitation
from frtb_sbm.eu_crr3_citation_map import BASEL_TO_EU_CRR3_CITATION_IDS
from frtb_sbm.reference_citations_basel_core import BASEL_CORE_CITATIONS
from frtb_sbm.reference_citations_basel_risk_classes import BASEL_RISK_CLASS_CITATIONS

EU_CRR3_URL = "https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng"
_EU_CRR3_SOURCE_ID = "eu_crr3_2024_1623"
_EU_CRR3_LOCATION = "Regulation (EU) 2024/1623, Articles 325e-325az"

_BASEL_CITATIONS = {**BASEL_CORE_CITATIONS, **BASEL_RISK_CLASS_CITATIONS}


def _eu_citation_from_basel(basel_citation_id: str, eu_citation_id: str) -> SbmCitation:
    basel = _BASEL_CITATIONS[basel_citation_id]
    return SbmCitation(
        source_id=_EU_CRR3_SOURCE_ID,
        location=_EU_CRR3_LOCATION,
        url=EU_CRR3_URL,
        note=(
            "EU CRR3 comparison slice — Basel-mirrored numerics with profile-owned "
            f"citation routing; {basel.note}"
        ),
    )


EU_CRR3_CITATIONS: dict[str, SbmCitation] = {
    "eu_crr3_art_325r_sbm_scope": SbmCitation(
        source_id=_EU_CRR3_SOURCE_ID,
        location="Article 325r",
        url=EU_CRR3_URL,
        note=(
            "EU sensitivities-based method own funds requirement for market risk "
            "under the comparison profile."
        ),
    ),
    "eu_crr3_art_325r_girr_buckets": SbmCitation(
        source_id=_EU_CRR3_SOURCE_ID,
        location="Article 325r",
        url=EU_CRR3_URL,
        note="GIRR delta currency bucket mapping for the EU CRR3 comparison slice.",
    ),
    "eu_crr3_art_325r_girr_delta_weights": SbmCitation(
        source_id=_EU_CRR3_SOURCE_ID,
        location="Article 325r",
        url=EU_CRR3_URL,
        note="GIRR delta tenor risk weights used by the EU CRR3 comparison slice.",
    ),
    "eu_crr3_art_325r_girr_special_factors": SbmCitation(
        source_id=_EU_CRR3_SOURCE_ID,
        location="Article 325r",
        url=EU_CRR3_URL,
        note="GIRR inflation and cross-currency-basis special risk-factor weights.",
    ),
    "eu_crr3_art_325r_girr_sqrt2": SbmCitation(
        source_id=_EU_CRR3_SOURCE_ID,
        location="Article 325r",
        url=EU_CRR3_URL,
        note="Specified-currency square-root-of-two GIRR risk-weight adjustment.",
    ),
    "eu_crr3_art_325r_girr_intra": SbmCitation(
        source_id=_EU_CRR3_SOURCE_ID,
        location="Article 325r",
        url=EU_CRR3_URL,
        note="GIRR delta intra-bucket tenor, curve, inflation, and XCCY correlations.",
    ),
    "eu_crr3_art_325r_girr_inter": SbmCitation(
        source_id=_EU_CRR3_SOURCE_ID,
        location="Article 325r",
        url=EU_CRR3_URL,
        note="GIRR delta inter-bucket correlation used in the EU CRR3 comparison slice.",
    ),
    "eu_crr3_art_325u_correlation_scenarios": SbmCitation(
        source_id=_EU_CRR3_SOURCE_ID,
        location="Article 325u",
        url=EU_CRR3_URL,
        note="Low, medium, and high correlation scenario aggregation.",
    ),
}

for _basel_id, _eu_id in BASEL_TO_EU_CRR3_CITATION_IDS.items():
    if _eu_id in EU_CRR3_CITATIONS:
        continue
    if _basel_id in _BASEL_CITATIONS:
        EU_CRR3_CITATIONS[_eu_id] = _eu_citation_from_basel(_basel_id, _eu_id)

__all__ = ["EU_CRR3_CITATIONS"]
