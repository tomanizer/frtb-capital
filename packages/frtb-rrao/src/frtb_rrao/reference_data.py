"""
Reference data for RRAO rule profiles.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for reference_data.py, Basel
    MAR23.2-MAR23.8, U.S. NPR 2.0 proposed section __.211, EU Article
    325u, and Delegated Regulation (EU) 2022/2328 Articles 1-3.
"""

from __future__ import annotations

from dataclasses import dataclass

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_rrao.data_models import (
    RraoCitation,
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoInvestmentFundExposureType,
    RraoRegulatoryProfile,
)
from frtb_rrao.validation import RraoInputError


@dataclass(frozen=True)
class RraoEvidenceRule:
    """Profile-specific mapping from evidence type to classification treatment."""

    evidence_type: RraoEvidenceType
    classification: RraoClassification
    risk_weight_key: str
    reason_code: str
    citation_id: str


@dataclass(frozen=True)
class RraoExclusionRule:
    """Profile-specific cited exclusion rule."""

    exclusion_reason: RraoExclusionReason
    risk_weight_key: str
    reason_code: str
    citation_id: str


@dataclass(frozen=True)
class RraoRiskWeightRule:
    """Profile-specific risk-weight lookup entry."""

    key: str
    classification: RraoClassification
    risk_weight: float
    citation_id: str


@dataclass(frozen=True)
class RraoInvestmentFundRule:
    """Profile-specific investment-fund inclusion mapping."""

    included_exposure_type: RraoInvestmentFundExposureType
    classification: RraoClassification
    risk_weight_key: str
    reason_code: str
    citation_ids: tuple[str, ...]


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

_EU_ARTICLE_2_EVIDENCE_TYPES = (
    RraoEvidenceType.PATH_DEPENDENT_OPTION,
    RraoEvidenceType.FORWARD_START_UNDETERMINED_STRIKE_OPTION,
    RraoEvidenceType.OPTION_ON_OPTION,
    RraoEvidenceType.DISCONTINUOUS_PAYOFF_OPTION,
    RraoEvidenceType.HOLDER_MODIFIABLE_OPTION,
    RraoEvidenceType.FINITE_EXERCISE_DATES_OPTION,
    RraoEvidenceType.CROSS_CURRENCY_SETTLED_OPTION,
    RraoEvidenceType.MULTI_UNDERLYING_OPTION,
    RraoEvidenceType.BEHAVIOURAL_OPTION,
)

_EU_ARTICLE_3_EXCLUSION_REASONS = (
    RraoExclusionReason.EU_ARTICLE_3_DELIVERABLE_RANGE,
    RraoExclusionReason.EU_ARTICLE_3_RELATIVE_IMPLIED_VOLATILITY,
    RraoExclusionReason.EU_ARTICLE_3_INDEX_OPTION_CORRELATION,
    RraoExclusionReason.EU_ARTICLE_3_CIU_INDEX_OPTION_CORRELATION,
    RraoExclusionReason.EU_ARTICLE_3_DIVIDEND_RISK,
)

