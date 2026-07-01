"""Citation and branch assembly helpers for DRC batch calculations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from frtb_drc.data_models import (
    BranchMetadata,
    CategoryDrc,
    DrcRiskClass,
    NetJtd,
)
from frtb_drc.validation import (
    BASEL_MAR22_PROFILE_ID,
    EU_CRR3_PROFILE_ID,
    PRA_UK_CRR_PROFILE_ID,
    US_NPR_2_0_PROFILE_ID,
)

if TYPE_CHECKING:
    from frtb_drc.batch import DrcPositionBatch

_US_NPR_FORMULA_CITATIONS = ("BASEL_MAR22_11", "BASEL_MAR22_13", "US_NPR_210_A_1_II")
_BASEL_FORMULA_CITATIONS = ("BASEL_MAR22_11", "BASEL_MAR22_13")
_EU_CRR3_FORMULA_CITATIONS = ("EU_CRR3_ARTICLE_325W",)
_PRA_FORMULA_CITATIONS = ("PRA_DRC_ARTICLE_325W",)
_US_NPR_NETTING_CITATION = "US_NPR_210_B_2"
_BASEL_NETTING_CITATION = "BASEL_MAR22_19"
_EU_CRR3_NETTING_CITATION = "EU_CRR3_ARTICLE_325X"
_PRA_NETTING_CITATION = "PRA_DRC_ARTICLE_325X"
_US_NPR_ZERO_CATEGORY_CITATION = "US_NPR_210_B_3_III"
_BASEL_ZERO_CATEGORY_CITATION = "BASEL_MAR22_26"
_EU_CRR3_ZERO_CATEGORY_CITATION = "EU_CRR3_ARTICLE_325Y_3_5"
_PRA_ZERO_CATEGORY_CITATION = "PRA_DRC_ARTICLE_325Y"
_SEC_NON_CTP_GROSS_CITATIONS = ("US_NPR_210_C_1", "BASEL_MAR22_27")
_SEC_NON_CTP_FAIR_VALUE_CAP_CITATIONS = ("US_NPR_210_C_3_III", "BASEL_MAR22_34")
_SEC_NON_CTP_NETTING_CITATIONS = (
    "US_NPR_210_C_2",
    "BASEL_MAR22_28",
    "BASEL_MAR22_29",
    "BASEL_MAR22_30",
)
_SEC_NON_CTP_BATCH_CITATIONS = (
    *_SEC_NON_CTP_GROSS_CITATIONS,
    *_SEC_NON_CTP_NETTING_CITATIONS,
    "US_NPR_210_C_3_I_II",
    "US_NPR_210_C_3_III",
    "US_NPR_210_C_3_IV",
    "BASEL_MAR22_31",
    "BASEL_MAR22_32",
    "BASEL_MAR22_33",
    "BASEL_MAR22_34",
    "BASEL_MAR22_35",
)
_BASEL_SEC_NON_CTP_GROSS_CITATIONS = ("BASEL_MAR22_27",)
_BASEL_SEC_NON_CTP_FAIR_VALUE_CAP_CITATIONS = ("BASEL_MAR22_34",)
_BASEL_SEC_NON_CTP_NETTING_CITATIONS = (
    "BASEL_MAR22_28",
    "BASEL_MAR22_29",
    "BASEL_MAR22_30",
)
_BASEL_SEC_NON_CTP_BATCH_CITATIONS = (
    *_BASEL_SEC_NON_CTP_GROSS_CITATIONS,
    *_BASEL_SEC_NON_CTP_NETTING_CITATIONS,
    "BASEL_MAR22_31",
    "BASEL_MAR22_32",
    "BASEL_MAR22_33",
    "BASEL_MAR22_34",
    "BASEL_MAR22_35",
)
_EU_CRR3_SEC_NON_CTP_GROSS_CITATIONS = ("EU_CRR3_ARTICLE_325Z",)
_EU_CRR3_SEC_NON_CTP_FAIR_VALUE_CAP_CITATIONS = ("EU_CRR3_ARTICLE_325AA",)
_EU_CRR3_SEC_NON_CTP_NETTING_CITATIONS = ("EU_CRR3_ARTICLE_325Z",)
_EU_CRR3_SEC_NON_CTP_BATCH_CITATIONS = (
    *_EU_CRR3_SEC_NON_CTP_GROSS_CITATIONS,
    *_EU_CRR3_SEC_NON_CTP_NETTING_CITATIONS,
    "EU_CRR3_ARTICLE_325AA",
)
_CTP_GROSS_CITATIONS = ("US_NPR_210_D_1",)
_BASEL_CTP_GROSS_CITATIONS = ("BASEL_MAR22_36", "BASEL_MAR22_37")
_CTP_NETTING_CITATIONS = ("US_NPR_210_D_2",)
_BASEL_CTP_NETTING_CITATIONS = ("BASEL_MAR22_39",)
_CTP_BATCH_CITATIONS = (
    *_CTP_GROSS_CITATIONS,
    *_CTP_NETTING_CITATIONS,
    "US_NPR_210_D_3_I_III",
    "US_NPR_210_D_3_IV",
    "US_NPR_210_D_3_IV_D",
    "US_NPR_210_D_3_V",
)
_BASEL_CTP_BATCH_CITATIONS = (
    *_BASEL_CTP_GROSS_CITATIONS,
    *_BASEL_CTP_NETTING_CITATIONS,
    "BASEL_MAR22_40",
    "BASEL_MAR22_41",
    "BASEL_MAR22_42",
    "BASEL_MAR22_44",
    "BASEL_MAR22_45",
)
_EU_CRR3_CTP_GROSS_CITATIONS = ("EU_CRR3_ARTICLE_325AB",)
_EU_CRR3_CTP_NETTING_CITATIONS = ("EU_CRR3_ARTICLE_325AC",)
_EU_CRR3_CTP_BATCH_CITATIONS = (
    *_EU_CRR3_CTP_GROSS_CITATIONS,
    *_EU_CRR3_CTP_NETTING_CITATIONS,
    "EU_CRR3_ARTICLE_325AD",
)


def collect_batch_citations(
    batch: DrcPositionBatch,
    *,
    category: CategoryDrc,
    net_jtds: tuple[NetJtd, ...],
    formula_citations: tuple[str, ...],
    profile_id: str,
    fx_citations: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Collect deterministic citation ids for a DRC batch capital result.

    Parameters
    ----------
    batch : DrcPositionBatch
        Canonical columnar DRC position batch.
    category : CategoryDrc
        Calculated risk-class category result.
    net_jtds : tuple[NetJtd, ...]
        Net JTD records produced by the batch kernel.
    formula_citations : tuple[str, ...]
        Formula citations selected for the active calculation branch.
    profile_id : str
        Active DRC rule profile identifier.
    fx_citations : tuple[str, ...], optional
        FX citations used by currency conversion.

    Returns
    -------
    tuple[str, ...]
        Sorted citation identifiers attached to the capital result.
    """

    citation_ids = {*formula_citations, *fx_citations}
    if profile_id == US_NPR_2_0_PROFILE_ID:
        citation_ids.add("US_NPR_210_SCOPE")
    for group in batch.citation_ids:
        citation_ids.update(group)
    citation_ids.update(_branch_citations(category.branch_metadata))
    for bucket in category.bucket_results:
        citation_ids.update(bucket.citations)
        citation_ids.update(bucket.hbr.citations)
        citation_ids.update(_branch_citations(bucket.branch_metadata))
        citation_ids.update(_branch_citations(bucket.hbr.branch_metadata))
    for net_jtd in net_jtds:
        citation_ids.update(_branch_citations(net_jtd.branch_metadata))
        for rejected_offset in net_jtd.rejected_offsets:
            citation_ids.update(rejected_offset.citations)
    return tuple(sorted(citation_ids))


