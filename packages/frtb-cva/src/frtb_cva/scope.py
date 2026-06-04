"""
CVA scope, method selection, and carve-out policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_cva._unsupported import MAR50_9_UNSUPPORTED_MESSAGE
from frtb_cva.data_models import (
    CvaCalculationContext,
    CvaCounterparty,
    CvaHedge,
    CvaMethod,
    CvaNettingSet,
)
from frtb_cva.validation import CvaInputError


@dataclass(frozen=True)
class ScopeResolution:
    """Resolved CVA method and carve-out routing metadata."""

    method: CvaMethod
    carve_out_netting_set_ids: tuple[str, ...]
    audit_metadata: tuple[tuple[str, str], ...]
    unsupported_flags: tuple[str, ...]


def resolve_calculation_method(
    context: CvaCalculationContext,
    *,
    netting_sets: tuple[CvaNettingSet, ...] = (),
) -> ScopeResolution:
    """Resolve the effective CVA method from calculation context.

    Parameters
    ----------
    context :
        Calculation context carrying profile, currency, and method metadata.

    netting_sets, optional :
        Input for ``resolve_calculation_method`` used in the CVA capital path.

    Returns
    -------
    ScopeResolution
        Result of ``resolve_calculation_method`` for audit and downstream aggregation."""

    unsupported_flags: list[str] = []
    audit_metadata: list[tuple[str, str]] = [
        ("requested_method", context.method.value),
        ("sa_cva_approved", str(context.sa_cva_approved)),
    ]

    if context.materiality_threshold_elected:
        raise UnsupportedRegulatoryFeatureError(MAR50_9_UNSUPPORTED_MESSAGE)

    if context.method is CvaMethod.BA_CVA_FULL:
        return _resolved_scope(context, CvaMethod.BA_CVA_FULL, audit_metadata, unsupported_flags)

    if context.method is CvaMethod.SA_CVA:
        if not context.sa_cva_approved:
            raise CvaInputError(
                "SA-CVA requires sa_cva_approved=True in calculation context",
                field="sa_cva_approved",
            )
        return _resolved_scope(context, CvaMethod.SA_CVA, audit_metadata, unsupported_flags)

    if context.method is CvaMethod.MIXED_CARVE_OUT:
        _validate_mixed_carve_out_context(context, netting_sets)
        return _resolved_scope(
            context,
            CvaMethod.MIXED_CARVE_OUT,
            audit_metadata,
            unsupported_flags,
        )

    if context.carve_out_netting_set_ids:
        _validate_carve_out_ids(context.carve_out_netting_set_ids, netting_sets)

    return _resolved_scope(context, CvaMethod.BA_CVA_REDUCED, audit_metadata, unsupported_flags)


def _resolved_scope(
    context: CvaCalculationContext,
    resolved_method: CvaMethod,
    audit_metadata: list[tuple[str, str]],
    unsupported_flags: list[str],
) -> ScopeResolution:
    audit_metadata.append(("resolved_method", resolved_method.value))
    return ScopeResolution(
        method=resolved_method,
        carve_out_netting_set_ids=context.carve_out_netting_set_ids,
        audit_metadata=tuple(audit_metadata),
        unsupported_flags=tuple(unsupported_flags),
    )


def _validate_mixed_carve_out_context(
    context: CvaCalculationContext,
    netting_sets: tuple[CvaNettingSet, ...],
) -> None:
    if not context.sa_cva_approved:
        raise CvaInputError(
            "mixed carve-out requires sa_cva_approved=True in calculation context",
            field="sa_cva_approved",
        )
    if not context.carve_out_netting_set_ids:
        raise CvaInputError(
            "mixed carve-out requires carve_out_netting_set_ids",
            field="carve_out_netting_set_ids",
        )
    _validate_carve_out_ids(context.carve_out_netting_set_ids, netting_sets)
    _validate_carve_out_evidence(context.carve_out_netting_set_ids, netting_sets)


def validate_method_selection(
    context: CvaCalculationContext,
    *,
    netting_sets: tuple[CvaNettingSet, ...] = (),
) -> ScopeResolution:
    """Validate method selection and carve-out evidence before capital calculation.

    Parameters
    ----------
    context :
        Calculation context carrying profile, currency, and method metadata.

    netting_sets, optional :
        Input for ``validate_method_selection`` used in the CVA capital path.

    Returns
    -------
    ScopeResolution
        Result of ``validate_method_selection`` for audit and downstream aggregation."""

    return resolve_calculation_method(context, netting_sets=netting_sets)


def _validate_carve_out_ids(
    carve_out_ids: tuple[str, ...],
    netting_sets: tuple[CvaNettingSet, ...],
) -> None:
    known_ids = {netting_set.netting_set_id for netting_set in netting_sets}
    for netting_set_id in carve_out_ids:
        if netting_set_id not in known_ids:
            raise CvaInputError(
                f"carve-out netting set {netting_set_id!r} is missing from inputs",
                field="carve_out_netting_set_ids",
                record_id=netting_set_id,
            )


def _validate_carve_out_evidence(
    carve_out_ids: tuple[str, ...],
    netting_sets: tuple[CvaNettingSet, ...],
) -> None:
    carve_out_set = set(carve_out_ids)
    for netting_set in netting_sets:
        if netting_set.netting_set_id in carve_out_set and not netting_set.carved_out_to_ba_cva:
            raise CvaInputError(
                "carved-out netting set must set carved_out_to_ba_cva=True",
                field="carved_out_to_ba_cva",
                record_id=netting_set.netting_set_id,
            )
        if netting_set.carved_out_to_ba_cva and netting_set.netting_set_id not in carve_out_set:
            raise CvaInputError(
                "carved_out_to_ba_cva netting set must appear in carve_out_netting_set_ids",
                field="carve_out_netting_set_ids",
                record_id=netting_set.netting_set_id,
            )


def partition_mixed_method_inputs(
    counterparties: tuple[CvaCounterparty, ...],
    netting_sets: tuple[CvaNettingSet, ...],
    hedges: tuple[CvaHedge, ...],
    *,
    carve_out_netting_set_ids: tuple[str, ...],
) -> tuple[
    tuple[CvaCounterparty, ...],
    tuple[CvaNettingSet, ...],
    tuple[CvaHedge, ...],
    tuple[CvaCounterparty, ...],
    tuple[CvaNettingSet, ...],
    tuple[CvaHedge, ...],
]:
    """Split inputs into SA-CVA and BA-CVA carve-out subsets without double-counting hedges.

    Parameters
    ----------
    counterparties :
        Input for ``partition_mixed_method_inputs`` used in the CVA capital path.

    netting_sets :
        Input for ``partition_mixed_method_inputs`` used in the CVA capital path.

    hedges :
        Declared BA-CVA or SA-CVA hedge records assessed for eligibility.

    carve_out_netting_set_ids :
        Stable identifiers for carve out netting set recorded on results.

    Returns
    -------
    tuple
        Six tuples from ``partition_mixed_method_inputs``: BA and SA
        counterparties, netting sets, and hedges for audit and aggregation.
    """

    carve_out_set = set(carve_out_netting_set_ids)
    ba_netting_sets = tuple(
        sorted(
            (ns for ns in netting_sets if ns.netting_set_id in carve_out_set),
            key=lambda item: item.netting_set_id,
        )
    )
    ba_counterparty_ids = {ns.counterparty_id for ns in ba_netting_sets}
    ba_counterparties = tuple(
        sorted(
            (cp for cp in counterparties if cp.counterparty_id in ba_counterparty_ids),
            key=lambda item: item.counterparty_id,
        )
    )
    ba_hedges = tuple(
        sorted(
            (hedge for hedge in hedges if hedge.counterparty_id in ba_counterparty_ids),
            key=lambda item: item.hedge_id,
        )
    )
    sa_hedges = tuple(
        sorted(
            (hedge for hedge in hedges if hedge.counterparty_id not in ba_counterparty_ids),
            key=lambda item: item.hedge_id,
        )
    )
    return ba_counterparties, ba_netting_sets, ba_hedges, (), (), sa_hedges


__all__ = [
    "ScopeResolution",
    "partition_mixed_method_inputs",
    "resolve_calculation_method",
    "validate_method_selection",
]
