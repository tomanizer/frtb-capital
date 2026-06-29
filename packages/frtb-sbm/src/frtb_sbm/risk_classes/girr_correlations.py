"""GIRR aggregation and correlation helpers for delta and vega kernels."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import numpy.typing as npt
from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.aggregation import (
    IntraBucketScenarioSpec,
    aggregate_risk_class_with_scenarios,
    group_weighted_sensitivities_by_bucket,
)
from frtb_sbm.data_models import (
    DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
    RiskClassCapital,
    SbmPairwiseEvidenceMode,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    WeightedSensitivity,
)
from frtb_sbm.girr_reference_tables import (
    PROFILE_GIRR_DELTA_INTRA_BUCKET_CITATION_IDS,
    PROFILE_GIRR_DELTA_INTER_BUCKET_CITATION_IDS,
    PROFILE_GIRR_VEGA_INTRA_BUCKET_CITATION_IDS,
    PROFILE_GIRR_VEGA_INTER_BUCKET_CITATION_IDS,
)
from frtb_sbm.reference_data import (
    GIRR_INTRA_BUCKET_CORRELATION_FLOOR,
    girr_inter_bucket_correlation,
    girr_vega_intra_bucket_correlation,
)
from frtb_sbm.risk_classes.girr_delta_correlations import (
    _build_girr_delta_intra_bucket_correlation_matrix,
)

_MAR21_INTRA_BUCKET_CITATION = ("basel_mar21_4_intra_bucket",)
_MAR21_INTER_BUCKET_CITATION = ("basel_mar21_4_inter_bucket",)
_GIRR_DELTA_INTRA_CITATIONS = (*_MAR21_INTRA_BUCKET_CITATION, "basel_mar21_45_49")
_GIRR_DELTA_INTER_CITATIONS = (*_MAR21_INTER_BUCKET_CITATION, "basel_mar21_50")
_GIRR_VEGA_INTRA_CITATIONS = (*_MAR21_INTRA_BUCKET_CITATION, "basel_mar21_93")
_GIRR_VEGA_INTER_CITATIONS = (*_MAR21_INTER_BUCKET_CITATION, "basel_mar21_95", "basel_mar21_50")
_PROFILE_GIRR_DELTA_INTRA_CITATIONS = {
    SbmRegulatoryProfile.BASEL_MAR21.value: _GIRR_DELTA_INTRA_CITATIONS,
    SbmRegulatoryProfile.EU_CRR3.value: (
        "eu_crr3_art_325r_sbm_scope",
        PROFILE_GIRR_DELTA_INTRA_BUCKET_CITATION_IDS[SbmRegulatoryProfile.EU_CRR3],
    ),
    SbmRegulatoryProfile.PRA_UK_CRR.value: (
        "pra_uk_crr_art_325r_sbm_scope",
        PROFILE_GIRR_DELTA_INTRA_BUCKET_CITATION_IDS[SbmRegulatoryProfile.PRA_UK_CRR],
    ),
    SbmRegulatoryProfile.US_NPR_2_0.value: (
        "us_npr_91_fr_14952_va7a_sbm_scope",
        "us_npr_91_fr_14952_va7a_girr_intra",
    ),
}
_PROFILE_GIRR_DELTA_INTER_CITATIONS = {
    SbmRegulatoryProfile.BASEL_MAR21.value: _GIRR_DELTA_INTER_CITATIONS,
    SbmRegulatoryProfile.EU_CRR3.value: (
        "eu_crr3_art_325r_sbm_scope",
        PROFILE_GIRR_DELTA_INTER_BUCKET_CITATION_IDS[SbmRegulatoryProfile.EU_CRR3],
    ),
    SbmRegulatoryProfile.PRA_UK_CRR.value: (
        "pra_uk_crr_art_325r_sbm_scope",
        PROFILE_GIRR_DELTA_INTER_BUCKET_CITATION_IDS[SbmRegulatoryProfile.PRA_UK_CRR],
    ),
    SbmRegulatoryProfile.US_NPR_2_0.value: (
        "us_npr_91_fr_14952_va7a_sbm_scope",
        "us_npr_91_fr_14952_va7a_girr_inter",
    ),
}
_PROFILE_GIRR_DELTA_SCENARIO_CITATIONS = {
    SbmRegulatoryProfile.BASEL_MAR21.value: (
        "basel_mar21_6_correlation_scenarios",
        "basel_mar21_7_scenario_selection",
    ),
    SbmRegulatoryProfile.EU_CRR3.value: ("eu_crr3_art_325u_correlation_scenarios",),
    SbmRegulatoryProfile.PRA_UK_CRR.value: ("pra_uk_crr_art_325u_correlation_scenarios",),
    SbmRegulatoryProfile.US_NPR_2_0.value: ("us_npr_91_fr_14952_va7a_correlation_scenarios",),
}
_PROFILE_GIRR_VEGA_INTRA_CITATIONS = {
    SbmRegulatoryProfile.BASEL_MAR21.value: _GIRR_VEGA_INTRA_CITATIONS,
    SbmRegulatoryProfile.EU_CRR3.value: (
        "eu_crr3_art_325r_sbm_scope",
        PROFILE_GIRR_VEGA_INTRA_BUCKET_CITATION_IDS[SbmRegulatoryProfile.EU_CRR3],
    ),
    SbmRegulatoryProfile.PRA_UK_CRR.value: (
        "pra_uk_crr_art_325r_sbm_scope",
        PROFILE_GIRR_VEGA_INTRA_BUCKET_CITATION_IDS[SbmRegulatoryProfile.PRA_UK_CRR],
    ),
    SbmRegulatoryProfile.US_NPR_2_0.value: (
        "us_npr_91_fr_14952_va7a_sbm_scope",
        PROFILE_GIRR_VEGA_INTRA_BUCKET_CITATION_IDS[SbmRegulatoryProfile.US_NPR_2_0],
    ),
}
_PROFILE_GIRR_VEGA_INTER_CITATIONS = {
    SbmRegulatoryProfile.BASEL_MAR21.value: _GIRR_VEGA_INTER_CITATIONS,
    SbmRegulatoryProfile.EU_CRR3.value: (
        "eu_crr3_art_325r_sbm_scope",
        PROFILE_GIRR_VEGA_INTER_BUCKET_CITATION_IDS[SbmRegulatoryProfile.EU_CRR3],
        PROFILE_GIRR_DELTA_INTER_BUCKET_CITATION_IDS[SbmRegulatoryProfile.EU_CRR3],
    ),
    SbmRegulatoryProfile.PRA_UK_CRR.value: (
        "pra_uk_crr_art_325r_sbm_scope",
        PROFILE_GIRR_VEGA_INTER_BUCKET_CITATION_IDS[SbmRegulatoryProfile.PRA_UK_CRR],
        PROFILE_GIRR_DELTA_INTER_BUCKET_CITATION_IDS[SbmRegulatoryProfile.PRA_UK_CRR],
    ),
    SbmRegulatoryProfile.US_NPR_2_0.value: (
        "us_npr_91_fr_14952_va7a_sbm_scope",
        PROFILE_GIRR_VEGA_INTER_BUCKET_CITATION_IDS[SbmRegulatoryProfile.US_NPR_2_0],
        "us_npr_91_fr_14952_va7a_girr_inter",
    ),
}
_PROFILE_GIRR_VEGA_SCENARIO_CITATIONS = {
    SbmRegulatoryProfile.BASEL_MAR21.value: (
        "basel_mar21_6_correlation_scenarios",
        "basel_mar21_7_scenario_selection",
    ),
    SbmRegulatoryProfile.EU_CRR3.value: ("eu_crr3_art_325u_correlation_scenarios",),
    SbmRegulatoryProfile.PRA_UK_CRR.value: ("pra_uk_crr_art_325u_correlation_scenarios",),
    SbmRegulatoryProfile.US_NPR_2_0.value: ("us_npr_91_fr_14952_va7a_correlation_scenarios",),
}


def _aggregate_girr_measure_capital(
    weighted: tuple[WeightedSensitivity, ...],
    *,
    profile_id: str,
    risk_measure: SbmRiskMeasure,
    tenor_by_id: Mapping[str, str],
    risk_factor_by_id: Mapping[str, str] | None = None,
    option_tenor_by_id: Mapping[str, str] | None = None,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    grouped = group_weighted_sensitivities_by_bucket(weighted)

    intra_specs: list[IntraBucketScenarioSpec] = []
    for (_risk_class, _risk_measure, bucket_id), bucket_weighted in sorted(grouped.items()):
        if risk_measure is SbmRiskMeasure.DELTA:
            matrix = _build_girr_delta_intra_bucket_correlation_matrix(
                bucket_weighted,
                profile_id=profile_id,
                tenor_by_id=tenor_by_id,
                risk_factor_by_id=risk_factor_by_id or {},
            )
        else:
            matrix = _build_girr_vega_intra_bucket_correlation_matrix(
                bucket_weighted,
                profile_id=profile_id,
                option_tenor_by_id=option_tenor_by_id or {},
                tenor_by_id=tenor_by_id,
            )
        intra_specs.append(
            IntraBucketScenarioSpec(
                bucket_id=bucket_id,
                weighted_sensitivities=tuple(bucket_weighted),
                base_correlation_matrix=matrix,
                sb_correlation_floor=GIRR_INTRA_BUCKET_CORRELATION_FLOOR
                if risk_measure is SbmRiskMeasure.DELTA
                else None,
            )
        )

    bucket_ids = tuple(sorted(spec.bucket_id for spec in intra_specs))
    inter_bucket_correlations = _build_inter_bucket_correlation_map(
        bucket_ids,
        profile_id=profile_id,
    )
    return aggregate_risk_class_with_scenarios(
        tuple(intra_specs),
        inter_bucket_correlations,
        risk_class=SbmRiskClass.GIRR,
        risk_measure=risk_measure,
        citation_ids=(
            _girr_delta_scenario_citations(profile_id)
            if risk_measure is SbmRiskMeasure.DELTA
            else _girr_vega_scenario_citations(profile_id)
        ),
        intra_bucket_citation_ids=(
            _girr_delta_intra_citations(profile_id)
            if risk_measure is SbmRiskMeasure.DELTA
            else _girr_vega_intra_citations(profile_id)
        ),
        inter_bucket_citation_ids=(
            _girr_delta_inter_citations(profile_id)
            if risk_measure is SbmRiskMeasure.DELTA
            else _girr_vega_inter_citations(profile_id)
        ),
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def _girr_delta_scenario_citations(profile_id: str) -> tuple[str, ...]:
    try:
        return _PROFILE_GIRR_DELTA_SCENARIO_CITATIONS[profile_id]
    except KeyError as exc:
        raise UnsupportedRegulatoryFeatureError(
            f"GIRR delta scenario citations are unsupported for profile={profile_id}"
        ) from exc


def _girr_delta_intra_citations(profile_id: str) -> tuple[str, ...]:
    try:
        return _PROFILE_GIRR_DELTA_INTRA_CITATIONS[profile_id]
    except KeyError as exc:
        raise UnsupportedRegulatoryFeatureError(
            f"GIRR delta intra-bucket citations are unsupported for profile={profile_id}"
        ) from exc


def _girr_delta_inter_citations(profile_id: str) -> tuple[str, ...]:
    try:
        return _PROFILE_GIRR_DELTA_INTER_CITATIONS[profile_id]
    except KeyError as exc:
        raise UnsupportedRegulatoryFeatureError(
            f"GIRR delta inter-bucket citations are unsupported for profile={profile_id}"
        ) from exc


def _girr_vega_scenario_citations(profile_id: str) -> tuple[str, ...]:
    try:
        return _PROFILE_GIRR_VEGA_SCENARIO_CITATIONS[profile_id]
    except KeyError as exc:
        raise UnsupportedRegulatoryFeatureError(
            f"GIRR vega scenario citations are unsupported for profile={profile_id}"
        ) from exc


def _girr_vega_intra_citations(profile_id: str) -> tuple[str, ...]:
    try:
        return _PROFILE_GIRR_VEGA_INTRA_CITATIONS[profile_id]
    except KeyError as exc:
        raise UnsupportedRegulatoryFeatureError(
            f"GIRR vega intra-bucket citations are unsupported for profile={profile_id}"
        ) from exc


def _girr_vega_inter_citations(profile_id: str) -> tuple[str, ...]:
    try:
        return _PROFILE_GIRR_VEGA_INTER_CITATIONS[profile_id]
    except KeyError as exc:
        raise UnsupportedRegulatoryFeatureError(
            f"GIRR vega inter-bucket citations are unsupported for profile={profile_id}"
        ) from exc


def _build_girr_vega_intra_bucket_correlation_matrix(
    ordered: Sequence[WeightedSensitivity],
    *,
    profile_id: str,
    option_tenor_by_id: Mapping[str, str],
    tenor_by_id: Mapping[str, str],
) -> npt.NDArray[np.float64]:
    size = len(ordered)
    matrix = np.eye(size, dtype=np.float64)
    for row_index, sensitivity_a in enumerate(ordered):
        for col_index in range(row_index, size):
            sensitivity_b = ordered[col_index]
            correlation, _ = girr_vega_intra_bucket_correlation(
                profile_id,
                option_tenor1=option_tenor_by_id[sensitivity_a.sensitivity_id],
                option_tenor2=option_tenor_by_id[sensitivity_b.sensitivity_id],
                tenor1=tenor_by_id[sensitivity_a.sensitivity_id],
                tenor2=tenor_by_id[sensitivity_b.sensitivity_id],
            )
            matrix[row_index, col_index] = correlation
            matrix[col_index, row_index] = correlation
    return matrix


def _build_inter_bucket_correlation_map(
    bucket_ids: Sequence[str],
    *,
    profile_id: str,
) -> dict[tuple[str, str], float]:
    correlations: dict[tuple[str, str], float] = {}
    ordered_ids = tuple(sorted(bucket_ids))
    for left_index, bucket_a in enumerate(ordered_ids):
        for bucket_b in ordered_ids[left_index + 1 :]:
            gamma, _ = girr_inter_bucket_correlation(
                profile_id,
                bucket1=bucket_a,
                bucket2=bucket_b,
            )
            correlations[(bucket_a, bucket_b)] = gamma
    return correlations


__all__ = ["_aggregate_girr_measure_capital"]
