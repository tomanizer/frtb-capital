"""EU CRR3 SBM citation fragments.

Regulatory traceability:
    Regulation (EU) 2024/1623 amended Regulation (EU) No 575/2013 market-risk
    provisions. These ids support EU_CRR3 comparison-profile reference data and
    map existing Basel MAR21 citation roles to CRR article/paragraph/table
    anchors.
"""

from __future__ import annotations

from frtb_sbm.data_models import SbmCitation

EU_CRR3_URL = "https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng"

_EU_LOCATION_BY_BASEL_ID: dict[str, tuple[str, str]] = {
    "basel_mar21_1": (
        "Regulation (EU) 2024/1623, Article 1(156) amending CRR Article 325(1); "
        "Article 1(159) amending CRR Article 325c",
        "Alternative standardised approach scope and sensitivities-based-method stack.",
    ),
    "basel_mar21_4_intra_bucket": (
        "Amended CRR Article 325e(4)",
        "Intra-bucket capital formula Kb.",
    ),
    "basel_mar21_4_inter_bucket": (
        "Amended CRR Article 325e(5)",
        "Inter-bucket capital formula.",
    ),
    "basel_mar21_curvature": (
        "Amended CRR Article 325e(6)",
        "Curvature risk capital with up/down shock inputs and delta exclusion.",
    ),
    "basel_mar21_6_correlation_scenarios": (
        "Amended CRR Article 325e(7)",
        "Low, medium, and high correlation scenario parameter adjustments.",
    ),
    "basel_mar21_7_scenario_selection": (
        "Amended CRR Article 325e(8)",
        "Maximum scenario capital selection.",
    ),
    "basel_mar21_8": (
        "Amended CRR Article 325f",
        "Risk-factor and bucket assignment boundary.",
    ),
    "basel_mar21_9": (
        "Amended CRR Article 325n",
        "CSR non-securitisation delta risk factors.",
    ),
    "basel_mar21_10": (
        "Amended CRR Article 325o",
        "CSR securitisation non-CTP tranche credit-spread risk factors.",
    ),
    "basel_mar21_11": (
        "Amended CRR Article 325p",
        "CSR securitisation ACTP underlying-name credit-spread risk factors.",
    ),
    "basel_mar21_12": (
        "Amended CRR Article 325r",
        "Equity delta and vega risk-factor definitions.",
    ),
    "basel_mar21_13": (
        "Amended CRR Article 325s; Regulation (EU) 2024/1623 Article 1(162)",
        "Commodity delta and vega risk-factor definitions and tenors.",
    ),
    "basel_mar21_14": (
        "Amended CRR Article 325q; Regulation (EU) 2024/1623 Article 1(161)",
        "FX delta and vega risk-factor definitions.",
    ),
    "basel_mar21_38": (
        "Amended CRR Article 325ae",
        "GIRR bucket registry and currency bucket mapping.",
    ),
    "basel_mar21_39": (
        "Amended CRR Article 325ae",
        "GIRR delta buckets, risk weights, and correlation-parameter lead-in.",
    ),
    "basel_mar21_40": (
        "Amended CRR Article 325ae",
        "Liquidity-adjusted calibration scope for prescribed GIRR delta parameters.",
    ),
    "basel_mar21_41": (
        "Amended CRR Article 325ae",
        "Each currency is a separate GIRR delta bucket.",
    ),
    "basel_mar21_42": (
        "Amended CRR Article 325ae(1), Table 3",
        "GIRR delta risk weights by prescribed tenor.",
    ),
    "basel_mar21_43": (
        "Amended CRR Article 325ae(2)",
        "GIRR inflation and cross-currency-basis risk weights.",
    ),
    "basel_mar21_44": (
        "Amended CRR Article 325ae(3); Regulation (EU) 2024/1623 Article 1(170)",
        "Specified-currency square-root-of-two GIRR risk-weight adjustment.",
    ),
    "basel_mar21_45_49": (
        "Amended CRR Articles 325af-325ai",
        "GIRR intra-bucket correlation parameters.",
    ),
    "basel_mar21_50": (
        "Amended CRR Article 325aj",
        "GIRR inter-bucket correlation parameter.",
    ),
    "basel_mar21_51": (
        "Amended CRR Article 325ah(1), Table 4; Regulation (EU) 2024/1623 Article 1(171)",
        "CSR non-securitisation delta bucket assignment.",
    ),
    "basel_mar21_53": (
        "Amended CRR Article 325ah(1), Table 4",
        "CSR non-securitisation delta risk weights.",
    ),
    "basel_mar21_54": (
        "Amended CRR Article 325ai(1); Regulation (EU) 2024/1623 Article 1(172)",
        "CSR non-securitisation intra-bucket correlations.",
    ),
    "basel_mar21_55": (
        "Amended CRR Article 325ai(2)",
        "CSR non-securitisation index-bucket intra-bucket correlations.",
    ),
    "basel_mar21_56": (
        "Amended CRR Article 325ai(3)",
        "CSR non-securitisation other-sector absolute-weight aggregation.",
    ),
    "basel_mar21_57": (
        "Amended CRR Article 325aj; Regulation (EU) 2024/1623 Article 1(173)",
        "CSR non-securitisation inter-bucket gamma.",
    ),
    "basel_mar21_58": (
        "Amended CRR Article 325am; Regulation (EU) 2024/1623 Article 1(175)",
        "CSR securitisation ACTP bucket assignment and correlation rule.",
    ),
    "basel_mar21_59": (
        "Amended CRR Article 325am(1), Table 7",
        "CSR securitisation ACTP delta risk weights.",
    ),
    "basel_mar21_60": (
        "Amended CRR Article 325am",
        "CSR securitisation ACTP other-bucket treatment.",
    ),
    "basel_mar21_61": (
        "Amended CRR Article 325ak; Regulation (EU) 2024/1623 Article 1(174)",
        "CSR securitisation non-ACTP bucket assignment.",
    ),
    "basel_mar21_65": (
        "Amended CRR Article 325ak(1), Table 6",
        "CSR securitisation non-ACTP delta risk weights.",
    ),
    "basel_mar21_66": (
        "Amended CRR Article 325ak",
        "CSR securitisation non-ACTP other-sector risk weight.",
    ),
    "basel_mar21_67": (
        "Amended CRR Article 325al",
        "CSR securitisation non-ACTP intra-bucket correlation rule.",
    ),
    "basel_mar21_68": (
        "Amended CRR Article 325al",
        "CSR securitisation non-ACTP other-sector aggregation rule.",
    ),
    "basel_mar21_70": (
        "Amended CRR Article 325al",
        "CSR securitisation non-ACTP inter-bucket gamma.",
    ),
    "basel_mar21_72": (
        "Amended CRR Article 325ap(1), Table 8",
        "Equity delta bucket assignment.",
    ),
    "basel_mar21_77": (
        "Amended CRR Article 325ap(2), Table 9",
        "Equity delta risk weights for spot and repo.",
    ),
    "basel_mar21_78": (
        "Amended CRR Article 325aq",
        "Equity delta intra-bucket correlation parameters.",
    ),
    "basel_mar21_79": (
        "Amended CRR Article 325aq",
        "Equity other-sector bucket absolute-weight aggregation.",
    ),
    "basel_mar21_80": (
        "Amended CRR Article 325ar",
        "Equity delta inter-bucket correlation parameters.",
    ),
    "basel_mar21_81": (
        "Amended CRR Article 325as, Table 9; Regulation (EU) 2024/1623 Article 1(176)",
        "Commodity delta bucket assignment.",
    ),
    "basel_mar21_82": (
        "Amended CRR Article 325as, Table 9; Regulation (EU) 2024/1623 Article 1(176)",
        "Commodity delta risk weights, including EU ETS carbon trading bucket split.",
    ),
    "basel_mar21_83": (
        "Amended CRR Article 325at",
        "Commodity delta intra-bucket correlation parameters.",
    ),
    "basel_mar21_85": (
        "Amended CRR Article 325au",
        "Commodity delta inter-bucket correlation parameters.",
    ),
    "basel_mar21_86": (
        "Amended CRR Article 325av",
        "FX delta bucket assignment by exchange rate versus reporting currency.",
    ),
    "basel_mar21_87": (
        "Amended CRR Article 325av",
        "FX delta uniform risk weight.",
    ),
    "basel_mar21_88": (
        "Amended CRR Article 325av",
        "FX specified-currency square-root-of-two risk-weight adjustment.",
    ),
    "basel_mar21_89": (
        "Amended CRR Article 325aw",
        "FX delta inter-bucket correlation parameter.",
    ),
    "basel_mar21_90": (
        "Amended CRR Article 325ax",
        "Vega risk capital requirement scope.",
    ),
    "basel_mar21_91": (
        "Amended CRR Article 325ax(1); Regulation (EU) 2024/1623 Article 1(177)",
        "Vega uses the same bucket definitions for each risk class as delta.",
    ),
    "basel_mar21_92": (
        "Amended CRR Article 325ax(2), Table 1; Regulation (EU) 2024/1623 Article 1(177)",
        "Vega risk weights by risk class.",
    ),
    "basel_mar21_93": (
        "Amended CRR Article 325ax(4)",
        "GIRR vega intra-bucket correlation from option and underlying tenors.",
    ),
    "basel_mar21_94": (
        "Amended CRR Article 325ax(5)",
        "Non-GIRR vega intra-bucket correlation rule.",
    ),
    "basel_mar21_95": (
        "Amended CRR Article 325ax(5)",
        "Vega inter-bucket correlations reuse corresponding delta gammas.",
    ),
    "basel_mar21_96": (
        "Amended CRR Article 325ax(6); Regulation (EU) 2024/1623 Article 1(177)",
        "Curvature buckets, risk weights, and correlation parameters scope.",
    ),
    "basel_mar21_97": (
        "Amended CRR Article 325ax(6)",
        "Delta buckets are replicated for curvature unless otherwise specified.",
    ),
    "basel_mar21_98": (
        "Amended CRR Article 325ax(6)",
        "FX and equity curvature shock sizes equal respective delta risk weights.",
    ),
    "basel_mar21_99": (
        "Amended CRR Article 325ax(6); Regulation (EU) 2024/1623 Article 1(177)",
        "GIRR, CSR, and commodity curvature shock sizes use the highest delta risk weight.",
    ),
    "basel_mar21_100": (
        "Amended CRR Article 325ax(6)",
        "Curvature intra-bucket correlations square corresponding delta parameters.",
    ),
    "basel_mar21_101": (
        "Amended CRR Article 325ax(6)",
        "Curvature inter-bucket correlations square corresponding delta parameters.",
    ),
}

