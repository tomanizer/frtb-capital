"""RRAO reference-data rule record types."""

from __future__ import annotations

from dataclasses import dataclass

from frtb_rrao.data_models import (
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoInvestmentFundExposureType,
)


@dataclass(frozen=True)
class RraoEvidenceRule:
    """Profile-specific mapping from evidence type to classification treatment."""

    evidence_type: RraoEvidenceType
    classification: RraoClassification
    risk_weight_key: str
    reason_code: str
    citation_id: str


@dataclass(frozen=True)
class RraoExclusionRule:
    """Profile-specific cited exclusion rule."""

    exclusion_reason: RraoExclusionReason
    risk_weight_key: str
    reason_code: str
    citation_id: str


@dataclass(frozen=True)
class RraoRiskWeightRule:
    """Profile-specific risk-weight lookup entry."""

    key: str
    classification: RraoClassification
    risk_weight: float
    citation_id: str


@dataclass(frozen=True)
class RraoInvestmentFundRule:
    """Profile-specific investment-fund inclusion mapping."""

    included_exposure_type: RraoInvestmentFundExposureType
    classification: RraoClassification
    risk_weight_key: str
    reason_code: str
    citation_ids: tuple[str, ...]


__all__ = [
    "RraoEvidenceRule",
    "RraoExclusionRule",
    "RraoInvestmentFundRule",
    "RraoRiskWeightRule",
]
