"""Basel CVA citation supplements."""

from __future__ import annotations

from frtb_cva.data_models import CvaCitation

BASEL_MAR50_URL = "https://www.bis.org/basel_framework/chapter/MAR/50.htm"

ADDITIONAL_BASEL_MAR50_CITATIONS: dict[str, CvaCitation] = {
    "basel_mar50_8": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.8",
        url=BASEL_MAR50_URL,
        note="SA-CVA portfolio with BA-CVA carve-out treatment.",
    ),
    "basel_mar50_9": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.9",
        url=BASEL_MAR50_URL,
        note="Materiality-threshold CCR substitution alternative.",
    ),
    "basel_mar50_11": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.11",
        url=BASEL_MAR50_URL,
        note="Internal CVA hedge transfer treatment.",
    ),
    "basel_mar50_17": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.17",
        url=BASEL_MAR50_URL,
        note="Full BA-CVA hedge-recognising approach.",
    ),
    "basel_mar50_18": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.18",
        url=BASEL_MAR50_URL,
        note="BA-CVA eligible hedge instrument types.",
    ),
    "basel_mar50_19": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.19",
        url=BASEL_MAR50_URL,
        note="BA-CVA eligible credit spread hedge treatment.",
    ),
    "basel_mar50_21": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.21",
        url=BASEL_MAR50_URL,
        note="Full BA-CVA hedge-recognising formula components.",
    ),
    "basel_mar50_23": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.23",
        url=BASEL_MAR50_URL,
        note="BA-CVA hedge maturity and discounting terms.",
    ),
    "basel_mar50_24": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.24",
        url=BASEL_MAR50_URL,
        note="BA-CVA index hedge risk-weight scalar.",
    ),
    "basel_mar50_26": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.26",
        url=BASEL_MAR50_URL,
        note="BA-CVA hedge-counterparty correlation table.",
    ),
    "basel_mar50_37": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.37",
        url=BASEL_MAR50_URL,
        note="SA-CVA eligible hedge treatment.",
    ),
    "basel_mar50_38": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.38",
        url=BASEL_MAR50_URL,
        note="SA-CVA whole-transaction hedge eligibility.",
    ),
    "basel_mar50_39": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.39",
        url=BASEL_MAR50_URL,
        note="SA-CVA hedge exclusions.",
    ),
    "basel_mar50_42": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.42",
        url=BASEL_MAR50_URL,
        note="SA-CVA capital requirement and approval context.",
    ),
    "basel_mar50_45": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.45",
        url=BASEL_MAR50_URL,
        note="SA-CVA risk classes and CCS delta-only treatment.",
    ),
    "basel_mar50_50": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.50",
        url=BASEL_MAR50_URL,
        note="SA-CVA qualified-index routing.",
    ),
    "basel_mar50_53": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.53",
        url=BASEL_MAR50_URL,
        note="SA-CVA bucket and risk-class aggregation.",
    ),
}

__all__ = [
    "ADDITIONAL_BASEL_MAR50_CITATIONS",
    "BASEL_MAR50_URL",
]
