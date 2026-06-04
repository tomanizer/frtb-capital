"""Deterministic validation and sign normalisation for canonical CVA inputs.

This module guards public CVA entrypoints: it validates dataclass rows, enforces
unique identifiers, normalises exposure and sensitivity signs, and raises
:class:`UnsupportedRegulatoryFeatureError` for unimplemented MAR50.9 elections.
"""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Literal

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_cva._unsupported import MAR50_9_UNSUPPORTED_MESSAGE
from frtb_cva.data_models import (
    BaCvaHedgeType,
    CvaCalculationContext,
    CvaCounterparty,
    CvaHedge,
    CvaMethod,
    CvaNettingSet,
    CvaRegulatoryProfile,
    CvaSector,
    CvaSourceLineage,
    HedgeEligibility,
    HedgeReferenceRelation,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
)

AmountSignConvention = Literal["positive_loss", "signed_absolute"]
EADSignConvention = Literal["non_negative", "signed_absolute"]


class EadSignConvention(StrEnum):
    """Supported exposure-at-default sign conventions for netting-set inputs."""

    NON_NEGATIVE = "non_negative"
    SIGNED_ABSOLUTE = "signed_absolute"


class AmountSignConventionEnum(StrEnum):
    """Supported sensitivity amount sign conventions for SA-CVA inputs."""

    POSITIVE_LOSS = "positive_loss"
    SIGNED_ABSOLUTE = "signed_absolute"


VALID_EAD_SIGN_CONVENTIONS: frozenset[str] = frozenset(EadSignConvention)
VALID_AMOUNT_SIGN_CONVENTIONS: frozenset[str] = frozenset(AmountSignConventionEnum)


class CvaInputError(ValueError):
    """Raised when canonical CVA inputs fail deterministic validation."""

    def __init__(self, message: str, *, field: str = "", record_id: str = "") -> None:
        self.field = field
        self.record_id = record_id
        prefix = f"record {record_id}: " if record_id else ""
        suffix = f" [{field}]" if field else ""
        super().__init__(f"{prefix}{message}{suffix}")


def normalise_ead_amount(
    value: float,
    *,
    source_sign_convention: EADSignConvention = "non_negative",
) -> float:
    """Return a finite non-negative exposure-at-default amount.

    Parameters
    ----------
    value : float
        Raw EAD amount from a netting set or adapter row.
    source_sign_convention : EADSignConvention, optional
        ``non_negative`` rejects negative values; ``signed_absolute`` takes the absolute value.

    Returns
    -------
    float
        Finite, non-negative EAD stored on canonical netting-set records.

    Raises
    ------
    CvaInputError
        If the value is non-finite or negative under ``non_negative``.
    """

    if source_sign_convention not in {"non_negative", "signed_absolute"}:
        raise CvaInputError(
            "source_sign_convention must be 'non_negative' or 'signed_absolute'",
            field="source_sign_convention",
        )
    amount = _finite_float(value, field="ead")
    if amount < 0:
        if source_sign_convention == "signed_absolute":
            return abs(amount)
        raise CvaInputError("EAD must be non-negative", field="ead")
    return amount


def normalise_sensitivity_amount(
    value: float,
    *,
    source_sign_convention: AmountSignConvention = "positive_loss",
) -> float:
    """Return a finite sensitivity amount under the positive-loss convention.

    Parameters
    ----------
    value : float
        Raw sensitivity amount from a row or adapter.
    source_sign_convention : AmountSignConvention, optional
        ``positive_loss`` requires a finite numeric value; ``signed_absolute`` allows negatives.

    Returns
    -------
    float
        Finite sensitivity amount stored on canonical SA-CVA records.

    Raises
    ------
    CvaInputError
        If the value is non-finite or the sign convention token is unknown.
    """

    if source_sign_convention not in {"positive_loss", "signed_absolute"}:
        raise CvaInputError(
            "source_sign_convention must be 'positive_loss' or 'signed_absolute'",
            field="source_sign_convention",
        )
    return _finite_float(value, field="amount")


normalise_cva_amount = normalise_sensitivity_amount


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


