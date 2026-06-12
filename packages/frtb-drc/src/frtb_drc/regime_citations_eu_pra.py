"""EU CRR3 and PRA UK CRR DRC citation anchors."""

from __future__ import annotations

from frtb_drc.data_models import DrcCitation

EU_CRR3_CITATIONS: dict[str, DrcCitation] = {
    "EU_CRR3_ARTICLE_325W": DrcCitation(
        citation_id="EU_CRR3_ARTICLE_325W",
        source_id="EU_CRR3_2024_1623",
        paragraph="Article 325w",
        url="https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng",
        note=(
            "EU default-risk charge gross JTD amounts for non-securitisations, "
            "including LGD seniority treatment."
        ),
    ),
    "EU_CRR3_ARTICLE_325X": DrcCitation(
        citation_id="EU_CRR3_ARTICLE_325X",
        source_id="EU_CRR3_2024_1623",
        paragraph="Article 325x(1)-(5)",
        url="https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng",
        note=(
            "EU non-securitisation net JTD offsetting, maturity weighting, and "
            "zero-net combined debt/equity derivative treatment."
        ),
    ),
    "EU_CRR3_ARTICLE_325Y_1_2": DrcCitation(
        citation_id="EU_CRR3_ARTICLE_325Y_1_2",
        source_id="EU_CRR3_2024_1623",
        paragraph="Article 325y(1)-(2)",
        url="https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng",
        note=(
            "EU non-securitisation default-risk bucket own funds requirement "
            "and Article 325y risk-weight table by credit quality category."
        ),
    ),
    "EU_CRR3_ARTICLE_325Y_3_5": DrcCitation(
        citation_id="EU_CRR3_ARTICLE_325Y_3_5",
        source_id="EU_CRR3_2024_1623",
        paragraph="Article 325y(3)-(5)",
        url="https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng",
        note=(
            "EU non-securitisation bucket-level hedge benefit ratio, bucket "
            "capital formula, and category aggregation."
        ),
    ),
    "EU_CRR3_ARTICLE_325Y_6": DrcCitation(
        citation_id="EU_CRR3_ARTICLE_325Y_6",
        source_id="EU_CRR3_2024_1623",
        paragraph="Article 325y(6)",
        url="https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng",
        note=(
            "EU credit quality category assignment follows the Standardised "
            "Approach for credit risk in Title II, Chapter 2."
        ),
    ),
    "EU_CRR3_ECAI_CQS_MAPPING": DrcCitation(
        citation_id="EU_CRR3_ECAI_CQS_MAPPING",
        source_id="EU_2016_1799_ECAI_CQS",
        paragraph="Commission Implementing Regulation (EU) 2016/1799, Article 19 and Annex III",
        url="https://eur-lex.europa.eu/eli/reg_impl/2016/1799/oj/eng",
        note=(
            "EU ECAI credit assessment to credit quality step mapping used by "
            "the Standardised Approach credit-quality categories referenced by Article 325y(6)."
        ),
    ),
    "EU_CRR3_ARTICLES_325Z_325AA": DrcCitation(
        citation_id="EU_CRR3_ARTICLES_325Z_325AA",
        source_id="EU_CRR3_2024_1623",
        paragraph="Articles 325z and 325aa",
        url="https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng",
        note=(
            "EU securitisation non-CTP DRC article range; runtime path remains "
            "fail-closed until profile-specific mappings are implemented."
        ),
    ),
    "EU_CRR3_ARTICLES_325AB_325AD": DrcCitation(
        citation_id="EU_CRR3_ARTICLES_325AB_325AD",
        source_id="EU_CRR3_2024_1623",
        paragraph="Articles 325ab to 325ad",
        url="https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng",
        note=(
            "EU CTP DRC article range; runtime path remains fail-closed until "
            "profile-specific mappings are implemented."
        ),
    ),
}

PRA_UK_CRR_CITATIONS: dict[str, DrcCitation] = {
    "PRA_PS1_26_MARKET_RISK": DrcCitation(
        citation_id="PRA_PS1_26_MARKET_RISK",
        source_id="UK_PRA_PS1_26_BASEL_3_1_FINAL_RULES",
        paragraph="Chapter 3 and Appendix 1",
        url="https://www.bankofengland.co.uk/prudential-regulation/publication/2026/january/implementation-of-the-basel-3-1-final-rules-policy-statement",
        note=(
            "UK Basel 3.1 market-risk profile anchor; runtime DRC profile remains "
            "fail-closed until PRA rulebook paragraph mapping is implemented."
        ),
    ),
}


__all__ = ["EU_CRR3_CITATIONS", "PRA_UK_CRR_CITATIONS"]
