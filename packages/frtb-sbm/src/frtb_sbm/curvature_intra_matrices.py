"""Vectorized curvature intra-bucket correlation matrix helpers.

Regulatory traceability:
    Basel MAR21.5, MAR21.96, MAR21.100, and SBM-CURV-001.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt
from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.commodity_reference_data import (
    COMMODITY_LOCATION_CORRELATION,
    commodity_bucket_definition,
)
from frtb_sbm.csr_nonsec_reference_data import (
    CSR_DIFFERENT_CURVE_CORRELATION,
    CSR_INDEX_NAME_CORRELATION,
    CSR_NAME_CORRELATION,
    CSR_OTHER_SECTOR_BUCKET,
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
    CSR_SEC_OTHER_SECTOR_BUCKET,
    CSR_SEC_SAME_BASIS_CORRELATION,
    CSR_SEC_TRANCHE_DIFFERENT_CORRELATION,
    CSR_SEC_TRANCHE_SAME_CORRELATION,
    csr_sec_nonctp_bucket_definition,
)
from frtb_sbm.curvature_correlation_types import CurvatureCorrelationFactor
from frtb_sbm.data_models import SbmRiskClass
from frtb_sbm.equity_reference_data import (
    EQUITY_OTHER_SECTOR_BUCKET,
    EQUITY_SPOT_RISK_FACTOR,
    equity_delta_intra_bucket_correlation,
)
from frtb_sbm.reference_data import (
    FX_INTRA_BUCKET_CORRELATION,
    GIRR_DIFFERENT_CURVE_CORRELATION,
    GIRR_SAME_CURVE_CORRELATION,
    fx_delta_intra_bucket_correlation,
    girr_bucket_definition,
)


def _build_curvature_intra_bucket_correlation_matrix(
    ordered: Sequence[CurvatureCorrelationFactor],
    *,
    profile_id: str,
    risk_class: SbmRiskClass,
) -> npt.NDArray[np.float64]:
    size = len(ordered)
    if size == 0:
        return np.zeros((0, 0), dtype=np.float64)
    matrix = _build_vectorized_curvature_intra_bucket_correlation_matrix(
        ordered,
        profile_id=profile_id,
        risk_class=risk_class,
    )
    np.fill_diagonal(matrix, 1.0)
    return matrix


def _build_vectorized_curvature_intra_bucket_correlation_matrix(
    ordered: Sequence[CurvatureCorrelationFactor],
    *,
    profile_id: str,
    risk_class: SbmRiskClass,
) -> npt.NDArray[np.float64]:
    risk_factors = np.array([factor.risk_factor for factor in ordered], dtype=object)
    qualifiers = np.array([factor.qualifier or "" for factor in ordered], dtype=object)
    if risk_class is SbmRiskClass.GIRR:
        return _girr_curvature_intra_matrix(ordered, profile_id, risk_factors)
    if risk_class is SbmRiskClass.FX:
        return _fx_curvature_intra_matrix(ordered, profile_id)
    if risk_class is SbmRiskClass.EQUITY:
        return _equity_curvature_intra_matrix(ordered, profile_id, qualifiers)
    if risk_class is SbmRiskClass.COMMODITY:
        return _commodity_curvature_intra_matrix(ordered, profile_id, risk_factors, qualifiers)
    if risk_class is SbmRiskClass.CSR_NONSEC:
        return _csr_nonsec_curvature_intra_matrix(ordered, profile_id, risk_factors, qualifiers)
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        return _csr_sec_ctp_curvature_intra_matrix(ordered, profile_id, risk_factors, qualifiers)
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return _csr_sec_nonctp_curvature_intra_matrix(
            ordered,
            profile_id,
            risk_factors,
            qualifiers,
        )
    raise UnsupportedRegulatoryFeatureError(
        f"curvature intra-bucket correlation is unsupported for risk_class={risk_class.value}"
    )


def _girr_curvature_intra_matrix(
    ordered: Sequence[CurvatureCorrelationFactor],
    profile_id: str,
    risk_factors: npt.NDArray[np.object_],
) -> npt.NDArray[np.float64]:
    girr_bucket_definition(profile_id, ordered[0].bucket_id)
    same_curve = risk_factors[:, None] == risk_factors[None, :]
    return (
        np.where(same_curve, GIRR_SAME_CURVE_CORRELATION, GIRR_DIFFERENT_CURVE_CORRELATION).astype(
            np.float64
        )
        ** 2
    )


def _fx_curvature_intra_matrix(
    ordered: Sequence[CurvatureCorrelationFactor],
    profile_id: str,
) -> npt.NDArray[np.float64]:
    fx_delta_intra_bucket_correlation(
        profile_id,
        bucket1=ordered[0].bucket_id,
        bucket2=ordered[0].bucket_id,
    )
    return np.full((len(ordered), len(ordered)), FX_INTRA_BUCKET_CORRELATION**2, dtype=np.float64)


def _equity_curvature_intra_matrix(
    ordered: Sequence[CurvatureCorrelationFactor],
    profile_id: str,
    qualifiers: npt.NDArray[np.object_],
) -> npt.NDArray[np.float64]:
    bucket_id = ordered[0].bucket_id
    if bucket_id == EQUITY_OTHER_SECTOR_BUCKET:
        return np.eye(len(ordered), dtype=np.float64)
    different_issuer, _ = equity_delta_intra_bucket_correlation(
        profile_id,
        bucket_id=bucket_id,
        risk_factor_a=EQUITY_SPOT_RISK_FACTOR,
        risk_factor_b=EQUITY_SPOT_RISK_FACTOR,
        issuer_a="__A__",
        issuer_b="__B__",
    )
    same_issuer = qualifiers[:, None] == qualifiers[None, :]
    return np.where(same_issuer, 1.0, different_issuer).astype(np.float64) ** 2


def _commodity_curvature_intra_matrix(
    ordered: Sequence[CurvatureCorrelationFactor],
    profile_id: str,
    risk_factors: npt.NDArray[np.object_],
    qualifiers: npt.NDArray[np.object_],
) -> npt.NDArray[np.float64]:
    commodity_bucket = commodity_bucket_definition(profile_id, ordered[0].bucket_id)
    same_commodity = risk_factors[:, None] == risk_factors[None, :]
    same_location = qualifiers[:, None] == qualifiers[None, :]
    delta = np.where(same_commodity, 1.0, commodity_bucket.commodity_correlation) * np.where(
        same_location,
        1.0,
        COMMODITY_LOCATION_CORRELATION,
    )
    return delta.astype(np.float64) ** 2


def _csr_nonsec_curvature_intra_matrix(
    ordered: Sequence[CurvatureCorrelationFactor],
    profile_id: str,
    risk_factors: npt.NDArray[np.object_],
    qualifiers: npt.NDArray[np.object_],
) -> npt.NDArray[np.float64]:
    csr_bucket = csr_nonsec_bucket_definition(profile_id, ordered[0].bucket_id)
    if csr_bucket.bucket_id == CSR_OTHER_SECTOR_BUCKET:
        return np.eye(len(ordered), dtype=np.float64)
    name_rho = CSR_INDEX_NAME_CORRELATION if csr_bucket.is_index_bucket else CSR_NAME_CORRELATION
    same_name = qualifiers[:, None] == qualifiers[None, :]
    same_basis = risk_factors[:, None] == risk_factors[None, :]
    delta = np.where(same_name, 1.0, name_rho) * np.where(
        same_basis,
        CSR_SAME_CURVE_CORRELATION,
        CSR_DIFFERENT_CURVE_CORRELATION,
    )
    return delta.astype(np.float64) ** 2


def _csr_sec_ctp_curvature_intra_matrix(
    ordered: Sequence[CurvatureCorrelationFactor],
    profile_id: str,
    risk_factors: npt.NDArray[np.object_],
    qualifiers: npt.NDArray[np.object_],
) -> npt.NDArray[np.float64]:
    csr_sec_ctp_bucket_definition(profile_id, ordered[0].bucket_id)
    same_name = qualifiers[:, None] == qualifiers[None, :]
    same_basis = risk_factors[:, None] == risk_factors[None, :]
    delta = np.where(same_name, 1.0, CSR_NAME_CORRELATION) * np.where(
        same_basis,
        CSR_CTP_SAME_BASIS_CORRELATION,
        CSR_CTP_DIFFERENT_BASIS_CORRELATION,
    )
    return delta.astype(np.float64) ** 2


def _csr_sec_nonctp_curvature_intra_matrix(
    ordered: Sequence[CurvatureCorrelationFactor],
    profile_id: str,
    risk_factors: npt.NDArray[np.object_],
    qualifiers: npt.NDArray[np.object_],
) -> npt.NDArray[np.float64]:
    nonctp_bucket = csr_sec_nonctp_bucket_definition(profile_id, ordered[0].bucket_id)
    if nonctp_bucket.bucket_id == CSR_SEC_OTHER_SECTOR_BUCKET:
        return np.eye(len(ordered), dtype=np.float64)
    same_tranche = qualifiers[:, None] == qualifiers[None, :]
    same_basis = risk_factors[:, None] == risk_factors[None, :]
    delta = np.where(
        same_tranche,
        CSR_SEC_TRANCHE_SAME_CORRELATION,
        CSR_SEC_TRANCHE_DIFFERENT_CORRELATION,
    ) * np.where(
        same_basis,
        CSR_SEC_SAME_BASIS_CORRELATION,
        CSR_SEC_DIFFERENT_BASIS_CORRELATION,
    )
    return delta.astype(np.float64) ** 2


__all__ = [
    "_build_curvature_intra_bucket_correlation_matrix",
    "_build_vectorized_curvature_intra_bucket_correlation_matrix",
]