BASEL_TO_EU_CRR3_CITATION_IDS: dict[str, str] = {
    basel_id: "eu_crr3_" + basel_id.removeprefix("basel_mar21_").replace("-", "_")
    for basel_id in _EU_LOCATION_BY_BASEL_ID
}

EU_CRR3_CITATIONS: dict[str, SbmCitation] = {
    eu_id: SbmCitation(
        source_id="eu_crr3_reg_2024_1623",
        location=location,
        url=EU_CRR3_URL,
        note=note,
    )
    for basel_id, (location, note) in _EU_LOCATION_BY_BASEL_ID.items()
    for eu_id in (BASEL_TO_EU_CRR3_CITATION_IDS[basel_id],)
}

EU_CRR3_CITATION_IDS = frozenset(EU_CRR3_CITATIONS)


def eu_crr3_citation_id_for_basel(basel_citation_id: str) -> str:
    """Return the EU CRR3 citation id for an existing Basel MAR21 citation role.

    Parameters
    ----------
    basel_citation_id:
        Basel MAR21 citation id whose EU CRR3 comparison-profile analogue is
        required.

    Returns
    -------
    str
        EU CRR3 citation id with the same policy role.
    """

    return BASEL_TO_EU_CRR3_CITATION_IDS[basel_citation_id]


def translate_basel_citation_ids_to_eu(citation_ids: tuple[str, ...]) -> tuple[str, ...]:
    """Translate Basel citation ids to EU CRR3 ids while preserving order.

    Parameters
    ----------
    citation_ids:
        Citation ids from profile-specific reference payloads or audit records.
        Basel ids must have an explicit EU CRR3 mapping; already-translated EU
        ids and non-Basel ids are preserved.

    Returns
    -------
    tuple[str, ...]
        Citation ids with mapped Basel MAR21 ids replaced by EU CRR3 ids.
    """

    translated: list[str] = []
    for item in citation_ids:
        if item in BASEL_TO_EU_CRR3_CITATION_IDS:
            translated.append(BASEL_TO_EU_CRR3_CITATION_IDS[item])
            continue
        if item.startswith("basel_"):
            raise KeyError(f"No EU CRR3 citation mapping for {item!r}")
        translated.append(item)
    return tuple(translated)


__all__ = [
    "BASEL_TO_EU_CRR3_CITATION_IDS",
    "EU_CRR3_CITATIONS",
    "EU_CRR3_CITATION_IDS",
    "EU_CRR3_URL",
    "eu_crr3_citation_id_for_basel",
    "translate_basel_citation_ids_to_eu",
]
