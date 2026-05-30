"""
Validation helpers for canonical SBM inputs.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for validation.py, Basel MAR21.1,
    U.S. NPR 2.0 section V.A.7.a, and SBM-NFR-004.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TypeVar

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.data_models import (
    SbmCalculationContext,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
)

EnumT = TypeVar("EnumT", SbmRiskClass, SbmRiskMeasure, SbmSignConvention)

_STRICT_CITATION_POLICY = "strict"

_TENOR_REQUIRED: frozenset[tuple[SbmRiskClass, SbmRiskMeasure]] = frozenset(
    {
        (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
        (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
        (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA),
        (SbmRiskClass.COMMODITY, SbmRiskMeasure.VEGA),
    }
)

_OPTION_TENOR_REQUIRED: frozenset[tuple[SbmRiskClass, SbmRiskMeasure]] = frozenset(
    {(SbmRiskClass.GIRR, SbmRiskMeasure.VEGA)}
)

_QUALIFIER_REQUIRED: frozenset[SbmRiskClass] = frozenset(
    {
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskClass.CSR_SEC_NONCTP,
        SbmRiskClass.EQUITY,
        SbmRiskClass.COMMODITY,
    }
)

_PHASE1_SUPPORTED: dict[str, frozenset[tuple[SbmRiskClass, SbmRiskMeasure]]] = {
    SbmRegulatoryProfile.US_NPR_2_0.value: frozenset(),
    SbmRegulatoryProfile.BASEL_MAR21.value: frozenset(
        {
            (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
            (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
        }
    ),
    SbmRegulatoryProfile.EU_CRR3.value: frozenset(),
    SbmRegulatoryProfile.PRA_UK_CRR.value: frozenset(),
}


class SbmInputError(ValueError):
    """Raised when canonical SBM inputs fail deterministic validation."""

    def __init__(self, message: str, *, field: str = "", sensitivity_id: str = "") -> None:
        self.field = field
        self.sensitivity_id = sensitivity_id
        prefix = f"sensitivity {sensitivity_id}: " if sensitivity_id else ""
        suffix = f" [{field}]" if field else ""
        super().__init__(f"{prefix}{message}{suffix}")


def normalise_sensitivity_amount(value: float, *, sensitivity_id: str = "") -> float:
    """Return a finite sensitivity amount."""

    return _finite_float(value, field="amount", sensitivity_id=sensitivity_id)


def normalise_currency_code(
    value: str,
    *,
    field: str = "amount_currency",
    sensitivity_id: str = "",
) -> str:
    """Return an upper-case ISO-style currency code."""

    code = _require_text(value, field, sensitivity_id)
    normalised = code.upper()
    if len(normalised) != 3 or not normalised.isalpha():
        raise SbmInputError(
            "currency code must be a three-letter alphabetic code",
            field=field,
            sensitivity_id=sensitivity_id,
        )
    return normalised


def coerce_risk_class(value: SbmRiskClass | str) -> SbmRiskClass:
    """Normalise a risk-class identifier to the canonical enum."""

    return _coerce_enum(value, SbmRiskClass, "risk_class")


def coerce_risk_measure(value: SbmRiskMeasure | str) -> SbmRiskMeasure:
    """Normalise a risk-measure identifier to the canonical enum."""

    return _coerce_enum(value, SbmRiskMeasure, "risk_measure")


def coerce_sign_convention(value: SbmSignConvention | str) -> SbmSignConvention:
    """Normalise a sign-convention identifier to the canonical enum."""

    return _coerce_enum(value, SbmSignConvention, "sign_convention")


def sensitivity_sort_key(sensitivity: SbmSensitivity) -> tuple[str, str, str, str, str]:
    """Return a deterministic ordering key for one sensitivity."""

    return (
        sensitivity.risk_class.value,
        sensitivity.risk_measure.value,
        sensitivity.bucket,
        sensitivity.risk_factor,
        sensitivity.sensitivity_id,
    )


def sort_sensitivities_deterministic(
    sensitivities: Sequence[SbmSensitivity],
) -> tuple[SbmSensitivity, ...]:
    """Return sensitivities in stable risk-class, bucket, and id order."""

    return tuple(sorted(sensitivities, key=sensitivity_sort_key))


def validate_sbm_calculation_context(context: SbmCalculationContext) -> SbmCalculationContext:
    """Validate run-level SBM context and return it unchanged."""

    _require_text(context.run_id, "run_id")
    _require_text(context.profile_id, "profile_id")
    normalise_currency_code(context.base_currency, field="base_currency")
    normalise_currency_code(context.reporting_currency, field="reporting_currency")
    _validate_citation_policy(context.citation_policy)
    ensure_sbm_profile_known(context.profile_id)
    if context.desk_id is not None and context.desk_id != context.desk_id.strip():
        raise SbmInputError(
            "desk_id must not contain leading or trailing whitespace",
            field="desk_id",
        )
    if context.legal_entity is not None and context.legal_entity != context.legal_entity.strip():
        raise SbmInputError(
            "legal_entity must not contain leading or trailing whitespace",
            field="legal_entity",
        )
    return context


def validate_sbm_sensitivities(sensitivities: object) -> tuple[SbmSensitivity, ...]:
    """Validate canonical SBM sensitivities and return them in input order."""

    if isinstance(sensitivities, SbmSensitivity):
        raise SbmInputError("sensitivities must be an iterable of SbmSensitivity objects")
    try:
        candidates: tuple[object, ...] = tuple(sensitivities)  # type: ignore[arg-type]
    except TypeError as exc:
        raise SbmInputError("sensitivities must be an iterable of SbmSensitivity objects") from exc

    seen_sensitivity_ids: set[str] = set()
    validated: list[SbmSensitivity] = []
    for candidate in candidates:
        if not isinstance(candidate, SbmSensitivity):
            raise SbmInputError("sensitivities must contain only SbmSensitivity objects")
        sensitivity = candidate
        _validate_sensitivity(sensitivity, seen_sensitivity_ids)
        seen_sensitivity_ids.add(sensitivity.sensitivity_id)
        validated.append(sensitivity)
    return tuple(validated)


def ensure_sbm_profile_known(profile_id: str) -> SbmRegulatoryProfile:
    """Raise when a requested profile id is unknown."""

    normalised = _require_text(profile_id, "profile_id")
    try:
        return SbmRegulatoryProfile(normalised)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in SbmRegulatoryProfile)
        raise SbmInputError(
            f"profile_id must be one of: {allowed}",
            field="profile_id",
        ) from exc


def ensure_sbm_risk_class_measure_supported(
    profile_id: str,
    risk_class: SbmRiskClass | str,
    risk_measure: SbmRiskMeasure | str,
) -> None:
    """Raise explicitly when a profile/risk-class/measure path is unsupported."""

    profile = ensure_sbm_profile_known(profile_id)
    resolved_risk_class = coerce_risk_class(risk_class)
    resolved_measure = coerce_risk_measure(risk_measure)
    supported = _PHASE1_SUPPORTED.get(profile.value, frozenset())
    if (resolved_risk_class, resolved_measure) in supported:
        return
    raise UnsupportedRegulatoryFeatureError(
        "frtb-sbm does not support "
        f"profile={profile.value}, risk_class={resolved_risk_class.value}, "
        f"risk_measure={resolved_measure.value}"
    )


def ensure_sbm_run_supported(
    context: SbmCalculationContext,
    sensitivities: Sequence[SbmSensitivity],
) -> None:
    """Validate that the requested run path is supported before capital math."""

    validated_context = validate_sbm_calculation_context(context)
    validated_sensitivities = validate_sbm_sensitivities(sensitivities)
    scoped_desk_id = validated_context.desk_id.strip()
    scoped_legal_entity = validated_context.legal_entity.strip()
    for sensitivity in validated_sensitivities:
        if scoped_desk_id and sensitivity.desk_id != scoped_desk_id:
            raise SbmInputError(
                f"desk_id {sensitivity.desk_id} does not match context desk_id {scoped_desk_id}",
                field="desk_id",
                sensitivity_id=sensitivity.sensitivity_id,
            )
        if scoped_legal_entity and sensitivity.legal_entity != scoped_legal_entity:
            raise SbmInputError(
                f"legal_entity {sensitivity.legal_entity} does not match "
                f"context legal_entity {scoped_legal_entity}",
                field="legal_entity",
                sensitivity_id=sensitivity.sensitivity_id,
            )
        ensure_sbm_risk_class_measure_supported(
            validated_context.profile_id,
            sensitivity.risk_class,
            sensitivity.risk_measure,
        )


def _validate_sensitivity(sensitivity: SbmSensitivity, seen_sensitivity_ids: set[str]) -> None:
    sensitivity_id = _require_text(sensitivity.sensitivity_id, "sensitivity_id")
    if sensitivity_id in seen_sensitivity_ids:
        raise SbmInputError(
            "duplicate sensitivity id",
            field="sensitivity_id",
            sensitivity_id=sensitivity_id,
        )

    _require_text(sensitivity.source_row_id, "source_row_id", sensitivity_id)
    _require_text(sensitivity.desk_id, "desk_id", sensitivity_id)
    _require_text(sensitivity.legal_entity, "legal_entity", sensitivity_id)
    _require_text(sensitivity.bucket, "bucket", sensitivity_id)
    _require_text(sensitivity.risk_factor, "risk_factor", sensitivity_id)
    normalise_currency_code(
        sensitivity.amount_currency,
        field="amount_currency",
        sensitivity_id=sensitivity_id,
    )
    normalise_sensitivity_amount(sensitivity.amount, sensitivity_id=sensitivity_id)

    risk_class = _coerce_enum(
        sensitivity.risk_class,
        SbmRiskClass,
        "risk_class",
        sensitivity_id,
    )
    risk_measure = _coerce_enum(
        sensitivity.risk_measure,
        SbmRiskMeasure,
        "risk_measure",
        sensitivity_id,
    )
    _coerce_enum(
        sensitivity.sign_convention,
        SbmSignConvention,
        "sign_convention",
        sensitivity_id,
    )

    if sensitivity.position_id is not None:
        _require_text(sensitivity.position_id, "position_id", sensitivity_id)

    _validate_lineage(sensitivity.lineage, sensitivity_id)
    if sensitivity.source_row_id != sensitivity.lineage.source_row_id:
        raise SbmInputError(
            "source_row_id must match lineage.source_row_id",
            field="source_row_id",
            sensitivity_id=sensitivity_id,
        )

    for citation_id in sensitivity.mapping_citation_ids:
        _require_text(citation_id, "mapping_citation_ids", sensitivity_id)

    _validate_risk_class_fields(
        sensitivity,
        risk_class=risk_class,
        risk_measure=risk_measure,
    )


def _validate_lineage(lineage: SbmSourceLineage, sensitivity_id: str) -> None:
    if not isinstance(lineage, SbmSourceLineage):
        raise SbmInputError(
            "invalid source lineage",
            field="lineage",
            sensitivity_id=sensitivity_id,
        )

    _require_text(lineage.source_system, "lineage.source_system", sensitivity_id)
    _require_text(lineage.source_file, "lineage.source_file", sensitivity_id)
    _require_text(lineage.source_row_id, "lineage.source_row_id", sensitivity_id)
    for mapping in lineage.source_column_map:
        if not isinstance(mapping, tuple | list) or len(mapping) != 2:
            raise SbmInputError(
                "source column map entries must be field pairs",
                field="lineage.source_column_map",
                sensitivity_id=sensitivity_id,
            )
        source_field, canonical_field = mapping
        _require_text(source_field, "lineage.source_column_map.source", sensitivity_id)
        _require_text(canonical_field, "lineage.source_column_map.canonical", sensitivity_id)


def _validate_risk_class_fields(
    sensitivity: SbmSensitivity,
    *,
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
) -> None:
    sensitivity_id = sensitivity.sensitivity_id

    if risk_class in _QUALIFIER_REQUIRED and _is_blank(sensitivity.qualifier):
        raise SbmInputError(
            "qualifier is required for the selected risk class",
            field="qualifier",
            sensitivity_id=sensitivity_id,
        )

    if (risk_class, risk_measure) in _TENOR_REQUIRED:
        _require_text(sensitivity.tenor, "tenor", sensitivity_id)

    if (risk_class, risk_measure) in _OPTION_TENOR_REQUIRED:
        _require_text(sensitivity.option_tenor, "option_tenor", sensitivity_id)

    if sensitivity.liquidity_horizon_days is not None:
        _require_positive_int(
            sensitivity.liquidity_horizon_days,
            "liquidity_horizon_days",
            sensitivity_id,
        )

    for field_name in ("tenor", "option_tenor", "maturity", "qualifier"):
        value = getattr(sensitivity, field_name)
        if value is not None:
            _require_text(value, field_name, sensitivity_id)

    if risk_measure is SbmRiskMeasure.CURVATURE:
        _validate_curvature_amounts(sensitivity)


def _validate_curvature_amounts(sensitivity: SbmSensitivity) -> None:
    sensitivity_id = sensitivity.sensitivity_id
    if sensitivity.up_shock_amount is None or sensitivity.down_shock_amount is None:
        raise SbmInputError(
            "curvature inputs require up_shock_amount and down_shock_amount",
            field="up_shock_amount",
            sensitivity_id=sensitivity_id,
        )
    normalise_sensitivity_amount(sensitivity.up_shock_amount, sensitivity_id=sensitivity_id)
    normalise_sensitivity_amount(sensitivity.down_shock_amount, sensitivity_id=sensitivity_id)


def _validate_citation_policy(citation_policy: str) -> None:
    if citation_policy.strip().lower() != _STRICT_CITATION_POLICY:
        raise SbmInputError(
            f"unsupported citation_policy: {citation_policy}",
            field="citation_policy",
        )


def _coerce_enum(
    value: object,
    enum_type: type[EnumT],
    field: str,
    sensitivity_id: str = "",
) -> EnumT:
    if isinstance(value, enum_type):
        return value
    if not isinstance(value, str):
        raise SbmInputError(f"invalid {field}", field=field, sensitivity_id=sensitivity_id)
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise SbmInputError(
            f"{field} must be one of: {allowed}",
            field=field,
            sensitivity_id=sensitivity_id,
        ) from exc


def _finite_float(value: object, *, field: str, sensitivity_id: str = "") -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SbmInputError("value must be numeric", field=field, sensitivity_id=sensitivity_id)
    number = float(value)
    if not math.isfinite(number):
        raise SbmInputError("value must be finite", field=field, sensitivity_id=sensitivity_id)
    return number


def _require_text(value: object, field: str, sensitivity_id: str = "") -> str:
    if not isinstance(value, str) or not value.strip():
        raise SbmInputError(
            "non-empty text is required",
            field=field,
            sensitivity_id=sensitivity_id,
        )
    return value.strip()


def _is_blank(value: str | None) -> bool:
    return value is None or value.strip() == ""


def _require_positive_int(value: object, field: str, sensitivity_id: str = "") -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SbmInputError(
            "value must be a positive integer",
            field=field,
            sensitivity_id=sensitivity_id,
        )
    if value <= 0:
        raise SbmInputError(
            "value must be a positive integer",
            field=field,
            sensitivity_id=sensitivity_id,
        )
    return value


__all__ = [
    "SbmInputError",
    "coerce_risk_class",
    "coerce_risk_measure",
    "coerce_sign_convention",
    "ensure_sbm_profile_known",
    "ensure_sbm_risk_class_measure_supported",
    "ensure_sbm_run_supported",
    "normalise_currency_code",
    "normalise_sensitivity_amount",
    "sensitivity_sort_key",
    "sort_sensitivities_deterministic",
    "validate_sbm_calculation_context",
    "validate_sbm_sensitivities",
]
