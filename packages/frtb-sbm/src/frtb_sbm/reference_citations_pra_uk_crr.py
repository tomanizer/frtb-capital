"""PRA UK CRR SBM citation fragments.

Regulatory traceability:
    PRA PS1/26 Appendix 1 / PRA2026/1 Market Risk: Advanced Standardised
    Approach (CRR) Part citations used by PRA_UK_CRR comparison-profile
    payloads.
"""

from __future__ import annotations

from frtb_sbm.data_models import SbmCitation

PRA_UK_CRR_URL = (
    "https://www.bankofengland.co.uk/-/media/boe/files/prudential-regulation/"
    "policy-statement/2026/january/ps126app1.pdf"
)

PRA_UK_CRR_CITATIONS: dict[str, SbmCitation] = {
    "pra_uk_crr_325c_asa_scope": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325c"
        ),
        url=PRA_UK_CRR_URL,
        note=("Advanced Standardised Approach scope for PRA_UK_CRR SBM comparison profile runs."),
    ),
    "pra_uk_crr_325ae_girr_buckets": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325ae"
        ),
        url=PRA_UK_CRR_URL,
        note="GIRR currency bucket definitions for the PRA_UK_CRR delta slice.",
    ),
    "pra_uk_crr_325ae_girr_delta_weights": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325ae"
        ),
        url=PRA_UK_CRR_URL,
        note="GIRR delta tenor risk weights for the PRA_UK_CRR comparison slice.",
    ),
    "pra_uk_crr_325ae_girr_special_factors": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325ae"
        ),
        url=PRA_UK_CRR_URL,
        note="GIRR inflation and cross-currency-basis special risk-factor weights.",
    ),
    "pra_uk_crr_325ae_girr_sqrt2": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325ae"
        ),
        url=PRA_UK_CRR_URL,
        note="Specified-currency square-root-of-two GIRR risk-weight adjustment.",
    ),
    "pra_uk_crr_325e_components": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325e"
        ),
        url=PRA_UK_CRR_URL,
        note="Delta, vega, and curvature component definitions for the ASA.",
    ),
    "pra_uk_crr_325f_delta_vega_aggregation": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325f"
        ),
        url=PRA_UK_CRR_URL,
        note="Delta and vega bucket and cross-bucket aggregation formulae.",
    ),
    "pra_uk_crr_325af_girr_intra": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325af"
        ),
        url=PRA_UK_CRR_URL,
        note="GIRR delta intra-bucket tenor, curve, inflation, and XCCY correlations.",
    ),
    "pra_uk_crr_325ag_girr_inter": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325ag"
        ),
        url=PRA_UK_CRR_URL,
        note="GIRR delta inter-bucket correlation for the PRA_UK_CRR slice.",
    ),
    "pra_uk_crr_325h_correlation_scenarios": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325h"
        ),
        url=PRA_UK_CRR_URL,
        note="Low, medium, and high correlation scenario aggregation.",
    ),
    "pra_uk_crr_325l_girr_risk_factors": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325l"
        ),
        url=PRA_UK_CRR_URL,
        note="GIRR prescribed risk factors and tenor axes for delta, vega, and curvature.",
    ),
    "pra_uk_crr_325o_equity_risk_factors": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325o"
        ),
        url=PRA_UK_CRR_URL,
        note="Equity spot and repo risk-factor definitions for PRA_UK_CRR runs.",
    ),
    "pra_uk_crr_325p_commodity_risk_factors": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325p"
        ),
        url=PRA_UK_CRR_URL,
        note="Commodity type, location, and maturity risk-factor definitions.",
    ),
    "pra_uk_crr_325q_fx_risk_factors": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325q"
        ),
        url=PRA_UK_CRR_URL,
        note="FX risk-factor definitions and reporting-currency treatment.",
    ),
    "pra_uk_crr_325s_vega_sensitivities": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325s"
        ),
        url=PRA_UK_CRR_URL,
        note="Vega sensitivity formula and option-underlying tenor treatment.",
    ),
    "pra_uk_crr_325g_curvature_aggregation": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325g"
        ),
        url=PRA_UK_CRR_URL,
        note="Curvature aggregation, branch selection, and floor mechanics.",
    ),
    "pra_uk_crr_325ap_equity_buckets": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325ap"
        ),
        url=PRA_UK_CRR_URL,
        note="Equity bucket assignment for the PRA_UK_CRR delta slice.",
    ),
    "pra_uk_crr_325ap_equity_weights": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325ap"
        ),
        url=PRA_UK_CRR_URL,
        note="Equity spot and repo risk weights for the PRA_UK_CRR delta slice.",
    ),
    "pra_uk_crr_325aq_equity_intra": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325aq"
        ),
        url=PRA_UK_CRR_URL,
        note="Equity delta intra-bucket correlations and other-sector treatment.",
    ),
    "pra_uk_crr_325aq_equity_other_sector": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325aq"
        ),
        url=PRA_UK_CRR_URL,
        note="Equity other-sector bucket absolute-weight aggregation treatment.",
    ),
    "pra_uk_crr_325ar_equity_inter": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325ar"
        ),
        url=PRA_UK_CRR_URL,
        note="Equity delta inter-bucket correlations.",
    ),
    "pra_uk_crr_325as_commodity_buckets": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325as"
        ),
        url=PRA_UK_CRR_URL,
        note="Commodity bucket assignment for the PRA_UK_CRR delta slice.",
    ),
    "pra_uk_crr_325as_commodity_weights": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325as"
        ),
        url=PRA_UK_CRR_URL,
        note="Commodity delta bucket risk weights.",
    ),
    "pra_uk_crr_325at_commodity_intra": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325at"
        ),
        url=PRA_UK_CRR_URL,
        note="Commodity intra-bucket type, tenor, and location correlations.",
    ),
    "pra_uk_crr_325au_commodity_inter": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325au"
        ),
        url=PRA_UK_CRR_URL,
        note="Commodity inter-bucket correlations.",
    ),
    "pra_uk_crr_325av_fx_delta_buckets": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325av"
        ),
        url=PRA_UK_CRR_URL,
        note="FX delta bucket assignment by currency against reporting currency.",
    ),
    "pra_uk_crr_325av_fx_delta_weights": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325av"
        ),
        url=PRA_UK_CRR_URL,
        note="FX delta risk weight for PRA_UK_CRR reporting-currency runs.",
    ),
    "pra_uk_crr_325av_fx_delta_sqrt2": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325av"
        ),
        url=PRA_UK_CRR_URL,
        note="Specified-currency square-root-of-two FX risk-weight adjustment.",
    ),
    "pra_uk_crr_325aw_fx_delta_inter": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325aw"
        ),
        url=PRA_UK_CRR_URL,
        note="FX delta inter-bucket correlation parameter.",
    ),
    "pra_uk_crr_325ax_vega_risk_weights": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325ax"
        ),
        url=PRA_UK_CRR_URL,
        note="Vega liquidity-horizon risk-weight scaling for PRA_UK_CRR comparison runs.",
    ),
    "pra_uk_crr_325ax_fx_vega_risk_weights": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325ax"
        ),
        url=PRA_UK_CRR_URL,
        note="FX vega liquidity-horizon risk-weight scaling.",
    ),
    "pra_uk_crr_325ax_curvature_risk_weights": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325ax"
        ),
        url=PRA_UK_CRR_URL,
        note="Curvature risk-weight shock scaling for PRA_UK_CRR comparison runs.",
    ),
    "pra_uk_crr_325ax_fx_curvature_risk_weights": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325ax"
        ),
        url=PRA_UK_CRR_URL,
        note="FX curvature shock scaling for PRA_UK_CRR comparison runs.",
    ),
    "pra_uk_crr_325ay_vega_correlations": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325ay"
        ),
        url=PRA_UK_CRR_URL,
        note="Vega correlation parameters, including GIRR option and underlying tenor terms.",
    ),
    "pra_uk_crr_325ay_curvature_correlations": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325ay"
        ),
        url=PRA_UK_CRR_URL,
        note="Curvature correlation parameters for PRA_UK_CRR comparison runs.",
    ),
}

__all__ = ["PRA_UK_CRR_CITATIONS", "PRA_UK_CRR_URL"]