PROFILE_EVIDENCE_RULES: dict[RraoRegulatoryProfile, tuple[RraoEvidenceRule, ...]] = {
    RraoRegulatoryProfile.BASEL_MAR23: (
        RraoEvidenceRule(
            evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
            classification=RraoClassification.EXOTIC,
            risk_weight_key="EXOTIC_1_PERCENT",
            reason_code="BASEL_EXOTIC_UNDERLYING",
            citation_id="basel_mar23_2",
        ),
        *(
            RraoEvidenceRule(
                evidence_type=evidence_type,
                classification=RraoClassification.OTHER_RESIDUAL_RISK,
                risk_weight_key="OTHER_0_1_PERCENT",
                reason_code=f"BASEL_{evidence_type.value}",
                citation_id="basel_mar23_3",
            )
            for evidence_type in (
                RraoEvidenceType.GAP_RISK,
                RraoEvidenceType.CORRELATION_RISK,
                RraoEvidenceType.BEHAVIOURAL_RISK,
                RraoEvidenceType.CTP_THREE_OR_MORE_UNDERLYINGS,
                RraoEvidenceType.NON_REPLICABLE_OPTIONALITY,
                RraoEvidenceType.NO_MATURITY_OPTIONALITY,
                RraoEvidenceType.NO_STRIKE_OR_BARRIER_OPTIONALITY,
                RraoEvidenceType.MULTIPLE_STRIKE_OR_BARRIER_OPTIONALITY,
            )
        ),
    ),
    RraoRegulatoryProfile.US_NPR_2_0: (
        RraoEvidenceRule(
            evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
            classification=RraoClassification.EXOTIC,
            risk_weight_key="EXOTIC_1_PERCENT",
            reason_code="US_NPR_EXOTIC_EXPOSURE",
            citation_id="us_npr_211_a_1",
        ),
        *(
            RraoEvidenceRule(
                evidence_type=evidence_type,
                classification=RraoClassification.OTHER_RESIDUAL_RISK,
                risk_weight_key="OTHER_0_1_PERCENT",
                reason_code=f"US_NPR_{evidence_type.value}",
                citation_id="us_npr_211_a_2",
            )
            for evidence_type in (
                RraoEvidenceType.GAP_RISK,
                RraoEvidenceType.CORRELATION_RISK,
                RraoEvidenceType.BEHAVIOURAL_RISK,
                RraoEvidenceType.CTP_THREE_OR_MORE_UNDERLYINGS,
                RraoEvidenceType.NON_REPLICABLE_OPTIONALITY,
                RraoEvidenceType.NO_MATURITY_OPTIONALITY,
                RraoEvidenceType.NO_STRIKE_OR_BARRIER_OPTIONALITY,
                RraoEvidenceType.MULTIPLE_STRIKE_OR_BARRIER_OPTIONALITY,
            )
        ),
        RraoEvidenceRule(
            evidence_type=RraoEvidenceType.SUPERVISOR_DIRECTIVE,
            classification=RraoClassification.SUPERVISOR_DIRECTED,
            risk_weight_key="SUPERVISOR_DIRECTED_0_1_PERCENT",
            reason_code="US_NPR_SUPERVISOR_DIRECTIVE",
            citation_id="us_npr_211_a_4",
        ),
    ),
    RraoRegulatoryProfile.EU_CRR3: (
        RraoEvidenceRule(
            evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
            classification=RraoClassification.EXOTIC,
            risk_weight_key="EXOTIC_1_PERCENT",
            reason_code="EU_CRR3_EXOTIC_UNDERLYING",
            citation_id="eu_rts_2022_2328_article_1",
        ),
        *(
            RraoEvidenceRule(
                evidence_type=evidence_type,
                classification=RraoClassification.OTHER_RESIDUAL_RISK,
                risk_weight_key="OTHER_0_1_PERCENT",
                reason_code=f"EU_CRR3_{evidence_type.value}",
                citation_id="eu_rts_2022_2328_article_2_annex",
            )
            for evidence_type in _EU_ARTICLE_2_EVIDENCE_TYPES
        ),
    ),
    RraoRegulatoryProfile.PRA_UK_CRR: (
        RraoEvidenceRule(
            evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
            classification=RraoClassification.EXOTIC,
            risk_weight_key="EXOTIC_1_PERCENT",
            reason_code="PRA_UK_CRR_EXOTIC_UNDERLYING",
            citation_id="uk_rts_2022_2328_article_1",
        ),
        *(
            RraoEvidenceRule(
                evidence_type=evidence_type,
                classification=RraoClassification.OTHER_RESIDUAL_RISK,
                risk_weight_key="OTHER_0_1_PERCENT",
                reason_code=f"PRA_UK_CRR_{evidence_type.value}",
                citation_id="uk_rts_2022_2328_article_2_annex",
            )
            for evidence_type in _EU_ARTICLE_2_EVIDENCE_TYPES
        ),
    ),
}

