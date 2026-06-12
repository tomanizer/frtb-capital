"""Basel MAR22 DRC citation anchors."""

from __future__ import annotations

from frtb_drc.data_models import DrcCitation
from frtb_drc.regime_citations_us import US_NPR_2_0_CITATIONS

BASEL_MAR22_CITATIONS: dict[str, DrcCitation] = {
    "BASEL_MAR22_11": US_NPR_2_0_CITATIONS["BASEL_MAR22_11"],
    "BASEL_MAR22_12": DrcCitation(
        citation_id="BASEL_MAR22_12",
        source_id="BASEL_MAR22",
        paragraph="MAR22.12",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note=(
            "Non-securitisation LGD ladder for equity, non-senior debt, senior debt, "
            "covered bonds, and recovery-unlinked instruments."
        ),
    ),
    "BASEL_MAR22_13": US_NPR_2_0_CITATIONS["BASEL_MAR22_13"],
    "BASEL_MAR22_15_18": DrcCitation(
        citation_id="BASEL_MAR22_15_18",
        source_id="BASEL_MAR22",
        paragraph="MAR22.15-MAR22.18",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="One-year maturity scaling with a three-month floor for exposures below three months.",
    ),
    "BASEL_MAR22_19": DrcCitation(
        citation_id="BASEL_MAR22_19",
        source_id="BASEL_MAR22",
        paragraph="MAR22.19",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Same-obligor non-securitisation offsetting and seniority rule.",
    ),
    "BASEL_MAR22_22": DrcCitation(
        citation_id="BASEL_MAR22_22",
        source_id="BASEL_MAR22",
        paragraph="MAR22.22",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note=(
            "Basel non-securitisation buckets: corporates, sovereigns, and local "
            "governments and municipalities."
        ),
    ),
    "BASEL_MAR22_23": DrcCitation(
        citation_id="BASEL_MAR22_23",
        source_id="BASEL_MAR22",
        paragraph="MAR22.23",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Hedge benefit ratio for long and short net default exposures within a bucket.",
    ),
    "BASEL_MAR22_24": DrcCitation(
        citation_id="BASEL_MAR22_24",
        source_id="BASEL_MAR22",
        paragraph="MAR22.24",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note=(
            "Basel non-securitisation risk weights by letter-grade credit quality, "
            "unrated, and defaulted categories."
        ),
    ),
    "BASEL_MAR22_25": DrcCitation(
        citation_id="BASEL_MAR22_25",
        source_id="BASEL_MAR22",
        paragraph="MAR22.25",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Bucket-level default-risk capital aggregation.",
    ),
    "BASEL_MAR22_26": DrcCitation(
        citation_id="BASEL_MAR22_26",
        source_id="BASEL_MAR22",
        paragraph="MAR22.26",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Non-securitisation default-risk capital equals the sum of bucket-level requirements.",
    ),
    "BASEL_MAR22_27": US_NPR_2_0_CITATIONS["BASEL_MAR22_27"],
    "BASEL_MAR22_28": US_NPR_2_0_CITATIONS["BASEL_MAR22_28"],
    "BASEL_MAR22_29": US_NPR_2_0_CITATIONS["BASEL_MAR22_29"],
    "BASEL_MAR22_30": US_NPR_2_0_CITATIONS["BASEL_MAR22_30"],
    "BASEL_MAR22_31": US_NPR_2_0_CITATIONS["BASEL_MAR22_31"],
    "BASEL_MAR22_32": US_NPR_2_0_CITATIONS["BASEL_MAR22_32"],
    "BASEL_MAR22_33": US_NPR_2_0_CITATIONS["BASEL_MAR22_33"],
    "BASEL_MAR22_34": US_NPR_2_0_CITATIONS["BASEL_MAR22_34"],
    "BASEL_MAR22_35": US_NPR_2_0_CITATIONS["BASEL_MAR22_35"],
    "BASEL_MAR22_42": DrcCitation(
        citation_id="BASEL_MAR22_42",
        source_id="BASEL_MAR22",
        paragraph="MAR22.42",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note=(
            "CTP securitisation risk weights use the banking-book securitisation "
            "hierarchy with one-year maturity."
        ),
    ),
}


__all__ = ["BASEL_MAR22_CITATIONS"]
