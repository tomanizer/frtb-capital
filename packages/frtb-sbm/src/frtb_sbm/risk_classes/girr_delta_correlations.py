"""GIRR delta intra-bucket correlation helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import numpy.typing as npt

from frtb_sbm.data_models import WeightedSensitivity
from frtb_sbm.reference_data import (
    GIRR_DELTA_INTRA_BUCKET_CONSTANT,
    GIRR_DIFFERENT_CURVE_CORRELATION,
    GIRR_INFLATION_DIFFERENT_TENOR_CORRELATION,
    GIRR_INFLATION_SAME_TENOR_CORRELATION,
    GIRR_INTRA_BUCKET_CORRELATION_FLOOR,
    GIRR_SAME_CURVE_CORRELATION,
    girr_tenor_definition,
)
from frtb_sbm.validation import SbmInputError


def _build_girr_delta_intra_bucket_correlation_matrix(
    ordered: Sequence[WeightedSensitivity],
    *,
    profile_id: str,
    tenor_by_id: Mapping[str, str],
    risk_factor_by_id: Mapping[str, str],
) -> npt.NDArray[np.float64]:
    tenors = _girr_delta_tenor_array(ordered, tenor_by_id=tenor_by_id)
    risk_factors = _girr_delta_risk_factor_array(ordered, risk_factor_by_id=risk_factor_by_id)
    maturities = _girr_delta_maturity_array(tenors, profile_id=profile_id)

    same_curve = risk_factors[:, np.newaxis] == risk_factors[np.newaxis, :]
    minimum_tenor = np.minimum(maturities[:, np.newaxis], maturities[np.newaxis, :])
    tenor_difference = np.abs(maturities[:, np.newaxis] - maturities[np.newaxis, :])
    with np.errstate(divide="ignore", invalid="ignore"):
        tenor_correlation = np.exp(
            -GIRR_DELTA_INTRA_BUCKET_CONSTANT * tenor_difference / minimum_tenor
        )
    tenor_correlation = np.where(minimum_tenor <= 0.0, 1.0, tenor_correlation)
    tenor_correlation = np.maximum(tenor_correlation, GIRR_INTRA_BUCKET_CORRELATION_FLOOR)
    curve_correlation = np.where(
        same_curve,
        GIRR_SAME_CURVE_CORRELATION,
        GIRR_DIFFERENT_CURVE_CORRELATION,
    )
    matrix = curve_correlation * tenor_correlation

    xccy = tenors == "XCCY"
    xccy_any = xccy[:, np.newaxis] | xccy[np.newaxis, :]
    if np.any(xccy_any):
        xccy_both = xccy[:, np.newaxis] & xccy[np.newaxis, :]
        matrix = np.where(xccy_any, np.where(xccy_both, GIRR_SAME_CURVE_CORRELATION, 0.0), matrix)

    inflation = tenors == "INFL"
    inflation_any = inflation[:, np.newaxis] | inflation[np.newaxis, :]
    if np.any(inflation_any):
        inflation_both = inflation[:, np.newaxis] & inflation[np.newaxis, :]
        matrix = np.where(
            inflation_any & ~xccy_any,
            np.where(
                inflation_both,
                GIRR_INFLATION_SAME_TENOR_CORRELATION,
                GIRR_INFLATION_DIFFERENT_TENOR_CORRELATION,
            ),
            matrix,
        )

    np.fill_diagonal(matrix, GIRR_SAME_CURVE_CORRELATION)
    return matrix


def _girr_delta_tenor_array(
    ordered: Sequence[WeightedSensitivity],
    *,
    tenor_by_id: Mapping[str, str],
) -> npt.NDArray[np.object_]:
    tenors: list[str] = []
    for sensitivity in ordered:
        try:
            tenor = tenor_by_id[sensitivity.sensitivity_id]
        except KeyError as exc:
            raise SbmInputError(
                "missing GIRR delta tenor for weighted sensitivity",
                field="tenor_by_id",
                sensitivity_id=sensitivity.sensitivity_id,
            ) from exc
        if not isinstance(tenor, str) or not tenor.strip():
            raise SbmInputError(
                "non-empty text is required",
                field="tenor",
                sensitivity_id=sensitivity.sensitivity_id,
            )
        tenors.append(tenor.strip())
    return np.asarray(tenors, dtype=object)


def _girr_delta_risk_factor_array(
    ordered: Sequence[WeightedSensitivity],
    *,
    risk_factor_by_id: Mapping[str, str],
) -> npt.NDArray[np.object_]:
    risk_factors: list[str] = []
    for sensitivity in ordered:
        try:
            risk_factor = risk_factor_by_id[sensitivity.sensitivity_id]
        except KeyError as exc:
            raise SbmInputError(
                "missing GIRR delta risk factor for weighted sensitivity",
                field="risk_factor_by_id",
                sensitivity_id=sensitivity.sensitivity_id,
            ) from exc
        risk_factors.append(risk_factor)
    return np.asarray(risk_factors, dtype=object)


def _girr_delta_maturity_array(
    tenors: npt.NDArray[np.object_],
    *,
    profile_id: str,
) -> npt.NDArray[np.float64]:
    maturity_by_tenor: dict[str, float] = {}
    for tenor in sorted(str(value) for value in set(tenors) if value not in {"INFL", "XCCY"}):
        maturity_by_tenor[tenor] = girr_tenor_definition(profile_id, tenor).maturity_years
    return np.asarray(
        [maturity_by_tenor.get(str(tenor), 0.0) for tenor in tenors],
        dtype=np.float64,
    )


__all__ = ["_build_girr_delta_intra_bucket_correlation_matrix"]