PROFILE_INVESTMENT_FUND_RULES: dict[
    RraoRegulatoryProfile,
    tuple[RraoInvestmentFundRule, ...],
] = {
    RraoRegulatoryProfile.BASEL_MAR23: (),
    RraoRegulatoryProfile.US_NPR_2_0: (
        RraoInvestmentFundRule(
            included_exposure_type=RraoInvestmentFundExposureType.EXOTIC_EXPOSURE,
            classification=RraoClassification.EXOTIC,
            risk_weight_key="EXOTIC_1_PERCENT",
            reason_code="US_NPR_INVESTMENT_FUND_EXOTIC_PORTION",
            citation_ids=(
                "us_npr_211_a_3",
                "us_npr_205_e_3_iii",
                "us_npr_211_c_1_i",
            ),
        ),
        RraoInvestmentFundRule(
            included_exposure_type=RraoInvestmentFundExposureType.OTHER_RESIDUAL_RISK,
            classification=RraoClassification.OTHER_RESIDUAL_RISK,
            risk_weight_key="OTHER_0_1_PERCENT",
            reason_code="US_NPR_INVESTMENT_FUND_OTHER_RESIDUAL_PORTION",
            citation_ids=(
                "us_npr_211_a_3",
                "us_npr_205_e_3_iii",
                "us_npr_211_c_1_ii",
            ),
        ),
    ),
    RraoRegulatoryProfile.EU_CRR3: (),
    RraoRegulatoryProfile.PRA_UK_CRR: (),
}

PROFILE_EXCLUSION_RULES: dict[RraoRegulatoryProfile, tuple[RraoExclusionRule, ...]] = {
    RraoRegulatoryProfile.BASEL_MAR23: tuple(
        RraoExclusionRule(
            exclusion_reason=reason,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code=f"BASEL_EXCLUSION_{reason.value}",
            citation_id="basel_mar23_4_7",
        )
        for reason in (
            RraoExclusionReason.LISTED,
            RraoExclusionReason.CCP_OR_QCCP_CLEARABLE,
            RraoExclusionReason.TWO_OR_FEWER_UNDERLYINGS_NON_PATH_DEPENDENT_OPTION,
            RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
        )
    ),
    RraoRegulatoryProfile.US_NPR_2_0: (
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.LISTED,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="US_NPR_EXCLUSION_LISTED",
            citation_id="us_npr_211_b_1",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.CCP_OR_QCCP_CLEARABLE,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="US_NPR_EXCLUSION_CLEARABLE",
            citation_id="us_npr_211_b_1",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.TWO_OR_FEWER_UNDERLYINGS_NON_PATH_DEPENDENT_OPTION,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="US_NPR_EXCLUSION_SIMPLE_OPTION",
            citation_id="us_npr_211_b_1",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="US_NPR_EXCLUSION_EXACT_BACK_TO_BACK",
            citation_id="us_npr_211_b_2_i",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.DELIVERABLE_HEDGE_PAIR,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="US_NPR_EXCLUSION_DELIVERABLE_HEDGE_PAIR",
            citation_id="us_npr_211_b_2_ii",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.GOVERNMENT_OR_GSE_DEBT,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="US_NPR_EXCLUSION_GOVERNMENT_OR_GSE_DEBT",
            citation_id="us_npr_211_b_2_iii",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.FALLBACK_CAPITAL_REQUIREMENT,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="US_NPR_EXCLUSION_FALLBACK_CAPITAL",
            citation_id="us_npr_211_b_2_iv",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.INTERNAL_DESK_TRANSACTION,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="US_NPR_EXCLUSION_INTERNAL_DESK_TRANSACTION",
            citation_id="us_npr_211_b_2_v",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.AGENCY_DETERMINED_EXCLUSION,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="US_NPR_EXCLUSION_AGENCY_DETERMINED",
            citation_id="us_npr_211_b_2_vi",
        ),
    ),
    RraoRegulatoryProfile.EU_CRR3: (
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.LISTED,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="EU_CRR3_EXCLUSION_LISTED",
            citation_id="eu_crr_325u_4",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.CCP_OR_QCCP_CLEARABLE,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="EU_CRR3_EXCLUSION_CLEARABLE",
            citation_id="eu_crr_325u_4",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="EU_CRR3_EXCLUSION_PERFECTLY_OFFSETTING",
            citation_id="eu_crr_325u_4",
        ),
        *(
            RraoExclusionRule(
                exclusion_reason=reason,
                risk_weight_key="NON_PRESUMPTIVE_0_PERCENT",
                reason_code=f"EU_CRR3_NON_PRESUMPTIVE_{reason.value}",
                citation_id="eu_rts_2022_2328_article_3",
            )
            for reason in _EU_ARTICLE_3_EXCLUSION_REASONS
        ),
    ),
    RraoRegulatoryProfile.PRA_UK_CRR: (
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.LISTED,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="PRA_UK_CRR_EXCLUSION_LISTED",
            citation_id="uk_crr_325u_4",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.CCP_OR_QCCP_CLEARABLE,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="PRA_UK_CRR_EXCLUSION_CLEARABLE",
            citation_id="uk_crr_325u_4",
        ),
        RraoExclusionRule(
            exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
            risk_weight_key="EXCLUDED_0_PERCENT",
            reason_code="PRA_UK_CRR_EXCLUSION_PERFECTLY_OFFSETTING",
            citation_id="uk_crr_325u_4",
        ),
        *(
            RraoExclusionRule(
                exclusion_reason=reason,
                risk_weight_key="NON_PRESUMPTIVE_0_PERCENT",
                reason_code=f"PRA_UK_CRR_NON_PRESUMPTIVE_{reason.value}",
                citation_id="uk_rts_2022_2328_article_3",
            )
            for reason in _EU_ARTICLE_3_EXCLUSION_REASONS
        ),
    ),
}

