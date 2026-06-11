"""RFET qualitative representativeness validation stage."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from frtb_ima.data_contracts import (
    RFETEvidence,
    RFETRepresentativenessEvidence,
    RiskFactorDefinition,
)


@dataclass(frozen=True)
class _RFETQualitativeStage:
    qualitative_pass: bool
    bucket_representative: bool
    representativeness: tuple[RFETRepresentativenessEvidence, ...]


def _representativeness_result(
    risk_factor: RiskFactorDefinition,
    evidence: RFETEvidence,
) -> tuple[bool, tuple[RFETRepresentativenessEvidence, ...]]:
    return _representativeness_result_from_controls(
        risk_factor,
        evidence.bucket_id,
        evidence.representativeness,
    )


def _representativeness_result_from_controls(
    risk_factor: RiskFactorDefinition,
    bucket_id: str,
    representativeness: Sequence[RFETRepresentativenessEvidence],
) -> tuple[bool, tuple[RFETRepresentativenessEvidence, ...]]:
    items = tuple(representativeness)
    if not items:
        if risk_factor.bucket is None:
            return True, ()
        return bucket_id == risk_factor.bucket.bucket_id, ()
    if risk_factor.bucket is None:
        relevant = items
    else:
        relevant = tuple(item for item in items if item.bucket_id == risk_factor.bucket.bucket_id)
    return bool(relevant) and all(item.passed for item in relevant), relevant


def _rfet_qualitative_stage(
    risk_factor: RiskFactorDefinition,
    evidence: RFETEvidence,
) -> _RFETQualitativeStage:
    bucket_representative, representativeness = _representativeness_result(
        risk_factor,
        evidence,
    )
    return _RFETQualitativeStage(
        qualitative_pass=evidence.qualitative_pass,
        bucket_representative=bucket_representative,
        representativeness=representativeness,
    )
