"""
CVA scope, method selection, and carve-out policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_cva.data_models import CvaCalculationContext, CvaMethod, CvaNettingSet
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
            "Materiality-threshold 100% CCR alternative (MAR50.9) is unsupported in phase 1."
        )

    if context.method is CvaMethod.BA_CVA_FULL:
        unsupported_flags.append("BA_CVA_FULL")
        raise UnsupportedRegulatoryFeatureError(
            "Full BA-CVA with hedge recognition is unsupported in phase 1."
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
        unsupported_flags.append("MIXED_CARVE_OUT")
        raise UnsupportedRegulatoryFeatureError(
            "Mixed SA-CVA and BA-CVA carve-out assembly is unsupported in phase 1."
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


__all__ = [
    "ScopeResolution",
    "resolve_calculation_method",
    "validate_method_selection",
]
