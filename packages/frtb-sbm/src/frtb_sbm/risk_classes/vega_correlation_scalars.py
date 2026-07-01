"""Scalar non-GIRR vega intra-bucket correlation helpers."""

from __future__ import annotations

from frtb_sbm._citations import merge_citation_ids as _merge_citation_ids
from frtb_sbm.commodity_reference_data import commodity_delta_intra_bucket_correlation
from frtb_sbm.csr_nonsec_reference_data import csr_nonsec_delta_intra_bucket_correlation
from frtb_sbm.csr_sec_ctp_reference_data import csr_sec_ctp_delta_intra_bucket_correlation
from frtb_sbm.csr_sec_nonctp_reference_data import csr_sec_nonctp_delta_intra_bucket_correlation
from frtb_sbm.data_models import SbmRiskClass
from frtb_sbm.equity_reference_data import (
    EQUITY_SPOT_RISK_FACTOR,
    equity_delta_intra_bucket_correlation,
)
from frtb_sbm.reference_data import (
    fx_delta_intra_bucket_correlation,
    vega_intra_bucket_citation_ids,
    vega_option_tenor_correlation,
)
from frtb_sbm.risk_classes.vega_correlation_common import (
    _VEGA_NEUTRAL_LOCATION,
    _VEGA_NEUTRAL_TENOR,
)
from frtb_sbm.risk_classes.vega_errors import UnsupportedNonGirrVegaPathError


def non_girr_vega_intra_bucket_correlation(
    profile_id: str,
    *,
    risk_class: SbmRiskClass,
    bucket_id: str,
    risk_factor_a: str,
    risk_factor_b: str,
    qualifier_a: str = "",
    qualifier_b: str = "",
    option_tenor_a: str,
    option_tenor_b: str,
) -> tuple[float, tuple[str, ...]]:
    """Return min(1, corresponding delta rho * option-tenor rho) per MAR21.94.
    Parameters
    ----------
    profile_id, risk_class, bucket_id, risk_factor_a, risk_factor_b, qualifier_a, qualifier_b,
    option_tenor_a, option_tenor_b :
        See function signature for types and defaults.

    Returns
    -------
    tuple[float, tuple[str, ...]]
    """

    delta_correlation, delta_citations = _corresponding_delta_correlation(
        profile_id,
        risk_class=risk_class,
        bucket_id=bucket_id,
        risk_factor_a=risk_factor_a,
        risk_factor_b=risk_factor_b,
        qualifier_a=qualifier_a,
        qualifier_b=qualifier_b,
    )
    option_correlation, option_citations = vega_option_tenor_correlation(
        profile_id,
        option_tenor1=option_tenor_a,
        option_tenor2=option_tenor_b,
        risk_class=risk_class,
    )
    return (
        min(1.0, delta_correlation * option_correlation),
        _merge_citation_ids(
            vega_intra_bucket_citation_ids(profile_id, risk_class),
            delta_citations,
            option_citations,
        ),
    )


def _corresponding_delta_correlation(
    profile_id: str,
    *,
    risk_class: SbmRiskClass,
    bucket_id: str,
    risk_factor_a: str,
    risk_factor_b: str,
    qualifier_a: str,
    qualifier_b: str,
) -> tuple[float, tuple[str, ...]]:
    if risk_class is SbmRiskClass.FX:
        return fx_delta_intra_bucket_correlation(
            profile_id,
            bucket1=bucket_id,
            bucket2=bucket_id,
        )
    if risk_class is SbmRiskClass.EQUITY:
        return equity_delta_intra_bucket_correlation(
            profile_id,
            bucket_id=bucket_id,
            risk_factor_a=EQUITY_SPOT_RISK_FACTOR,
            risk_factor_b=EQUITY_SPOT_RISK_FACTOR,
            issuer_a=qualifier_a,
            issuer_b=qualifier_b,
        )
    if risk_class is SbmRiskClass.COMMODITY:
        return commodity_delta_intra_bucket_correlation(
            profile_id,
            bucket_id=bucket_id,
            commodity_a=risk_factor_a,
            commodity_b=risk_factor_b,
            tenor_a=_VEGA_NEUTRAL_TENOR,
            tenor_b=_VEGA_NEUTRAL_TENOR,
            location_a=_VEGA_NEUTRAL_LOCATION,
            location_b=_VEGA_NEUTRAL_LOCATION,
        )
    if risk_class is SbmRiskClass.CSR_NONSEC:
        return csr_nonsec_delta_intra_bucket_correlation(
            profile_id,
            bucket_id=bucket_id,
            risk_factor_a=risk_factor_a,
            risk_factor_b=risk_factor_b,
            issuer_a=qualifier_a,
            issuer_b=qualifier_b,
            tenor_a=_VEGA_NEUTRAL_TENOR,
            tenor_b=_VEGA_NEUTRAL_TENOR,
        )
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return csr_sec_nonctp_delta_intra_bucket_correlation(
            profile_id,
            bucket_id=bucket_id,
            tranche_a=qualifier_a,
            tranche_b=qualifier_b,
            tenor_a=_VEGA_NEUTRAL_TENOR,
            tenor_b=_VEGA_NEUTRAL_TENOR,
            risk_factor_a=risk_factor_a,
            risk_factor_b=risk_factor_b,
        )
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        return csr_sec_ctp_delta_intra_bucket_correlation(
            profile_id,
            bucket_id=bucket_id,
            name_a=qualifier_a,
            name_b=qualifier_b,
            tenor_a=_VEGA_NEUTRAL_TENOR,
            tenor_b=_VEGA_NEUTRAL_TENOR,
            risk_factor_a=risk_factor_a,
            risk_factor_b=risk_factor_b,
        )
    raise UnsupportedNonGirrVegaPathError(
        f"non-GIRR vega intra-bucket correlations do not support {risk_class.value}"
    )


__all__ = ["non_girr_vega_intra_bucket_correlation"]
