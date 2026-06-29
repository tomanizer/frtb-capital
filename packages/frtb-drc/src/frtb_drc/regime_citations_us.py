"""U.S. NPR 2.0 DRC citation anchors."""

from __future__ import annotations

from frtb_drc.data_models import DrcCitation
from frtb_drc.regime_citations_us_shared import US_NPR_2_0_SHARED_BASEL_CITATIONS

US_NPR_2_0_CITATIONS: dict[str, DrcCitation] = {
    **US_NPR_2_0_SHARED_BASEL_CITATIONS,
    "US_NPR_210_SCOPE": DrcCitation(
        citation_id="US_NPR_210_SCOPE",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(a)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Default risk capital requirement scope and aggregation.",
    ),
    "US_NPR_210_A_1_II": DrcCitation(
        citation_id="US_NPR_210_A_1_II",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(a)(1)(ii)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Non-securitisation long JTD is capped by the market value of the position.",
    ),
    "US_NPR_207_A_8": DrcCitation(
        citation_id="US_NPR_207_A_8",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.207(a)(8)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note=(
            "Market-risk standardized calculations use the banking organization's "
            "reporting currency, except the approved FX base-currency case."
        ),
    ),
    "US_NPR_208_H_1_II": DrcCitation(
        citation_id="US_NPR_208_H_1_II",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.208(h)(1)(ii)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note=(
            "FX risk factors use spot reporting/base exchange rates; the DRC package "
            "uses explicitly supplied spot rates to translate native-currency DRC "
            "amounts into the context base currency before aggregation."
        ),
    ),
    "US_NPR_210_B_1_IV": DrcCitation(
        citation_id="US_NPR_210_B_1_IV",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(b)(1)(iv)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Non-securitisation LGD values.",
    ),
    "US_NPR_210_A_2_III": DrcCitation(
        citation_id="US_NPR_210_A_2_III",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(a)(2)(iii)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Maturity weighting and floor.",
    ),
    "US_NPR_210_A_2_IV_A": DrcCitation(
        citation_id="US_NPR_210_A_2_IV_A",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(a)(2)(iv)(A)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Hedge benefit ratio for long and short net default exposures within a bucket.",
    ),
    "US_NPR_210_A_2_IV_C": DrcCitation(
        citation_id="US_NPR_210_A_2_IV_C",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(a)(2)(iv)(C)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Bucket-level default-risk capital aggregation.",
    ),
    "US_NPR_210_B_2": DrcCitation(
        citation_id="US_NPR_210_B_2",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(b)(2)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Same-obligor non-securitisation offsetting and seniority rule.",
    ),
    "US_NPR_210_B_3_I": DrcCitation(
        citation_id="US_NPR_210_B_3_I",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(b)(3)(i)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Non-securitisation bucket definitions.",
    ),
    "US_NPR_210_B_3_II": DrcCitation(
        citation_id="US_NPR_210_B_3_II",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(b)(3)(ii), Table 1 to section __.210",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Non-securitisation risk weights by bucket and credit quality.",
    ),
    "US_NPR_210_B_3_III": DrcCitation(
        citation_id="US_NPR_210_B_3_III",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(b)(3)(iii)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Non-securitisation default-risk capital equals the sum of bucket-level requirements.",
    ),
    "US_NPR_210_C_1": DrcCitation(
        citation_id="US_NPR_210_C_1",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(c)(1)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Securitisation non-CTP gross default exposure equals market value.",
    ),
    "US_NPR_210_C_2": DrcCitation(
        citation_id="US_NPR_210_C_2",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(c)(2)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note=(
            "Securitisation non-CTP offsetting by same underlying pool and "
            "tranche, with decomposition."
        ),
    ),
    "US_NPR_210_C_3_I_II": DrcCitation(
        citation_id="US_NPR_210_C_3_I_II",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(c)(3)(i)-(ii)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Securitisation non-CTP bucket definitions and assignment rules.",
    ),
    "US_NPR_210_C_3_III": DrcCitation(
        citation_id="US_NPR_210_C_3_III",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(c)(3)(iii)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Securitisation non-CTP bucket-level capital formula and risk-weight source.",
    ),
    "US_NPR_210_C_3_IV": DrcCitation(
        citation_id="US_NPR_210_C_3_IV",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(c)(3)(iv)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Securitisation non-CTP category capital equals the sum of bucket-level requirements.",
    ),
    "US_NPR_210_D_1": DrcCitation(
        citation_id="US_NPR_210_D_1",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(d)(1)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="CTP gross default exposure and Nth-to-default treatment.",
    ),
    "US_NPR_210_D_2": DrcCitation(
        citation_id="US_NPR_210_D_2",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(d)(2)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note=(
            "CTP offsetting through exact maturity differences, replication, "
            "decomposition, and residual treatment."
        ),
    ),
    "US_NPR_210_D_3_I_III": DrcCitation(
        citation_id="US_NPR_210_D_3_I_III",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(d)(3)(i)-(iii)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="CTP index, bespoke, and hedge bucket assignment.",
    ),
    "US_NPR_210_D_3_IV": DrcCitation(
        citation_id="US_NPR_210_D_3_IV",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(d)(3)(iv)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note=(
            "CTP bucket-level capital uses CTP-wide HBR and spans all exposures "
            "relating to the index."
        ),
    ),
    "US_NPR_210_D_3_IV_D": DrcCitation(
        citation_id="US_NPR_210_D_3_IV_D",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(d)(3)(iv)(D)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note=(
            "CTP risk-weight sources for tranched positions, non-tranched hedges, "
            "and decomposed single-name exposures."
        ),
    ),
    "US_NPR_210_D_3_V": DrcCitation(
        citation_id="US_NPR_210_D_3_V",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(d)(3)(v)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="CTP category-level aggregation of bucket-level capital requirements.",
    ),
}

__all__ = ["US_NPR_2_0_CITATIONS"]
