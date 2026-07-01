"""RFET/NMRF/SES risk-factor evidence mart dataclasses.

These result-store-owned records describe fixture-backed RFET observation evidence,
NMRF/SES capital linkage, and hierarchy usage for risk factors within a committed
run. They are read-model contracts for Capital Navigator, not calculation inputs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from frtb_common import RiskFactorId

from frtb_result_store.model_enums import ResultStoreContractError
from frtb_result_store.model_validation import (
    _freeze_metadata,
    _require_finite_number,
    _require_non_empty_text,
    _require_non_negative_int,
    _require_plain_date,
    _validate_optional_text,
)

__all__ = [
    "ModellabilityState",
    "NMRFSESBridge",
    "RFETObservationEvidence",
    "RiskFactorEvidenceRow",
    "RiskFactorHierarchyUsage",
    "SesComponent",
]


class SesComponent(StrEnum):
    """SES component type for NMRF capital attribution."""

    TYPE_A = "TYPE_A"
    TYPE_B = "TYPE_B"


class ModellabilityState(StrEnum):
    """Extended modellability state for risk factors."""

    MODELLABLE = "modellable"
    NON_MODELLABLE = "non_modellable"
    PENDING = "pending"
    STALE = "stale"
    UNSUPPORTED = "unsupported"
    OVERRIDE = "override"


class RfetStaleState(StrEnum):
    """RFET observation staleness state."""

    CURRENT = "current"
    STALE = "stale"
    MISSING_EVIDENCE = "missing_evidence"
    NO_DATA = "no_data"


@dataclass(frozen=True, slots=True)
class RFETObservationEvidence:
    """RFET observation evidence summary for one risk factor.

    This read model summarizes observation counts, gaps, and staleness for
    dashboard rendering. It does not store raw observation rows.
    """

    observation_count: int
    latest_observation_date: date | None
    gap_days: int | None
    stale_state: RfetStaleState | str
    rejected_observation_count: int | None
    artifact_id: str | None

    def __post_init__(self) -> None:
        _require_non_negative_int(self.observation_count, "observation_count")
        if self.latest_observation_date is not None:
            _require_plain_date(self.latest_observation_date, "latest_observation_date")
        if self.gap_days is not None:
            _require_non_negative_int(self.gap_days, "gap_days")
        object.__setattr__(self, "stale_state", RfetStaleState(self.stale_state))
        if self.rejected_observation_count is not None:
            _require_non_negative_int(
                self.rejected_observation_count,
                "rejected_observation_count",
            )
        _validate_optional_text(self.artifact_id, "artifact_id")


@dataclass(frozen=True, slots=True)
class RiskFactorHierarchyUsage:
    """Hierarchy usage mapping for one risk factor.

    Tracks which books, desks, and business lines use a risk factor.
    This is a denormalized read model for dashboard filtering.
    """

    risk_factor_id: RiskFactorId | str
    book_id: str | None
    desk_id: str | None
    volcker_desk_id: str | None
    business_line_id: str | None
    legal_entity_id: str | None
    usage_count: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "risk_factor_id",
            _coerce_risk_factor_id(self.risk_factor_id),
        )
        for field_name in (
            "book_id",
            "desk_id",
            "volcker_desk_id",
            "business_line_id",
            "legal_entity_id",
        ):
            _validate_optional_text(getattr(self, field_name), field_name)
        _require_non_negative_int(self.usage_count, "usage_count")


@dataclass(frozen=True, slots=True)
class NMRFSESBridge:
    """NMRF/SES capital bridge for one risk factor.

    Links non-modellable risk factors to their SES capital contribution.
    This data comes from IMA calculation results; the result store persists
    the completed evidence without recalculating SES.
    """

    risk_factor_id: RiskFactorId | str
    ses_component: SesComponent | str | None
    ses_amount: float | None
    ses_movement: float | None
    stress_period_id: str | None
    liquidity_horizon_days: int | None
    aggregation_bucket: str | None
    capital_node_id: str | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "risk_factor_id",
            _coerce_risk_factor_id(self.risk_factor_id),
        )
        if self.ses_component is not None:
            object.__setattr__(self, "ses_component", SesComponent(self.ses_component))
        if self.ses_amount is not None:
            object.__setattr__(
                self,
                "ses_amount",
                _require_finite_number(self.ses_amount, "ses_amount"),
            )
        if self.ses_movement is not None:
            object.__setattr__(
                self,
                "ses_movement",
                _require_finite_number(self.ses_movement, "ses_movement"),
            )
        _validate_optional_text(self.stress_period_id, "stress_period_id")
        if self.liquidity_horizon_days is not None:
            _require_non_negative_int(
                self.liquidity_horizon_days,
                "liquidity_horizon_days",
            )
        _validate_optional_text(self.aggregation_bucket, "aggregation_bucket")
        _validate_optional_text(self.capital_node_id, "capital_node_id")


@dataclass(frozen=True, slots=True)
class RiskFactorEvidenceRow:
    """Complete RFET/NMRF/SES evidence mart row for one risk factor.

    This is the primary read model for Capital Navigator's RFET/NMRF/SES mode.
    It combines metadata, observation evidence, modellability state,
    NMRF/SES capital linkage, and hierarchy usage into one denormalized row.
    """

    run_id: str
    risk_factor_id: RiskFactorId | str
    display_name: str
    risk_class: str
    risk_factor_type: str

    rfet_observation_evidence: RFETObservationEvidence
    modellability_state: ModellabilityState | str

    nmrf_ses_bridge: NMRFSESBridge | None
    hierarchy_usage: RiskFactorHierarchyUsage | None

    rfet_artifact_id: str | None
    source_artifact_id: str | None

    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        object.__setattr__(
            self,
            "risk_factor_id",
            _coerce_risk_factor_id(self.risk_factor_id),
        )
        _require_non_empty_text(self.display_name, "display_name")
        _require_non_empty_text(self.risk_class, "risk_class")
        _require_non_empty_text(self.risk_factor_type, "risk_factor_type")

        if not isinstance(self.rfet_observation_evidence, RFETObservationEvidence):
            raise ResultStoreContractError(
                "rfet_observation_evidence must be RFETObservationEvidence",
                field="rfet_observation_evidence",
            )

        object.__setattr__(
            self,
            "modellability_state",
            ModellabilityState(self.modellability_state),
        )

        if self.nmrf_ses_bridge is not None and not isinstance(
            self.nmrf_ses_bridge,
            NMRFSESBridge,
        ):
            raise ResultStoreContractError(
                "nmrf_ses_bridge must be NMRFSESBridge",
                field="nmrf_ses_bridge",
            )

        if self.hierarchy_usage is not None and not isinstance(
            self.hierarchy_usage,
            RiskFactorHierarchyUsage,
        ):
            raise ResultStoreContractError(
                "hierarchy_usage must be RiskFactorHierarchyUsage",
                field="hierarchy_usage",
            )

        _validate_optional_text(self.rfet_artifact_id, "rfet_artifact_id")
        _validate_optional_text(self.source_artifact_id, "source_artifact_id")

        _freeze_metadata(self, self.metadata)


def _coerce_risk_factor_id(value: RiskFactorId | str, field_name: str = "risk_factor_id") -> str:
    """Coerce a risk factor ID to a string value."""
    if isinstance(value, str):
        return value
    try:
        return str(value)
    except Exception as exc:
        raise ResultStoreContractError(
            f"{field_name} must be a valid risk factor ID",
            field=field_name,
        ) from exc
