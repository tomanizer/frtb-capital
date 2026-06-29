"""PRA UK CRR SBM citation fragments.

Regulatory traceability:
    UK CRR Articles 325r-325az citation ids used by the PRA_UK_CRR
    comparison-profile payloads.
"""

from __future__ import annotations

from frtb_sbm.data_models import SbmCitation
from frtb_sbm.pra_uk_crr_citation_map import BASEL_TO_PRA_UK_CRR_CITATION_IDS
from frtb_sbm.reference_citations_basel_core import BASEL_CORE_CITATIONS
from frtb_sbm.reference_citations_basel_risk_classes import BASEL_RISK_CLASS_CITATIONS

PRA_UK_CRR_URL = (
    "https://www.legislation.gov.uk/eur/2013/575/part/8/crossheading/sensitivities-based-method"
)
_PRA_UK_CRR_SOURCE_ID = "uk_crr_sbm_retained"
_PRA_UK_CRR_LOCATION = "UK CRR, Articles 325r-325az"

_BASEL_CITATIONS = {**BASEL_CORE_CITATIONS, **BASEL_RISK_CLASS_CITATIONS}


def _pra_citation_from_basel(basel_citation_id: str, pra_citation_id: str) -> SbmCitation:
    basel = _BASEL_CITATIONS[basel_citation_id]
    return SbmCitation(
        source_id=_PRA_UK_CRR_SOURCE_ID,
        location=_PRA_UK_CRR_LOCATION,
        url=PRA_UK_CRR_URL,
        note=f"PRA UK CRR comparison slice — {basel.note}",
    )


PRA_UK_CRR_CITATIONS: dict[str, SbmCitation] = {
    "pra_uk_crr_art_325r_sbm_scope": SbmCitation(
        source_id=_PRA_UK_CRR_SOURCE_ID,
        location="Article 325r",
        url=PRA_UK_CRR_URL,
        note=(
            "UK sensitivities-based method own funds requirement for market risk "
            "under the comparison profile."
        ),
    ),
    "pra_uk_crr_art_325r_girr_buckets": SbmCitation(
        source_id=_PRA_UK_CRR_SOURCE_ID,
        location="Article 325r",
        url=PRA_UK_CRR_URL,
        note="GIRR delta currency bucket mapping for the PRA UK CRR comparison slice.",
    ),
    "pra_uk_crr_art_325r_girr_delta_weights": SbmCitation(
        source_id=_PRA_UK_CRR_SOURCE_ID,
        location="Article 325r",
        url=PRA_UK_CRR_URL,
        note="GIRR delta tenor risk weights used by the PRA UK CRR comparison slice.",
    ),
    "pra_uk_crr_art_325r_girr_special_factors": SbmCitation(
        source_id=_PRA_UK_CRR_SOURCE_ID,
        location="Article 325r",
        url=PRA_UK_CRR_URL,
        note="GIRR inflation and cross-currency-basis special risk-factor weights.",
    ),
    "pra_uk_crr_art_325r_girr_sqrt2": SbmCitation(
        source_id=_PRA_UK_CRR_SOURCE_ID,
        location="Article 325r",
        url=PRA_UK_CRR_URL,
        note="Specified-currency square-root-of-two GIRR risk-weight adjustment.",
    ),
    "pra_uk_crr_art_325r_girr_intra": SbmCitation(
        source_id=_PRA_UK_CRR_SOURCE_ID,
        location="Article 325r",
        url=PRA_UK_CRR_URL,
        note="GIRR delta intra-bucket tenor, curve, inflation, and XCCY correlations.",
    ),
    "pra_uk_crr_art_325r_girr_inter": SbmCitation(
        source_id=_PRA_UK_CRR_SOURCE_ID,
        location="Article 325r",
        url=PRA_UK_CRR_URL,
        note="GIRR delta inter-bucket correlation used in the PRA UK CRR comparison slice.",
    ),
    "pra_uk_crr_art_325u_correlation_scenarios": SbmCitation(
        source_id=_PRA_UK_CRR_SOURCE_ID,
        location="Article 325u",
        url=PRA_UK_CRR_URL,
        note="Low, medium, and high correlation scenario aggregation.",
    ),
}

for _basel_id, _pra_id in BASEL_TO_PRA_UK_CRR_CITATION_IDS.items():
    if _pra_id in PRA_UK_CRR_CITATIONS:
        continue
    if _basel_id in _BASEL_CITATIONS:
        PRA_UK_CRR_CITATIONS[_pra_id] = _pra_citation_from_basel(_basel_id, _pra_id)

__all__ = ["PRA_UK_CRR_CITATIONS"]