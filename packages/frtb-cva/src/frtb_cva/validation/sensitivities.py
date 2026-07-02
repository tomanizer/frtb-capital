"""SA-CVA sensitivity row validation."""

from __future__ import annotations

from frtb_cva.data_models import (
    CvaSector,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
)
from frtb_cva.validation.common import (
    VALID_AMOUNT_SIGN_CONVENTIONS,
    CvaInputError,
    _finite_float,
    _require_text,
    _validate_lineage,
    _validate_optional_text,
    normalise_sensitivity_amount,
)


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
    _validate_optional_text(
        sensitivity.volatility_surface_id,
        "volatility_surface_id",
        record_id,
    )
    _validate_optional_text(
        sensitivity.volatility_surface_point_id,
        "volatility_surface_point_id",
        record_id,
    )
    _validate_optional_text(sensitivity.shock_id, "shock_id", record_id)
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


__all__ = ["validate_sa_cva_sensitivities"]
