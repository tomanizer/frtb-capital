"""
CSR securitisation non-CTP delta assembly onto shared SBM aggregation primitives.

Regulatory traceability:
    Basel MAR21.10 — tranche credit-spread delta risk factors.
    Basel MAR21.61-MAR21.70 — buckets, weights, correlations, other-sector rule.
    SBM-FUNC-015.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import numpy.typing as npt

from frtb_sbm.aggregation import (
    IntraBucketScenarioSpec,
    aggregate_risk_class_with_scenarios,
    group_weighted_sensitivities_by_bucket,
    select_max_correlation_scenario,
)
from frtb_sbm.batch import (
    SbmSensitivityBatch,
    build_csr_sec_nonctp_delta_batch_from_sensitivities,
)
from frtb_sbm.csr_sec_nonctp_reference_data import (
    CSR_SEC_OTHER_SECTOR_BUCKET,
    csr_sec_nonctp_delta_intra_bucket_correlation,
    csr_sec_nonctp_inter_bucket_correlation,
)
from frtb_sbm.data_models import (
    DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
    BucketCapital,
    RiskClassCapital,
    RiskClassScenarioDetail,
    SbmPairwiseEvidenceMode,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmScenarioLabel,
    SbmSensitivity,
    WeightedSensitivity,
)
from frtb_sbm.weighted_sensitivity import weight_csr_sec_nonctp_delta_sensitivity_batch

_MAR21_CSR_SEC_INTRA_CITATION = ("basel_mar21_4_intra_bucket", "basel_mar21_67")
_MAR21_CSR_SEC_OTHER_CITATION = ("basel_mar21_56", "basel_mar21_68")
_MAR21_CSR_SEC_INTER_CITATION = ("basel_mar21_4_inter_bucket", "basel_mar21_70")
_MAR21_SCENARIO_CITATION = (
    "basel_mar21_6_correlation_scenarios",
    "basel_mar21_7_scenario_selection",
)


def calculate_csr_sec_nonctp_delta_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate cited CSR securitisation non-CTP delta risk-class capital."""

    batch = build_csr_sec_nonctp_delta_batch_from_sensitivities(sensitivities)
    return calculate_csr_sec_nonctp_delta_risk_class_capital_from_batch(
        batch,
        profile_id=profile_id,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def calculate_csr_sec_nonctp_delta_risk_class_capital_from_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate cited CSR securitisation non-CTP delta capital from a batch."""

    from frtb_sbm.batch import _batch_text_by_id

    weighted = weight_csr_sec_nonctp_delta_sensitivity_batch(
        batch,
        profile_id=profile_id,
    )
    return aggregate_csr_sec_nonctp_delta_measure_capital(
        weighted,
        profile_id=profile_id,
        tranche_by_id=_batch_text_by_id(batch, batch.qualifiers, field="qualifier"),
        tenor_by_id=_batch_text_by_id(batch, batch.tenors, field="tenor"),
        risk_factor_by_id=_batch_text_by_id(batch, batch.risk_factors, field="risk_factor"),
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def aggregate_csr_sec_nonctp_delta_measure_capital(
    weighted: tuple[WeightedSensitivity, ...],
    *,
    profile_id: str,
    tranche_by_id: Mapping[str, str],
    tenor_by_id: Mapping[str, str],
    risk_factor_by_id: Mapping[str, str],
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Aggregate weighted CSR securitisation non-CTP delta sensitivities."""

    grouped = group_weighted_sensitivities_by_bucket(weighted)
    core_specs: list[IntraBucketScenarioSpec] = []
    other_spec: IntraBucketScenarioSpec | None = None
    for (_risk_class, _risk_measure, bucket_id), bucket_weighted in sorted(grouped.items()):
        matrix = build_csr_sec_nonctp_delta_intra_bucket_correlation_matrix(
            bucket_weighted,
            profile_id=profile_id,
            bucket_id=bucket_id,
            tranche_by_id=tranche_by_id,
            tenor_by_id=tenor_by_id,
            risk_factor_by_id=risk_factor_by_id,
        )
        spec = IntraBucketScenarioSpec(
            bucket_id=bucket_id,
            weighted_sensitivities=tuple(bucket_weighted),
            base_correlation_matrix=matrix,
            absolute_weight_intra=bucket_id == CSR_SEC_OTHER_SECTOR_BUCKET,
            absolute_weight_citation_ids=_MAR21_CSR_SEC_OTHER_CITATION
            if bucket_id == CSR_SEC_OTHER_SECTOR_BUCKET
            else (),
        )
        if bucket_id == CSR_SEC_OTHER_SECTOR_BUCKET:
            other_spec = spec
        else:
            core_specs.append(spec)

    if not core_specs and other_spec is None:
        raise ValueError("csr sec non-ctp aggregation requires at least one bucket")

    scenario_labels = (
        SbmScenarioLabel.LOW,
        SbmScenarioLabel.MEDIUM,
        SbmScenarioLabel.HIGH,
    )
    scenario_totals: dict[SbmScenarioLabel, float] = {}
    scenario_details: list[RiskClassScenarioDetail] = []
    selected_buckets: tuple[BucketCapital, ...] = ()
    for scenario in scenario_labels:
        core_capital = 0.0
        core_buckets: tuple[BucketCapital, ...] = ()
        core_details: tuple[RiskClassScenarioDetail, ...] = ()
        if core_specs:
            inter_map = build_csr_sec_nonctp_inter_bucket_correlation_map(
                tuple(spec.bucket_id for spec in core_specs),
                profile_id=profile_id,
            )
            core_result = aggregate_risk_class_with_scenarios(
                tuple(core_specs),
                inter_map,
                risk_class=SbmRiskClass.CSR_SEC_NONCTP,
                risk_measure=SbmRiskMeasure.DELTA,
                scenarios=(scenario,),
                apply_scenario_adjustment=True,
                intra_bucket_citation_ids=_MAR21_CSR_SEC_INTRA_CITATION,
                inter_bucket_citation_ids=_MAR21_CSR_SEC_INTER_CITATION,
                pairwise_evidence_mode=pairwise_evidence_mode,
                pairwise_evidence_limit=pairwise_evidence_limit,
            )
            core_capital = core_result.selected_capital
            core_buckets = core_result.buckets
            core_details = core_result.scenario_details
        other_capital = 0.0
        other_buckets: tuple[BucketCapital, ...] = ()
        other_details: tuple[RiskClassScenarioDetail, ...] = ()
        if other_spec is not None:
            other_result = aggregate_risk_class_with_scenarios(
                (other_spec,),
                {},
                risk_class=SbmRiskClass.CSR_SEC_NONCTP,
                risk_measure=SbmRiskMeasure.DELTA,
                scenarios=(scenario,),
                apply_scenario_adjustment=False,
                intra_bucket_citation_ids=_MAR21_CSR_SEC_OTHER_CITATION,
                inter_bucket_citation_ids=_MAR21_CSR_SEC_INTER_CITATION,
                pairwise_evidence_mode=pairwise_evidence_mode,
                pairwise_evidence_limit=pairwise_evidence_limit,
            )
            other_capital = other_result.selected_capital
            other_buckets = other_result.buckets
            other_details = other_result.scenario_details
        scenario_totals[scenario] = core_capital + other_capital
        if scenario is SbmScenarioLabel.MEDIUM:
            selected_buckets = core_buckets + other_buckets
        core_detail = core_details[0] if core_details else None
        other_detail = other_details[0] if other_details else None
        scenario_details.append(
            RiskClassScenarioDetail(
                scenario=scenario,
                capital=core_capital + other_capital,
                inter_bucket_correlations=(
                    (core_detail.inter_bucket_correlations if core_detail else ())
                    + (other_detail.inter_bucket_correlations if other_detail else ())
                ),
                alternative_sb_used=(
                    (core_detail.alternative_sb_used if core_detail else False)
                    or (other_detail.alternative_sb_used if other_detail else False)
                ),
                intra_buckets=(
                    (core_detail.intra_buckets if core_detail else ())
                    + (other_detail.intra_buckets if other_detail else ())
                ),
                citation_ids=_MAR21_SCENARIO_CITATION,
            )
        )

    selection = select_max_correlation_scenario(
        scenario_totals,
        risk_class=SbmRiskClass.CSR_SEC_NONCTP,
        risk_measure=SbmRiskMeasure.DELTA,
        citation_ids=("basel_mar21_7_scenario_selection",),
    )
    return RiskClassCapital(
        risk_class=SbmRiskClass.CSR_SEC_NONCTP,
        risk_measure=SbmRiskMeasure.DELTA,
        selected_capital=selection.selected_capital,
        buckets=selected_buckets,
        citation_ids=_MAR21_SCENARIO_CITATION + _MAR21_CSR_SEC_INTRA_CITATION,
        scenario_totals=selection.scenario_totals,
        selected_scenario=selection.selected_scenario,
        scenario_details=tuple(scenario_details),
        scenario_selection=selection.branch_metadata,
    )


def build_csr_sec_nonctp_delta_intra_bucket_correlation_matrix(
    ordered: Sequence[WeightedSensitivity],
    *,
    profile_id: str,
    bucket_id: str,
    tranche_by_id: Mapping[str, str],
    tenor_by_id: Mapping[str, str],
    risk_factor_by_id: Mapping[str, str],
) -> npt.NDArray[np.float64]:
    """Return the cited CSR securitisation non-CTP delta intra-bucket correlation matrix."""

    if bucket_id == CSR_SEC_OTHER_SECTOR_BUCKET:
        size = len(ordered)
        return np.eye(size, dtype=np.float64)

    size = len(ordered)
    matrix = np.eye(size, dtype=np.float64)
    for row_index, sensitivity_a in enumerate(ordered):
        for col_index in range(row_index + 1, size):
            sensitivity_b = ordered[col_index]
            correlation, _ = csr_sec_nonctp_delta_intra_bucket_correlation(
                profile_id,
                bucket_id=bucket_id,
                tranche_a=tranche_by_id[sensitivity_a.sensitivity_id],
                tranche_b=tranche_by_id[sensitivity_b.sensitivity_id],
                tenor_a=tenor_by_id[sensitivity_a.sensitivity_id],
                tenor_b=tenor_by_id[sensitivity_b.sensitivity_id],
                risk_factor_a=risk_factor_by_id[sensitivity_a.sensitivity_id],
                risk_factor_b=risk_factor_by_id[sensitivity_b.sensitivity_id],
            )
            matrix[row_index, col_index] = correlation
            matrix[col_index, row_index] = correlation
    return matrix


def build_csr_sec_nonctp_inter_bucket_correlation_map(
    bucket_ids: Sequence[str],
    *,
    profile_id: str,
) -> dict[tuple[str, str], float]:
    """Return cited CSR securitisation non-CTP inter-bucket correlations."""

    correlations: dict[tuple[str, str], float] = {}
    ordered_ids = tuple(sorted(bucket_ids))
    for left_index, bucket_a in enumerate(ordered_ids):
        for bucket_b in ordered_ids[left_index + 1 :]:
            gamma, _ = csr_sec_nonctp_inter_bucket_correlation(
                profile_id,
                bucket1=bucket_a,
                bucket2=bucket_b,
            )
            correlations[(bucket_a, bucket_b)] = gamma
    return correlations


__all__ = [
    "aggregate_csr_sec_nonctp_delta_measure_capital",
    "build_csr_sec_nonctp_delta_intra_bucket_correlation_matrix",
    "build_csr_sec_nonctp_inter_bucket_correlation_map",
    "calculate_csr_sec_nonctp_delta_risk_class_capital",
    "calculate_csr_sec_nonctp_delta_risk_class_capital_from_batch",
]
