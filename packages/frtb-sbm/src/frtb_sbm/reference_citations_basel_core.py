"""Basel MAR21 SBM citation fragments.

Regulatory traceability:
    Basel MAR21 citation ids used by SBM reference-data payloads.
"""

from __future__ import annotations

from frtb_sbm.data_models import SbmCitation

BASEL_MAR21_URL = "https://www.bis.org/basel_framework/chapter/MAR/21.htm"

BASEL_CORE_CITATIONS: dict[str, SbmCitation] = {
    "basel_mar21_1": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.1",
        url=BASEL_MAR21_URL,
        note="Sensitivities-based method scope and risk-class stack.",
    ),
    "basel_mar21_8": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.8",
        url=BASEL_MAR21_URL,
        note="Risk-factor and bucket assignment boundary.",
    ),
    "basel_mar21_38": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.38-MAR21.41",
        url=BASEL_MAR21_URL,
        note=(
            "GIRR bucket registry keyed to MAR21.41 one-currency-one-bucket rule; "
            "see ADR 0017 for CNH/CNY mapping."
        ),
    ),
    "basel_mar21_39": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.39",
        url=BASEL_MAR21_URL,
        note="Delta buckets, risk weights, and correlation-parameter section lead-in.",
    ),
    "basel_mar21_40": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.40",
        url=BASEL_MAR21_URL,
        note="Liquidity-adjusted calibration scope for prescribed delta weights and correlations.",
    ),
    "basel_mar21_4_intra_bucket": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.4(4)",
        url=BASEL_MAR21_URL,
        note="Intra-bucket capital formula Kb.",
    ),
    "basel_mar21_4_inter_bucket": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.4(5)",
        url=BASEL_MAR21_URL,
        note="Inter-bucket capital formula.",
    ),
    "basel_mar21_curvature": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.5",
        url=BASEL_MAR21_URL,
        note="Curvature risk capital with up/down shock inputs and delta exclusion.",
    ),
    "basel_mar21_6_correlation_scenarios": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.6",
        url=BASEL_MAR21_URL,
        note="Low, medium, and high correlation scenario parameter adjustments.",
    ),
    "basel_mar21_7_scenario_selection": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.7(2)",
        url=BASEL_MAR21_URL,
        note="Select maximum scenario capital for GIRR delta.",
    ),
    "basel_mar21_96": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.96",
        url=BASEL_MAR21_URL,
        note="Curvature buckets, risk weights, and correlation parameters scope.",
    ),
    "basel_mar21_97": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.97",
        url=BASEL_MAR21_URL,
        note="Delta buckets are replicated for curvature unless otherwise specified.",
    ),
    "basel_mar21_98": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.98",
        url=BASEL_MAR21_URL,
        note="FX and equity curvature shock sizes equal the respective delta risk weights.",
    ),
    "basel_mar21_99": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.99",
        url=BASEL_MAR21_URL,
        note=(
            "GIRR, CSR, and commodity curvature shock sizes are parallel shifts based "
            "on the highest prescribed delta risk weight for the relevant bucket."
        ),
    ),
    "basel_mar21_100": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.100",
        url=BASEL_MAR21_URL,
        note="Curvature intra-bucket correlations square the corresponding delta parameters.",
    ),
    "basel_mar21_101": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.101",
        url=BASEL_MAR21_URL,
        note="Curvature inter-bucket correlations square the corresponding delta parameters.",
    ),
    "basel_mar21_41": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.41",
        url=BASEL_MAR21_URL,
        note="Each currency is a separate GIRR delta bucket.",
    ),
    "basel_mar21_42": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.42",
        url=BASEL_MAR21_URL,
        note="GIRR delta risk weights by prescribed tenor.",
    ),
    "basel_mar21_43": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.43",
        url=BASEL_MAR21_URL,
        note="GIRR inflation and cross-currency basis risk weights.",
    ),
    "basel_mar21_44": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.44",
        url=BASEL_MAR21_URL,
        note="Specified-currency sqrt(2) GIRR risk-weight adjustment.",
    ),
    "basel_mar21_45_49": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.45-MAR21.49",
        url=BASEL_MAR21_URL,
        note="GIRR intra-bucket correlation parameters, including inflation and XCCY.",
    ),
    "basel_mar21_50": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.50",
        url=BASEL_MAR21_URL,
        note="GIRR inter-bucket correlation parameter.",
    ),
    "basel_mar21_91": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.91",
        url=BASEL_MAR21_URL,
        note="Vega uses the same bucket definitions for each risk class as delta.",
    ),
    "basel_mar21_92": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.92",
        url=BASEL_MAR21_URL,
        note="Vega liquidity horizon and risk-weight scaling by risk class (Table 13).",
    ),
    "basel_mar21_93": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.93",
        url=BASEL_MAR21_URL,
        note="GIRR vega intra-bucket correlation from option and underlying tenors.",
    ),
    "basel_mar21_90": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.90",
        url=BASEL_MAR21_URL,
        note="Vega risk capital requirement scope.",
    ),
    "basel_mar21_94": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.94",
        url=BASEL_MAR21_URL,
        note=(
            "Non-GIRR vega intra-bucket correlation equals the corresponding "
            "delta correlation times option-tenor correlation, capped at 1."
        ),
    ),
    "basel_mar21_95": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.95",
        url=BASEL_MAR21_URL,
        note="Vega inter-bucket correlations reuse the corresponding delta gammas.",
    ),
    "basel_mar21_14": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.14",
        url=BASEL_MAR21_URL,
        note="FX delta risk-factor definition relative to reporting currency.",
    ),
    "basel_mar21_86": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.86",
        url=BASEL_MAR21_URL,
        note="FX delta bucket assignment by exchange rate versus reporting currency.",
    ),
    "basel_mar21_87": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.87",
        url=BASEL_MAR21_URL,
        note="FX delta uniform 15% risk weight.",
    ),
    "basel_mar21_88": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.88",
        url=BASEL_MAR21_URL,
        note="FX delta sqrt(2) risk-weight reduction for specified and first-order cross pairs.",
    ),
    "basel_mar21_89": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.89",
        url=BASEL_MAR21_URL,
        note="FX delta inter-bucket correlation parameter.",
    ),
}

__all__ = ["BASEL_CORE_CITATIONS"]
