"""
CVA scope, method selection, and carve-out policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from frtb_common import UnsupportedRegulatoryFeatureError

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
    """Resolve the effective CVA method from calculation context."""

    unsupported_flags: list[str] = []
    audit_metadata: list[tuple[str, str]] = [
        ("requested_method", context.method.value),
        ("sa_cva_approved", str(context.sa_cva_approved)),
    ]

    if context.materiality_threshold_elected:
        raise UnsupportedRegulatoryFeatureError(
            "Materiality-threshold 100% CCR alternative (MAR50.9) is unsupported "
            "in the delivered slice."
        )

    if context.method is CvaMethod.BA_CVA_FULL:
        audit_metadata.append(("resolved_method", CvaMethod.BA_CVA_FULL.value))
        return ScopeResolution(
            method=CvaMethod.BA_CVA_FULL,
            carve_out_netting_set_ids=context.carve_out_netting_set_ids,
            audit_metadata=tuple(audit_metadata),
            unsupported_flags=tuple(unsupported_flags),
        )

    if context.method is CvaMethod.SA_CVA:
        if not context.sa_cva_approved:
            raise CvaInputError(
                "SA-CVA requires sa_cva_approved=True in calculation context",
                field="sa_cva_approved",
            )
        audit_metadata.append(("resolved_method", CvaMethod.SA_CVA.value))
        return ScopeResolution(
            method=CvaMethod.SA_CVA,
            carve_out_netting_set_ids=context.carve_out_netting_set_ids,
            audit_metadata=tuple(audit_metadata),
            unsupported_flags=tuple(unsupported_flags),
        )

    if context.method is CvaMethod.MIXED_CARVE_OUT:
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
        audit_metadata.append(("resolved_method", CvaMethod.MIXED_CARVE_OUT.value))
        return ScopeResolution(
            method=CvaMethod.MIXED_CARVE_OUT,
            carve_out_netting_set_ids=context.carve_out_netting_set_ids,
            audit_metadata=tuple(audit_metadata),
            unsupported_flags=tuple(unsupported_flags),
        )

    if context.carve_out_netting_set_ids:
        _validate_carve_out_ids(context.carve_out_netting_set_ids, netting_sets)

    resolved_method = CvaMethod.BA_CVA_REDUCED
    audit_metadata.append(("resolved_method", resolved_method.value))
    return ScopeResolution(
        method=resolved_method,
        carve_out_netting_set_ids=context.carve_out_netting_set_ids,
        audit_metadata=tuple(audit_metadata),
        unsupported_flags=tuple(unsupported_flags),
    )


def validate_method_selection(
    context: CvaCalculationContext,
    *,
    netting_sets: tuple[CvaNettingSet, ...] = (),
) -> ScopeResolution:
    """Validate method selection and carve-out evidence before capital calculation."""

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
    """Split inputs into SA-CVA and BA-CVA carve-out subsets without double-counting hedges."""

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
