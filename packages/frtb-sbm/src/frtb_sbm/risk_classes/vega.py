"""
Non-GIRR vega assembly onto shared SBM aggregation primitives.

Regulatory traceability:
    Basel MAR21.90-MAR21.95 — vega buckets, weights, and correlations.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from frtb_sbm._batch_lookup import (
    batch_optional_text_by_id as _batch_optional_text_by_id,
)
from frtb_sbm._batch_lookup import (
    batch_text_by_id as _batch_required_text_by_id,
)
from frtb_sbm._citations import merge_citation_ids as _merge_citation_ids
from frtb_sbm._text import require_text as _require_text
from frtb_sbm.aggregation import (
    IntraBucketScenarioSpec,
    aggregate_risk_class_with_scenarios,
    group_weighted_sensitivities_by_bucket,
    select_max_correlation_scenario,
)
from frtb_sbm.batch import SbmSensitivityBatch
from frtb_sbm.csr_nonsec_reference_data import CSR_OTHER_SECTOR_BUCKET
from frtb_sbm.csr_sec_nonctp_reference_data import CSR_SEC_OTHER_SECTOR_BUCKET
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
from frtb_sbm.equity_reference_data import EQUITY_OTHER_SECTOR_BUCKET
from frtb_sbm.reference_citation_routing import (
    profile_citation_id,
    profile_citation_ids,
    profile_scenario_citation_ids,
)
from frtb_sbm.risk_classes.csr_sec_nonctp import (
    build_csr_sec_nonctp_inter_bucket_correlation_map,
)
from frtb_sbm.risk_classes.vega_correlation_common import (
    _uses_absolute_weight_intra_bucket,
)
from frtb_sbm.risk_classes.vega_correlations import (
    build_non_girr_vega_inter_bucket_correlation_map,
    build_non_girr_vega_intra_bucket_correlation_matrix,
    non_girr_vega_intra_bucket_correlation,
)
from frtb_sbm.risk_classes.vega_errors import UnsupportedNonGirrVegaPathError
from frtb_sbm.risk_classes.vega_weighting import (
    weight_non_girr_vega_sensitivities,
    weight_non_girr_vega_sensitivity_batch,
)
from frtb_sbm.validation import SbmInputError

_NON_GIRR_VEGA_RISK_CLASSES = frozenset(
    {
        SbmRiskClass.FX,
        SbmRiskClass.EQUITY,
        SbmRiskClass.COMMODITY,
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_NONCTP,
        SbmRiskClass.CSR_SEC_CTP,
    }
)


def calculate_non_girr_vega_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate cited non-GIRR vega risk-class capital for a supported profile.
    Parameters
    ----------
    sensitivities, profile_id, pairwise_evidence_mode, pairwise_evidence_limit :
        See function signature for types and defaults.

    Returns
    -------
    RiskClassCapital
    """

    if not sensitivities:
        raise SbmInputError("sensitivities must not be empty", field="sensitivities")
    risk_classes = {item.risk_class for item in sensitivities}
    if len(risk_classes) != 1:
        raise UnsupportedNonGirrVegaPathError("non-GIRR vega requires homogeneous risk class")
    risk_class = next(iter(risk_classes))
    if risk_class not in _NON_GIRR_VEGA_RISK_CLASSES:
        raise UnsupportedNonGirrVegaPathError(
            f"non-GIRR vega does not support risk_class={risk_class.value}"
        )
    weighted = weight_non_girr_vega_sensitivities(
        sensitivities,
        profile_id=profile_id,
    )
    return aggregate_non_girr_vega_measure_capital(
        weighted,
        profile_id=profile_id,
        risk_class=risk_class,
        risk_factor_by_id=_text_by_id(sensitivities, "risk_factor"),
        qualifier_by_id=_optional_text_by_id(sensitivities, "qualifier"),
        option_tenor_by_id=_optional_text_by_id(sensitivities, "option_tenor"),
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def calculate_non_girr_vega_risk_class_capital_from_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate cited non-GIRR vega risk-class capital from a package-owned batch.
    Parameters
    ----------
    batch, profile_id, pairwise_evidence_mode, pairwise_evidence_limit :
        See function signature for types and defaults.

    Returns
    -------
    RiskClassCapital
    """

    if batch.row_count == 0:
        raise SbmInputError("batch must not be empty", field="batch")
    risk_class = batch.risk_class
    if risk_class not in _NON_GIRR_VEGA_RISK_CLASSES:
        raise UnsupportedNonGirrVegaPathError(
            f"non-GIRR vega does not support risk_class={risk_class.value}"
        )
    if batch.risk_measure is not SbmRiskMeasure.VEGA:
        raise UnsupportedNonGirrVegaPathError(
            f"non-GIRR vega does not support risk_measure={batch.risk_measure.value}"
        )
    weighted = weight_non_girr_vega_sensitivity_batch(
        batch,
        profile_id=profile_id,
    )
    return aggregate_non_girr_vega_measure_capital(
        weighted,
        profile_id=profile_id,
        risk_class=risk_class,
        risk_factor_by_id=_batch_required_text_by_id(batch, batch.risk_factors, "risk_factor"),
        qualifier_by_id=_batch_optional_text_by_id(batch, batch.qualifiers),
        option_tenor_by_id=_batch_required_text_by_id(batch, batch.option_tenors, "option_tenor"),
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def aggregate_non_girr_vega_measure_capital(
    weighted: tuple[WeightedSensitivity, ...],
    *,
    profile_id: str,
    risk_class: SbmRiskClass,
    risk_factor_by_id: Mapping[str, str],
    qualifier_by_id: Mapping[str, str],
    option_tenor_by_id: Mapping[str, str],
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Aggregate weighted non-GIRR vega sensitivities through shared primitives.
    Parameters
    ----------
    weighted, profile_id, risk_class, risk_factor_by_id, qualifier_by_id, option_tenor_by_id,
    pairwise_evidence_mode, pairwise_evidence_limit :
        See function signature for types and defaults.

    Returns
    -------
    RiskClassCapital
    """

    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return _aggregate_csr_sec_nonctp_vega_measure_capital(
            weighted,
            profile_id=profile_id,
            risk_factor_by_id=risk_factor_by_id,
            qualifier_by_id=qualifier_by_id,
            option_tenor_by_id=option_tenor_by_id,
            pairwise_evidence_mode=pairwise_evidence_mode,
            pairwise_evidence_limit=pairwise_evidence_limit,
        )

    grouped = group_weighted_sensitivities_by_bucket(weighted)
    intra_specs: list[IntraBucketScenarioSpec] = []
    for (_risk_class, _risk_measure, bucket_id), bucket_weighted in sorted(grouped.items()):
        absolute = _uses_absolute_weight_intra_bucket(risk_class, bucket_id)
        matrix = build_non_girr_vega_intra_bucket_correlation_matrix(
            bucket_weighted,
            profile_id=profile_id,
            risk_class=risk_class,
            bucket_id=bucket_id,
            risk_factor_by_id=risk_factor_by_id,
            qualifier_by_id=qualifier_by_id,
            option_tenor_by_id=option_tenor_by_id,
        )
        intra_specs.append(
            IntraBucketScenarioSpec(
                bucket_id=bucket_id,
                weighted_sensitivities=tuple(bucket_weighted),
                base_correlation_matrix=matrix,
                absolute_weight_intra=absolute,
                absolute_weight_citation_ids=_absolute_weight_citations(
                    profile_id,
                    risk_class,
                    bucket_id,
                )
                if absolute
                else (),
            )
        )

    bucket_ids = tuple(spec.bucket_id for spec in intra_specs)
    inter_bucket_correlations = build_non_girr_vega_inter_bucket_correlation_map(
        risk_class,
        bucket_ids,
        profile_id=profile_id,
    )
    return aggregate_risk_class_with_scenarios(
        tuple(intra_specs),
        inter_bucket_correlations,
        risk_class=risk_class,
        risk_measure=SbmRiskMeasure.VEGA,
        intra_bucket_citation_ids=_intra_bucket_citations(profile_id, risk_class),
        inter_bucket_citation_ids=_inter_bucket_citations(profile_id, risk_class),
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def _aggregate_csr_sec_nonctp_vega_measure_capital(
    weighted: tuple[WeightedSensitivity, ...],
    *,
    profile_id: str,
    risk_factor_by_id: Mapping[str, str],
    qualifier_by_id: Mapping[str, str],
    option_tenor_by_id: Mapping[str, str],
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    grouped = group_weighted_sensitivities_by_bucket(weighted)
    core_specs: list[IntraBucketScenarioSpec] = []
    other_spec: IntraBucketScenarioSpec | None = None
    for (_risk_class, _risk_measure, bucket_id), bucket_weighted in sorted(grouped.items()):
        matrix = build_non_girr_vega_intra_bucket_correlation_matrix(
            bucket_weighted,
            profile_id=profile_id,
            risk_class=SbmRiskClass.CSR_SEC_NONCTP,
            bucket_id=bucket_id,
            risk_factor_by_id=risk_factor_by_id,
            qualifier_by_id=qualifier_by_id,
            option_tenor_by_id=option_tenor_by_id,
        )
        spec = IntraBucketScenarioSpec(
            bucket_id=bucket_id,
            weighted_sensitivities=tuple(bucket_weighted),
            base_correlation_matrix=matrix,
            absolute_weight_intra=bucket_id == CSR_SEC_OTHER_SECTOR_BUCKET,
            absolute_weight_citation_ids=_absolute_weight_citations(
                profile_id,
                SbmRiskClass.CSR_SEC_NONCTP,
                bucket_id,
            )
            if bucket_id == CSR_SEC_OTHER_SECTOR_BUCKET
            else (),
        )
        if bucket_id == CSR_SEC_OTHER_SECTOR_BUCKET:
            other_spec = spec
        else:
            core_specs.append(spec)

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
                risk_measure=SbmRiskMeasure.VEGA,
                scenarios=(scenario,),
                apply_scenario_adjustment=True,
                intra_bucket_citation_ids=_intra_bucket_citations(
                    profile_id,
                    SbmRiskClass.CSR_SEC_NONCTP,
                ),
                inter_bucket_citation_ids=_inter_bucket_citations(
                    profile_id,
                    SbmRiskClass.CSR_SEC_NONCTP,
                ),
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
                risk_measure=SbmRiskMeasure.VEGA,
                scenarios=(scenario,),
                apply_scenario_adjustment=False,
                intra_bucket_citation_ids=_absolute_weight_citations(
                    profile_id,
                    SbmRiskClass.CSR_SEC_NONCTP,
                    other_spec.bucket_id,
                ),
                inter_bucket_citation_ids=_inter_bucket_citations(
                    profile_id,
                    SbmRiskClass.CSR_SEC_NONCTP,
                ),
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
                citation_ids=_scenario_citations(profile_id),
            )
        )

    selection = select_max_correlation_scenario(
        scenario_totals,
        risk_class=SbmRiskClass.CSR_SEC_NONCTP,
        risk_measure=SbmRiskMeasure.VEGA,
        citation_ids=(profile_citation_id(profile_id, "basel_mar21_7_scenario_selection"),),
    )
    return RiskClassCapital(
        risk_class=SbmRiskClass.CSR_SEC_NONCTP,
        risk_measure=SbmRiskMeasure.VEGA,
        selected_capital=selection.selected_capital,
        buckets=selected_buckets,
        citation_ids=_merge_citation_ids(
            _scenario_citations(profile_id),
            _intra_bucket_citations(profile_id, SbmRiskClass.CSR_SEC_NONCTP),
            _inter_bucket_citations(profile_id, SbmRiskClass.CSR_SEC_NONCTP),
        ),
        scenario_totals=selection.scenario_totals,
        selected_scenario=selection.selected_scenario,
        scenario_details=tuple(scenario_details),
        scenario_selection=selection.branch_metadata,
    )


def _scenario_citations(profile_id: str) -> tuple[str, ...]:
    return profile_scenario_citation_ids(profile_id)


def _vega_scope_citations(profile_id: str) -> tuple[str, ...]:
    return (
        profile_citation_id(profile_id, "basel_mar21_4_intra_bucket"),
        profile_citation_id(profile_id, "basel_mar21_94"),
    )


def _vega_inter_scope_citations(profile_id: str) -> tuple[str, ...]:
    return (
        profile_citation_id(profile_id, "basel_mar21_4_inter_bucket"),
        profile_citation_id(profile_id, "basel_mar21_95"),
    )


def _absolute_weight_citations(
    profile_id: str,
    risk_class: SbmRiskClass,
    bucket_id: str,
) -> tuple[str, ...]:
    if risk_class is SbmRiskClass.EQUITY and bucket_id == EQUITY_OTHER_SECTOR_BUCKET:
        return (profile_citation_id(profile_id, "basel_mar21_79"),)
    if risk_class is SbmRiskClass.CSR_NONSEC and bucket_id == CSR_OTHER_SECTOR_BUCKET:
        return (profile_citation_id(profile_id, "basel_mar21_56"),)
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP and bucket_id == CSR_SEC_OTHER_SECTOR_BUCKET:
        return (profile_citation_id(profile_id, "basel_mar21_68"),)
    return ()


def _intra_bucket_citations(profile_id: str, risk_class: SbmRiskClass) -> tuple[str, ...]:
    delta_citation_by_class = {
        SbmRiskClass.FX: ("basel_mar21_86",),
        SbmRiskClass.EQUITY: ("basel_mar21_78", "basel_mar21_79"),
        SbmRiskClass.COMMODITY: ("basel_mar21_83",),
        SbmRiskClass.CSR_NONSEC: ("basel_mar21_54", "basel_mar21_55", "basel_mar21_56"),
        SbmRiskClass.CSR_SEC_NONCTP: ("basel_mar21_67", "basel_mar21_68"),
        SbmRiskClass.CSR_SEC_CTP: ("basel_mar21_58",),
    }
    basel_ids = delta_citation_by_class.get(risk_class, ())
    return _merge_citation_ids(
        _vega_scope_citations(profile_id),
        profile_citation_ids(profile_id, basel_ids),
    )


def _inter_bucket_citations(profile_id: str, risk_class: SbmRiskClass) -> tuple[str, ...]:
    delta_citation_by_class = {
        SbmRiskClass.FX: ("basel_mar21_89",),
        SbmRiskClass.EQUITY: ("basel_mar21_80",),
        SbmRiskClass.COMMODITY: ("basel_mar21_85",),
        SbmRiskClass.CSR_NONSEC: ("basel_mar21_57",),
        SbmRiskClass.CSR_SEC_NONCTP: ("basel_mar21_70",),
        SbmRiskClass.CSR_SEC_CTP: ("basel_mar21_57",),
    }
    basel_ids = delta_citation_by_class.get(risk_class, ())
    return _merge_citation_ids(
        _vega_inter_scope_citations(profile_id),
        profile_citation_ids(profile_id, basel_ids),
    )


def _text_by_id(sensitivities: Sequence[SbmSensitivity], field: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for sensitivity in sensitivities:
        value = getattr(sensitivity, field)
        values[sensitivity.sensitivity_id] = _require_text(
            value,
            field,
            sensitivity.sensitivity_id,
        )
    return values


def _optional_text_by_id(sensitivities: Sequence[SbmSensitivity], field: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for sensitivity in sensitivities:
        value = getattr(sensitivity, field)
        if value is None:
            continue
        values[sensitivity.sensitivity_id] = _require_text(
            value,
            field,
            sensitivity.sensitivity_id,
        )
    return values


__all__ = [
    "aggregate_non_girr_vega_measure_capital",
    "build_non_girr_vega_inter_bucket_correlation_map",
    "build_non_girr_vega_intra_bucket_correlation_matrix",
    "calculate_non_girr_vega_risk_class_capital",
    "calculate_non_girr_vega_risk_class_capital_from_batch",
    "non_girr_vega_intra_bucket_correlation",
]
