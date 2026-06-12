"""Shared Basel citation anchors used by the U.S. NPR DRC profile."""

from __future__ import annotations

from frtb_drc.data_models import DrcCitation

US_NPR_2_0_SHARED_BASEL_CITATIONS: dict[str, DrcCitation] = {
    "BASEL_MAR22_11": DrcCitation(
        citation_id="BASEL_MAR22_11",
        source_id="BASEL_MAR22",
        paragraph="MAR22.11",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Gross JTD formula inputs: LGD, notional, and cumulative P&L.",
    ),
    "BASEL_MAR22_13": DrcCitation(
        citation_id="BASEL_MAR22_13",
        source_id="BASEL_MAR22",
        paragraph="MAR22.13",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Notional and P&L signs for long and short JTD.",
    ),
    "BASEL_MAR22_27": DrcCitation(
        citation_id="BASEL_MAR22_27",
        source_id="BASEL_MAR22",
        paragraph="MAR22.27",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Securitisation non-CTP gross JTD equals market value without a separate LGD.",
    ),
    "BASEL_MAR22_28": DrcCitation(
        citation_id="BASEL_MAR22_28",
        source_id="BASEL_MAR22",
        paragraph="MAR22.28",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Securitisation non-CTP decomposition into equivalent replicating tranches.",
    ),
    "BASEL_MAR22_29": DrcCitation(
        citation_id="BASEL_MAR22_29",
        source_id="BASEL_MAR22",
        paragraph="MAR22.29",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Securitisation non-CTP offsetting is limited by underlying pool and tranche.",
    ),
    "BASEL_MAR22_30": DrcCitation(
        citation_id="BASEL_MAR22_30",
        source_id="BASEL_MAR22",
        paragraph="MAR22.30",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Securitisation non-CTP maturity offsetting and replication conditions.",
    ),
    "BASEL_MAR22_31": DrcCitation(
        citation_id="BASEL_MAR22_31",
        source_id="BASEL_MAR22",
        paragraph="MAR22.31",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Securitisation non-CTP bucket taxonomy by corporate, asset class, and region.",
    ),
    "BASEL_MAR22_32": DrcCitation(
        citation_id="BASEL_MAR22_32",
        source_id="BASEL_MAR22",
        paragraph="MAR22.32",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Securitisation non-CTP bucket assignment using market classification.",
    ),
    "BASEL_MAR22_33": DrcCitation(
        citation_id="BASEL_MAR22_33",
        source_id="BASEL_MAR22",
        paragraph="MAR22.33",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Securitisation non-CTP bucket capital uses the non-securitisation HBR formula.",
    ),
    "BASEL_MAR22_34": DrcCitation(
        citation_id="BASEL_MAR22_34",
        source_id="BASEL_MAR22",
        paragraph="MAR22.34",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note=(
            "Securitisation non-CTP risk weights are defined by tranche using "
            "banking-book treatment; individual cash securitisation position capital "
            "may be capped at fair value."
        ),
    ),
    "BASEL_MAR22_35": DrcCitation(
        citation_id="BASEL_MAR22_35",
        source_id="BASEL_MAR22",
        paragraph="MAR22.35",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note=(
            "No hedging across securitisation non-CTP buckets; category capital is the bucket sum."
        ),
    ),
    "BASEL_MAR22_36": DrcCitation(
        citation_id="BASEL_MAR22_36",
        source_id="BASEL_MAR22",
        paragraph="MAR22.36",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="CTP securitisation gross JTD follows the securitisation gross JTD approach.",
    ),
    "BASEL_MAR22_37": DrcCitation(
        citation_id="BASEL_MAR22_37",
        source_id="BASEL_MAR22",
        paragraph="MAR22.37",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="CTP non-securitisation hedge gross JTD is market value.",
    ),
    "BASEL_MAR22_39": DrcCitation(
        citation_id="BASEL_MAR22_39",
        source_id="BASEL_MAR22",
        paragraph="MAR22.39",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="CTP offsetting, replication, decomposition, and residual-exposure constraints.",
    ),
    "BASEL_MAR22_40": DrcCitation(
        citation_id="BASEL_MAR22_40",
        source_id="BASEL_MAR22",
        paragraph="MAR22.40",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Each CTP index is a bucket of its own.",
    ),
    "BASEL_MAR22_41": DrcCitation(
        citation_id="BASEL_MAR22_41",
        source_id="BASEL_MAR22",
        paragraph="MAR22.41",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="Bespoke CTP securitisations are allocated to the corresponding index bucket.",
    ),
    "BASEL_MAR22_44": DrcCitation(
        citation_id="BASEL_MAR22_44",
        source_id="BASEL_MAR22",
        paragraph="MAR22.44",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note="CTP bucket capital uses CTP-wide HBR and has no bucket-level zero floor.",
    ),
    "BASEL_MAR22_45": DrcCitation(
        citation_id="BASEL_MAR22_45",
        source_id="BASEL_MAR22",
        paragraph="MAR22.45",
        url="https://www.bis.org/basel_framework/chapter/MAR/22.htm",
        note=(
            "CTP category aggregation recognises negative bucket capital at 50% "
            "and floors total at zero."
        ),
    ),
}

__all__ = ["US_NPR_2_0_SHARED_BASEL_CITATIONS"]
