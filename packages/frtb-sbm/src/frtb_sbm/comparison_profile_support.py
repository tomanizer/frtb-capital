"""Shared helpers for full-slice SBM comparison regulatory profiles."""

from __future__ import annotations

from frtb_sbm.data_models import SbmRegulatoryProfile
from frtb_sbm.eu_crr3_citation_map import BASEL_TO_EU_CRR3_CITATION_IDS
from frtb_sbm.pra_uk_crr_citation_map import BASEL_TO_PRA_UK_CRR_CITATION_IDS
from frtb_sbm.us_npr_citation_map import BASEL_TO_US_NPR_CITATION_IDS

FULL_COMPARISON_PROFILES: frozenset[SbmRegulatoryProfile] = frozenset(
    {
        SbmRegulatoryProfile.US_NPR_2_0,
        SbmRegulatoryProfile.EU_CRR3,
        SbmRegulatoryProfile.PRA_UK_CRR,
    }
)

COMPARISON_PROFILE_CITATION_MAPS: dict[SbmRegulatoryProfile, dict[str, str]] = {
    SbmRegulatoryProfile.US_NPR_2_0: BASEL_TO_US_NPR_CITATION_IDS,
    SbmRegulatoryProfile.EU_CRR3: BASEL_TO_EU_CRR3_CITATION_IDS,
    SbmRegulatoryProfile.PRA_UK_CRR: BASEL_TO_PRA_UK_CRR_CITATION_IDS,
}

__all__ = [
    "COMPARISON_PROFILE_CITATION_MAPS",
    "FULL_COMPARISON_PROFILES",
]