PROFILE_RISK_WEIGHT_RULES: dict[RraoRegulatoryProfile, tuple[RraoRiskWeightRule, ...]] = {
    RraoRegulatoryProfile.BASEL_MAR23: (
        RraoRiskWeightRule(
            key="EXOTIC_1_PERCENT",
            classification=RraoClassification.EXOTIC,
            risk_weight=0.01,
            citation_id="basel_mar23_8_2_a",
        ),
        RraoRiskWeightRule(
            key="OTHER_0_1_PERCENT",
            classification=RraoClassification.OTHER_RESIDUAL_RISK,
            risk_weight=0.001,
            citation_id="basel_mar23_8_2_b",
        ),
        RraoRiskWeightRule(
            key="EXCLUDED_0_PERCENT",
            classification=RraoClassification.EXCLUDED,
            risk_weight=0.0,
            citation_id="basel_mar23_4_7",
        ),
    ),
    RraoRegulatoryProfile.US_NPR_2_0: (
        RraoRiskWeightRule(
            key="EXOTIC_1_PERCENT",
            classification=RraoClassification.EXOTIC,
            risk_weight=0.01,
            citation_id="us_npr_211_c_1_i",
        ),
        RraoRiskWeightRule(
            key="OTHER_0_1_PERCENT",
            classification=RraoClassification.OTHER_RESIDUAL_RISK,
            risk_weight=0.001,
            citation_id="us_npr_211_c_1_ii",
        ),
        RraoRiskWeightRule(
            key="SUPERVISOR_DIRECTED_0_1_PERCENT",
            classification=RraoClassification.SUPERVISOR_DIRECTED,
            risk_weight=0.001,
            citation_id="us_npr_211_c_1_ii",
        ),
        RraoRiskWeightRule(
            key="EXCLUDED_0_PERCENT",
            classification=RraoClassification.EXCLUDED,
            risk_weight=0.0,
            citation_id="us_npr_211_b_1",
        ),
    ),
    RraoRegulatoryProfile.EU_CRR3: (
        RraoRiskWeightRule(
            key="EXOTIC_1_PERCENT",
            classification=RraoClassification.EXOTIC,
            risk_weight=0.01,
            citation_id="eu_crr_325u_3_a",
        ),
        RraoRiskWeightRule(
            key="OTHER_0_1_PERCENT",
            classification=RraoClassification.OTHER_RESIDUAL_RISK,
            risk_weight=0.001,
            citation_id="eu_crr_325u_3_b",
        ),
        RraoRiskWeightRule(
            key="EXCLUDED_0_PERCENT",
            classification=RraoClassification.EXCLUDED,
            risk_weight=0.0,
            citation_id="eu_crr_325u_4",
        ),
        RraoRiskWeightRule(
            key="NON_PRESUMPTIVE_0_PERCENT",
            classification=RraoClassification.EXCLUDED,
            risk_weight=0.0,
            citation_id="eu_rts_2022_2328_article_3",
        ),
    ),
    RraoRegulatoryProfile.PRA_UK_CRR: (
        RraoRiskWeightRule(
            key="EXOTIC_1_PERCENT",
            classification=RraoClassification.EXOTIC,
            risk_weight=0.01,
            citation_id="uk_crr_325u_3_a",
        ),
        RraoRiskWeightRule(
            key="OTHER_0_1_PERCENT",
            classification=RraoClassification.OTHER_RESIDUAL_RISK,
            risk_weight=0.001,
            citation_id="uk_crr_325u_3_b",
        ),
        RraoRiskWeightRule(
            key="EXCLUDED_0_PERCENT",
            classification=RraoClassification.EXCLUDED,
            risk_weight=0.0,
            citation_id="uk_crr_325u_4",
        ),
        RraoRiskWeightRule(
            key="NON_PRESUMPTIVE_0_PERCENT",
            classification=RraoClassification.EXCLUDED,
            risk_weight=0.0,
            citation_id="uk_rts_2022_2328_article_3",
        ),
    ),
}


