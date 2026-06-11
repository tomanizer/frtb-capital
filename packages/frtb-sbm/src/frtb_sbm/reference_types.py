"""Shared SBM reference-data record types.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for reference_data.py, Basel
    MAR21.38-MAR21.43, and SBM-REF-001.
"""

from __future__ import annotations

from dataclasses import dataclass

from frtb_sbm.data_models import SbmScenarioLabel


@dataclass(frozen=True)
class SbmFxBucketDefinition:
    """Profile-specific FX currency bucket definition."""

    bucket_id: str
    currency: str
    citation_id: str


@dataclass(frozen=True)
class SbmGirrBucketDefinition:
    """Profile-specific GIRR currency bucket definition."""

    bucket_id: str
    currency: str
    citation_id: str


@dataclass(frozen=True)
class SbmGirrTenorDefinition:
    """Profile-specific GIRR tenor label and maturity in years."""

    tenor: str
    maturity_years: float
    citation_id: str


@dataclass(frozen=True)
class SbmGirrRiskWeightRule:
    """Profile-specific GIRR delta risk-weight lookup entry."""

    tenor: str
    risk_weight: float
    citation_id: str


@dataclass(frozen=True)
class SbmGirrSpecialRiskFactorRule:
    """Profile-specific inflation or cross-currency basis risk factor."""

    risk_factor: str
    risk_weight: float
    citation_id: str


@dataclass(frozen=True)
class SbmCorrelationScenarioDefinition:
    """Profile-specific low, medium, or high correlation scenario rule."""

    scenario: SbmScenarioLabel
    multiplier: float
    floor_factor: float | None
    cap: float | None
    citation_id: str


__all__ = [
    "SbmCorrelationScenarioDefinition",
    "SbmFxBucketDefinition",
    "SbmGirrBucketDefinition",
    "SbmGirrRiskWeightRule",
    "SbmGirrSpecialRiskFactorRule",
    "SbmGirrTenorDefinition",
]
