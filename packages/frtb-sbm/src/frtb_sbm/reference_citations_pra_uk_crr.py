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
    "pra_uk_crr_325ax_vega_risk_weights": SbmCitation(
        source_id="uk_pra_ps1_26_sbm_asa",
        location=(
            "PRA PS1/26 Appendix 1, Market Risk: Advanced Standardised "
            "Approach (CRR) Part, Article 325ax"
        ),
        url=PRA_UK_CRR_URL,
        note="Vega liquidity-horizon risk-weight scaling for PRA_UK_CRR comparison runs.",
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