def citations_for_profile(
    profile: RraoRegulatoryProfile | str,
) -> dict[str, RraoCitation]:
    """Return citations for a supported RRAO profile.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.

    Returns
    -------
    dict[str, RraoCitation]
        Result of the operation.
    """

    resolved = _resolve_supported_profile(profile)
    return dict(PROFILE_CITATIONS[resolved])


def evidence_rules_for_profile(
    profile: RraoRegulatoryProfile | str,
) -> tuple[RraoEvidenceRule, ...]:
    """Return supported evidence rules for a profile.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.

    Returns
    -------
    tuple[RraoEvidenceRule, ...]
        Result of the operation.
    """

    resolved = _resolve_supported_profile(profile)
    return PROFILE_EVIDENCE_RULES[resolved]


def exclusion_rules_for_profile(
    profile: RraoRegulatoryProfile | str,
) -> tuple[RraoExclusionRule, ...]:
    """Return supported exclusion rules for a profile.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.

    Returns
    -------
    tuple[RraoExclusionRule, ...]
        Result of the operation.
    """

    resolved = _resolve_supported_profile(profile)
    return PROFILE_EXCLUSION_RULES[resolved]


def investment_fund_rules_for_profile(
    profile: RraoRegulatoryProfile | str,
) -> tuple[RraoInvestmentFundRule, ...]:
    """Return supported investment-fund inclusion rules for a profile.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.

    Returns
    -------
    tuple[RraoInvestmentFundRule, ...]
        Result of the operation.
    """

    resolved = _resolve_supported_profile(profile)
    return PROFILE_INVESTMENT_FUND_RULES[resolved]


def risk_weight_rules_for_profile(
    profile: RraoRegulatoryProfile | str,
) -> tuple[RraoRiskWeightRule, ...]:
    """Return supported risk-weight rules for a profile.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.

    Returns
    -------
    tuple[RraoRiskWeightRule, ...]
        Result of the operation.
    """

    resolved = _resolve_supported_profile(profile)
    return PROFILE_RISK_WEIGHT_RULES[resolved]


def evidence_rule_for(
    profile: RraoRegulatoryProfile | str,
    evidence_type: RraoEvidenceType,
) -> RraoEvidenceRule:
    """Return the profile rule for a classification evidence type.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.
    evidence_type : RraoEvidenceType
        Evidence type.

    Returns
    -------
    RraoEvidenceRule
        Result of the operation.
    """

    for rule in evidence_rules_for_profile(profile):
        if rule.evidence_type is evidence_type:
            return rule
    raise RraoInputError(
        f"no RRAO evidence rule for {evidence_type.value}",
        field="evidence_type",
    )


def exclusion_rule_for(
    profile: RraoRegulatoryProfile | str,
    exclusion_reason: RraoExclusionReason,
) -> RraoExclusionRule:
    """Return the profile rule for an exclusion reason.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.
    exclusion_reason : RraoExclusionReason
        Exclusion reason.

    Returns
    -------
    RraoExclusionRule
        Result of the operation.
    """

    for rule in exclusion_rules_for_profile(profile):
        if rule.exclusion_reason is exclusion_reason:
            return rule
    raise RraoInputError(
        f"no RRAO exclusion rule for {exclusion_reason.value}",
        field="exclusion_reason",
    )


