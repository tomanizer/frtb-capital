"""Curvature intra-bucket correlation helpers.

Regulatory traceability:
    Basel MAR21.5, MAR21.6, MAR21.96, MAR21.100, and SBM-CURV-001.
"""

from __future__ import annotations

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.commodity_reference_data import (
    commodity_delta_intra_bucket_correlation,
)
from frtb_sbm.csr_nonsec_reference_data import (
    CSR_HY_INDEX_BUCKET,
    CSR_IG_INDEX_BUCKET,
    CSR_INDEX_NAME_CORRELATION,
    CSR_NAME_CORRELATION,
    CSR_OTHER_SECTOR_BUCKET,
    csr_nonsec_bucket_definition,
)
from frtb_sbm.csr_sec_nonctp_reference_data import (
    CSR_SEC_OTHER_SECTOR_BUCKET,
    CSR_SEC_TRANCHE_DIFFERENT_CORRELATION,
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
    fx_delta_intra_bucket_correlation,
    girr_delta_intra_bucket_correlation,
)
from frtb_sbm.validation import SbmInputError

_GIRR_CURVATURE_PARALLEL_TENOR = "3m"
_COMMODITY_CURVATURE_PARALLEL_TENOR = "parallel"


def _curvature_intra_bucket_correlation(
    profile_id: str,
    *,
    risk_class: SbmRiskClass,
    factor_a: CurvatureCorrelationFactor,
    factor_b: CurvatureCorrelationFactor,
) -> float:
    if risk_class is SbmRiskClass.GIRR:
        return _girr_curvature_intra_correlation(profile_id, factor_a, factor_b)
    if risk_class is SbmRiskClass.FX:
        correlation, _ = fx_delta_intra_bucket_correlation(
            profile_id,
            bucket1=factor_a.bucket_id,
            bucket2=factor_b.bucket_id,
        )
        return correlation**2
    if risk_class is SbmRiskClass.EQUITY:
        return _equity_curvature_intra_correlation(profile_id, factor_a, factor_b)
    if risk_class is SbmRiskClass.COMMODITY:
        return _commodity_curvature_intra_correlation(profile_id, factor_a, factor_b)
    if risk_class is SbmRiskClass.CSR_NONSEC:
        return _csr_nonsec_curvature_intra_correlation(profile_id, factor_a, factor_b)
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        if _required_factor_qualifier(factor_a) == _required_factor_qualifier(factor_b):
            return 1.0
        return CSR_NAME_CORRELATION**2
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return _csr_sec_nonctp_curvature_intra_correlation(profile_id, factor_a, factor_b)
    raise UnsupportedRegulatoryFeatureError(
        f"curvature intra-bucket correlation is unsupported for risk_class={risk_class.value}"
    )


def _girr_curvature_intra_correlation(
    profile_id: str,
    factor_a: CurvatureCorrelationFactor,
    factor_b: CurvatureCorrelationFactor,
) -> float:
    same_curve = factor_a.risk_factor == factor_b.risk_factor
    correlation, _ = girr_delta_intra_bucket_correlation(
        profile_id,
        tenor1=_GIRR_CURVATURE_PARALLEL_TENOR,
        tenor2=_GIRR_CURVATURE_PARALLEL_TENOR,
        same_curve=same_curve,
    )
    return correlation**2


def _equity_curvature_intra_correlation(
    profile_id: str,
    factor_a: CurvatureCorrelationFactor,
    factor_b: CurvatureCorrelationFactor,
) -> float:
    if factor_a.bucket_id == EQUITY_OTHER_SECTOR_BUCKET:
        return 0.0
    correlation, _ = equity_delta_intra_bucket_correlation(
        profile_id,
        bucket_id=factor_a.bucket_id,
        risk_factor_a=EQUITY_SPOT_RISK_FACTOR,
        risk_factor_b=EQUITY_SPOT_RISK_FACTOR,
        issuer_a=_required_factor_qualifier(factor_a),
        issuer_b=_required_factor_qualifier(factor_b),
    )
    return correlation**2


def _commodity_curvature_intra_correlation(
    profile_id: str,
    factor_a: CurvatureCorrelationFactor,
    factor_b: CurvatureCorrelationFactor,
) -> float:
    correlation, _ = commodity_delta_intra_bucket_correlation(
        profile_id,
        bucket_id=factor_a.bucket_id,
        commodity_a=factor_a.risk_factor,
        commodity_b=factor_b.risk_factor,
        tenor_a=_COMMODITY_CURVATURE_PARALLEL_TENOR,
        tenor_b=_COMMODITY_CURVATURE_PARALLEL_TENOR,
        location_a=_required_factor_qualifier(factor_a),
        location_b=_required_factor_qualifier(factor_b),
    )
    return correlation**2


def _csr_nonsec_curvature_intra_correlation(
    profile_id: str,
    factor_a: CurvatureCorrelationFactor,
    factor_b: CurvatureCorrelationFactor,
) -> float:
    if factor_a.bucket_id == CSR_OTHER_SECTOR_BUCKET:
        return 0.0
    nonsec_bucket = csr_nonsec_bucket_definition(profile_id, factor_a.bucket_id)
    if _required_factor_qualifier(factor_a) == _required_factor_qualifier(factor_b):
        return 1.0
    name_rho = (
        CSR_INDEX_NAME_CORRELATION
        if nonsec_bucket.bucket_id in {CSR_IG_INDEX_BUCKET, CSR_HY_INDEX_BUCKET}
        else CSR_NAME_CORRELATION
    )
    return name_rho**2


def _csr_sec_nonctp_curvature_intra_correlation(
    profile_id: str,
    factor_a: CurvatureCorrelationFactor,
    factor_b: CurvatureCorrelationFactor,
) -> float:
    nonctp_bucket = csr_sec_nonctp_bucket_definition(profile_id, factor_a.bucket_id)
    if nonctp_bucket.bucket_id == CSR_SEC_OTHER_SECTOR_BUCKET:
        return 0.0
    if _required_factor_qualifier(factor_a) == _required_factor_qualifier(factor_b):
        return 1.0
    return CSR_SEC_TRANCHE_DIFFERENT_CORRELATION**2


def _required_factor_qualifier(factor: CurvatureCorrelationFactor) -> str:
    if factor.qualifier is None or not factor.qualifier.strip():
        raise SbmInputError("curvature factor qualifier is required", field="qualifier")
    return factor.qualifier.strip()


__all__ = [
    "CurvatureCorrelationFactor",
    "_curvature_intra_bucket_correlation",
    "_required_factor_qualifier",
]
