"""
Commodity delta assembly onto shared SBM aggregation primitives.

Regulatory traceability:
    Basel MAR21.13 — commodity spot/forward delta risk factors and tenors.
    Basel MAR21.81-MAR21.85 — buckets, weights, correlations.
    SBM-FUNC-018.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import numpy.typing as npt

from frtb_sbm._batch_lookup import batch_text_by_id as _batch_text_by_id
from frtb_sbm.adapters.sensitivities import build_sbm_batch
from frtb_sbm.aggregation import (
    IntraBucketScenarioSpec,
    aggregate_risk_class_with_scenarios,
    group_weighted_sensitivities_by_bucket,
)
from frtb_sbm.batch import SbmSensitivityBatch
from frtb_sbm.commodity_reference_data import (
    _require_commodity_bucket_number,
    commodity_delta_intra_bucket_correlation,
)
from frtb_sbm.commodity_reference_data import (
    commodity_inter_bucket_correlation as commodity_inter_bucket_gamma,
)
from frtb_sbm.data_models import (
    DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
    RiskClassCapital,
    SbmPairwiseEvidenceMode,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    WeightedSensitivity,
)
from frtb_sbm.reference_citations_eu_crr3 import translate_basel_citation_ids_to_eu
from frtb_sbm.risk_classes.commodity_weighting import weight_commodity_delta_sensitivity_batch

_COMMODITY_SCENARIO_CITATION_IDS: dict[str, tuple[str, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21.value: (
        "basel_mar21_6_correlation_scenarios",
        "basel_mar21_7_scenario_selection",
    ),
    SbmRegulatoryProfile.US_NPR_2_0.value: ("us_npr_91_fr_14952_va7a_correlation_scenarios",),
    SbmRegulatoryProfile.EU_CRR3.value: translate_basel_citation_ids_to_eu(
        (
            "basel_mar21_6_correlation_scenarios",
            "basel_mar21_7_scenario_selection",
        )
    ),
}
_COMMODITY_INTRA_BRANCH_CITATION_IDS: dict[str, tuple[str, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21.value: ("basel_mar21_4_intra_bucket",),
    SbmRegulatoryProfile.US_NPR_2_0.value: ("us_npr_91_fr_14952_va7a_commodity_delta_intra",),
    SbmRegulatoryProfile.EU_CRR3.value: translate_basel_citation_ids_to_eu(
        ("basel_mar21_4_intra_bucket",)
    ),
}
_COMMODITY_INTER_BRANCH_CITATION_IDS: dict[str, tuple[str, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21.value: ("basel_mar21_4_inter_bucket",),
    SbmRegulatoryProfile.US_NPR_2_0.value: ("us_npr_91_fr_14952_va7a_commodity_delta_inter",),
    SbmRegulatoryProfile.EU_CRR3.value: translate_basel_citation_ids_to_eu(
        ("basel_mar21_4_inter_bucket",)
    ),
}


def calculate_commodity_delta_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate cited commodity delta risk-class capital for a supported profile.
    Parameters
    ----------
    sensitivities, profile_id, pairwise_evidence_mode, pairwise_evidence_limit :
        See function signature for types and defaults.

    Returns
    -------
    RiskClassCapital
    """

    batch = build_sbm_batch(sensitivities, SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA)
    return calculate_commodity_delta_risk_class_capital_from_batch(
        batch,
        profile_id=profile_id,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def calculate_commodity_delta_risk_class_capital_from_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate cited commodity delta risk-class capital from a package-owned batch.
    Parameters
    ----------
    batch, profile_id, pairwise_evidence_mode, pairwise_evidence_limit :
        See function signature for types and defaults.

    Returns
    -------
    RiskClassCapital
    """

    weighted = weight_commodity_delta_sensitivity_batch(
        batch,
        profile_id=profile_id,
    )
    return aggregate_commodity_delta_measure_capital(
        weighted,
        profile_id=profile_id,
        commodity_by_id=_batch_text_by_id(batch, batch.risk_factors, field="risk_factor"),
        tenor_by_id=_batch_text_by_id(batch, batch.tenors, field="tenor"),
        location_by_id=_batch_text_by_id(batch, batch.qualifiers, field="qualifier"),
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def aggregate_commodity_delta_measure_capital(
    weighted: tuple[WeightedSensitivity, ...],
    *,
    profile_id: str,
    commodity_by_id: Mapping[str, str],
    tenor_by_id: Mapping[str, str],
    location_by_id: Mapping[str, str],
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Aggregate weighted commodity delta sensitivities through shared bucket primitives.
    Parameters
    ----------
    weighted, profile_id, commodity_by_id, tenor_by_id, location_by_id, pairwise_evidence_mode,
    pairwise_evidence_limit :
        See function signature for types and defaults.

    Returns
    -------
    RiskClassCapital
    """

    grouped = group_weighted_sensitivities_by_bucket(weighted)
    intra_specs: list[IntraBucketScenarioSpec] = []
    for (_risk_class, _risk_measure, bucket_id), bucket_weighted in sorted(grouped.items()):
        matrix = build_commodity_delta_intra_bucket_correlation_matrix(
            bucket_weighted,
            profile_id=profile_id,
            bucket_id=bucket_id,
            commodity_by_id=commodity_by_id,
            tenor_by_id=tenor_by_id,
            location_by_id=location_by_id,
        )
        intra_specs.append(
            IntraBucketScenarioSpec(
                bucket_id=bucket_id,
                weighted_sensitivities=tuple(bucket_weighted),
                base_correlation_matrix=matrix,
                sb_correlation_floor=None,
            )
        )

    bucket_ids = tuple(spec.bucket_id for spec in intra_specs)
    inter_bucket_correlations = build_commodity_inter_bucket_correlation_map(
        bucket_ids,
        profile_id=profile_id,
    )
    return aggregate_risk_class_with_scenarios(
        tuple(intra_specs),
        inter_bucket_correlations,
        risk_class=SbmRiskClass.COMMODITY,
        risk_measure=SbmRiskMeasure.DELTA,
        citation_ids=commodity_scenario_citation_ids(profile_id),
        intra_bucket_citation_ids=commodity_intra_branch_citation_ids(profile_id),
        inter_bucket_citation_ids=commodity_inter_branch_citation_ids(profile_id),
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def commodity_scenario_citation_ids(profile_id: str) -> tuple[str, ...]:
    """Return commodity delta scenario-selection citation ids for a supported profile.

    Parameters
    ----------
    profile_id : str
        Regulatory profile id.

    Returns
    -------
    tuple[str, ...]
        Citation identifiers for low/medium/high scenario selection.
    """

    return _COMMODITY_SCENARIO_CITATION_IDS.get(
        profile_id,
        _COMMODITY_SCENARIO_CITATION_IDS["BASEL_MAR21"],
    )


def commodity_intra_branch_citation_ids(profile_id: str) -> tuple[str, ...]:
    """Return risk-class branch intra-bucket citation ids for commodity delta.

    Parameters
    ----------
    profile_id : str
        Regulatory profile identifier.

    Returns
    -------
    tuple[str, ...]
        Citation identifiers attached to the commodity delta risk-class branch.
    """

    return _COMMODITY_INTRA_BRANCH_CITATION_IDS.get(
        profile_id,
        _COMMODITY_INTRA_BRANCH_CITATION_IDS["BASEL_MAR21"],
    )


def commodity_inter_branch_citation_ids(profile_id: str) -> tuple[str, ...]:
    """Return risk-class branch inter-bucket citation ids for commodity delta.

    Parameters
    ----------
    profile_id : str
        Regulatory profile identifier.

    Returns
    -------
    tuple[str, ...]
        Citation identifiers attached to the commodity delta risk-class branch.
    """

    return _COMMODITY_INTER_BRANCH_CITATION_IDS.get(
        profile_id,
        _COMMODITY_INTER_BRANCH_CITATION_IDS["BASEL_MAR21"],
    )


def build_commodity_delta_intra_bucket_correlation_matrix(
    ordered: Sequence[WeightedSensitivity],
    *,
    profile_id: str,
    bucket_id: str,
    commodity_by_id: Mapping[str, str],
    tenor_by_id: Mapping[str, str],
    location_by_id: Mapping[str, str],
) -> npt.NDArray[np.float64]:
    """Return the cited commodity delta intra-bucket correlation matrix.
    Parameters
    ----------
    ordered, profile_id, bucket_id, commodity_by_id, tenor_by_id, location_by_id :
        See function signature for types and defaults.

    Returns
    -------
    npt.NDArray[np.float64]
    """

    size = len(ordered)
    matrix = np.eye(size, dtype=np.float64)
    for row_index, sensitivity_a in enumerate(ordered):
        for col_index in range(row_index + 1, size):
            sensitivity_b = ordered[col_index]
            correlation, _ = commodity_delta_intra_bucket_correlation(
                profile_id,
                bucket_id=bucket_id,
                commodity_a=commodity_by_id[sensitivity_a.sensitivity_id],
                commodity_b=commodity_by_id[sensitivity_b.sensitivity_id],
                tenor_a=tenor_by_id[sensitivity_a.sensitivity_id],
                tenor_b=tenor_by_id[sensitivity_b.sensitivity_id],
                location_a=location_by_id[sensitivity_a.sensitivity_id],
                location_b=location_by_id[sensitivity_b.sensitivity_id],
            )
            matrix[row_index, col_index] = correlation
            matrix[col_index, row_index] = correlation
    return matrix


def build_commodity_inter_bucket_correlation_map(
    bucket_ids: Sequence[str],
    *,
    profile_id: str,
) -> dict[tuple[str, str], float]:
    """Return cited commodity inter-bucket correlations for distinct bucket pairs.
    Parameters
    ----------
    bucket_ids : Sequence[str]
        See signature.
    profile_id : str
        See signature.

    Returns
    -------
    dict[tuple[str, str], float]
    """

    correlations: dict[tuple[str, str], float] = {}
    ordered_ids = tuple(sorted(bucket_ids, key=_require_commodity_bucket_number))
    for left_index, bucket_a in enumerate(ordered_ids):
        for bucket_b in ordered_ids[left_index + 1 :]:
            gamma, _ = commodity_inter_bucket_gamma(
                profile_id,
                bucket1=bucket_a,
                bucket2=bucket_b,
            )
            correlations[(bucket_a, bucket_b)] = gamma
    return correlations


__all__ = [
    "aggregate_commodity_delta_measure_capital",
    "build_commodity_delta_intra_bucket_correlation_matrix",
    "build_commodity_inter_bucket_correlation_map",
    "calculate_commodity_delta_risk_class_capital",
    "calculate_commodity_delta_risk_class_capital_from_batch",
    "commodity_inter_branch_citation_ids",
    "commodity_intra_branch_citation_ids",
    "commodity_scenario_citation_ids",
]
