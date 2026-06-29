"""Portfolio-level SBM batch dispatch.

Regulatory traceability:
    Basel MAR21.7 scenario selection is applied after per-path batch capital
    results are produced. This module owns portfolio dispatch only; risk-class
    capital math remains in ``frtb_sbm.capital`` and risk-class modules.
"""

from __future__ import annotations

from collections.abc import Sequence

from frtb_sbm.batch import (
    SbmSensitivityBatch,
    coerce_sbm_batch_sequence,
    concatenate_sbm_batches,
    input_hash_algorithm_for_sbm_batches,
    input_hash_for_sbm_batches,
)
from frtb_sbm.data_models import (
    RiskClassCapital,
    SbmBatchPathDiagnostic,
    SbmBatchPortfolioCalculation,
    SbmCalculationContext,
    SbmRiskClass,
    SbmRiskMeasure,
)
from frtb_sbm.regimes import get_sbm_rule_profile
from frtb_sbm.registry import SBM_BATCH_PATH_ORDER
from frtb_sbm.validation import (
    SbmInputError,
    ensure_sbm_risk_class_measure_supported,
    phase1_capital_supported_paths,
    validate_sbm_calculation_context,
)

_SBM_CAPITAL_PATH_ORDER = SBM_BATCH_PATH_ORDER


def calculate_sbm_portfolio_capital_from_batches(
    batches: object | None = None,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmBatchPortfolioCalculation:
    """Calculate portfolio-level SBM capital from package-owned columnar batches.

    Parameters
    ----------
    batches
        One or more homogeneous ``SbmSensitivityBatch`` objects.
    context
        Calculation context for the portfolio run.

    Returns
    -------
    SbmBatchPortfolioCalculation
    """

    if batches is None:
        raise SbmInputError("batches are required", field="batches")
    if context is None:
        raise SbmInputError("calculation context is required", field="context")
    if not isinstance(context, SbmCalculationContext):
        raise SbmInputError(
            "calculation context must be SbmCalculationContext",
            field="context",
        )

    from frtb_sbm.capital import _build_sbm_capital_result, _calculate_batch_risk_class_capital

    validated_batches = coerce_sbm_batch_sequence(batches)
    validate_sbm_calculation_context(context)
    rule_profile = get_sbm_rule_profile(context.profile_id)
    grouped = _group_batches_by_capital_path(validated_batches, profile_id=context.profile_id)

    risk_class_results: list[RiskClassCapital] = []
    diagnostics: list[SbmBatchPathDiagnostic] = []
    ordered_paths = _ordered_supported_batch_paths(
        tuple(grouped.keys()),
        profile_id=context.profile_id,
    )
    for path in ordered_paths:
        path_batches = tuple(grouped[path])
        batch = concatenate_sbm_batches(path_batches)
        risk_class_results.append(_calculate_batch_risk_class_capital(batch, context=context))
        diagnostics.append(
            SbmBatchPathDiagnostic(
                risk_class=path[0],
                risk_measure=path[1],
                input_count=batch.row_count,
                batch_count=len(path_batches),
                accepted_row_dataclasses_materialized=(batch.accepted_row_dataclasses_materialized),
            )
        )

    result = _build_sbm_capital_result(
        risk_class_results,
        rule_profile=rule_profile,
        context=context,
        input_hash=input_hash_for_sbm_batches(validated_batches),
        input_count=sum(batch.row_count for batch in validated_batches),
        input_hash_algorithm=input_hash_algorithm_for_sbm_batches(validated_batches),
    )
    return SbmBatchPortfolioCalculation(
        result=result,
        path_diagnostics=tuple(diagnostics),
        accepted_row_dataclasses_materialized=sum(
            item.accepted_row_dataclasses_materialized for item in diagnostics
        ),
    )


def _group_batches_by_capital_path(
    batches: Sequence[SbmSensitivityBatch],
    *,
    profile_id: str,
) -> dict[tuple[SbmRiskClass, SbmRiskMeasure], list[SbmSensitivityBatch]]:
    grouped: dict[tuple[SbmRiskClass, SbmRiskMeasure], list[SbmSensitivityBatch]] = {}
    for batch in batches:
        if batch.row_count == 0:
            raise SbmInputError("batch must not be empty", field="batch")
        risk_class = batch.risk_class
        risk_measure = batch.risk_measure
        ensure_sbm_risk_class_measure_supported(profile_id, risk_class, risk_measure)
        grouped.setdefault((risk_class, risk_measure), []).append(batch)
    return grouped


def _ordered_supported_batch_paths(
    present_paths: Sequence[tuple[SbmRiskClass, SbmRiskMeasure]],
    *,
    profile_id: str,
) -> tuple[tuple[SbmRiskClass, SbmRiskMeasure], ...]:
    supported = phase1_capital_supported_paths(profile_id)
    present = {path for path in present_paths if path in supported}
    ordered = tuple(path for path in _SBM_CAPITAL_PATH_ORDER if path in present)
    remaining = tuple(sorted(present - set(ordered), key=lambda p: (p[0].value, p[1].value)))
    return ordered + remaining


__all__ = [
    "calculate_sbm_portfolio_capital_from_batches",
]
