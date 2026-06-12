"""RRAO regulatory citation registries by supported profile."""

from __future__ import annotations

from frtb_rrao.data_models import RraoCitation, RraoRegulatoryProfile

BASEL_CITATIONS: dict[str, RraoCitation] = {
    "basel_mar20_4": RraoCitation(
        source_id="basel_mar20_standardised_approach",
        paragraph="MAR20.4",
        url="https://www.bis.org/basel_framework/chapter/MAR/20.htm",
        note="Standardised Approach component stack includes RRAO.",
    ),
    "basel_mar23_2": RraoCitation(
        source_id="basel_mar23_residual_risk_addon",
        paragraph="MAR23.2",
        url="https://www.bis.org/basel_framework/chapter/MAR/23.htm",
        note="Exotic underlying RRAO scope.",
    ),
    "basel_mar23_3": RraoCitation(
        source_id="basel_mar23_residual_risk_addon",
        paragraph="MAR23.3",
        url="https://www.bis.org/basel_framework/chapter/MAR/23.htm",
        note="Other residual-risk RRAO scope.",
    ),
    "basel_mar23_4_7": RraoCitation(
        source_id="basel_mar23_residual_risk_addon",
        paragraph="MAR23.4-MAR23.7",
        url="https://www.bis.org/basel_framework/chapter/MAR/23.htm",
        note="Residual-risk exclusions and back-to-back treatment.",
    ),
    "basel_mar23_8_2_a": RraoCitation(
        source_id="basel_mar23_residual_risk_addon",
        paragraph="MAR23.8(2)(a)",
        url="https://www.bis.org/basel_framework/chapter/MAR/23.htm",
        note="1.0% gross notional add-on for exotic exposures.",
    ),
    "basel_mar23_8_2_b": RraoCitation(
        source_id="basel_mar23_residual_risk_addon",
        paragraph="MAR23.8(2)(b)",
        url="https://www.bis.org/basel_framework/chapter/MAR/23.htm",
        note="0.1% gross notional add-on for other residual risks.",
    ),
}

US_NPR_CITATIONS: dict[str, RraoCitation] = {
    "us_npr_section_v_a_7_b": RraoCitation(
        source_id="us_npr_2_0_91_fr_14952",
        paragraph="Section V.A.7.b",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Narrative residual risk capital requirement.",
    ),
    "us_npr_211_a_1": RraoCitation(
        source_id="us_npr_2_0_91_fr_14952",
        paragraph="Proposed section __.211(a)(1)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Exotic exposure inclusion.",
    ),
    "us_npr_211_a_2": RraoCitation(
        source_id="us_npr_2_0_91_fr_14952",
        paragraph="Proposed section __.211(a)(2)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Other residual-risk inclusion.",
    ),
    "us_npr_211_a_3": RraoCitation(
        source_id="us_npr_2_0_91_fr_14952",
        paragraph="Proposed section __.211(a)(3)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Investment-fund portion included in RRAO.",
    ),
    "us_npr_211_a_4": RraoCitation(
        source_id="us_npr_2_0_91_fr_14952",
        paragraph="Proposed section __.211(a)(4)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Agency-determined RRAO inclusion.",
    ),
    "us_npr_211_b_1": RraoCitation(
        source_id="us_npr_2_0_91_fr_14952",
        paragraph="Proposed section __.211(b)(1)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Listed, clearable, and simple option exclusions.",
    ),
    "us_npr_211_b_2_i": RraoCitation(
        source_id="us_npr_2_0_91_fr_14952",
        paragraph="Proposed section __.211(b)(2)(i)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Exact third-party back-to-back exclusion.",
    ),
    "us_npr_211_b_2_ii": RraoCitation(
        source_id="us_npr_2_0_91_fr_14952",
        paragraph="Proposed section __.211(b)(2)(ii)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Deliverable hedge-pair exclusion.",
    ),
    "us_npr_211_b_2_iii": RraoCitation(
        source_id="us_npr_2_0_91_fr_14952",
        paragraph="Proposed section __.211(b)(2)(iii)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="U.S. government and GSE debt exclusion.",
    ),
    "us_npr_211_b_2_iv": RraoCitation(
        source_id="us_npr_2_0_91_fr_14952",
        paragraph="Proposed section __.211(b)(2)(iv)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Fallback-capital exclusion.",
    ),
    "us_npr_211_b_2_v": RraoCitation(
        source_id="us_npr_2_0_91_fr_14952",
        paragraph="Proposed section __.211(b)(2)(v)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Qualifying internal desk transaction exclusion.",
    ),
    "us_npr_211_b_2_vi": RraoCitation(
        source_id="us_npr_2_0_91_fr_14952",
        paragraph="Proposed section __.211(b)(2)(vi)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Agency-determined exclusion.",
    ),
    "us_npr_211_c_1_i": RraoCitation(
        source_id="us_npr_2_0_91_fr_14952",
        paragraph="Proposed section __.211(c)(1)(i)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="1.0% gross effective notional add-on for exotic exposures.",
    ),
    "us_npr_211_c_1_ii": RraoCitation(
        source_id="us_npr_2_0_91_fr_14952",
        paragraph="Proposed section __.211(c)(1)(ii)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="0.1% gross effective notional add-on for other residual risks.",
    ),
    "us_npr_211_c_2": RraoCitation(
        source_id="us_npr_2_0_91_fr_14952",
        paragraph="Proposed section __.211(c)(2)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Gross effective notional source.",
    ),
    "us_npr_205_e_3_iii": RraoCitation(
        source_id="us_npr_2_0_91_fr_14952",
        paragraph="Proposed section __.205(e)(3)(iii)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
        note="Backstop fund method and mandate-based RRAO exposure portion.",
    ),
}

