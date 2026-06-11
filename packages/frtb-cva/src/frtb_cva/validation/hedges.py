"""Hedge row validation for CVA inputs."""

from __future__ import annotations

from frtb_cva.data_models import (
    BaCvaHedgeType,
    CvaHedge,
    HedgeEligibility,
    HedgeReferenceRelation,
    SaCvaHedgeInstrumentType,
    SaCvaHedgePurpose,
    SaCvaRiskClass,
)
from frtb_cva.validation.common import (
    CvaInputError,
    _finite_float,
    _require_text,
    _validate_lineage,
)


def validate_cva_hedges(hedges: object) -> tuple[CvaHedge, ...]:
    """Validate canonical hedge records and return them as a tuple.

    Parameters
    ----------
    hedges : object
        Iterable of :class:`~frtb_cva.data_models.CvaHedge` rows (may be empty).

    Returns
    -------
    tuple[CvaHedge, ...]
        Validated hedges with unique ``hedge_id`` values.

    Raises
    ------
    CvaInputError
        If rows are ill-typed, duplicated, or missing eligibility evidence.
    """

    if isinstance(hedges, CvaHedge):
        raise CvaInputError("hedges must be an iterable of CvaHedge objects")
    try:
        candidates: tuple[object, ...] = tuple(hedges)  # type: ignore[arg-type]
    except TypeError as exc:
        raise CvaInputError("hedges must be an iterable of CvaHedge objects") from exc

    seen_ids: set[str] = set()
    validated: list[CvaHedge] = []
    for candidate in candidates:
        if not isinstance(candidate, CvaHedge):
            raise CvaInputError("hedges must contain only CvaHedge objects")
        hedge = candidate
        _validate_hedge(hedge, seen_ids)
        seen_ids.add(hedge.hedge_id)
        validated.append(hedge)
    return tuple(validated)


def _validate_hedge(hedge: CvaHedge, seen_ids: set[str]) -> None:
    record_id = _require_text(hedge.hedge_id, "hedge_id")
    if record_id in seen_ids:
        raise CvaInputError("duplicate hedge id", field="hedge_id", record_id=record_id)
    _require_text(hedge.source_row_id, "source_row_id", record_id)
    _require_text(hedge.counterparty_id, "counterparty_id", record_id)
    _require_text(hedge.reference_region, "reference_region", record_id)
    if hedge.hedge_type is not None and not isinstance(hedge.hedge_type, BaCvaHedgeType):
        raise CvaInputError("invalid hedge type", field="hedge_type", record_id=record_id)
    if not isinstance(hedge.eligibility, HedgeEligibility):
        raise CvaInputError("invalid hedge eligibility", field="eligibility", record_id=record_id)
    if not isinstance(hedge.reference_relation, HedgeReferenceRelation):
        raise CvaInputError(
            "invalid hedge reference relation",
            field="reference_relation",
            record_id=record_id,
        )
    if hedge.sa_cva_risk_class is not None and not isinstance(
        hedge.sa_cva_risk_class,
        SaCvaRiskClass,
    ):
        raise CvaInputError(
            "invalid SA-CVA risk class assignment",
            field="sa_cva_risk_class",
            record_id=record_id,
        )
    if hedge.sa_cva_hedge_purpose is not None and not isinstance(
        hedge.sa_cva_hedge_purpose,
        SaCvaHedgePurpose,
    ):
        raise CvaInputError(
            "invalid SA-CVA hedge purpose",
            field="sa_cva_hedge_purpose",
            record_id=record_id,
        )
    if hedge.sa_cva_hedge_instrument_type is not None and not isinstance(
        hedge.sa_cva_hedge_instrument_type,
        SaCvaHedgeInstrumentType,
    ):
        raise CvaInputError(
            "invalid SA-CVA hedge instrument type",
            field="sa_cva_hedge_instrument_type",
            record_id=record_id,
        )
    if hedge.market_risk_ima_eligible is not None and not isinstance(
        hedge.market_risk_ima_eligible,
        bool,
    ):
        raise CvaInputError(
            "market_risk_ima_eligible must be a bool when supplied",
            field="market_risk_ima_eligible",
            record_id=record_id,
        )
    notional = _finite_float(hedge.notional, field="notional")
    if notional < 0:
        raise CvaInputError("notional must be non-negative", field="notional", record_id=record_id)
    _finite_float(hedge.remaining_maturity, field="remaining_maturity")
    _finite_float(hedge.discount_factor, field="discount_factor")
    if not isinstance(hedge.discount_factor_explicit, bool):
        raise CvaInputError(
            "discount_factor_explicit must be a bool",
            field="discount_factor_explicit",
            record_id=record_id,
        )
    if not isinstance(hedge.is_internal, bool):
        raise CvaInputError("is_internal must be a bool", field="is_internal", record_id=record_id)
    if hedge.eligibility is HedgeEligibility.ELIGIBLE:
        _require_text(hedge.eligibility_evidence_id, "eligibility_evidence_id", record_id)
    if hedge.eligibility is HedgeEligibility.INELIGIBLE:
        _require_text(hedge.rejection_reason, "rejection_reason", record_id)
    if hedge.eligibility is HedgeEligibility.EXCLUDED:
        _require_text(hedge.rejection_reason, "rejection_reason", record_id)
        _require_text(
            hedge.market_risk_ima_exclusion_reason,
            "market_risk_ima_exclusion_reason",
            record_id,
        )
    _validate_lineage(hedge.lineage, record_id)


__all__ = ["validate_cva_hedges"]
