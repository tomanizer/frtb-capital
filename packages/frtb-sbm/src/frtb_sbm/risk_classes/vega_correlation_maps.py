"""Non-GIRR vega inter-bucket correlation map dispatch."""

from __future__ import annotations

from collections.abc import Sequence

from frtb_sbm.data_models import SbmRiskClass
from frtb_sbm.risk_classes.commodity import build_commodity_inter_bucket_correlation_map
from frtb_sbm.risk_classes.csr_nonsec import build_csr_nonsec_inter_bucket_correlation_map
from frtb_sbm.risk_classes.csr_sec_nonctp import (
    build_csr_sec_nonctp_inter_bucket_correlation_map,
)
from frtb_sbm.risk_classes.equity import build_equity_inter_bucket_correlation_map
from frtb_sbm.risk_classes.fx import build_fx_inter_bucket_correlation_map
from frtb_sbm.risk_classes.vega_errors import UnsupportedNonGirrVegaPathError


def build_non_girr_vega_inter_bucket_correlation_map(
    risk_class: SbmRiskClass,
    bucket_ids: Sequence[str],
    *,
    profile_id: str,
) -> dict[tuple[str, str], float]:
    """Return MAR21.95 vega inter-bucket correlations from delta gamma tables.
    Parameters
    ----------
    risk_class : SbmRiskClass
        See signature.
    bucket_ids : Sequence[str]
        See signature.
    profile_id : str
        See signature.

    Returns
    -------
    dict[tuple[str, str], float]
    """

    if risk_class is SbmRiskClass.FX:
        return build_fx_inter_bucket_correlation_map(bucket_ids, profile_id=profile_id)
    if risk_class is SbmRiskClass.EQUITY:
        return build_equity_inter_bucket_correlation_map(bucket_ids, profile_id=profile_id)
    if risk_class is SbmRiskClass.COMMODITY:
        return build_commodity_inter_bucket_correlation_map(bucket_ids, profile_id=profile_id)
    if risk_class is SbmRiskClass.CSR_NONSEC:
        return build_csr_nonsec_inter_bucket_correlation_map(bucket_ids, profile_id=profile_id)
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        return build_csr_nonsec_inter_bucket_correlation_map(bucket_ids, profile_id=profile_id)
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return build_csr_sec_nonctp_inter_bucket_correlation_map(
            bucket_ids,
            profile_id=profile_id,
        )
    raise UnsupportedNonGirrVegaPathError(
        f"non-GIRR vega inter-bucket correlations do not support {risk_class.value}"
    )


__all__ = ["build_non_girr_vega_inter_bucket_correlation_map"]
