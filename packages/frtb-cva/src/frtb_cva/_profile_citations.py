"""Profile-specific CVA citation maps."""

from __future__ import annotations

from frtb_cva.data_models import CvaCitation, CvaRegulatoryProfile

US_NPR20_URL = "https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959"
EU_CRR3_URL = "https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng"
UK_PRA_PS1_26_URL = (
    "https://www.bankofengland.co.uk/prudential-regulation/publication/2026/"
    "january/implementation-of-the-basel-3-1-final-rules-policy-statement"
)
UK_PRA_CVA_RULEBOOK_URL = (
    "https://www.prarulebook.co.uk/-/media/pra/files/legal-instruments/2026/pra2026-1.pdf"
)

US_NPR20_CITATIONS: dict[str, CvaCitation] = {
    "us_npr20_vb_scope": CvaCitation(
        source_id="us_npr20_91fr14952",
        paragraph="91 FR 14952 section V.B",
        url=US_NPR20_URL,
        note="Proposed CVA risk scope, covered positions, and method context.",
    ),
    "us_npr20_vb_ba_cva": CvaCitation(
        source_id="us_npr20_91fr14952",
        paragraph="91 FR 14952 section V.B",
        url=US_NPR20_URL,
        note="Proposed U.S. NPR CVA risk measure crosswalk for BA-CVA-style inputs.",
    ),
    "us_npr20_vb_sa_cva": CvaCitation(
        source_id="us_npr20_91fr14952",
        paragraph="91 FR 14952 section V.B",
        url=US_NPR20_URL,
        note="Proposed U.S. NPR standardised CVA approach crosswalk.",
    ),
    "us_npr20_vb_hedges": CvaCitation(
        source_id="us_npr20_91fr14952",
        paragraph="91 FR 14952 sections V.A.6.c and V.B.3",
        url=US_NPR20_URL,
        note="Proposed CVA hedge and internal CVA risk transfer treatment.",
    ),
    "us_npr20_vb_materiality": CvaCitation(
        source_id="us_npr20_91fr14952",
        paragraph="91 FR 14952 section V.B",
        url=US_NPR20_URL,
        note="Proposed materiality and alternative CVA treatment context.",
    ),
}

EU_CRR3_CITATIONS: dict[str, CvaCitation] = {
    "eu_crr3_article_381": CvaCitation(
        source_id="eu_crr3_2024_1623",
        paragraph="CRR Article 381 as amended by Regulation (EU) 2024/1623",
        url=EU_CRR3_URL,
        note="EU CRR3 CVA risk definitions and title scope context.",
    ),
    "eu_crr3_article_382": CvaCitation(
        source_id="eu_crr3_2024_1623",
        paragraph="CRR Article 382 as amended by Regulation (EU) 2024/1623",
        url=EU_CRR3_URL,
        note="EU CRR3 CVA risk scope and approach selection.",
    ),
    "eu_crr3_article_383": CvaCitation(
        source_id="eu_crr3_2024_1623",
        paragraph="CRR Article 383 as amended by Regulation (EU) 2024/1623",
        url=EU_CRR3_URL,
        note="EU CRR3 standardised approach permission and governance.",
    ),
    "eu_crr3_articles_383a_383z": CvaCitation(
        source_id="eu_crr3_2024_1623",
        paragraph="CRR Articles 383a-383z inserted by Regulation (EU) 2024/1623",
        url=EU_CRR3_URL,
        note="EU CRR3 regulatory CVA model, sensitivity, bucket, weight, and correlation rules.",
    ),
    "eu_crr3_article_384": CvaCitation(
        source_id="eu_crr3_2024_1623",
        paragraph="CRR Article 384 as amended by Regulation (EU) 2024/1623",
        url=EU_CRR3_URL,
        note="EU CRR3 basic approach for CVA risk.",
    ),
    "eu_crr3_article_385": CvaCitation(
        source_id="eu_crr3_2024_1623",
        paragraph="CRR Article 385 as amended by Regulation (EU) 2024/1623",
        url=EU_CRR3_URL,
        note="EU CRR3 simplified approach context, retained fail-closed in frtb-cva.",
    ),
    "eu_crr3_article_386": CvaCitation(
        source_id="eu_crr3_2024_1623",
        paragraph="CRR Article 386 as amended by Regulation (EU) 2024/1623",
        url=EU_CRR3_URL,
        note="EU CRR3 eligible CVA hedge treatment.",
    ),
}

