"""Top-level CVA batch capital result assembly."""

from __future__ import annotations

from frtb_cva._batch_contracts import (
    CvaBatchCapitalCalculation,
    CvaCounterpartyBatch,
    CvaHedgeBatch,
    CvaNettingSetBatch,
    SaCvaSensitivityBatch,
)
from frtb_cva._batch_method_outputs import _calculate_method_outputs
from frtb_cva._batch_utils import (
    _empty_counterparty_batch,
    _empty_hedge_batch,
    _empty_netting_set_batch,
)
from frtb_cva._batch_validation import _resolve_scope_for_batches
from frtb_cva._citations import collect_ba_citations as _collect_ba_citations
from frtb_cva._citations import merge_citations as _merge_citations
from frtb_cva._profile_warnings import profile_warnings as _profile_warnings
from frtb_cva.assembly.batch_payloads import input_hash_for_cva_batches
from frtb_cva.audit import validate_cva_result_reconciliation
from frtb_cva.data_models import (
    CvaCalculationContext,
    CvaCapitalResult,
)
from frtb_cva.regimes import get_cva_rule_profile
from frtb_cva.validation import validate_calculation_context


def calculate_cva_capital_from_batches(
    context: CvaCalculationContext,
    counterparties: CvaCounterpartyBatch | None = None,
    netting_sets: CvaNettingSetBatch | None = None,
    *,
    hedges: CvaHedgeBatch | None = None,
    sensitivities: SaCvaSensitivityBatch | None = None,
) -> CvaBatchCapitalCalculation:
    """Calculate supported CVA capital from package-owned columnar batches.

    Parameters
    ----------
    context : CvaCalculationContext
        Method, profile, and carve-out controls for the run.
    counterparties, netting_sets, hedges, sensitivities : optional
        Columnar CVA input batches required by the selected method.

    Returns
    -------
    CvaBatchCapitalCalculation
        Capital result plus counters for dataclass materialisation during the run.
    """

    validated_context = validate_calculation_context(context)
    counterparty_batch = counterparties or _empty_counterparty_batch()
    netting_set_batch = netting_sets or _empty_netting_set_batch()
    hedge_batch = hedges or _empty_hedge_batch()
    rule_profile = get_cva_rule_profile(validated_context.profile)
    scope = _resolve_scope_for_batches(validated_context, netting_set_batch)
    outputs = _calculate_method_outputs(
        validated_context,
        rule_profile.profile,
        scope.method,
        counterparty_batch,
        netting_set_batch,
        hedge_batch,
        sensitivities=sensitivities,
        carve_out_netting_set_ids=scope.carve_out_netting_set_ids,
    )

    citations: tuple[str, ...] = ()
    if outputs.ba_cva_full is not None:
        citations = _merge_citations(citations, outputs.ba_cva_full.citations)
    if outputs.ba_cva_reduced is not None:
        citations = _merge_citations(
            citations,
            _collect_ba_citations(
                outputs.ba_cva_reduced.citations,
                outputs.ba_cva_netting_set_lines,
            ),
        )
    if outputs.sa_cva_risk_class_capitals:
        citations = _merge_citations(
            citations,
            tuple(
                citation
                for item in outputs.sa_cva_risk_class_capitals
                for citation in item.citations
            ),
        )

    result = CvaCapitalResult(
        run_id=validated_context.run_id,
        calculation_date=validated_context.calculation_date,
        base_currency=validated_context.base_currency,
        profile_id=rule_profile.profile.value,
        profile_hash=rule_profile.content_hash,
        input_hash=input_hash_for_cva_batches(
            validated_context,
            counterparty_batch,
            netting_set_batch,
            hedges=hedge_batch,
            sensitivities=sensitivities,
        ),
        method=scope.method,
        total_cva_capital=outputs.total_cva_capital,
        ba_cva_reduced=outputs.ba_cva_reduced,
        ba_cva_full=outputs.ba_cva_full,
        ba_cva_counterparty_capitals=outputs.ba_cva_counterparty_capitals,
        ba_cva_netting_set_lines=outputs.ba_cva_netting_set_lines,
        sa_cva_risk_class_capitals=outputs.sa_cva_risk_class_capitals,
        method_components=outputs.method_components,
        citations=citations,
        warnings=_profile_warnings(rule_profile.profile.value, scope.method),
        unsupported_flags=scope.unsupported_flags,
        audit_metadata=scope.audit_metadata,
    )
    validate_cva_result_reconciliation(result)
    return CvaBatchCapitalCalculation(result=result)


__all__ = ["calculate_cva_capital_from_batches"]
