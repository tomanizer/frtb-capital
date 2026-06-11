"""Context hashing and validation for securitisation non-CTP DRC."""

from __future__ import annotations

from collections.abc import Iterable

from frtb_drc._hashing import hash_payload
from frtb_drc._validation_utils import require_text
from frtb_drc.data_models import DrcCalculationContext, DrcPosition, DrcRiskClass
from frtb_drc.fair_value_cap import (
    fair_value_cap_hash_payload,
    validate_fair_value_cap_evidence,
)
from frtb_drc.risk_weight_evidence import (
    effective_risk_weights,
    risk_weight_evidence_hash_payload,
)
from frtb_drc.validation import DrcInputError


def securitisation_non_ctp_context_input_hash(
    input_hash: str,
    *,
    positions: Iterable[DrcPosition],
    context: DrcCalculationContext,
) -> str:
    """Include securitisation non-CTP context overlays in the input hash.

    Parameters
    ----------
    input_hash : str
        Precomputed input digest before FX lineage.
    positions : Iterable[DrcPosition]
        Canonical DRC position records.
    context : DrcCalculationContext
        Calculation context including profile, FX, and run metadata.

    Returns
    -------
    str
        Input hash including risk-weight, fair-value-cap, and offset-group evidence.
    """

    records = tuple(
        position
        for position in positions
        if DrcRiskClass(position.risk_class) == DrcRiskClass.SECURITISATION_NON_CTP
    )
    if not records:
        return input_hash
    position_ids = tuple(sorted(position.position_id for position in records))
    weights = effective_risk_weights(
        context,
        risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
    )
    payload = {
        "input_hash": input_hash,
        "securitisation_non_ctp_risk_weights": {
            position_id: weights[position_id] for position_id in position_ids
        },
        "securitisation_non_ctp_risk_weight_evidence": risk_weight_evidence_hash_payload(
            position_ids,
            context,
            risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
        ),
        "securitisation_non_ctp_fair_value_cap_evidence": fair_value_cap_hash_payload(
            position_ids,
            context,
        ),
        "securitisation_non_ctp_offset_groups": {
            position_id: context.securitisation_non_ctp_offset_groups[position_id]
            for position_id in position_ids
            if position_id in context.securitisation_non_ctp_offset_groups
        },
    }
    return hash_payload(payload)


def validate_securitisation_non_ctp_context(context: DrcCalculationContext) -> None:
    """Validate securitisation non-CTP context maps without requiring positions.

    Parameters
    ----------
    context : DrcCalculationContext
        Calculation context including profile, FX, and run metadata.
    """

    effective_risk_weights(context, risk_class=DrcRiskClass.SECURITISATION_NON_CTP)
    validate_fair_value_cap_evidence(
        context.securitisation_non_ctp_fair_value_cap_evidence,
        context=context,
    )
    for position_id, offset_group in context.securitisation_non_ctp_offset_groups.items():
        require_text(position_id, "securitisation_non_ctp_offset_groups position_id")
        require_text(
            offset_group,
            f"securitisation_non_ctp_offset_groups[{position_id!r}]",
        )


def validate_securitisation_non_ctp_context_for_positions(
    positions: tuple[DrcPosition, ...],
    *,
    context: DrcCalculationContext,
) -> None:
    """Validate securitisation non-CTP context maps against supplied positions.

    Parameters
    ----------
    positions : tuple[DrcPosition, ...]
        Validated securitisation non-CTP positions in the run.
    context : DrcCalculationContext
        Calculation context containing risk weights, fair-value-cap evidence,
        and optional offset groups.
    """

    validate_securitisation_non_ctp_context(context)
    risk_weights = effective_risk_weights(
        context,
        risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
    )
    position_ids = {position.position_id for position in positions}
    missing_risk_weights = sorted(position_ids - set(risk_weights))
    if missing_risk_weights:
        raise DrcInputError(
            "context.securitisation_non_ctp_risk_weights is required for "
            "securitisation non-CTP positions: " + ", ".join(missing_risk_weights)
        )
    unused_risk_weights = sorted(set(risk_weights) - position_ids)
    if unused_risk_weights:
        raise DrcInputError(
            "context.securitisation_non_ctp_risk_weights contains unused "
            "securitisation non-CTP position ids: " + ", ".join(unused_risk_weights)
        )
    unused_cap_evidence = sorted(
        set(context.securitisation_non_ctp_fair_value_cap_evidence) - position_ids
    )
    if unused_cap_evidence:
        raise DrcInputError(
            "context.securitisation_non_ctp_fair_value_cap_evidence contains unused "
            "securitisation non-CTP position ids: " + ", ".join(unused_cap_evidence)
        )
    unused_offset_groups = sorted(set(context.securitisation_non_ctp_offset_groups) - position_ids)
    if unused_offset_groups:
        raise DrcInputError(
            "context.securitisation_non_ctp_offset_groups contains unused "
            "securitisation non-CTP position ids: " + ", ".join(unused_offset_groups)
        )


__all__ = [
    "securitisation_non_ctp_context_input_hash",
    "validate_securitisation_non_ctp_context",
    "validate_securitisation_non_ctp_context_for_positions",
]
