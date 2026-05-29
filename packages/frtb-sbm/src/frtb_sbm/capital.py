"""
Public SBM capital calculation for supported GIRR delta inputs.

Regulatory traceability:
    Basel MAR21.4-MAR21.7 — delta aggregation and scenario selection.
    U.S. NPR 2.0 section V.A.7.a steps three through six.
    SBM-WS-001, SBM-AGG-001, SBM-AGG-002.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import numpy.typing as npt
from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.aggregation import (
    aggregate_intra_bucket,
    aggregate_risk_class_with_scenarios,
    group_weighted_sensitivities_by_bucket,
)
from frtb_sbm.audit import (
    _input_hash_for_validated_sensitivities,
    validate_sbm_result_reconciliation,
)
from frtb_sbm.data_models import (
    RiskClassCapital,
    SbmCalculationContext,
    SbmCapitalResult,
    SbmReconciliationMetadata,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    WeightedSensitivity,
)
from frtb_sbm.reference_data import (
    GIRR_INTRA_BUCKET_CORRELATION_FLOOR,
    girr_delta_intra_bucket_correlation,
    girr_inter_bucket_correlation,
)
from frtb_sbm.regimes import get_sbm_rule_profile
from frtb_sbm.validation import SbmInputError, ensure_sbm_run_supported
from frtb_sbm.weighted_sensitivity import weight_girr_delta_sensitivities

_GIRR_DELTA_REQUIREMENT_IDS = (
    "SBM-WS-001",
    "SBM-AGG-001",
    "SBM-AGG-002",
    "SBM-AUDIT-001",
)


def calculate_sbm_capital(
    sensitivities: object | None = None,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate supported canonical-input SBM capital for the GIRR delta slice."""

    if sensitivities is None:
        raise SbmInputError("sensitivities are required", field="sensitivities")
    if context is None:
        raise SbmInputError("calculation context is required", field="context")
    if not isinstance(context, SbmCalculationContext):
        raise SbmInputError(
            "calculation context must be SbmCalculationContext",
            field="context",
        )

    validated = _coerce_sensitivities(sensitivities)
    rule_profile = get_sbm_rule_profile(context.profile_id)
    ensure_sbm_run_supported(context, validated)
    _ensure_girr_delta_only(validated)

    girr_capital = _calculate_girr_delta_risk_class_capital(
        validated,
        profile_id=rule_profile.profile_id,
        reporting_currency=context.reporting_currency,
    )
    citation_ids = _collect_citation_ids(girr_capital)
    result = SbmCapitalResult(
        total_capital=girr_capital.selected_capital,
        risk_classes=(girr_capital,),
        profile_id=rule_profile.profile_id,
        profile_hash=rule_profile.content_hash,
        input_hash=_input_hash_for_validated_sensitivities(validated),
        warnings=_profile_warnings(rule_profile.profile_id),
        reconciliation=SbmReconciliationMetadata(
            input_count=len(validated),
            rejected_input_count=0,
            requirement_ids=_GIRR_DELTA_REQUIREMENT_IDS,
            citation_ids=citation_ids,
        ),
    )
    validate_sbm_result_reconciliation(result)
    return result


def _calculate_girr_delta_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    reporting_currency: str,
) -> RiskClassCapital:
    weighted = weight_girr_delta_sensitivities(
        sensitivities,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
    )
    tenor_by_id = {item.sensitivity_id: item.tenor or "" for item in sensitivities}
    risk_factor_by_id = {item.sensitivity_id: item.risk_factor for item in sensitivities}
    grouped = group_weighted_sensitivities_by_bucket(weighted)

    intra_results = []
    for (_risk_class, _risk_measure, bucket_id), bucket_weighted in sorted(grouped.items()):
        matrix = _build_intra_bucket_correlation_matrix(
            bucket_weighted,
            profile_id=profile_id,
            tenor_by_id=tenor_by_id,
            risk_factor_by_id=risk_factor_by_id,
        )
        intra_results.append(
            aggregate_intra_bucket(
                bucket_id,
                bucket_weighted,
                matrix,
                risk_class=SbmRiskClass.GIRR,
                risk_measure=SbmRiskMeasure.DELTA,
                sb_correlation_floor=GIRR_INTRA_BUCKET_CORRELATION_FLOOR,
            )
        )

    bucket_ids = tuple(sorted({result.bucket_capital.bucket_id for result in intra_results}))
    inter_bucket_correlations = _build_inter_bucket_correlation_map(
        bucket_ids,
        profile_id=profile_id,
    )
    return aggregate_risk_class_with_scenarios(
        intra_results,
        inter_bucket_correlations,
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
    )


def _build_intra_bucket_correlation_matrix(
    ordered: Sequence[WeightedSensitivity],
    *,
    profile_id: str,
    tenor_by_id: Mapping[str, str],
    risk_factor_by_id: Mapping[str, str],
) -> npt.NDArray[np.float64]:
    size = len(ordered)
    matrix = np.eye(size, dtype=np.float64)
    for row_index, sensitivity_a in enumerate(ordered):
        for col_index in range(row_index, size):
            sensitivity_b = ordered[col_index]
            same_curve = (
                risk_factor_by_id[sensitivity_a.sensitivity_id]
                == risk_factor_by_id[sensitivity_b.sensitivity_id]
            )
            correlation, _ = girr_delta_intra_bucket_correlation(
                profile_id,
                tenor1=tenor_by_id[sensitivity_a.sensitivity_id],
                tenor2=tenor_by_id[sensitivity_b.sensitivity_id],
                same_curve=same_curve,
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


def _collect_citation_ids(risk_class_capital: RiskClassCapital) -> tuple[str, ...]:
    citation_ids: list[str] = []
    seen: set[str] = set()
    for citation_id in risk_class_capital.citation_ids:
        _append_citation(citation_ids, seen, citation_id)
    for bucket in risk_class_capital.buckets:
        for citation_id in bucket.citation_ids:
            _append_citation(citation_ids, seen, citation_id)
        for weighted in bucket.weighted_sensitivities:
            for citation_id in weighted.citation_ids:
                _append_citation(citation_ids, seen, citation_id)
    return tuple(citation_ids)


def _append_citation(citation_ids: list[str], seen: set[str], citation_id: str) -> None:
    if citation_id not in seen:
        citation_ids.append(citation_id)
        seen.add(citation_id)


def _ensure_girr_delta_only(sensitivities: Sequence[SbmSensitivity]) -> None:
    if not sensitivities:
        raise SbmInputError("sensitivities must not be empty", field="sensitivities")
    for sensitivity in sensitivities:
        if (
            sensitivity.risk_class is not SbmRiskClass.GIRR
            or sensitivity.risk_measure is not SbmRiskMeasure.DELTA
        ):
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm phase-1 capital supports only GIRR delta inputs; "
                f"received risk_class={sensitivity.risk_class.value}, "
                f"risk_measure={sensitivity.risk_measure.value}"
            )


def _coerce_sensitivities(sensitivities: object) -> tuple[SbmSensitivity, ...]:
    from frtb_sbm.validation import validate_sbm_sensitivities

    return validate_sbm_sensitivities(sensitivities)


def _profile_warnings(profile_id: str) -> tuple[str, ...]:
    return ()


__all__ = ["calculate_sbm_capital"]