UK_PRA_CITATIONS: dict[str, CvaCitation] = {
    "uk_pra_ps1_26": CvaCitation(
        source_id="uk_pra_ps1_26",
        paragraph="PRA PS1/26 CVA risk implementation",
        url=UK_PRA_PS1_26_URL,
        note="UK PRA Basel 3.1 CVA implementation and 1 January 2027 effective date.",
    ),
    "uk_pra_cva_risk_ba": CvaCitation(
        source_id="uk_pra_cva_risk_part",
        paragraph="PRA Rulebook CVA Risk Part BA-CVA provisions",
        url=UK_PRA_CVA_RULEBOOK_URL,
        note="UK PRA basic approach crosswalk.",
    ),
    "uk_pra_cva_risk_sa": CvaCitation(
        source_id="uk_pra_cva_risk_part",
        paragraph="PRA Rulebook CVA Risk Part SA-CVA provisions",
        url=UK_PRA_CVA_RULEBOOK_URL,
        note="UK PRA standardised approach crosswalk.",
    ),
    "uk_pra_cva_risk_aa": CvaCitation(
        source_id="uk_pra_cva_risk_part",
        paragraph="PRA Rulebook CVA Risk Part AA-CVA provisions",
        url=UK_PRA_CVA_RULEBOOK_URL,
        note="UK PRA alternative approach context, retained fail-closed in frtb-cva.",
    ),
    "uk_pra_cva_risk_hedges": CvaCitation(
        source_id="uk_pra_cva_risk_part",
        paragraph="PRA Rulebook CVA Risk Part hedge provisions",
        url=UK_PRA_CVA_RULEBOOK_URL,
        note="UK PRA eligible CVA hedge crosswalk.",
    ),
}

_SCOPE_CITATION_IDS = frozenset({"basel_mar50_8", "basel_mar50_42", "basel_mar50_45"})
_MATERIALITY_CITATION_IDS = frozenset({"basel_mar50_9"})
_BA_CVA_CITATION_IDS = frozenset(
    {
        "basel_mar50_14",
        "basel_mar50_15",
        "basel_mar50_15_4",
        "basel_mar50_16",
        "basel_mar50_17",
        "basel_mar50_20",
        "basel_mar50_21",
        "basel_mar50_23",
        "basel_mar50_24",
        "basel_mar50_26",
    }
)
_HEDGE_CITATION_IDS = frozenset(
    {
        "basel_mar50_11",
        "basel_mar50_18",
        "basel_mar50_19",
        "basel_mar50_37",
        "basel_mar50_38",
        "basel_mar50_39",
    }
)
_SA_CVA_CITATION_IDS = frozenset(
    {
        "basel_mar50_32_1",
        "basel_mar50_50",
        "basel_mar50_52",
        "basel_mar50_53",
        "basel_mar50_54",
        "basel_mar50_55",
        "basel_mar50_56",
        "basel_mar50_57",
        "basel_mar50_58",
        "basel_mar50_59",
        "basel_mar50_60",
        "basel_mar50_61",
        "basel_mar50_62",
        "basel_mar50_63",
        "basel_mar50_64",
        "basel_mar50_65",
        "basel_mar50_66",
        "basel_mar50_67",
        "basel_mar50_68",
        "basel_mar50_69",
        "basel_mar50_70",
        "basel_mar50_71",
        "basel_mar50_72",
        "basel_mar50_73",
        "basel_mar50_74",
        "basel_mar50_75",
        "basel_mar50_76",
        "basel_mar50_77",
    }
)

_US_NPR20_CITATION_MAP = {
    **{citation_id: "us_npr20_vb_scope" for citation_id in _SCOPE_CITATION_IDS},
    **{citation_id: "us_npr20_vb_materiality" for citation_id in _MATERIALITY_CITATION_IDS},
    **{citation_id: "us_npr20_vb_ba_cva" for citation_id in _BA_CVA_CITATION_IDS},
    **{citation_id: "us_npr20_vb_hedges" for citation_id in _HEDGE_CITATION_IDS},
    **{citation_id: "us_npr20_vb_sa_cva" for citation_id in _SA_CVA_CITATION_IDS},
}
_EU_CRR3_CITATION_MAP = {
    **{citation_id: "eu_crr3_article_382" for citation_id in _SCOPE_CITATION_IDS},
    **{citation_id: "eu_crr3_article_385" for citation_id in _MATERIALITY_CITATION_IDS},
    **{citation_id: "eu_crr3_article_384" for citation_id in _BA_CVA_CITATION_IDS},
    **{citation_id: "eu_crr3_article_386" for citation_id in _HEDGE_CITATION_IDS},
    **{citation_id: "eu_crr3_articles_383a_383z" for citation_id in _SA_CVA_CITATION_IDS},
}
_UK_PRA_CITATION_MAP = {
    **{citation_id: "uk_pra_ps1_26" for citation_id in _SCOPE_CITATION_IDS},
    **{citation_id: "uk_pra_cva_risk_aa" for citation_id in _MATERIALITY_CITATION_IDS},
    **{citation_id: "uk_pra_cva_risk_ba" for citation_id in _BA_CVA_CITATION_IDS},
    **{citation_id: "uk_pra_cva_risk_hedges" for citation_id in _HEDGE_CITATION_IDS},
    **{citation_id: "uk_pra_cva_risk_sa" for citation_id in _SA_CVA_CITATION_IDS},
}

PROFILE_CITATION_ID_MAP: dict[CvaRegulatoryProfile, dict[str, str]] = {
    CvaRegulatoryProfile.BASEL_MAR50_2020: {},
    CvaRegulatoryProfile.US_NPR20_VB: _US_NPR20_CITATION_MAP,
    CvaRegulatoryProfile.EU_CRR3_CVA: _EU_CRR3_CITATION_MAP,
    CvaRegulatoryProfile.UK_PRA_CVA: _UK_PRA_CITATION_MAP,
}

__all__ = [
    "EU_CRR3_CITATIONS",
    "PROFILE_CITATION_ID_MAP",
    "UK_PRA_CITATIONS",
    "US_NPR20_CITATIONS",
]
