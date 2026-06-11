"""Vectorized non-GIRR vega intra-bucket correlation matrices."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import numpy.typing as npt

from frtb_sbm.commodity_reference_data import commodity_bucket_definition
from frtb_sbm.csr_nonsec_reference_data import (
    CSR_DIFFERENT_CURVE_CORRELATION,
    CSR_INDEX_NAME_CORRELATION,
    CSR_NAME_CORRELATION,
    CSR_SAME_CURVE_CORRELATION,
    csr_nonsec_bucket_definition,
)
from frtb_sbm.csr_sec_ctp_reference_data import (
    CSR_CTP_DIFFERENT_BASIS_CORRELATION,
    CSR_CTP_SAME_BASIS_CORRELATION,
    csr_sec_ctp_bucket_definition,
)
from frtb_sbm.csr_sec_nonctp_reference_data import (
    CSR_SEC_DIFFERENT_BASIS_CORRELATION,
    CSR_SEC_SAME_BASIS_CORRELATION,
    CSR_SEC_TRANCHE_DIFFERENT_CORRELATION,
    CSR_SEC_TRANCHE_SAME_CORRELATION,
    csr_sec_nonctp_bucket_definition,
)
from frtb_sbm.data_models import SbmRiskClass, WeightedSensitivity
from frtb_sbm.equity_reference_data import (
    EQUITY_SPOT_RISK_FACTOR,
    equity_delta_intra_bucket_correlation,
)
from frtb_sbm.reference_data import (
    FX_INTRA_BUCKET_CORRELATION,
    GIRR_VEGA_INTRA_BUCKET_CONSTANT,
    fx_delta_intra_bucket_correlation,
    girr_vega_option_tenor_definition,
)
from frtb_sbm.risk_classes.vega_correlation_common import (
    _lookup_axis,
    _uses_absolute_weight_intra_bucket,
)
from frtb_sbm.risk_classes.vega_errors import UnsupportedNonGirrVegaPathError


def build_non_girr_vega_intra_bucket_correlation_matrix(
    ordered: Sequence[WeightedSensitivity],
    *,
    profile_id: str,
    risk_class: SbmRiskClass,
    bucket_id: str,
    risk_factor_by_id: Mapping[str, str],
    qualifier_by_id: Mapping[str, str],
    option_tenor_by_id: Mapping[str, str],
) -> npt.NDArray[np.float64]:
    """Return MAR21.94 non-GIRR vega intra-bucket correlations.
    Parameters
    ----------
    ordered, profile_id, risk_class, bucket_id, risk_factor_by_id, qualifier_by_id,
    option_tenor_by_id :
        See function signature for types and defaults.

    Returns
    -------
    npt.NDArray[np.float64]
    """

    size = len(ordered)
    if size == 0:
        return np.zeros((0, 0), dtype=np.float64)
    if _uses_absolute_weight_intra_bucket(risk_class, bucket_id):
        return np.eye(size, dtype=np.float64)
    return _build_vectorized_non_girr_vega_intra_bucket_correlation_matrix(
        ordered,
        profile_id=profile_id,
        risk_class=risk_class,
        bucket_id=bucket_id,
        risk_factor_by_id=risk_factor_by_id,
        qualifier_by_id=qualifier_by_id,
        option_tenor_by_id=option_tenor_by_id,
    )


def _build_vectorized_non_girr_vega_intra_bucket_correlation_matrix(
    ordered: Sequence[WeightedSensitivity],
    *,
    profile_id: str,
    risk_class: SbmRiskClass,
    bucket_id: str,
    risk_factor_by_id: Mapping[str, str],
    qualifier_by_id: Mapping[str, str],
    option_tenor_by_id: Mapping[str, str],
) -> npt.NDArray[np.float64]:
    ids = tuple(item.sensitivity_id for item in ordered)
    risk_factors = np.array(
        [_lookup_axis(risk_factor_by_id, sensitivity_id, "risk_factor") for sensitivity_id in ids],
        dtype=object,
    )
    qualifiers = np.array(
        [qualifier_by_id.get(sensitivity_id, "") for sensitivity_id in ids],
        dtype=object,
    )
    option_tenors = tuple(
        _lookup_axis(option_tenor_by_id, sensitivity_id, "option_tenor") for sensitivity_id in ids
    )
    option_matrix = _vega_option_tenor_correlation_matrix(
        profile_id,
        option_tenors=option_tenors,
    )
    delta_matrix = _non_girr_vega_delta_correlation_matrix(
        profile_id,
        risk_class=risk_class,
        bucket_id=bucket_id,
        risk_factors=risk_factors,
        qualifiers=qualifiers,
    )
    matrix = np.minimum(1.0, delta_matrix * option_matrix)
    np.fill_diagonal(matrix, 1.0)
    return matrix


def _vega_option_tenor_correlation_matrix(
    profile_id: str,
    *,
    option_tenors: Sequence[str],
) -> npt.NDArray[np.float64]:
    maturities_by_tenor = {
        tenor: girr_vega_option_tenor_definition(profile_id, tenor).maturity_years
        for tenor in set(option_tenors)
    }
    maturities = np.array([maturities_by_tenor[tenor] for tenor in option_tenors], dtype=np.float64)
    minimum = np.minimum.outer(maturities, maturities)
    difference = np.abs(maturities[:, None] - maturities[None, :])
    with np.errstate(divide="ignore", invalid="ignore"):
        exponent = -GIRR_VEGA_INTRA_BUCKET_CONSTANT * difference / minimum
    matrix = np.exp(exponent)
    matrix[minimum <= 0.0] = 1.0
    np.fill_diagonal(matrix, 1.0)
    return matrix


def _non_girr_vega_delta_correlation_matrix(
    profile_id: str,
    *,
    risk_class: SbmRiskClass,
    bucket_id: str,
    risk_factors: npt.NDArray[np.object_],
    qualifiers: npt.NDArray[np.object_],
) -> npt.NDArray[np.float64]:
    size = len(risk_factors)
    if risk_class is SbmRiskClass.FX:
        fx_delta_intra_bucket_correlation(profile_id, bucket1=bucket_id, bucket2=bucket_id)
        return np.full((size, size), FX_INTRA_BUCKET_CORRELATION, dtype=np.float64)
    if risk_class is SbmRiskClass.EQUITY:
        same_issuer = qualifiers[:, None] == qualifiers[None, :]
        different_issuer, _ = equity_delta_intra_bucket_correlation(
            profile_id,
            bucket_id=bucket_id,
            risk_factor_a=EQUITY_SPOT_RISK_FACTOR,
            risk_factor_b=EQUITY_SPOT_RISK_FACTOR,
            issuer_a="__A__",
            issuer_b="__B__",
        )
        return np.where(same_issuer, 1.0, different_issuer).astype(np.float64)
    if risk_class is SbmRiskClass.COMMODITY:
        commodity_bucket = commodity_bucket_definition(profile_id, bucket_id)
        same_commodity = risk_factors[:, None] == risk_factors[None, :]
        return np.where(same_commodity, 1.0, commodity_bucket.commodity_correlation).astype(
            np.float64
        )
    if risk_class is SbmRiskClass.CSR_NONSEC:
        csr_bucket = csr_nonsec_bucket_definition(profile_id, bucket_id)
        name_rho = (
            CSR_INDEX_NAME_CORRELATION if csr_bucket.is_index_bucket else CSR_NAME_CORRELATION
        )
        same_issuer = qualifiers[:, None] == qualifiers[None, :]
        same_basis = risk_factors[:, None] == risk_factors[None, :]
        return (
            np.where(same_issuer, 1.0, name_rho)
            * np.where(same_basis, CSR_SAME_CURVE_CORRELATION, CSR_DIFFERENT_CURVE_CORRELATION)
        ).astype(np.float64)
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        csr_sec_nonctp_bucket_definition(profile_id, bucket_id)
        same_tranche = qualifiers[:, None] == qualifiers[None, :]
        same_basis = risk_factors[:, None] == risk_factors[None, :]
        return (
            np.where(
                same_tranche,
                CSR_SEC_TRANCHE_SAME_CORRELATION,
                CSR_SEC_TRANCHE_DIFFERENT_CORRELATION,
            )
            * np.where(
                same_basis,
                CSR_SEC_SAME_BASIS_CORRELATION,
                CSR_SEC_DIFFERENT_BASIS_CORRELATION,
            )
        ).astype(np.float64)
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        csr_sec_ctp_bucket_definition(profile_id, bucket_id)
        same_name = qualifiers[:, None] == qualifiers[None, :]
        same_basis = risk_factors[:, None] == risk_factors[None, :]
        return (
            np.where(same_name, 1.0, CSR_NAME_CORRELATION)
            * np.where(
                same_basis,
                CSR_CTP_SAME_BASIS_CORRELATION,
                CSR_CTP_DIFFERENT_BASIS_CORRELATION,
            )
        ).astype(np.float64)
    raise UnsupportedNonGirrVegaPathError(
        f"non-GIRR vega intra-bucket correlations do not support {risk_class.value}"
    )


__all__ = ["build_non_girr_vega_intra_bucket_correlation_matrix"]