def batch_api_citations(profile_id: str, risk_class: DrcRiskClass) -> tuple[str, ...]:
    """Return profile-level API citations for one DRC risk class.

    Parameters
    ----------
    profile_id : str
        Active DRC rule profile identifier.
    risk_class : DrcRiskClass
        Risk class represented by the batch.

    Returns
    -------
    tuple[str, ...]
        Citation identifiers required at the batch API boundary.
    """

    if profile_id == EU_CRR3_PROFILE_ID and risk_class is DrcRiskClass.NON_SECURITISATION:
        return (
            "EU_CRR3_ARTICLE_325W",
            "EU_CRR3_ARTICLE_325X",
            "EU_CRR3_ARTICLE_325Y_1_2",
            "EU_CRR3_ARTICLE_325Y_3_5",
            "EU_CRR3_ARTICLE_325Y_6",
            "EU_CRR3_ECAI_CQS_MAPPING",
        )
    if profile_id == PRA_UK_CRR_PROFILE_ID and risk_class is DrcRiskClass.NON_SECURITISATION:
        return (
            "PRA_DRC_ARTICLE_325W",
            "PRA_DRC_ARTICLE_325X",
            "PRA_DRC_ARTICLE_325Y",
        )
    if profile_id == BASEL_MAR22_PROFILE_ID and risk_class is DrcRiskClass.SECURITISATION_NON_CTP:
        return _BASEL_SEC_NON_CTP_BATCH_CITATIONS
    if profile_id == EU_CRR3_PROFILE_ID and risk_class is DrcRiskClass.SECURITISATION_NON_CTP:
        return _EU_CRR3_SEC_NON_CTP_BATCH_CITATIONS
    if (
        profile_id == BASEL_MAR22_PROFILE_ID
        and risk_class is DrcRiskClass.CORRELATION_TRADING_PORTFOLIO
    ):
        return _BASEL_CTP_BATCH_CITATIONS
    if (
        profile_id == EU_CRR3_PROFILE_ID
        and risk_class is DrcRiskClass.CORRELATION_TRADING_PORTFOLIO
    ):
        return _EU_CRR3_CTP_BATCH_CITATIONS
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return ()
    if profile_id == EU_CRR3_PROFILE_ID:
        return ()
    if profile_id == PRA_UK_CRR_PROFILE_ID:
        return ()
    return ("US_NPR_210_SCOPE",)


