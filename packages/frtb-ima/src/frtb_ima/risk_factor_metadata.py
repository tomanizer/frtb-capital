"""IMA risk-factor metadata and evidence view helpers.

IMA consumes already-resolved risk-factor metadata from upstream mapping layers.
The helpers in this module preserve stable IDs, mapping versions, RFET evidence,
liquidity-horizon assignment, NMRF classification, and stress-period provenance
for audit and Navigator drilldown. They do not query the result store or infer
canonical reference data.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from frtb_ima.data_models import (
    ModellabilityStatus,
    RealPriceObservation,
    RiskFactor,
)
from frtb_ima.nmrf_types import NMRFStressArtifact


class ImaRiskFactorEvidenceState(StrEnum):
    """Availability state for IMA risk-factor evidence."""

    AVAILABLE = "available"
    NO_DATA = "no_data"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class ImaRiskFactorEvidenceRow:
    """One IMA risk-factor metadata/evidence row for downstream views."""

    risk_factor_name: str
    risk_factor_id: str | None
    risk_factor_mapping_version: str | None
    risk_class: str
    liquidity_horizon_days: int
    bucket: str | None
    source_row_id: str | None
    modellability_status: str | None
    rfet_state: ImaRiskFactorEvidenceState
    rfet_evidence_ids: tuple[str, ...]
    nmrf_state: ImaRiskFactorEvidenceState
    nmrf_stress_artifact_ids: tuple[str, ...]
    stress_period_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-compatible row for result-store or Navigator handoff.

        Returns
        -------
        dict[str, object]
            Serialized risk-factor metadata and evidence state.
        """

        return {
            "risk_factor_name": self.risk_factor_name,
            "risk_factor_id": self.risk_factor_id,
            "risk_factor_mapping_version": self.risk_factor_mapping_version,
            "risk_class": self.risk_class,
            "liquidity_horizon_days": self.liquidity_horizon_days,
            "bucket": self.bucket,
            "source_row_id": self.source_row_id,
            "modellability_status": self.modellability_status,
            "rfet_state": self.rfet_state.value,
            "rfet_evidence_ids": list(self.rfet_evidence_ids),
            "nmrf_state": self.nmrf_state.value,
            "nmrf_stress_artifact_ids": list(self.nmrf_stress_artifact_ids),
            "stress_period_ids": list(self.stress_period_ids),
        }


def build_ima_risk_factor_evidence_rows(
    risk_factors: Sequence[RiskFactor],
    *,
    classifications: Mapping[str, ModellabilityStatus | str] | None = None,
    observations: Sequence[RealPriceObservation] = (),
    nmrf_artifacts: Sequence[NMRFStressArtifact] = (),
) -> tuple[ImaRiskFactorEvidenceRow, ...]:
    """Build deterministic IMA risk-factor evidence rows.

    Parameters
    ----------
    risk_factors
        Calculation-ready IMA risk factors supplied by upstream metadata
        mapping.
    classifications
        Optional RFET/NMRF classification labels keyed by risk-factor name.
    observations
        Optional RFET real-price observations. Their vendor/data-pool evidence
        IDs are preserved when present.
    nmrf_artifacts
        Optional post-valuation NMRF stress artifacts consumed by SES
        aggregation.

    Returns
    -------
    tuple[ImaRiskFactorEvidenceRow, ...]
        Rows sorted by risk class, risk-factor ID/name, and mapping version.
    """

    classification_map = classifications or {}
    observation_ids = _rfet_evidence_ids_by_name(observations or ())
    artifact_ids = _nmrf_artifact_ids_by_name(nmrf_artifacts or ())
    stress_period_ids = _stress_period_ids_by_name(nmrf_artifacts or ())
    rows = [
        ImaRiskFactorEvidenceRow(
            risk_factor_name=risk_factor.name,
            risk_factor_id=risk_factor.risk_factor_id,
            risk_factor_mapping_version=risk_factor.risk_factor_mapping_version,
            risk_class=risk_factor.risk_class.value,
            liquidity_horizon_days=risk_factor.liquidity_horizon.value,
            bucket=risk_factor.bucket,
            source_row_id=risk_factor.source_row_id,
            modellability_status=_classification_value(classification_map.get(risk_factor.name)),
            rfet_state=_state_for_values(observation_ids.get(risk_factor.name, ())),
            rfet_evidence_ids=observation_ids.get(risk_factor.name, ()),
            nmrf_state=_state_for_values(artifact_ids.get(risk_factor.name, ())),
            nmrf_stress_artifact_ids=artifact_ids.get(risk_factor.name, ()),
            stress_period_ids=stress_period_ids.get(risk_factor.name, ()),
        )
        for risk_factor in risk_factors
    ]
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row.risk_class,
                row.risk_factor_id or row.risk_factor_name,
                row.risk_factor_mapping_version or "",
            ),
        )
    )


def _rfet_evidence_ids_by_name(
    observations: Sequence[RealPriceObservation] | None,
) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, set[str]] = {}
    for observation in observations or ():
        evidence_id = observation.vendor_audit_evidence_id or observation.data_pool_id
        if evidence_id:
            grouped.setdefault(observation.risk_factor_name, set()).add(evidence_id)
    return {name: tuple(sorted(values)) for name, values in grouped.items()}


def _nmrf_artifact_ids_by_name(
    artifacts: Sequence[NMRFStressArtifact] | None,
) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, set[str]] = {}
    for artifact in artifacts or ():
        artifact_id = artifact.artifact_id or artifact.scenario_vector_id
        if artifact_id:
            grouped.setdefault(artifact.risk_factor_name, set()).add(artifact_id)
    return {name: tuple(sorted(values)) for name, values in grouped.items()}


def _stress_period_ids_by_name(
    artifacts: Sequence[NMRFStressArtifact] | None,
) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, set[str]] = {}
    for artifact in artifacts or ():
        if artifact.stress_period:
            grouped.setdefault(artifact.risk_factor_name, set()).add(artifact.stress_period)
    return {name: tuple(sorted(values)) for name, values in grouped.items()}


def _classification_value(value: ModellabilityStatus | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, ModellabilityStatus):
        return value.value
    return str(value)


def _state_for_values(values: Sequence[str]) -> ImaRiskFactorEvidenceState:
    return ImaRiskFactorEvidenceState.AVAILABLE if values else ImaRiskFactorEvidenceState.NO_DATA


__all__ = [
    "ImaRiskFactorEvidenceRow",
    "ImaRiskFactorEvidenceState",
    "build_ima_risk_factor_evidence_rows",
]