EU_CRR3_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02013R0575-20240709"
EU_RTS_RRAO_URL = "https://eur-lex.europa.eu/eli/reg_del/2022/2328/oj/eng"

EU_CRR3_CITATIONS: dict[str, RraoCitation] = {
    "eu_crr_325u_2_a": RraoCitation(
        source_id="eu_crr_article_325u",
        paragraph="Article 325u(2)(a)",
        url=EU_CRR3_URL,
        note="Exotic underlying residual-risk condition.",
    ),
    "eu_crr_325u_2_b": RraoCitation(
        source_id="eu_crr_article_325u",
        paragraph="Article 325u(2)(b)",
        url=EU_CRR3_URL,
        note="Other residual-risk instrument condition.",
    ),
    "eu_crr_325u_3_a": RraoCitation(
        source_id="eu_crr_article_325u",
        paragraph="Article 325u(3)(a)",
        url=EU_CRR3_URL,
        note="1.0% gross notional add-on for Article 325u(2)(a) instruments.",
    ),
    "eu_crr_325u_3_b": RraoCitation(
        source_id="eu_crr_article_325u",
        paragraph="Article 325u(3)(b)",
        url=EU_CRR3_URL,
        note="0.1% gross notional add-on for Article 325u(2)(b) instruments.",
    ),
    "eu_crr_325u_4": RraoCitation(
        source_id="eu_crr_article_325u",
        paragraph="Article 325u(4)",
        url=EU_CRR3_URL,
        note="Listed, centrally clearable, and perfectly offsetting exemptions.",
    ),
    "eu_rts_2022_2328_article_1": RraoCitation(
        source_id="eu_delegated_reg_2022_2328_rrao",
        paragraph="Article 1",
        url=EU_RTS_RRAO_URL,
        note=(
            "Longevity, weather, natural disaster, and future realised "
            "volatility exotic underlyings."
        ),
    ),
    "eu_rts_2022_2328_article_2_annex": RraoCitation(
        source_id="eu_delegated_reg_2022_2328_rrao",
        paragraph="Article 2 and Annex",
        url=EU_RTS_RRAO_URL,
        note="Specified instruments bearing residual risks.",
    ),
    "eu_rts_2022_2328_article_3": RraoCitation(
        source_id="eu_delegated_reg_2022_2328_rrao",
        paragraph="Article 3",
        url=EU_RTS_RRAO_URL,
        note="Risks that do not by themselves presume Article 325u(2)(b) residual-risk treatment.",
    ),
}