def nonsec_formula_citations(profile_id: str) -> tuple[str, ...]:
    """Return non-securitisation formula citations for the active profile.

    Parameters
    ----------
    profile_id : str
        Active DRC rule profile identifier.

    Returns
    -------
    tuple[str, ...]
        Citation identifiers for non-securitisation formula aggregation.
    """

    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_FORMULA_CITATIONS
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_FORMULA_CITATIONS
    if profile_id == PRA_UK_CRR_PROFILE_ID:
        return _PRA_FORMULA_CITATIONS
    return _US_NPR_FORMULA_CITATIONS


def nonsec_netting_citation(profile_id: str) -> str:
    """Return non-securitisation netting citation for the active profile.

    Parameters
    ----------
    profile_id : str
        Active DRC rule profile identifier.

    Returns
    -------
    str
        Citation identifier for non-securitisation netting.
    """

    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_NETTING_CITATION
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_NETTING_CITATION
    if profile_id == PRA_UK_CRR_PROFILE_ID:
        return _PRA_NETTING_CITATION
    return _US_NPR_NETTING_CITATION


def zero_nonsec_category_citation(profile_id: str) -> str:
    """Return zero-category branch citation for non-securitisation DRC.

    Parameters
    ----------
    profile_id : str
        Active DRC rule profile identifier.

    Returns
    -------
    str
        Citation identifier for the zero-category branch.
    """

    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_ZERO_CATEGORY_CITATION
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_ZERO_CATEGORY_CITATION
    if profile_id == PRA_UK_CRR_PROFILE_ID:
        return _PRA_ZERO_CATEGORY_CITATION
    return _US_NPR_ZERO_CATEGORY_CITATION


