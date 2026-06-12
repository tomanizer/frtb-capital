"""Batch curvature input validation and branch-record helpers.

Regulatory traceability:
    Basel MAR21.5, MAR21.8-MAR21.14, MAR21.96-MAR21.99, and SBM-CURV-001.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.batch import SbmSensitivityBatch, sorted_curvature_batch_indices
from frtb_sbm.curvature_batch_mapping import (
    _mapping_citation_ids_from_batch,
    _optional_text_at,
    _scaled_curvature_batch_shock,
    _text_at,
    _validate_curvature_mapping_from_batch,
)
from frtb_sbm.curvature_inputs import curvature_worst_branch
from frtb_sbm.data_models import (
    CurvatureBranchRecord,
    SbmRiskClass,
    SbmRiskMeasure,
)
from frtb_sbm.reference_data import (
    curvature_citation_ids,
    normalise_fx_delta_currency_code,
)
from frtb_sbm.regimes import ensure_profile_supports_risk_class_measure
from frtb_sbm.validation import SbmInputError, ensure_sbm_profile_known

_SUPPORTED_CURVATURE_RISK_CLASSES: frozenset[SbmRiskClass] = frozenset(SbmRiskClass)


def validate_girr_curvature_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> SbmSensitivityBatch:
    """Validate a GIRR curvature batch and its separate MAR21.5 shock arrays.
    Parameters
    ----------
    batch : SbmSensitivityBatch
        See signature.
    profile_id : str
        See signature.

    Returns
    -------
    SbmSensitivityBatch
    """

    _validate_and_get_girr_curvature_shocks(batch, profile_id=profile_id)
    return batch


def validate_curvature_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    reporting_currency: str,
    expected_risk_class: SbmRiskClass | None = None,
) -> SbmSensitivityBatch:
    """Validate a curvature batch without materialising row dataclasses.
    Parameters
    ----------
    batch, profile_id, reporting_currency, expected_risk_class :
        See function signature for types and defaults.

    Returns
    -------
    SbmSensitivityBatch
    """

    _validate_curvature_batch_for_capital(
        batch,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
        expected_risk_class=expected_risk_class,
    )
    return batch


def _validate_curvature_batch_for_capital(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    reporting_currency: str,
    expected_risk_class: SbmRiskClass | None,
) -> tuple[SbmRiskClass, npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    ensure_sbm_profile_known(profile_id)
    if not isinstance(batch, SbmSensitivityBatch):
        raise SbmInputError("batch must be SbmSensitivityBatch", field="batch")
    if batch.row_count == 0:
        raise SbmInputError("curvature batch must not be empty", field="batch")
    risk_class = batch.risk_class
    if expected_risk_class is not None and risk_class is not expected_risk_class:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm curvature capital expected "
            f"risk_class={expected_risk_class.value}; received risk_class={risk_class.value}"
        )
    if risk_class not in _SUPPORTED_CURVATURE_RISK_CLASSES:
        raise UnsupportedRegulatoryFeatureError(
            f"frtb-sbm curvature capital is unsupported for risk_class={risk_class.value}"
        )
    if batch.risk_measure is not SbmRiskMeasure.CURVATURE:
        raise UnsupportedRegulatoryFeatureError(
            f"frtb-sbm curvature capital does not support risk_measure={batch.risk_measure.value}"
        )
    ensure_profile_supports_risk_class_measure(
        profile_id,
        risk_class,
        SbmRiskMeasure.CURVATURE,
    )
    up_shocks, down_shocks = _validate_and_get_curvature_shocks(
        batch,
        profile_id=profile_id,
    )
    reporting = normalise_fx_delta_currency_code(reporting_currency)
    for row_index in sorted_curvature_batch_indices(batch):
        _validate_curvature_mapping_from_batch(
            batch,
            int(row_index),
            profile_id=profile_id,
            reporting_currency=reporting,
            risk_class=risk_class,
        )
    return risk_class, up_shocks, down_shocks


def _curvature_input_branch_records_from_batch(
    batch: SbmSensitivityBatch,
    *,
    up_shocks: npt.NDArray[np.float64],
    down_shocks: npt.NDArray[np.float64],
    profile_id: str,
) -> tuple[CurvatureBranchRecord, ...]:
    citations = curvature_citation_ids(profile_id)
    records: list[CurvatureBranchRecord] = []
    for row_index in sorted_curvature_batch_indices(batch):
        up_shock = float(up_shocks[row_index])
        down_shock = float(down_shocks[row_index])
        records.append(
            CurvatureBranchRecord(
                sensitivity_id=_text_at(batch.sensitivity_ids, int(row_index)),
                selected_branch=curvature_worst_branch(up_shock, down_shock),
                up_shock_amount=up_shock,
                down_shock_amount=down_shock,
                citation_ids=citations,
            )
        )
    return tuple(records)


def _require_girr_curvature_batch(batch: SbmSensitivityBatch) -> None:
    if not isinstance(batch, SbmSensitivityBatch):
        raise SbmInputError("batch must be SbmSensitivityBatch", field="batch")
    if batch.risk_class is not SbmRiskClass.GIRR:
        raise SbmInputError("GIRR curvature batch only accepts GIRR sensitivities")
    if batch.risk_measure is not SbmRiskMeasure.CURVATURE:
        raise SbmInputError("GIRR curvature batch only accepts CURVATURE sensitivities")
    if batch.up_shock_amounts is None or batch.down_shock_amounts is None:
        raise SbmInputError(
            "curvature inputs require up_shock_amount and down_shock_amount",
            field="up_shock_amount",
        )


def _validate_and_get_girr_curvature_shocks(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    ensure_sbm_profile_known(profile_id)
    _require_girr_curvature_batch(batch)
    return _validate_and_get_curvature_shocks(batch, profile_id=profile_id)


def _validate_and_get_curvature_shocks(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    ensure_sbm_profile_known(profile_id)
    if not isinstance(batch, SbmSensitivityBatch):
        raise SbmInputError("batch must be SbmSensitivityBatch", field="batch")
    if batch.risk_measure is not SbmRiskMeasure.CURVATURE:
        raise SbmInputError("curvature batch only accepts CURVATURE sensitivities")
    if batch.up_shock_amounts is None or batch.down_shock_amounts is None:
        raise SbmInputError(
            "curvature inputs require up_shock_amount and down_shock_amount",
            field="up_shock_amount",
        )
    return (
        _curvature_shock_float_array(batch, batch.up_shock_amounts, field="up_shock_amount"),
        _curvature_shock_float_array(batch, batch.down_shock_amounts, field="down_shock_amount"),
    )


def _curvature_shock_float_array(
    batch: SbmSensitivityBatch,
    values: npt.NDArray[np.object_] | None,
    *,
    field: str,
) -> npt.NDArray[np.float64]:
    if values is None:
        raise SbmInputError(
            "curvature inputs require up_shock_amount and down_shock_amount",
            field=field,
        )
    shocks = np.empty(batch.row_count, dtype=np.float64)
    for row_index, value in enumerate(values):
        sensitivity_id = str(batch.sensitivity_ids[row_index])
        if value is None:
            raise SbmInputError(
                "curvature inputs require up_shock_amount and down_shock_amount",
                field=field,
                sensitivity_id=sensitivity_id,
            )
        try:
            shocks[row_index] = float(value)
        except (TypeError, ValueError) as exc:
            raise SbmInputError(
                "value must be numeric",
                field=field,
                sensitivity_id=sensitivity_id,
            ) from exc
        if not np.isfinite(shocks[row_index]):
            raise SbmInputError(
                "value must be finite",
                field=field,
                sensitivity_id=sensitivity_id,
            )
    shocks.setflags(write=False)
    return shocks


__all__ = [
    "_curvature_input_branch_records_from_batch",
    "_mapping_citation_ids_from_batch",
    "_optional_text_at",
    "_scaled_curvature_batch_shock",
    "_text_at",
    "_validate_and_get_curvature_shocks",
    "_validate_and_get_girr_curvature_shocks",
    "_validate_curvature_batch_for_capital",
    "_validate_curvature_mapping_from_batch",
    "validate_curvature_batch",
    "validate_girr_curvature_batch",
]
