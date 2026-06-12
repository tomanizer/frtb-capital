"""Homogeneous SBM batch validation helpers.

Regulatory traceability:
    ADR 0045 validation stage for package-owned SBM batches; Basel MAR21.1
    input scope, MAR21.4-MAR21.7 path homogeneity, and SBM-NFR-002.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import numpy as np

from frtb_sbm._errors import SbmInputError
from frtb_sbm.data_models import SbmRiskClass, SbmRiskMeasure
from frtb_sbm.validation.batch_arrays import FloatArray, ObjectArray, sensitivity_id_for_index
from frtb_sbm.validation.coercion import (
    coerce_risk_class,
    coerce_risk_measure,
    coerce_sign_convention,
    normalise_currency_code,
)

_CORE_REQUIRED_TEXT_FIELDS = frozenset(
    {
        "sensitivity_ids",
        "source_row_ids",
        "desk_ids",
        "legal_entities",
        "risk_classes",
        "risk_measures",
        "buckets",
        "risk_factors",
        "amount_currencies",
        "sign_conventions",
        "lineage_source_systems",
        "lineage_source_files",
    }
)

_TENOR_REQUIRED_PATHS = frozenset(
    {
        (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
        (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
        (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
        (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA),
        (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA),
        (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA),
        (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA),
    }
)

_OPTION_TENOR_REQUIRED_PATHS = frozenset(
    {(risk_class, SbmRiskMeasure.VEGA) for risk_class in SbmRiskClass}
)

_CURVATURE_REQUIRED_PATHS = frozenset(
    {(risk_class, SbmRiskMeasure.CURVATURE) for risk_class in SbmRiskClass}
)

_QUALIFIER_REQUIRED_RISK_CLASSES = frozenset(
    {
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskClass.CSR_SEC_NONCTP,
        SbmRiskClass.EQUITY,
        SbmRiskClass.COMMODITY,
    }
)


def validate_homogeneous_batch_arrays(
    arrays: Mapping[str, ObjectArray],
    amount_array: FloatArray,
    *,
    expected_risk_class: SbmRiskClass,
    expected_risk_measure: SbmRiskMeasure,
    optional_arrays: Mapping[str, ObjectArray | None],
) -> None:
    """Validate path homogeneity and required fields for one batch.

    Parameters
    ----------
    arrays
        Required object arrays by canonical batch field.
    amount_array
        Sensitivity amount array.
    expected_risk_class
        Homogeneous risk class for this batch.
    expected_risk_measure
        Homogeneous risk measure for this batch.
    optional_arrays
        Optional object arrays by canonical batch field.
    """

    sensitivity_ids = arrays["sensitivity_ids"]
    for field_name, column in arrays.items():
        if field_name in _CORE_REQUIRED_TEXT_FIELDS:
            validate_required_text_column(column, field_name, sensitivity_ids=sensitivity_ids)
        else:
            validate_optional_text_column(column, field_name, sensitivity_ids=sensitivity_ids)
    validate_unique_sensitivity_ids(sensitivity_ids)
    validate_constant_column(
        arrays["risk_classes"],
        expected=expected_risk_class.value,
        field="risk_class",
        message=f"batch only accepts {expected_risk_class.value} sensitivities",
        sensitivity_ids=sensitivity_ids,
    )
    validate_constant_column(
        arrays["risk_measures"],
        expected=expected_risk_measure.value,
        field="risk_measure",
        message=f"batch only accepts {expected_risk_measure.value} sensitivities",
        sensitivity_ids=sensitivity_ids,
    )
    _validate_path_specific_arrays(
        arrays,
        expected_risk_class=expected_risk_class,
        expected_risk_measure=expected_risk_measure,
        optional_arrays=optional_arrays,
        sensitivity_ids=sensitivity_ids,
    )
    for amount_currency in np.unique(arrays["amount_currencies"]):
        normalise_currency_code(cast(str, amount_currency))
    for sign_convention in np.unique(arrays["sign_conventions"]):
        coerce_sign_convention(sign_convention)
    if not np.all(np.isfinite(amount_array)):
        raise SbmInputError("value must be finite", field="amount")


def _validate_path_specific_arrays(
    arrays: Mapping[str, ObjectArray],
    *,
    expected_risk_class: SbmRiskClass,
    expected_risk_measure: SbmRiskMeasure,
    optional_arrays: Mapping[str, ObjectArray | None],
    sensitivity_ids: ObjectArray,
) -> None:
    path = (expected_risk_class, expected_risk_measure)
    if path in _TENOR_REQUIRED_PATHS:
        validate_required_text_column(
            arrays["tenors"],
            "tenor",
            sensitivity_ids=sensitivity_ids,
        )

    option_tenors = optional_arrays["option_tenors"]
    if path in _OPTION_TENOR_REQUIRED_PATHS:
        if option_tenors is None:
            raise SbmInputError("option_tenor is required", field="option_tenor")
        validate_required_text_column(
            option_tenors,
            "option_tenor",
            sensitivity_ids=sensitivity_ids,
        )
    elif option_tenors is not None:
        validate_optional_text_column(
            option_tenors,
            "option_tenor",
            sensitivity_ids=sensitivity_ids,
        )

    qualifiers = optional_arrays["qualifiers"]
    if _qualifier_required_for_path(expected_risk_class, expected_risk_measure):
        if qualifiers is None:
            raise SbmInputError("qualifier is required", field="qualifier")
        validate_required_text_column(
            qualifiers,
            "qualifier",
            sensitivity_ids=sensitivity_ids,
        )
    elif qualifiers is not None:
        validate_optional_text_column(qualifiers, "qualifier", sensitivity_ids=sensitivity_ids)

    if path in _CURVATURE_REQUIRED_PATHS:
        for optional_field, field_name in (
            ("up_shock_amounts", "up_shock_amount"),
            ("down_shock_amounts", "down_shock_amount"),
        ):
            shock_values = optional_arrays[optional_field]
            if shock_values is None:
                raise SbmInputError(
                    "curvature inputs require up_shock_amount and down_shock_amount",
                    field=field_name,
                )
            validate_required_float_column(
                shock_values,
                field_name,
                sensitivity_ids=sensitivity_ids,
            )


def _qualifier_required_for_path(
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
) -> bool:
    if risk_class is SbmRiskClass.COMMODITY and risk_measure is SbmRiskMeasure.VEGA:
        return False
    return risk_class in _QUALIFIER_REQUIRED_RISK_CLASSES


def validate_required_text_column(
    values: ObjectArray,
    field: str,
    *,
    sensitivity_ids: ObjectArray,
) -> None:
    """Raise when a required text column contains blank or non-text values.

    Parameters
    ----------
    values
        Candidate column values.
    field
        Field name reported in diagnostics.
    sensitivity_ids
        Sensitivity ids used in diagnostics.
    """

    invalid_mask = np.fromiter(
        (not isinstance(value, str) or not value.strip() for value in values),
        dtype=np.bool_,
        count=int(values.shape[0]),
    )
    if np.any(invalid_mask):
        row_index = int(np.flatnonzero(invalid_mask)[0])
        raise SbmInputError(
            "non-empty text is required",
            field=field,
            sensitivity_id=sensitivity_id_for_index(sensitivity_ids, row_index),
        )


def validate_optional_text_column(
    values: ObjectArray,
    field: str,
    *,
    sensitivity_ids: ObjectArray,
) -> None:
    """Raise when an optional text column contains non-text values.

    Parameters
    ----------
    values
        Candidate column values.
    field
        Field name reported in diagnostics.
    sensitivity_ids
        Sensitivity ids used in diagnostics.
    """

    invalid_mask = np.fromiter(
        (value is not None and not isinstance(value, str) for value in values),
        dtype=np.bool_,
        count=int(values.shape[0]),
    )
    if np.any(invalid_mask):
        row_index = int(np.flatnonzero(invalid_mask)[0])
        raise SbmInputError(
            "text is required when present",
            field=field,
            sensitivity_id=sensitivity_id_for_index(sensitivity_ids, row_index),
        )


def validate_unique_sensitivity_ids(sensitivity_ids: ObjectArray) -> None:
    """Raise when a batch contains duplicate sensitivity ids.

    Parameters
    ----------
    sensitivity_ids
        Batch sensitivity id array.
    """

    unique_ids, counts = np.unique(sensitivity_ids, return_counts=True)
    duplicate_mask = counts > 1
    if not np.any(duplicate_mask):
        return
    duplicate_id = cast(str, unique_ids[int(np.flatnonzero(duplicate_mask)[0])])
    raise SbmInputError(
        "duplicate sensitivity id",
        field="sensitivity_id",
        sensitivity_id=duplicate_id,
    )


def validate_constant_column(
    values: ObjectArray,
    *,
    expected: str,
    field: str,
    message: str,
    sensitivity_ids: ObjectArray,
) -> None:
    """Raise when a homogeneous path column differs from its expected value.

    Parameters
    ----------
    values
        Candidate column values.
    expected
        Expected string value.
    field
        Field name reported in diagnostics.
    message
        Error message for mismatched canonical values.
    sensitivity_ids
        Sensitivity ids used in diagnostics.
    """

    invalid_mask = values != expected
    if not np.any(invalid_mask):
        return
    row_index = int(np.flatnonzero(invalid_mask)[0])
    if field == "risk_class":
        coerce_risk_class(values[row_index])
    if field == "risk_measure":
        coerce_risk_measure(values[row_index])
    raise SbmInputError(
        message,
        field=field,
        sensitivity_id=sensitivity_id_for_index(sensitivity_ids, row_index),
    )


def validate_required_float_column(
    values: ObjectArray,
    field: str,
    *,
    sensitivity_ids: ObjectArray,
) -> None:
    """Raise when a required numeric object column is missing or invalid.

    Parameters
    ----------
    values
        Candidate column values.
    field
        Field name reported in diagnostics.
    sensitivity_ids
        Sensitivity ids used in diagnostics.
    """

    for row_index, value in enumerate(values):
        if value is None:
            raise SbmInputError(
                "curvature inputs require up_shock_amount and down_shock_amount",
                field=field,
                sensitivity_id=sensitivity_id_for_index(sensitivity_ids, row_index),
            )
        try:
            float_value = float(value)
        except (TypeError, ValueError) as exc:
            raise SbmInputError(
                "value must be numeric",
                field=field,
                sensitivity_id=sensitivity_id_for_index(sensitivity_ids, row_index),
            ) from exc
        if not np.isfinite(float_value):
            raise SbmInputError(
                "value must be finite",
                field=field,
                sensitivity_id=sensitivity_id_for_index(sensitivity_ids, row_index),
            )


__all__ = [
    "validate_constant_column",
    "validate_homogeneous_batch_arrays",
    "validate_optional_text_column",
    "validate_required_float_column",
    "validate_required_text_column",
    "validate_unique_sensitivity_ids",
]