UK_CRR_RRAO_URL = (
    "https://www.legislation.gov.uk/eur/2013/575/part/8/crossheading/residual-risk-add-on"
)
UK_RETAINED_RRAO_RTS_URL = "https://www.legislation.gov.uk/eur/2022/2328"

PRA_UK_CRR_CITATIONS: dict[str, RraoCitation] = {
    "uk_crr_325u_2_a": RraoCitation(
        source_id="uk_crr_article_325u_rrao",
        paragraph="Article 325u(2)(a)",
        url=UK_CRR_RRAO_URL,
        note="UK onshored exotic underlying residual-risk condition.",
    ),
    "uk_crr_325u_2_b": RraoCitation(
        source_id="uk_crr_article_325u_rrao",
        paragraph="Article 325u(2)(b)",
        url=UK_CRR_RRAO_URL,
        note="UK onshored other residual-risk instrument condition.",
    ),
    "uk_crr_325u_3_a": RraoCitation(
        source_id="uk_crr_article_325u_rrao",
        paragraph="Article 325u(3)(a)",
        url=UK_CRR_RRAO_URL,
        note="1.0% gross notional add-on for Article 325u(2)(a) instruments.",
    ),
    "uk_crr_325u_3_b": RraoCitation(
        source_id="uk_crr_article_325u_rrao",
        paragraph="Article 325u(3)(b)",
        url=UK_CRR_RRAO_URL,
        note="0.1% gross notional add-on for Article 325u(2)(b) instruments.",
    ),
    "uk_crr_325u_4": RraoCitation(
        source_id="uk_crr_article_325u_rrao",
        paragraph="Article 325u(4)",
        url=UK_CRR_RRAO_URL,
        note="Listed, centrally clearable, and perfectly offsetting exemptions.",
    ),
    "uk_rts_2022_2328_article_1": RraoCitation(
        source_id="uk_retained_dr_2022_2328_rrao",
        paragraph="Article 1",
        url=UK_RETAINED_RRAO_RTS_URL,
        note=("UK retained RTS exotic underlyings, including future realised volatility."),
    ),
    "uk_rts_2022_2328_article_2_annex": RraoCitation(
        source_id="uk_retained_dr_2022_2328_rrao",
        paragraph="Article 2 and Annex",
        url=UK_RETAINED_RRAO_RTS_URL,
        note="UK retained RTS instruments bearing residual risks.",
    ),
    "uk_rts_2022_2328_article_3": RraoCitation(
        source_id="uk_retained_dr_2022_2328_rrao",
        paragraph="Article 3",
        url=UK_RETAINED_RRAO_RTS_URL,
        note=(
            "UK retained RTS risks that do not by themselves presume "
            "Article 325u(2)(b) residual-risk treatment."
        ),
    ),
    "pra_ps1_26_chapter_3": RraoCitation(
        source_id="pra_rrao_basel_3_1_final_rules",
        paragraph="Chapter 3 market risk",
        url=(
            "https://www.bankofengland.co.uk/prudential-regulation/publication/2026/"
            "january/implementation-of-the-basel-3-1-final-rules-policy-statement"
        ),
        note="PRA PS1/26 profile anchor for UK RRAO implementation timing.",
    ),
}

PROFILE_CITATIONS: dict[RraoRegulatoryProfile, dict[str, RraoCitation]] = {
    RraoRegulatoryProfile.BASEL_MAR23: BASEL_CITATIONS,
    RraoRegulatoryProfile.US_NPR_2_0: US_NPR_CITATIONS,
    RraoRegulatoryProfile.EU_CRR3: EU_CRR3_CITATIONS,
    RraoRegulatoryProfile.PRA_UK_CRR: PRA_UK_CRR_CITATIONS,
}

__all__ = [
    "BASEL_CITATIONS",
    "EU_CRR3_CITATIONS",
    "PRA_UK_CRR_CITATIONS",
    "PROFILE_CITATIONS",
    "US_NPR_CITATIONS",
]