def validate_sa_cva_sensitivities(
    sensitivities: object,
) -> tuple[SaCvaSensitivity, ...]:
    """Validate canonical SA-CVA sensitivity records and return them as a tuple.

    Parameters
    ----------
    sensitivities : object
        Iterable of :class:`~frtb_cva.data_models.SaCvaSensitivity` rows.

    Returns
    -------
    tuple[SaCvaSensitivity, ...]
        Validated sensitivities with unique ``sensitivity_id`` values.

    Raises
    ------
    CvaInputError
        If rows are ill-typed, duplicated, or violate SA-CVA field requirements.
    """

    if isinstance(sensitivities, SaCvaSensitivity):
        raise CvaInputError("sensitivities must be an iterable of SaCvaSensitivity objects")
    try:
        candidates: tuple[object, ...] = tuple(sensitivities)  # type: ignore[arg-type]
    except TypeError as exc:
        raise CvaInputError(
            "sensitivities must be an iterable of SaCvaSensitivity objects"
        ) from exc

    seen_ids: set[str] = set()
    validated: list[SaCvaSensitivity] = []
    for candidate in candidates:
        if not isinstance(candidate, SaCvaSensitivity):
            raise CvaInputError("sensitivities must contain only SaCvaSensitivity objects")
        sensitivity = candidate
        _validate_sa_cva_sensitivity(sensitivity, seen_ids)
        seen_ids.add(sensitivity.sensitivity_id)
        validated.append(sensitivity)
    return tuple(validated)


def validate_calculation_context(context: object) -> CvaCalculationContext:
    """Validate a CVA calculation context.

    Parameters
    ----------
    context : object
        Candidate :class:`~frtb_cva.data_models.CvaCalculationContext`.

    Returns
    -------
    CvaCalculationContext
        The same context when all required fields and enums are valid.

    Raises
    ------
    CvaInputError
        If the object is not a context or required text fields are blank.
    UnsupportedRegulatoryFeatureError
        If ``materiality_threshold_elected`` is requested but not implemented.
    """

    if not isinstance(context, CvaCalculationContext):
        raise CvaInputError("context must be a CvaCalculationContext", field="context")
    _require_text(context.run_id, "run_id")
    _require_text(context.base_currency, "base_currency")
    if not isinstance(context.profile, CvaRegulatoryProfile):
        raise CvaInputError("invalid regulatory profile", field="profile")
    if not isinstance(context.method, CvaMethod):
        raise CvaInputError("invalid CVA method", field="method")
    if context.materiality_threshold_elected:
        raise UnsupportedRegulatoryFeatureError(MAR50_9_UNSUPPORTED_MESSAGE)
    for netting_set_id in context.carve_out_netting_set_ids:
        _require_text(netting_set_id, "carve_out_netting_set_ids")
    return context


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


def _validate_hedge(hedge: CvaHedge, seen_ids: set[str]) -> None:
    record_id = _require_text(hedge.hedge_id, "hedge_id")
    if record_id in seen_ids:
        raise CvaInputError("duplicate hedge id", field="hedge_id", record_id=record_id)
    _require_text(hedge.source_row_id, "source_row_id", record_id)
    _require_text(hedge.counterparty_id, "counterparty_id", record_id)
    _require_text(hedge.reference_region, "reference_region", record_id)
    if not isinstance(hedge.hedge_type, BaCvaHedgeType):
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
    _validate_lineage(hedge.lineage, record_id)