def sec_non_ctp_gross_citations(profile_id: str) -> tuple[str, ...]:
    """Return securitisation non-CTP gross-JTD citations.

    Parameters
    ----------
    profile_id : str
        Active DRC rule profile identifier.

    Returns
    -------
    tuple[str, ...]
        Citation identifiers for securitisation non-CTP gross JTD.
    """

    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_SEC_NON_CTP_GROSS_CITATIONS
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_SEC_NON_CTP_GROSS_CITATIONS
    return _SEC_NON_CTP_GROSS_CITATIONS


def sec_non_ctp_fair_value_cap_citations(profile_id: str) -> tuple[str, ...]:
    """Return securitisation non-CTP fair-value-cap citations.

    Parameters
    ----------
    profile_id : str
        Active DRC rule profile identifier.

    Returns
    -------
    tuple[str, ...]
        Citation identifiers for fair-value-cap treatment.
    """

    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_SEC_NON_CTP_FAIR_VALUE_CAP_CITATIONS
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_SEC_NON_CTP_FAIR_VALUE_CAP_CITATIONS
    return _SEC_NON_CTP_FAIR_VALUE_CAP_CITATIONS


def sec_non_ctp_netting_citations(profile_id: str) -> tuple[str, ...]:
    """Return securitisation non-CTP netting citations.

    Parameters
    ----------
    profile_id : str
        Active DRC rule profile identifier.

    Returns
    -------
    tuple[str, ...]
        Citation identifiers for securitisation non-CTP netting.
    """

    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_SEC_NON_CTP_NETTING_CITATIONS
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_SEC_NON_CTP_NETTING_CITATIONS
    return _SEC_NON_CTP_NETTING_CITATIONS


def sec_non_ctp_batch_citations(profile_id: str) -> tuple[str, ...]:
    """Return securitisation non-CTP batch citations.

    Parameters
    ----------
    profile_id : str
        Active DRC rule profile identifier.

    Returns
    -------
    tuple[str, ...]
        Citation identifiers for securitisation non-CTP batch calculation.
    """

    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_SEC_NON_CTP_BATCH_CITATIONS
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_SEC_NON_CTP_BATCH_CITATIONS
    return _SEC_NON_CTP_BATCH_CITATIONS


def ctp_netting_citations(profile_id: str) -> tuple[str, ...]:
    """Return CTP netting citations.

    Parameters
    ----------
    profile_id : str
        Active DRC rule profile identifier.

    Returns
    -------
    tuple[str, ...]
        Citation identifiers for CTP netting.
    """

    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_CTP_NETTING_CITATIONS
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_CTP_NETTING_CITATIONS
    return _CTP_NETTING_CITATIONS


def ctp_batch_citations(profile_id: str) -> tuple[str, ...]:
    """Return CTP batch citations.

    Parameters
    ----------
    profile_id : str
        Active DRC rule profile identifier.

    Returns
    -------
    tuple[str, ...]
        Citation identifiers for CTP batch calculation.
    """

    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_CTP_BATCH_CITATIONS
    if profile_id == EU_CRR3_PROFILE_ID:
        return _EU_CRR3_CTP_BATCH_CITATIONS
    return _CTP_BATCH_CITATIONS


def _branch_citations(branches: tuple[BranchMetadata, ...]) -> set[str]:
    citation_ids: set[str] = set()
    for branch in branches:
        citation_ids.update(branch.citations)
    return citation_ids


__all__ = [
    "batch_api_citations",
    "collect_batch_citations",
    "ctp_batch_citations",
    "ctp_netting_citations",
    "nonsec_formula_citations",
    "nonsec_netting_citation",
    "sec_non_ctp_batch_citations",
    "sec_non_ctp_fair_value_cap_citations",
    "sec_non_ctp_gross_citations",
    "sec_non_ctp_netting_citations",
    "zero_nonsec_category_citation",
]
