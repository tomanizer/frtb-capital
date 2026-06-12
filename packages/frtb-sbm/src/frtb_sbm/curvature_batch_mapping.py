"""Batch row mapping helpers for curvature input validation.

Regulatory traceability:
    Basel MAR21.8-MAR21.14, MAR21.96-MAR21.99, and SBM-CURV-001.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.batch import SbmSensitivityBatch
from frtb_sbm.commodity_reference_data import commodity_bucket_definition
from frtb_sbm.csr_nonsec_reference_data import csr_nonsec_bucket_definition
from frtb_sbm.csr_sec_ctp_reference_data import csr_sec_ctp_bucket_definition
from frtb_sbm.csr_sec_nonctp_reference_data import csr_sec_nonctp_bucket_definition
from frtb_sbm.curvature_factors import FX_CURVATURE_SCALAR_1_5_FLAG
from frtb_sbm.curvature_inputs import _normalise_csr_basis, _normalise_csr_sec_basis
from frtb_sbm.data_models import SbmRiskClass
from frtb_sbm.equity_reference_data import EQUITY_SPOT_RISK_FACTOR, equity_bucket_definition
from frtb_sbm.reference_data import (
    curvature_risk_weight,
    girr_bucket_definition,
    normalise_fx_delta_currency_code,
)
from frtb_sbm.validation import SbmInputError


def _validate_curvature_mapping_from_batch(
    batch: SbmSensitivityBatch,
    row_index: int,
    *,
    profile_id: str,
    reporting_currency: str,
    risk_class: SbmRiskClass,
) -> None:
    sensitivity_id = _text_at(batch.sensitivity_ids, row_index)
    bucket = _text_at(batch.buckets, row_index)
    risk_factor = _text_at(batch.risk_factors, row_index)
    qualifier = _optional_text_at(batch.qualifiers, row_index)
    if risk_class is SbmRiskClass.GIRR:
        girr_bucket_definition(profile_id, bucket)
        if risk_factor.strip().upper() in {"INFL", "XCCY"}:
            raise UnsupportedRegulatoryFeatureError(
                "GIRR curvature has no capital requirement for inflation or "
                "cross-currency basis risk factors (MAR21.8(5)(b))"
            )
        return
    if risk_class is SbmRiskClass.FX:
        normalised_bucket = normalise_fx_delta_currency_code(bucket)
        normalised_risk_factor = normalise_fx_delta_currency_code(risk_factor)
        if normalised_bucket != normalised_risk_factor:
            raise SbmInputError(
                "FX curvature bucket must match risk_factor currency",
                field="bucket",
                sensitivity_id=sensitivity_id,
            )
        curvature_risk_weight(
            profile_id,
            risk_class=risk_class,
            currency=normalised_risk_factor,
            reporting_currency=reporting_currency,
        )
        _validate_fx_curvature_scalar_flag_from_values(
            qualifier,
            _mapping_citation_ids_from_batch(batch, row_index),
            reporting_currency=reporting_currency,
        )
        return
    if risk_class is SbmRiskClass.EQUITY:
        equity_bucket_definition(profile_id, bucket)
        if risk_factor.strip().upper() != EQUITY_SPOT_RISK_FACTOR:
            raise UnsupportedRegulatoryFeatureError(
                "equity curvature has no capital requirement for equity repo rates (MAR21.12(3))"
            )
        return
    if risk_class is SbmRiskClass.COMMODITY:
        commodity_bucket_definition(profile_id, bucket)
        return
    if risk_class is SbmRiskClass.CSR_NONSEC:
        csr_nonsec_bucket_definition(profile_id, bucket)
        _normalise_csr_basis(risk_factor)
        return
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        csr_sec_ctp_bucket_definition(profile_id, bucket)
        _normalise_csr_basis(risk_factor)
        return
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        csr_sec_nonctp_bucket_definition(profile_id, bucket)
        _normalise_csr_sec_basis(risk_factor)
        return
    raise UnsupportedRegulatoryFeatureError(
        f"frtb-sbm curvature capital is unsupported for risk_class={risk_class.value}"
    )


def _scaled_curvature_batch_shock(
    batch: SbmSensitivityBatch,
    row_index: int,
    shock: float,
) -> float:
    if (
        batch.risk_class is SbmRiskClass.FX
        and FX_CURVATURE_SCALAR_1_5_FLAG in _mapping_citation_ids_from_batch(batch, row_index)
    ):
        return float(shock) / 1.5
    return float(shock)


def _validate_fx_curvature_scalar_flag_from_values(
    qualifier: str | None,
    mapping_citation_ids: tuple[str, ...],
    *,
    reporting_currency: str,
) -> None:
    if FX_CURVATURE_SCALAR_1_5_FLAG not in mapping_citation_ids:
        return
    qualifier_text = qualifier.strip().upper() if qualifier else ""
    if qualifier_text:
        tokens = tuple(
            token for token in qualifier_text.replace("/", " ").replace("-", " ").split() if token
        )
        if len(tokens) == 2 and all(len(token) == 3 and token.isalpha() for token in tokens):
            if reporting_currency in tokens:
                raise UnsupportedRegulatoryFeatureError(
                    "FX curvature MAR21.98 scalar applies only when the option does not "
                    "reference the reporting currency"
                )
            return
    raise UnsupportedRegulatoryFeatureError(
        "FX curvature MAR21.98 scalar requires a two-currency qualifier such as "
        "'EUR/GBP' so audit evidence identifies the non-reporting-currency pair"
    )


def _text_at(values: npt.NDArray[np.object_], row_index: int) -> str:
    return str(values[row_index])


def _optional_text_at(values: npt.NDArray[np.object_] | None, row_index: int) -> str | None:
    if values is None:
        return None
    value = values[row_index]
    if value is None:
        return None
    return str(value)


def _mapping_citation_ids_from_batch(
    batch: SbmSensitivityBatch,
    row_index: int,
) -> tuple[str, ...]:
    if batch.mapping_citation_ids is None:
        return ()
    return batch.mapping_citation_ids[row_index]


__all__ = [
    "_mapping_citation_ids_from_batch",
    "_optional_text_at",
    "_scaled_curvature_batch_shock",
    "_text_at",
    "_validate_curvature_mapping_from_batch",
]