def _validate_sa_cva_sensitivity(sensitivity: SaCvaSensitivity, seen_ids: set[str]) -> None:
    record_id = _require_text(sensitivity.sensitivity_id, "sensitivity_id")
    if record_id in seen_ids:
        raise CvaInputError(
            "duplicate sensitivity id",
            field="sensitivity_id",
            record_id=record_id,
        )
    _require_text(sensitivity.source_row_id, "source_row_id", record_id)
    _require_text(sensitivity.bucket_id, "bucket_id", record_id)
    _require_text(sensitivity.risk_factor_key, "risk_factor_key", record_id)
    _require_text(sensitivity.amount_currency, "amount_currency", record_id)
    _require_text(sensitivity.sign_convention, "sign_convention", record_id)
    if sensitivity.sign_convention not in VALID_AMOUNT_SIGN_CONVENTIONS:
        raise CvaInputError(
            f"sign_convention must be one of {sorted(VALID_AMOUNT_SIGN_CONVENTIONS)}",
            field="sign_convention",
            record_id=record_id,
        )
    if not isinstance(sensitivity.risk_class, SaCvaRiskClass):
        raise CvaInputError("invalid risk class", field="risk_class", record_id=record_id)
    if not isinstance(sensitivity.risk_measure, SaCvaRiskMeasure):
        raise CvaInputError("invalid risk measure", field="risk_measure", record_id=record_id)
    if not isinstance(sensitivity.sensitivity_tag, SensitivityTag):
        raise CvaInputError(
            "invalid sensitivity tag",
            field="sensitivity_tag",
            record_id=record_id,
        )
    normalise_sensitivity_amount(sensitivity.amount)
    if sensitivity.volatility_input is not None:
        volatility = _finite_float(sensitivity.volatility_input, field="volatility_input")
        if volatility < 0:
            raise CvaInputError(
                "volatility input must be non-negative",
                field="volatility_input",
                record_id=record_id,
            )
    if sensitivity.tenor is not None:
        _require_text(sensitivity.tenor, "tenor", record_id)
    if (
        sensitivity.risk_class is SaCvaRiskClass.GIRR
        and sensitivity.risk_measure is SaCvaRiskMeasure.DELTA
        and sensitivity.tenor is None
    ):
        raise CvaInputError(
            "GIRR delta sensitivities must specify tenor",
            field="tenor",
            record_id=record_id,
        )
    if sensitivity.risk_measure is SaCvaRiskMeasure.VEGA and sensitivity.volatility_input is None:
        raise CvaInputError(
            "vega sensitivities must specify volatility_input",
            field="volatility_input",
            record_id=record_id,
        )
    if sensitivity.sensitivity_tag is SensitivityTag.HDG:
        _require_text(sensitivity.hedge_id, "hedge_id", record_id)
    if sensitivity.index_max_sector_weight is not None:
        weight = _finite_float(sensitivity.index_max_sector_weight, field="index_max_sector_weight")
        if not (0.0 <= weight <= 1.0):
            raise CvaInputError(
                "index_max_sector_weight must be between 0.0 and 1.0",
                field="index_max_sector_weight",
                record_id=record_id,
            )
    if sensitivity.index_remap_bucket_id is not None:
        _require_text(sensitivity.index_remap_bucket_id, "index_remap_bucket_id", record_id)
    if sensitivity.index_dominant_sector is not None and not isinstance(
        sensitivity.index_dominant_sector,
        CvaSector,
    ):
        raise CvaInputError(
            "invalid index dominant sector",
            field="index_dominant_sector",
            record_id=record_id,
        )
    _validate_lineage(sensitivity.lineage, record_id)


def _validate_lineage(lineage: CvaSourceLineage | None, record_id: str) -> None:
    if lineage is None:
        return
    if not isinstance(lineage, CvaSourceLineage):
        raise CvaInputError("invalid source lineage", field="lineage", record_id=record_id)
    _require_text(lineage.source_system, "lineage.source_system", record_id)
    _require_text(lineage.source_file, "lineage.source_file", record_id)
    _require_text(lineage.source_row_id, "lineage.source_row_id", record_id)
    for mapping in lineage.source_column_map:
        if not isinstance(mapping, tuple) or len(mapping) != 2:
            raise CvaInputError(
                "source column map entries must be field pairs",
                field="lineage.source_column_map",
                record_id=record_id,
            )
        source_field, canonical_field = mapping
        _require_text(source_field, "lineage.source_column_map.source", record_id)
        _require_text(canonical_field, "lineage.source_column_map.canonical", record_id)


def _finite_float(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise CvaInputError("value must be numeric", field=field)
    number = float(value)
    if not math.isfinite(number):
        raise CvaInputError("value must be finite", field=field)
    return number


def validate_m_cva_multiplier(value: object) -> float:
    """Return a finite, positive SA-CVA multiplier.

    Parameters
    ----------
    value : object
        Candidate ``m_cva`` multiplier from caller configuration.

    Returns
    -------
    float
        Finite multiplier strictly greater than zero.

    Raises
    ------
    CvaInputError
        If the value is non-numeric, non-finite, or not positive.
    """

    m_cva = _finite_float(value, field="m_cva")
    if m_cva <= 0.0:
        raise CvaInputError("m_cva must be positive", field="m_cva")
    return m_cva


def _require_text(value: object, field: str, record_id: str = "") -> str:
    if not isinstance(value, str) or not value.strip():
        raise CvaInputError("non-empty text is required", field=field, record_id=record_id)
    return value


__all__ = [
    "VALID_AMOUNT_SIGN_CONVENTIONS",
    "VALID_EAD_SIGN_CONVENTIONS",
    "AmountSignConvention",
    "AmountSignConventionEnum",
    "CvaInputError",
    "EADSignConvention",
    "EadSignConvention",
    "normalise_cva_amount",
    "normalise_ead_amount",
    "normalise_sensitivity_amount",
    "validate_calculation_context",
    "validate_cva_counterparties",
    "validate_cva_hedges",
    "validate_cva_netting_sets",
    "validate_m_cva_multiplier",
    "validate_sa_cva_sensitivities",
]
