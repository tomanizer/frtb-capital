"""CVA regulatory citation registries for reference-data profiles."""

from __future__ import annotations

from frtb_cva._basel_citations import ADDITIONAL_BASEL_MAR50_CITATIONS, BASEL_MAR50_URL
from frtb_cva._profile_citations import (
    EU_CRR3_CITATIONS,
    UK_PRA_CITATIONS,
    US_NPR20_CITATIONS,
)
from frtb_cva.data_models import CvaCitation, CvaRegulatoryProfile

BASEL_MAR50_CITATIONS: dict[str, CvaCitation] = {
    "basel_mar50_14": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.14",
        url=BASEL_MAR50_URL,
        note="Reduced BA-CVA portfolio aggregation and D_BA-CVA scalar.",
    ),
    "basel_mar50_15": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.15",
        url=BASEL_MAR50_URL,
        note="Stand-alone counterparty capital multiplier, maturity, EAD, and DF.",
    ),
    "basel_mar50_15_4": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.15(4)",
        url=BASEL_MAR50_URL,
        note="Non-IMM discount factor formula and IMM DF=1 branch.",
    ),
    "basel_mar50_16": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.16",
        url=BASEL_MAR50_URL,
        note="BA-CVA Table 1 sector and credit-quality risk weights.",
    ),
    "basel_mar50_20": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.20",
        url=BASEL_MAR50_URL,
        note="Full BA-CVA supervisory floor with beta=0.25.",
    ),
    "basel_mar50_32_1": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.32(1)",
        url=BASEL_MAR50_URL,
        note="Positive regulatory CVA convention for SA-CVA sensitivity inputs.",
    ),
    "basel_mar50_52": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.52",
        url=BASEL_MAR50_URL,
        note="SA-CVA weighted sensitivity netting of CVA and eligible hedge sensitivities.",
    ),
    "basel_mar50_54": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.54",
        url=BASEL_MAR50_URL,
        note="SA-CVA GIRR currency buckets.",
    ),
    "basel_mar50_55": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.55",
        url=BASEL_MAR50_URL,
        note="SA-CVA GIRR cross-bucket correlation gamma_bc=0.5.",
    ),
    "basel_mar50_56": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.56",
        url=BASEL_MAR50_URL,
        note="SA-CVA GIRR delta risk factors, weights, and correlations for specified currencies.",
    ),
    "basel_mar50_57": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.57",
        url=BASEL_MAR50_URL,
        note="SA-CVA GIRR delta risk factors for other currencies.",
    ),
    "basel_mar50_58": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.58",
        url=BASEL_MAR50_URL,
        note="SA-CVA GIRR vega risk factors and RW_sigma.",
    ),
    "basel_mar50_59": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.59",
        url=BASEL_MAR50_URL,
        note="SA-CVA FX currency buckets excluding reporting currency.",
    ),
    "basel_mar50_60": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.60",
        url=BASEL_MAR50_URL,
        note="SA-CVA FX cross-bucket gamma_bc=0.6.",
    ),
    "basel_mar50_61": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.61",
        url=BASEL_MAR50_URL,
        note="SA-CVA FX delta risk factors and 11% risk weight.",
    ),
    "basel_mar50_62": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.62",
        url=BASEL_MAR50_URL,
        note="SA-CVA FX vega risk factors and RW_sigma.",
    ),
    "basel_mar50_63": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.63",
        url=BASEL_MAR50_URL,
        note="SA-CVA CCS delta buckets; no CCS vega.",
    ),
    "basel_mar50_64": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.64",
        url=BASEL_MAR50_URL,
        note="SA-CVA CCS cross-bucket gamma_bc table.",
    ),
    "basel_mar50_65": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.65",
        url=BASEL_MAR50_URL,
        note="SA-CVA CCS delta risk weights and rho_kl.",
    ),
    "basel_mar50_66": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.66",
        url=BASEL_MAR50_URL,
        note="SA-CVA RCS delta and vega buckets.",
    ),
    "basel_mar50_67": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.67",
        url=BASEL_MAR50_URL,
        note="SA-CVA RCS cross-bucket gamma_bc with cross-quality halving.",
    ),
    "basel_mar50_68": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.68",
        url=BASEL_MAR50_URL,
        note="SA-CVA RCS delta risk weights.",
    ),
    "basel_mar50_69": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.69",
        url=BASEL_MAR50_URL,
        note="SA-CVA RCS vega risk weights.",
    ),
    "basel_mar50_70": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.70",
        url=BASEL_MAR50_URL,
        note="SA-CVA equity buckets by size, region, and sector.",
    ),
    "basel_mar50_71": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.71",
        url=BASEL_MAR50_URL,
        note="SA-CVA equity cross-bucket gamma_bc rules.",
    ),
    "basel_mar50_72": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.72",
        url=BASEL_MAR50_URL,
        note="SA-CVA equity delta risk weights.",
    ),
    "basel_mar50_73": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.73",
        url=BASEL_MAR50_URL,
        note="SA-CVA equity vega risk weights.",
    ),
    "basel_mar50_74": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.74",
        url=BASEL_MAR50_URL,
        note="SA-CVA commodity buckets.",
    ),
    "basel_mar50_75": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.75",
        url=BASEL_MAR50_URL,
        note="SA-CVA commodity cross-bucket gamma_bc rules.",
    ),
    "basel_mar50_76": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.76",
        url=BASEL_MAR50_URL,
        note="SA-CVA commodity delta risk weights.",
    ),
    "basel_mar50_77": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.77",
        url=BASEL_MAR50_URL,
        note="SA-CVA commodity vega risk weights.",
    ),
}

BASEL_PROFILE_CITATIONS: dict[str, CvaCitation] = {
    **BASEL_MAR50_CITATIONS,
    **ADDITIONAL_BASEL_MAR50_CITATIONS,
}

PROFILE_CITATIONS: dict[CvaRegulatoryProfile, dict[str, CvaCitation]] = {
    CvaRegulatoryProfile.BASEL_MAR50_2020: BASEL_PROFILE_CITATIONS,
    CvaRegulatoryProfile.US_NPR20_VB: US_NPR20_CITATIONS,
    CvaRegulatoryProfile.EU_CRR3_CVA: EU_CRR3_CITATIONS,
    CvaRegulatoryProfile.UK_PRA_CVA: UK_PRA_CITATIONS,
}


__all__ = [
    "BASEL_MAR50_CITATIONS",
    "BASEL_PROFILE_CITATIONS",
    "PROFILE_CITATIONS",
]
