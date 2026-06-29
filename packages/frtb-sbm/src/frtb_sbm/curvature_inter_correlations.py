"""Curvature inter-bucket correlation and citation helpers.

Regulatory traceability:
    Basel MAR21.5, MAR21.96, MAR21.101, and SBM-CURV-001.
"""

from __future__ import annotations

from collections.abc import Sequence

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.commodity_reference_data import (
    _require_commodity_bucket_number,
    commodity_inter_bucket_correlation,
)
from frtb_sbm.csr_nonsec_reference_data import csr_nonsec_inter_bucket_correlation
from frtb_sbm.csr_sec_ctp_reference_data import csr_sec_ctp_inter_bucket_correlation
from frtb_sbm.csr_sec_nonctp_reference_data import csr_sec_nonctp_inter_bucket_correlation
from frtb_sbm.data_models import SbmRegulatoryProfile, SbmRiskClass
from frtb_sbm.equity_reference_data import (
    _require_equity_bucket_number,
    equity_inter_bucket_correlation,
)
from frtb_sbm.reference_citation_routing import profile_citation_id, profile_citation_ids
from frtb_sbm.reference_data import fx_inter_bucket_correlation, girr_inter_bucket_correlation


def _curvature_scope_intra_citations(profile_id: str) -> tuple[str, ...]:
    return profile_citation_ids(
        profile_id,
        ("basel_mar21_curvature", "basel_mar21_100"),
    )


def _curvature_scope_inter_citations(profile_id: str) -> tuple[str, ...]:
    return profile_citation_ids(
        profile_id,
        ("basel_mar21_curvature", "basel_mar21_101"),
    )


def _build_curvature_inter_bucket_correlation_map(
    bucket_ids: Sequence[str],
    *,
    profile_id: str,
    risk_class: SbmRiskClass,
) -> dict[tuple[str, str], float]:
    correlations: dict[tuple[str, str], float] = {}
    ordered_ids = tuple(sorted(bucket_ids, key=lambda item: _bucket_sort_key(risk_class, item)))
    for left_index, bucket_a in enumerate(ordered_ids):
        for bucket_b in ordered_ids[left_index + 1 :]:
            gamma = _curvature_inter_bucket_correlation(
                profile_id,
                risk_class=risk_class,
                bucket_a=bucket_a,
                bucket_b=bucket_b,
            )
            correlations[(bucket_a, bucket_b)] = gamma**2
    return correlations


def _curvature_inter_bucket_correlation(
    profile_id: str,
    *,
    risk_class: SbmRiskClass,
    bucket_a: str,
    bucket_b: str,
) -> float:
    if risk_class is SbmRiskClass.GIRR:
        gamma, _ = girr_inter_bucket_correlation(profile_id, bucket1=bucket_a, bucket2=bucket_b)
        return gamma
    if risk_class is SbmRiskClass.FX:
        gamma, _ = fx_inter_bucket_correlation(profile_id, bucket1=bucket_a, bucket2=bucket_b)
        return gamma
    if risk_class is SbmRiskClass.EQUITY:
        gamma, _ = equity_inter_bucket_correlation(profile_id, bucket1=bucket_a, bucket2=bucket_b)
        return gamma
    if risk_class is SbmRiskClass.COMMODITY:
        gamma, _ = commodity_inter_bucket_correlation(
            profile_id,
            bucket1=bucket_a,
            bucket2=bucket_b,
        )
        return gamma
    if risk_class is SbmRiskClass.CSR_NONSEC:
        gamma, _ = csr_nonsec_inter_bucket_correlation(
            profile_id,
            bucket1=bucket_a,
            bucket2=bucket_b,
        )
        return gamma
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        gamma, _ = csr_sec_ctp_inter_bucket_correlation(
            profile_id,
            bucket1=bucket_a,
            bucket2=bucket_b,
        )
        return gamma
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        gamma, _ = csr_sec_nonctp_inter_bucket_correlation(
            profile_id,
            bucket1=bucket_a,
            bucket2=bucket_b,
        )
        return gamma
    raise UnsupportedRegulatoryFeatureError(
        f"curvature inter-bucket correlation is unsupported for risk_class={risk_class.value}"
    )


def _curvature_intra_citation_ids(
    risk_class: SbmRiskClass,
    *,
    profile_id: str = SbmRegulatoryProfile.BASEL_MAR21.value,
) -> tuple[str, ...]:
    scope = _curvature_scope_intra_citations(profile_id)
    if risk_class is SbmRiskClass.GIRR:
        return (*scope, profile_citation_id(profile_id, "basel_mar21_45_49"))
    if risk_class is SbmRiskClass.FX:
        return (*scope, profile_citation_id(profile_id, "basel_mar21_86"))
    if risk_class is SbmRiskClass.EQUITY:
        return (
            *scope,
            profile_citation_id(profile_id, "basel_mar21_78"),
            profile_citation_id(profile_id, "basel_mar21_79"),
        )
    if risk_class is SbmRiskClass.COMMODITY:
        return (*scope, profile_citation_id(profile_id, "basel_mar21_83"))
    if risk_class is SbmRiskClass.CSR_NONSEC:
        return (
            *scope,
            profile_citation_id(profile_id, "basel_mar21_54"),
            profile_citation_id(profile_id, "basel_mar21_55"),
        )
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        return (*scope, profile_citation_id(profile_id, "basel_mar21_58"))
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return (
            *scope,
            profile_citation_id(profile_id, "basel_mar21_67"),
            profile_citation_id(profile_id, "basel_mar21_68"),
        )
    return scope


def _curvature_inter_citation_ids(
    risk_class: SbmRiskClass,
    *,
    profile_id: str = SbmRegulatoryProfile.BASEL_MAR21.value,
) -> tuple[str, ...]:
    scope = _curvature_scope_inter_citations(profile_id)
    if risk_class is SbmRiskClass.GIRR:
        return (*scope, profile_citation_id(profile_id, "basel_mar21_50"))
    if risk_class is SbmRiskClass.FX:
        return (*scope, profile_citation_id(profile_id, "basel_mar21_89"))
    if risk_class is SbmRiskClass.EQUITY:
        return (*scope, profile_citation_id(profile_id, "basel_mar21_80"))
    if risk_class is SbmRiskClass.COMMODITY:
        return (*scope, profile_citation_id(profile_id, "basel_mar21_85"))
    if risk_class in {SbmRiskClass.CSR_NONSEC, SbmRiskClass.CSR_SEC_CTP}:
        return (*scope, profile_citation_id(profile_id, "basel_mar21_57"))
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return (*scope, profile_citation_id(profile_id, "basel_mar21_70"))
    return scope


def _bucket_sort_key(risk_class: SbmRiskClass, bucket_id: str) -> tuple[int, str]:
    if risk_class is SbmRiskClass.EQUITY:
        return (_require_equity_bucket_number(bucket_id), bucket_id)
    if risk_class is SbmRiskClass.COMMODITY:
        return (_require_commodity_bucket_number(bucket_id), bucket_id)
    try:
        return (int(bucket_id), bucket_id)
    except ValueError:
        return (10_000, bucket_id)


__all__ = [
    "_bucket_sort_key",
    "_build_curvature_inter_bucket_correlation_map",
    "_curvature_inter_bucket_correlation",
    "_curvature_inter_citation_ids",
    "_curvature_intra_citation_ids",
]
