"""PRA UK CRR SBM citation fragments.

Regulatory traceability:
    PRA PS1/26 policy anchor and UK CRR Articles 325r-325az citation ids used by
    the PRA_UK_CRR comparison-profile payloads. Retained Chapter 1a articles are
    omitted on legislation.gov.uk since 1 January 2022; live UK SBM text is in
    the PRA Rulebook cross-referenced by PS1/26.
"""

from __future__ import annotations

import re

from frtb_sbm.data_models import SbmCitation
from frtb_sbm.pra_uk_crr_citation_map import BASEL_TO_PRA_UK_CRR_CITATION_IDS
from frtb_sbm.reference_citations_basel_core import BASEL_CORE_CITATIONS
from frtb_sbm.reference_citations_basel_risk_classes import BASEL_RISK_CLASS_CITATIONS

PRA_UK_CRR_PS1_26_URL = (
    "https://www.bankofengland.co.uk/prudential-regulation/publication/2026/"
    "january/implementation-of-the-basel-3-1-final-rules-policy-statement"
)
PRA_UK_CRR_LEGISLATION_CHAPTER_URL = (
    "https://www.legislation.gov.uk/eur/2013/575/part/THREE/title/IV/chapter/1a"
)
PRA_UK_CRR_URL = PRA_UK_CRR_LEGISLATION_CHAPTER_URL
_PRA_UK_CRR_SOURCE_ID = "uk_crr_sbm_retained"
_PRA_UK_CRR_POLICY_SOURCE_ID = "uk_pra_ps1_26_sbm"
_PRA_UK_CRR_LOCATION = "UK CRR Part Three Title IV Chapter 1a, Articles 325r-325az"
_ARTICLE_ID_PATTERN = re.compile(r"^pra_uk_crr_art_(325[a-z]+)_")

_BASEL_CITATIONS = {**BASEL_CORE_CITATIONS, **BASEL_RISK_CLASS_CITATIONS}


def _uk_crr_article_url(article: str) -> str:
    return f"https://www.legislation.gov.uk/eur/2013/575/article/{article}"


def _article_from_pra_citation_id(citation_id: str) -> str:
    match = _ARTICLE_ID_PATTERN.match(citation_id)
    if match is None:
        return "325r"
    return match.group(1)


def _pra_citation_from_basel(basel_citation_id: str, pra_citation_id: str) -> SbmCitation:
    basel = _BASEL_CITATIONS[basel_citation_id]
    article = _article_from_pra_citation_id(pra_citation_id)
    return SbmCitation(
        source_id=_PRA_UK_CRR_SOURCE_ID,
        location=f"Article {article}",
        url=_uk_crr_article_url(article),
        note=(
            "PRA UK CRR comparison slice — Basel-mirrored numerics with profile-owned "
            f"citation routing; {basel.note}"
        ),
    )


PRA_UK_CRR_CITATIONS: dict[str, SbmCitation] = {
    "pra_uk_crr_art_325r_sbm_scope": SbmCitation(
        source_id=_PRA_UK_CRR_POLICY_SOURCE_ID,
        location="PRA PS1/26 Chapter 3; UK CRR Article 325r",
        url=PRA_UK_CRR_PS1_26_URL,
        note=(
            "UK sensitivities-based method own funds requirement for market risk "
            "under the comparison profile. PS1/26 is the policy anchor; Article "
            "325r is the retained CRR3 article crosswalk."
        ),
    ),
    "pra_uk_crr_art_325r_girr_buckets": SbmCitation(
        source_id=_PRA_UK_CRR_SOURCE_ID,
        location="Article 325r",
        url=_uk_crr_article_url("325r"),
        note="GIRR delta currency bucket mapping for the PRA UK CRR comparison slice.",
    ),
    "pra_uk_crr_art_325r_girr_delta_weights": SbmCitation(
        source_id=_PRA_UK_CRR_SOURCE_ID,
        location="Article 325r",
        url=_uk_crr_article_url("325r"),
        note="GIRR delta tenor risk weights used by the PRA UK CRR comparison slice.",
    ),
    "pra_uk_crr_art_325r_girr_special_factors": SbmCitation(
        source_id=_PRA_UK_CRR_SOURCE_ID,
        location="Article 325r",
        url=_uk_crr_article_url("325r"),
        note="GIRR inflation and cross-currency-basis special risk-factor weights.",
    ),
    "pra_uk_crr_art_325r_girr_sqrt2": SbmCitation(
        source_id=_PRA_UK_CRR_SOURCE_ID,
        location="Article 325r",
        url=_uk_crr_article_url("325r"),
        note="Specified-currency square-root-of-two GIRR risk-weight adjustment.",
    ),
    "pra_uk_crr_art_325r_girr_intra": SbmCitation(
        source_id=_PRA_UK_CRR_SOURCE_ID,
        location="Article 325r",
        url=_uk_crr_article_url("325r"),
        note="GIRR delta intra-bucket tenor, curve, inflation, and XCCY correlations.",
    ),
    "pra_uk_crr_art_325r_girr_inter": SbmCitation(
        source_id=_PRA_UK_CRR_SOURCE_ID,
        location="Article 325r",
        url=_uk_crr_article_url("325r"),
        note="GIRR delta inter-bucket correlation used in the PRA UK CRR comparison slice.",
    ),
    "pra_uk_crr_art_325u_correlation_scenarios": SbmCitation(
        source_id=_PRA_UK_CRR_SOURCE_ID,
        location="Article 325u",
        url=_uk_crr_article_url("325u"),
        note="Low, medium, and high correlation scenario aggregation.",
    ),
}

for _basel_id, _pra_id in BASEL_TO_PRA_UK_CRR_CITATION_IDS.items():
    if _pra_id in PRA_UK_CRR_CITATIONS:
        continue
    if _basel_id in _BASEL_CITATIONS:
        PRA_UK_CRR_CITATIONS[_pra_id] = _pra_citation_from_basel(_basel_id, _pra_id)

__all__ = [
    "PRA_UK_CRR_CITATIONS",
    "PRA_UK_CRR_LEGISLATION_CHAPTER_URL",
    "PRA_UK_CRR_PS1_26_URL",
    "PRA_UK_CRR_URL",
]
