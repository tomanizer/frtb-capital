"""Counterparty and netting-set row validation for CVA inputs."""

from __future__ import annotations

from frtb_cva.data_models import CvaCounterparty, CvaNettingSet
from frtb_cva.validation.common import (
    VALID_EAD_SIGN_CONVENTIONS,
    CvaInputError,
    _finite_float,
    _require_text,
    _validate_lineage,
    normalise_ead_amount,
)


def validate_cva_counterparties(counterparties: object) -> tuple[CvaCounterparty, ...]:
    """Validate canonical counterparty records and return them as a tuple.

    Parameters
    ----------
    counterparties : object
        Iterable of :class:`~frtb_cva.data_models.CvaCounterparty` rows.

    Returns
    -------
    tuple[CvaCounterparty, ...]
        Validated counterparties with unique ``counterparty_id`` values.

    Raises
    ------
    CvaInputError
        If the input is not an iterable of counterparty dataclasses or validation fails.
    """

    if isinstance(counterparties, CvaCounterparty):
        raise CvaInputError("counterparties must be an iterable of CvaCounterparty objects")
    try:
        candidates: tuple[object, ...] = tuple(counterparties)  # type: ignore[arg-type]
    except TypeError as exc:
        raise CvaInputError(
            "counterparties must be an iterable of CvaCounterparty objects"
        ) from exc

    seen_ids: set[str] = set()
    validated: list[CvaCounterparty] = []
    for candidate in candidates:
        if not isinstance(candidate, CvaCounterparty):
            raise CvaInputError("counterparties must contain only CvaCounterparty objects")
        counterparty = candidate
        _validate_counterparty(counterparty, seen_ids)
        seen_ids.add(counterparty.counterparty_id)
        validated.append(counterparty)
    return tuple(validated)


def validate_cva_netting_sets(
    netting_sets: object,
    *,
    counterparties: tuple[CvaCounterparty, ...] | None = None,
) -> tuple[CvaNettingSet, ...]:
    """Validate canonical netting-set records and return them as a tuple.

    Parameters
    ----------
    netting_sets : object
        Iterable of :class:`~frtb_cva.data_models.CvaNettingSet` rows.
    counterparties : tuple[CvaCounterparty, ...] or None, optional
        When provided, each netting set must reference a known counterparty id.

    Returns
    -------
    tuple[CvaNettingSet, ...]
        Validated netting sets with unique ``netting_set_id`` values.

    Raises
    ------
    CvaInputError
        If rows are ill-typed, duplicated, or reference unknown counterparties.
    """

    if isinstance(netting_sets, CvaNettingSet):
        raise CvaInputError("netting_sets must be an iterable of CvaNettingSet objects")
    try:
        candidates: tuple[object, ...] = tuple(netting_sets)  # type: ignore[arg-type]
    except TypeError as exc:
        raise CvaInputError("netting_sets must be an iterable of CvaNettingSet objects") from exc

    counterparty_ids = (
        {counterparty.counterparty_id for counterparty in counterparties}
        if counterparties is not None
        else None
    )
    seen_ids: set[str] = set()
    validated: list[CvaNettingSet] = []
    for candidate in candidates:
        if not isinstance(candidate, CvaNettingSet):
            raise CvaInputError("netting_sets must contain only CvaNettingSet objects")
        netting_set = candidate
        _validate_netting_set(netting_set, seen_ids, counterparty_ids)
        seen_ids.add(netting_set.netting_set_id)
        validated.append(netting_set)
    return tuple(validated)


def _validate_counterparty(counterparty: CvaCounterparty, seen_ids: set[str]) -> None:
    record_id = _require_text(counterparty.counterparty_id, "counterparty_id")
    if record_id in seen_ids:
        raise CvaInputError(
            "duplicate counterparty id",
            field="counterparty_id",
            record_id=record_id,
        )
    _require_text(counterparty.source_row_id, "source_row_id", record_id)
    _require_text(counterparty.desk_id, "desk_id", record_id)
    _require_text(counterparty.legal_entity, "legal_entity", record_id)
    _require_text(counterparty.region, "region", record_id)
    _validate_lineage(counterparty.lineage, record_id)


def _validate_netting_set(
    netting_set: CvaNettingSet,
    seen_ids: set[str],
    counterparty_ids: set[str] | None,
) -> None:
    record_id = _require_text(netting_set.netting_set_id, "netting_set_id")
    if record_id in seen_ids:
        raise CvaInputError(
            "duplicate netting set id",
            field="netting_set_id",
            record_id=record_id,
        )
    _require_text(netting_set.counterparty_id, "counterparty_id", record_id)
    if counterparty_ids is not None and netting_set.counterparty_id not in counterparty_ids:
        raise CvaInputError(
            "netting set references unknown counterparty",
            field="counterparty_id",
            record_id=record_id,
        )
    _require_text(netting_set.source_row_id, "source_row_id", record_id)
    _require_text(netting_set.currency, "currency", record_id)
    _require_text(netting_set.sign_convention, "sign_convention", record_id)
    if netting_set.sign_convention not in VALID_EAD_SIGN_CONVENTIONS:
        raise CvaInputError(
            f"sign_convention must be one of {sorted(VALID_EAD_SIGN_CONVENTIONS)}",
            field="sign_convention",
            record_id=record_id,
        )
    normalise_ead_amount(
        netting_set.ead,
        source_sign_convention=netting_set.sign_convention,  # type: ignore[arg-type]
    )
    _finite_float(netting_set.effective_maturity, field="effective_maturity")
    if netting_set.effective_maturity < 0:
        raise CvaInputError(
            "effective maturity must be non-negative",
            field="effective_maturity",
            record_id=record_id,
        )
    discount_factor = _finite_float(netting_set.discount_factor, field="discount_factor")
    if discount_factor <= 0:
        raise CvaInputError(
            "discount factor must be positive",
            field="discount_factor",
            record_id=record_id,
        )
    if not isinstance(netting_set.uses_imm_ead, bool):
        raise CvaInputError(
            "uses_imm_ead must be a bool",
            field="uses_imm_ead",
            record_id=record_id,
        )
    if not isinstance(netting_set.carved_out_to_ba_cva, bool):
        raise CvaInputError(
            "carved_out_to_ba_cva must be a bool",
            field="carved_out_to_ba_cva",
            record_id=record_id,
        )
    if not isinstance(netting_set.discount_factor_explicit, bool):
        raise CvaInputError(
            "discount_factor_explicit must be a bool",
            field="discount_factor_explicit",
            record_id=record_id,
        )
    _validate_lineage(netting_set.lineage, record_id)


__all__ = [
    "validate_cva_counterparties",
    "validate_cva_netting_sets",
]
