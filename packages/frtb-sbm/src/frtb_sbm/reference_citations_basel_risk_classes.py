"""Basel MAR21 risk-class citation fragments.

Regulatory traceability:
    Basel MAR21 citation ids used by SBM reference-data payloads.
"""

from __future__ import annotations

from frtb_sbm.data_models import SbmCitation

BASEL_MAR21_URL = "https://www.bis.org/basel_framework/chapter/MAR/21.htm"

BASEL_RISK_CLASS_CITATIONS: dict[str, SbmCitation] = {
    "basel_mar21_12": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.12",
        url=BASEL_MAR21_URL,
        note="Equity delta and vega risk-factor definitions.",
    ),
    "basel_mar21_13": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.13",
        url=BASEL_MAR21_URL,
        note="Commodity delta and vega risk-factor definitions and tenors.",
    ),
    "basel_mar21_72": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.72",
        url=BASEL_MAR21_URL,
        note="Equity delta bucket assignment (Table 9).",
    ),
    "basel_mar21_77": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.77",
        url=BASEL_MAR21_URL,
        note="Equity delta risk weights for spot and repo (Table 10).",
    ),
    "basel_mar21_78": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.78",
        url=BASEL_MAR21_URL,
        note="Equity delta intra-bucket correlation parameters.",
    ),
    "basel_mar21_79": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.79",
        url=BASEL_MAR21_URL,
        note="Equity other-sector bucket absolute-weight aggregation.",
    ),
    "basel_mar21_80": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.80",
        url=BASEL_MAR21_URL,
        note="Equity delta inter-bucket correlation parameters.",
    ),
    "basel_mar21_81": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.81",
        url=BASEL_MAR21_URL,
        note="Commodity delta bucket assignment (Table 11).",
    ),
    "basel_mar21_82": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.82",
        url=BASEL_MAR21_URL,
        note="Commodity delta risk weights (Table 11).",
    ),
    "basel_mar21_83": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.83",
        url=BASEL_MAR21_URL,
        note="Commodity delta intra-bucket correlation parameters (Table 12).",
    ),
    "basel_mar21_85": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.85",
        url=BASEL_MAR21_URL,
        note="Commodity delta inter-bucket correlation parameters.",
    ),
    "basel_mar21_9": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.9",
        url=BASEL_MAR21_URL,
        note="CSR non-securitisation delta risk factors (bond and CDS credit spreads).",
    ),
    "basel_mar21_10": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.10",
        url=BASEL_MAR21_URL,
        note="CSR securitisation non-CTP tranche credit-spread risk factors.",
    ),
    "basel_mar21_11": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.11",
        url=BASEL_MAR21_URL,
        note="CSR securitisation CTP underlying-name credit-spread risk factors.",
    ),
    "basel_mar21_51": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.51",
        url=BASEL_MAR21_URL,
        note="CSR non-securitisation delta bucket assignment (Table 3).",
    ),
    "basel_mar21_53": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.53",
        url=BASEL_MAR21_URL,
        note="CSR non-securitisation delta risk weights (Table 4).",
    ),
    "basel_mar21_54": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.54",
        url=BASEL_MAR21_URL,
        note="CSR non-securitisation delta intra-bucket correlations for buckets 1-15.",
    ),
    "basel_mar21_55": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.55",
        url=BASEL_MAR21_URL,
        note="CSR non-securitisation delta intra-bucket correlations for index buckets 17-18.",
    ),
    "basel_mar21_56": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.56",
        url=BASEL_MAR21_URL,
        note="CSR non-securitisation other-sector bucket absolute-weight aggregation.",
    ),
    "basel_mar21_57": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.57",
        url=BASEL_MAR21_URL,
        note="CSR non-securitisation delta inter-bucket gamma (Table 5).",
    ),
    "basel_mar21_58": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.58",
        url=BASEL_MAR21_URL,
        note="CSR securitisation CTP bucket assignment and intra-bucket correlation rule.",
    ),
    "basel_mar21_59": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.59",
        url=BASEL_MAR21_URL,
        note="CSR securitisation CTP delta risk weights.",
    ),
    "basel_mar21_60": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.60",
        url=BASEL_MAR21_URL,
        note="CSR securitisation CTP other-bucket treatment.",
    ),
    "basel_mar21_61": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.61",
        url=BASEL_MAR21_URL,
        note="CSR securitisation non-CTP bucket assignment.",
    ),
    "basel_mar21_65": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.65",
        url=BASEL_MAR21_URL,
        note="CSR securitisation non-CTP delta risk weights.",
    ),
    "basel_mar21_66": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.66",
        url=BASEL_MAR21_URL,
        note="CSR securitisation non-CTP other-sector risk weight.",
    ),
    "basel_mar21_67": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.67",
        url=BASEL_MAR21_URL,
        note="CSR securitisation non-CTP intra-bucket correlation rule.",
    ),
    "basel_mar21_68": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.68",
        url=BASEL_MAR21_URL,
        note="CSR securitisation non-CTP other-sector aggregation rule.",
    ),
    "basel_mar21_70": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.70",
        url=BASEL_MAR21_URL,
        note="CSR securitisation non-CTP inter-bucket gamma.",
    ),
}

__all__ = ["BASEL_RISK_CLASS_CITATIONS"]