def investment_fund_rule_for(
    profile: RraoRegulatoryProfile | str,
    included_exposure_type: RraoInvestmentFundExposureType,
) -> RraoInvestmentFundRule:
    """Return the profile rule for an investment-fund included exposure type.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.
    included_exposure_type : RraoInvestmentFundExposureType
        Included exposure type.

    Returns
    -------
    RraoInvestmentFundRule
        Result of the operation.
    """

    for rule in investment_fund_rules_for_profile(profile):
        if rule.included_exposure_type is included_exposure_type:
            return rule
    raise RraoInputError(
        f"no RRAO investment-fund rule for {included_exposure_type.value}",
        field="investment_fund_descriptor.included_exposure_type",
    )


def risk_weight_rule_for(
    profile: RraoRegulatoryProfile | str,
    risk_weight_key: str,
) -> RraoRiskWeightRule:
    """Return the profile rule for a risk-weight key.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.
    risk_weight_key : str
        Risk weight key.

    Returns
    -------
    RraoRiskWeightRule
        Result of the operation.
    """

    for rule in risk_weight_rules_for_profile(profile):
        if rule.key == risk_weight_key:
            return rule
    raise RraoInputError(f"no RRAO risk-weight rule for {risk_weight_key}", field="risk_weight_key")


def profile_reference_payload(profile: RraoRegulatoryProfile | str) -> dict[str, object]:
    """Return a deterministic, JSON-serialisable payload for profile hashing.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.

    Returns
    -------
    dict[str, object]
        Result of the operation.
    """

    resolved = _resolve_supported_profile(profile)
    citations = citations_for_profile(resolved)
    return {
        "profile": resolved.value,
        "citations": {
            citation_id: {
                "source_id": citation.source_id,
                "paragraph": citation.paragraph,
                "url": citation.url,
                "note": citation.note,
            }
            for citation_id, citation in sorted(citations.items())
        },
        "evidence_rules": [
            {
                "evidence_type": rule.evidence_type.value,
                "classification": rule.classification.value,
                "risk_weight_key": rule.risk_weight_key,
                "reason_code": rule.reason_code,
                "citation_id": rule.citation_id,
            }
            for rule in sorted(
                evidence_rules_for_profile(resolved), key=lambda item: item.reason_code
            )
        ],
        "exclusion_rules": [
            {
                "exclusion_reason": rule.exclusion_reason.value,
                "risk_weight_key": rule.risk_weight_key,
                "reason_code": rule.reason_code,
                "citation_id": rule.citation_id,
            }
            for rule in sorted(
                exclusion_rules_for_profile(resolved), key=lambda item: item.reason_code
            )
        ],
        "investment_fund_rules": [
            {
                "included_exposure_type": rule.included_exposure_type.value,
                "classification": rule.classification.value,
                "risk_weight_key": rule.risk_weight_key,
                "reason_code": rule.reason_code,
                "citation_ids": list(rule.citation_ids),
            }
            for rule in sorted(
                investment_fund_rules_for_profile(resolved),
                key=lambda item: item.reason_code,
            )
        ],
        "risk_weight_rules": [
            {
                "key": rule.key,
                "classification": rule.classification.value,
                "risk_weight": rule.risk_weight,
                "citation_id": rule.citation_id,
            }
            for rule in sorted(risk_weight_rules_for_profile(resolved), key=lambda item: item.key)
        ],
    }


def _resolve_supported_profile(profile: RraoRegulatoryProfile | str) -> RraoRegulatoryProfile:
    try:
        resolved = RraoRegulatoryProfile(profile)
    except ValueError as exc:
        raise RraoInputError(
            f"unknown RRAO regulatory profile: {profile!r}", field="profile"
        ) from exc

    if resolved not in PROFILE_CITATIONS:
        raise UnsupportedRegulatoryFeatureError(
            f"RRAO profile {resolved.value} is unsupported until mapped and fixture-tested."
        )
    return resolved


__all__ = [
    "RraoEvidenceRule",
    "RraoExclusionRule",
    "RraoInvestmentFundRule",
    "RraoRiskWeightRule",
    "citations_for_profile",
    "evidence_rule_for",
    "evidence_rules_for_profile",
    "exclusion_rule_for",
    "exclusion_rules_for_profile",
    "investment_fund_rule_for",
    "investment_fund_rules_for_profile",
    "profile_reference_payload",
    "risk_weight_rule_for",
    "risk_weight_rules_for_profile",
]
