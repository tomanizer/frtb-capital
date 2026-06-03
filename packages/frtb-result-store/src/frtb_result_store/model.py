"""FRTB result-store domain contracts.

The result store persists capital evidence after calculation. It does not own
regulatory capital formulae; it owns immutable run identity, FRTB drilldown
shape, large-artifact references, and attribution-ready records.
"""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import TypeVar

from frtb_common import AttributionMethod, CapitalContribution
from frtb_common.hashing import stable_json_hash

__all__ = [
    "ArtifactRef",
    "ArtifactType",
    "CalculationRun",
    "CapitalAttributionRecord",
    "CapitalEdge",
    "CapitalMeasure",
    "CapitalNode",
    "CapitalNodeFamily",
    "CapitalNodeSpec",
    "EdgeType",
    "FrtbComponent",
    "HierarchyDefinition",
    "HierarchyLevel",
    "HierarchyNode",
    "LineageRef",
    "NodeType",
    "ResultBundle",
    "ResultStoreContractError",
    "RunStatus",
    "RunStatusEvent",
    "StorageBackend",
    "canonical_run_group_identity_payload",
    "canonical_run_identity_payload",
    "generate_run_group_id",
    "generate_run_id",
]


class ResultStoreContractError(ValueError):
    """Raised when a result-store contract would produce unauditable output."""

    def __init__(self, message: str, *, field: str = "") -> None:
        self.field = field
        super().__init__(message)


class StorageBackend(StrEnum):
    """Supported or reserved storage backend modes."""

    LOCAL_PARQUET = "local_parquet"
    S3_PARQUET = "s3_parquet"
    DUCKLAKE = "ducklake"


class FrtbComponent(StrEnum):
    """FRTB result components served by the store."""

    TOP_OF_HOUSE = "TOP_OF_HOUSE"
    IMA = "IMA"
    STANDARDISED_APPROACH = "SA"
    SBM = "SBM"
    DRC = "DRC"
    RRAO = "RRAO"
    CVA = "CVA"


class NodeType(StrEnum):
    """Capital graph node classes used for FRTB drilldown."""

    ROOT = "ROOT"
    COMPONENT = "COMPONENT"
    DESK = "DESK"
    PORTFOLIO = "PORTFOLIO"
    BOOK = "BOOK"
    RISK_CLASS = "RISK_CLASS"
    BUCKET = "BUCKET"
    ISSUER = "ISSUER"
    COUNTERPARTY = "COUNTERPARTY"
    HEDGE_SET = "HEDGE_SET"
    MEASURE_BRANCH = "MEASURE_BRANCH"
    RISK_FACTOR = "RISK_FACTOR"
    POSITION = "POSITION"


class EdgeType(StrEnum):
    """Capital graph relationship types."""

    AGGREGATES = "AGGREGATES"
    DRILLDOWN = "DRILLDOWN"
    ATTRIBUTION_BRANCH = "ATTRIBUTION_BRANCH"


class ArtifactType(StrEnum):
    """Large drillthrough artifacts stored outside scalar measure rows."""

    IMA_PNL_VECTOR = "IMA_PNL_VECTOR"
    IMA_TAIL_OBSERVATION = "IMA_TAIL_OBSERVATION"
    IMA_LIQUIDITY_HORIZON_VECTOR = "IMA_LIQUIDITY_HORIZON_VECTOR"
    SBM_SENSITIVITY_TABLE = "SBM_SENSITIVITY_TABLE"
    SBM_CORRELATION_INPUT = "SBM_CORRELATION_INPUT"
    DRC_JTD_TABLE = "DRC_JTD_TABLE"
    RRAO_EXPOSURE_TABLE = "RRAO_EXPOSURE_TABLE"
    CVA_EXPOSURE_TABLE = "CVA_EXPOSURE_TABLE"
    ATTRIBUTION_VECTOR = "ATTRIBUTION_VECTOR"
    MOVEMENT_EXPLAIN = "MOVEMENT_EXPLAIN"
    OTHER = "OTHER"


class RunStatus(StrEnum):
    """Append-only lifecycle status for a committed calculation run."""

    CANDIDATE = "CANDIDATE"
    VALIDATED = "VALIDATED"
    OFFICIAL = "OFFICIAL"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


class CapitalNodeFamily(StrEnum):
    """Canonical ID-bearing FRTB capital node families."""

    COMPONENT = "component"
    RISK_CLASS = "risk_class"
    BUCKET = "bucket"
    ISSUER = "issuer"
    COUNTERPARTY = "counterparty"
    RESIDUAL_BRANCH = "residual_branch"
    RISK_FACTOR = "risk_factor"
    POSITION = "position"


EnumT = TypeVar("EnumT", bound=StrEnum)


@dataclass(frozen=True, slots=True)
class HierarchyLevel:
    """One configured business hierarchy level."""

    level_name: str
    dimension: str
    level_order: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "level_name", _normalize_identity_text(self.level_name))
        object.__setattr__(self, "dimension", _normalize_identity_text(self.dimension))
        _require_int(self.level_order, "level_order")
        if self.level_order < 0:
            raise ResultStoreContractError("level_order must be non-negative", field="level_order")


@dataclass(frozen=True, slots=True)
class HierarchyDefinition:
    """Configured hierarchy shape used to generate deterministic hierarchy nodes."""

    hierarchy_id: str
    hierarchy_version: str
    hierarchy_name: str
    leaf_level: str
    levels: tuple[HierarchyLevel, ...]
    created_at: datetime
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "hierarchy_id", _normalize_identity_text(self.hierarchy_id))
        object.__setattr__(
            self, "hierarchy_version", _normalize_identity_text(self.hierarchy_version)
        )
        object.__setattr__(self, "hierarchy_name", _normalize_identity_text(self.hierarchy_name))
        object.__setattr__(self, "leaf_level", _normalize_identity_text(self.leaf_level))
        if not isinstance(self.created_at, datetime):
            raise ResultStoreContractError("created_at must be a datetime", field="created_at")
        if self.created_at.tzinfo is None:
            raise ResultStoreContractError("created_at must be timezone-aware", field="created_at")
        ordered_levels = tuple(sorted(self.levels, key=lambda level: level.level_order))
        if not ordered_levels:
            raise ResultStoreContractError("levels must be non-empty", field="levels")
        level_names = [level.level_name for level in ordered_levels]
        if len(set(level_names)) != len(level_names):
            raise ResultStoreContractError("level names must be unique", field="levels")
        if self.leaf_level not in level_names:
            raise ResultStoreContractError(
                "leaf_level must name a hierarchy level",
                field="leaf_level",
            )
        object.__setattr__(self, "levels", ordered_levels)
        _freeze_metadata(self, self.metadata)

    @property
    def leaf_dimension(self) -> str:
        """Return the dimension that supplies the configured hierarchy leaf."""

        return next(level.dimension for level in self.levels if level.level_name == self.leaf_level)


@dataclass(frozen=True, slots=True)
class HierarchyNode:
    """One generated business hierarchy node."""

    hierarchy_id: str
    hierarchy_version: str
    hierarchy_node_id: str
    parent_hierarchy_node_id: str | None
    level_name: str
    level_order: int
    business_key: str
    label: str
    path: tuple[tuple[str, str], ...]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.hierarchy_node_id, "hierarchy_node_id")
        _validate_optional_text(self.parent_hierarchy_node_id, "parent_hierarchy_node_id")
        for field_name in (
            "hierarchy_id",
            "hierarchy_version",
            "level_name",
            "business_key",
            "label",
        ):
            object.__setattr__(
                self,
                field_name,
                _normalize_identity_text(getattr(self, field_name)),
            )
        _require_int(self.level_order, "level_order")
        if not isinstance(self.path, tuple) or not self.path:
            raise ResultStoreContractError("path must be a non-empty tuple", field="path")
        normalized_path: list[tuple[str, str]] = []
        for level_name, business_key in self.path:
            normalized_path.append(
                (_normalize_identity_text(level_name), _normalize_identity_text(business_key))
            )
        object.__setattr__(self, "path", tuple(normalized_path))
        _freeze_metadata(self, self.metadata)


@dataclass(frozen=True, slots=True)
class CapitalNodeSpec:
    """Normalized dimensions used to generate one canonical capital node."""

    node_family: CapitalNodeFamily | str
    component: FrtbComponent | str
    label: str
    risk_class: str | None = None
    risk_measure: str | None = None
    bucket: str | None = None
    issuer_id: str | None = None
    counterparty_id: str | None = None
    hedge_set_id: str | None = None
    residual_risk_type: str | None = None
    exposure_category: str | None = None
    risk_factor_id: str | None = None
    risk_factor_set_id: str | None = None
    position_id: str | None = None
    calculation_branch: str | None = None
    regulatory_rule_id: str | None = None
    sort_key: int = 0
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "node_family",
            _coerce_enum(self.node_family, CapitalNodeFamily, "node_family"),
        )
        object.__setattr__(
            self, "component", _coerce_enum(self.component, FrtbComponent, "component")
        )
        object.__setattr__(self, "label", _normalize_identity_text(self.label))
        for field_name in (
            "risk_class",
            "risk_measure",
            "bucket",
            "issuer_id",
            "counterparty_id",
            "hedge_set_id",
            "residual_risk_type",
            "exposure_category",
            "risk_factor_id",
            "risk_factor_set_id",
            "position_id",
            "calculation_branch",
            "regulatory_rule_id",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _normalize_identity_text(value))
        _require_int(self.sort_key, "sort_key")
        _freeze_metadata(self, self.metadata)


def canonical_run_identity_payload(
    *,
    as_of_date: date,
    regime_id: str,
    calculation_scope: str,
    input_snapshot_id: str,
    calculation_policy_id: str,
    engine_version: str,
    code_version: str,
) -> Mapping[str, object]:
    """Return the canonical payload used to derive a run storage id."""

    _require_plain_date(as_of_date, "as_of_date")
    for field_name, value in (
        ("regime_id", regime_id),
        ("calculation_scope", calculation_scope),
        ("input_snapshot_id", input_snapshot_id),
        ("calculation_policy_id", calculation_policy_id),
        ("engine_version", engine_version),
        ("code_version", code_version),
    ):
        _require_non_empty_text(value, field_name)
    return MappingProxyType(
        {
            "as_of_date": as_of_date.isoformat(),
            "regime_id": regime_id,
            "calculation_scope": calculation_scope,
            "input_snapshot_id": input_snapshot_id,
            "calculation_policy_id": calculation_policy_id,
            "engine_version": engine_version,
            "code_version": code_version,
        }
    )


def canonical_run_group_identity_payload(
    *,
    as_of_date: date,
    calculation_scope: str,
    input_snapshot_id: str,
    calculation_policy_group_id: str,
    engine_version: str,
    code_version: str,
    group_purpose: str,
) -> Mapping[str, object]:
    """Return the canonical payload used to link comparable regime runs."""

    _require_plain_date(as_of_date, "as_of_date")
    for field_name, value in (
        ("calculation_scope", calculation_scope),
        ("input_snapshot_id", input_snapshot_id),
        ("calculation_policy_group_id", calculation_policy_group_id),
        ("engine_version", engine_version),
        ("code_version", code_version),
        ("group_purpose", group_purpose),
    ):
        _require_non_empty_text(value, field_name)
    return MappingProxyType(
        {
            "as_of_date": as_of_date.isoformat(),
            "calculation_scope": calculation_scope,
            "input_snapshot_id": input_snapshot_id,
            "calculation_policy_group_id": calculation_policy_group_id,
            "engine_version": engine_version,
            "code_version": code_version,
            "group_purpose": group_purpose,
        }
    )


def generate_run_id(identity_payload: Mapping[str, object]) -> str:
    """Generate the full deterministic storage id for a run identity payload."""

    _require_mapping(identity_payload, "identity_payload")
    return stable_json_hash(identity_payload)


def generate_run_group_id(identity_payload: Mapping[str, object]) -> str:
    """Generate the full deterministic storage id for a run-group payload."""

    _require_mapping(identity_payload, "run_group_identity_payload")
    return stable_json_hash(identity_payload)


@dataclass(frozen=True, slots=True)
class CalculationRun:
    """Immutable identity for one linked FRTB calculation run."""

    run_id: str
    as_of_date: date
    regime_id: str
    base_currency: str
    input_snapshot_id: str
    calculation_scope: str
    engine_version: str
    code_version: str
    calculation_policy_id: str
    created_at: datetime
    run_group_id: str | None = None
    identity_payload: Mapping[str, object] = field(default_factory=dict)
    run_group_identity_payload: Mapping[str, object] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_plain_date(self.as_of_date, "as_of_date")
        _require_non_empty_text(self.regime_id, "regime_id")
        _require_non_empty_text(self.base_currency, "base_currency")
        _require_non_empty_text(self.input_snapshot_id, "input_snapshot_id")
        _require_non_empty_text(self.calculation_scope, "calculation_scope")
        _require_non_empty_text(self.engine_version, "engine_version")
        _require_non_empty_text(self.code_version, "code_version")
        _require_non_empty_text(self.calculation_policy_id, "calculation_policy_id")
        if not isinstance(self.created_at, datetime):
            raise ResultStoreContractError("created_at must be a datetime", field="created_at")
        if self.created_at.tzinfo is None:
            raise ResultStoreContractError("created_at must be timezone-aware", field="created_at")
        _validate_optional_text(self.run_group_id, "run_group_id")
        _freeze_mapping(self, "identity_payload", self.identity_payload)
        _freeze_mapping(self, "run_group_identity_payload", self.run_group_identity_payload)
        if self.identity_payload:
            expected_run_id = generate_run_id(self.identity_payload)
            if self.run_id != expected_run_id:
                raise ResultStoreContractError(
                    "run_id does not match canonical identity payload",
                    field="run_id",
                )
        if self.run_group_identity_payload:
            expected_group_id = generate_run_group_id(self.run_group_identity_payload)
            if self.run_group_id != expected_group_id:
                raise ResultStoreContractError(
                    "run_group_id does not match canonical group identity payload",
                    field="run_group_id",
                )
        _freeze_metadata(self, self.metadata)

    @classmethod
    def from_identity(
        cls,
        *,
        as_of_date: date,
        regime_id: str,
        base_currency: str,
        input_snapshot_id: str,
        calculation_scope: str,
        engine_version: str,
        code_version: str,
        calculation_policy_id: str,
        created_at: datetime,
        run_group_id: str | None = None,
        run_group_identity_payload: Mapping[str, object] | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> CalculationRun:
        """Create a run whose storage id is generated from canonical identity."""

        if run_group_id is None and run_group_identity_payload:
            run_group_id = generate_run_group_id(run_group_identity_payload)
        identity_payload = canonical_run_identity_payload(
            as_of_date=as_of_date,
            regime_id=regime_id,
            calculation_scope=calculation_scope,
            input_snapshot_id=input_snapshot_id,
            calculation_policy_id=calculation_policy_id,
            engine_version=engine_version,
            code_version=code_version,
        )
        return cls(
            run_id=generate_run_id(identity_payload),
            as_of_date=as_of_date,
            regime_id=regime_id,
            base_currency=base_currency,
            input_snapshot_id=input_snapshot_id,
            calculation_scope=calculation_scope,
            engine_version=engine_version,
            code_version=code_version,
            calculation_policy_id=calculation_policy_id,
            created_at=created_at,
            run_group_id=run_group_id,
            identity_payload=identity_payload,
            run_group_identity_payload=(
                {} if run_group_identity_payload is None else run_group_identity_payload
            ),
            metadata={} if metadata is None else metadata,
        )


@dataclass(frozen=True, slots=True)
class RunStatusEvent:
    """Append-only lifecycle transition for a committed run."""

    event_id: str
    run_id: str
    from_status: RunStatus | str | None
    to_status: RunStatus | str
    event_time: datetime
    actor: str
    reason_code: str
    reason_text: str
    external_evidence_ref: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_text(self.event_id, "event_id")
        _require_non_empty_text(self.run_id, "run_id")
        if self.from_status is not None:
            object.__setattr__(
                self,
                "from_status",
                _coerce_enum(self.from_status, RunStatus, "from_status"),
            )
        object.__setattr__(self, "to_status", _coerce_enum(self.to_status, RunStatus, "to_status"))
        if not isinstance(self.event_time, datetime):
            raise ResultStoreContractError("event_time must be a datetime", field="event_time")
        if self.event_time.tzinfo is None:
            raise ResultStoreContractError("event_time must be timezone-aware", field="event_time")
        _require_non_empty_text(self.actor, "actor")
        _require_non_empty_text(self.reason_code, "reason_code")
        _require_non_empty_text(self.reason_text, "reason_text")
        _validate_optional_text(self.external_evidence_ref, "external_evidence_ref")

    @classmethod
    def transition(
        cls,
        *,
        run_id: str,
        from_status: RunStatus | str | None,
        to_status: RunStatus | str,
        event_time: datetime,
        actor: str,
        reason_code: str,
        reason_text: str,
        external_evidence_ref: str | None = None,
    ) -> RunStatusEvent:
        """Create a transition with a deterministic event id."""

        payload = {
            "run_id": run_id,
            "from_status": None if from_status is None else RunStatus(from_status).value,
            "to_status": RunStatus(to_status).value,
            "event_time": event_time.isoformat(),
            "actor": actor,
            "reason_code": reason_code,
            "reason_text": reason_text,
            "external_evidence_ref": external_evidence_ref,
        }
        return cls(
            event_id=stable_json_hash(payload),
            run_id=run_id,
            from_status=from_status,
            to_status=to_status,
            event_time=event_time,
            actor=actor,
            reason_code=reason_code,
            reason_text=reason_text,
            external_evidence_ref=external_evidence_ref,
        )


@dataclass(frozen=True, slots=True)
class CapitalNode:
    """One node in the FRTB capital result graph."""

    run_id: str
    node_id: str
    node_type: NodeType | str
    component: FrtbComponent | str
    label: str
    desk_id: str | None = None
    portfolio_id: str | None = None
    book_id: str | None = None
    risk_class: str | None = None
    bucket: str | None = None
    issuer_id: str | None = None
    counterparty_id: str | None = None
    calculation_branch: str | None = None
    regulatory_rule_id: str | None = None
    sort_key: int = 0
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_non_empty_text(self.node_id, "node_id")
        object.__setattr__(self, "node_type", _coerce_enum(self.node_type, NodeType, "node_type"))
        object.__setattr__(
            self, "component", _coerce_enum(self.component, FrtbComponent, "component")
        )
        _require_non_empty_text(self.label, "label")
        for field_name in (
            "desk_id",
            "portfolio_id",
            "book_id",
            "risk_class",
            "bucket",
            "issuer_id",
            "counterparty_id",
            "calculation_branch",
            "regulatory_rule_id",
        ):
            _validate_optional_text(getattr(self, field_name), field_name)
        _require_int(self.sort_key, "sort_key")
        _freeze_metadata(self, self.metadata)


@dataclass(frozen=True, slots=True)
class CapitalEdge:
    """Directed relationship between two capital graph nodes."""

    run_id: str
    parent_node_id: str
    child_node_id: str
    edge_type: EdgeType | str = EdgeType.AGGREGATES
    aggregation_weight: float = 1.0
    sort_key: int = 0

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_non_empty_text(self.parent_node_id, "parent_node_id")
        _require_non_empty_text(self.child_node_id, "child_node_id")
        object.__setattr__(self, "edge_type", _coerce_enum(self.edge_type, EdgeType, "edge_type"))
        object.__setattr__(
            self,
            "aggregation_weight",
            _require_finite_number(self.aggregation_weight, "aggregation_weight"),
        )
        _require_int(self.sort_key, "sort_key")


@dataclass(frozen=True, slots=True)
class CapitalMeasure:
    """Scalar capital amount or intermediate FRTB result attached to a node."""

    run_id: str
    node_id: str
    measure_name: str
    amount: float
    currency: str
    unit: str = "currency"
    scenario: str | None = None
    methodology: str | None = None
    regulatory_rule_id: str | None = None
    citations: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_non_empty_text(self.node_id, "node_id")
        _require_non_empty_text(self.measure_name, "measure_name")
        object.__setattr__(self, "amount", _require_finite_number(self.amount, "amount"))
        _require_non_empty_text(self.currency, "currency")
        _require_non_empty_text(self.unit, "unit")
        _validate_optional_text(self.scenario, "scenario")
        _validate_optional_text(self.methodology, "methodology")
        _validate_optional_text(self.regulatory_rule_id, "regulatory_rule_id")
        object.__setattr__(self, "citations", _require_text_tuple(self.citations, "citations"))
        _freeze_metadata(self, self.metadata)


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """Reference to a large drillthrough artifact such as an IMA P&L vector."""

    run_id: str
    artifact_id: str
    component: FrtbComponent | str
    artifact_type: ArtifactType | str
    uri: str
    format: str
    row_count: int
    schema_fingerprint: str | None = None
    partition_keys: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_non_empty_text(self.artifact_id, "artifact_id")
        object.__setattr__(
            self, "component", _coerce_enum(self.component, FrtbComponent, "component")
        )
        object.__setattr__(
            self,
            "artifact_type",
            _coerce_enum(self.artifact_type, ArtifactType, "artifact_type"),
        )
        _require_non_empty_text(self.uri, "uri")
        _require_non_empty_text(self.format, "format")
        _require_non_negative_int(self.row_count, "row_count")
        _validate_optional_text(self.schema_fingerprint, "schema_fingerprint")
        object.__setattr__(
            self,
            "partition_keys",
            _require_text_tuple(self.partition_keys, "partition_keys"),
        )
        _freeze_metadata(self, self.metadata)


@dataclass(frozen=True, slots=True)
class LineageRef:
    """Trace one stored result object back to an input, policy, or source hash."""

    run_id: str
    result_id: str
    source_type: str
    source_id: str
    relationship: str = "derived_from"
    source_hash: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_non_empty_text(self.result_id, "result_id")
        _require_non_empty_text(self.source_type, "source_type")
        _require_non_empty_text(self.source_id, "source_id")
        _require_non_empty_text(self.relationship, "relationship")
        _validate_optional_text(self.source_hash, "source_hash")
        _freeze_metadata(self, self.metadata)


@dataclass(frozen=True, slots=True)
class CapitalAttributionRecord:
    """Attribution row for Euler, residual, or unsupported contribution methods."""

    run_id: str
    node_id: str
    contribution_id: str
    source_id: str
    source_level: str
    category: str
    base_amount: float
    method: AttributionMethod | str
    bucket_key: str | None = None
    marginal_multiplier: float | None = None
    contribution: float | None = None
    residual: float = 0.0
    reason: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_non_empty_text(self.node_id, "node_id")
        _require_non_empty_text(self.contribution_id, "contribution_id")
        _require_non_empty_text(self.source_id, "source_id")
        _require_non_empty_text(self.source_level, "source_level")
        _validate_optional_text(self.bucket_key, "bucket_key")
        _require_non_empty_text(self.category, "category")
        object.__setattr__(
            self, "base_amount", _require_finite_number(self.base_amount, "base_amount")
        )
        if self.marginal_multiplier is not None:
            object.__setattr__(
                self,
                "marginal_multiplier",
                _require_finite_number(self.marginal_multiplier, "marginal_multiplier"),
            )
        if self.contribution is not None:
            object.__setattr__(
                self,
                "contribution",
                _require_finite_number(self.contribution, "contribution"),
            )
        object.__setattr__(self, "method", _coerce_enum(self.method, AttributionMethod, "method"))
        object.__setattr__(self, "residual", _require_finite_number(self.residual, "residual"))
        if not isinstance(self.reason, str):
            raise ResultStoreContractError("reason must be text", field="reason")
        if self.method == AttributionMethod.ANALYTICAL_EULER:
            if self.marginal_multiplier is None or self.contribution is None:
                raise ResultStoreContractError(
                    "analytical Euler attribution requires marginal_multiplier and contribution",
                    field="method",
                )
        _freeze_metadata(self, self.metadata)

    @classmethod
    def from_contribution(
        cls,
        *,
        run_id: str,
        node_id: str,
        contribution: CapitalContribution,
        metadata: Mapping[str, object] | None = None,
    ) -> CapitalAttributionRecord:
        """Create a stored attribution record from the shared contribution DTO."""

        return cls(
            run_id=run_id,
            node_id=node_id,
            contribution_id=contribution.contribution_id,
            source_id=contribution.source_id,
            source_level=contribution.source_level,
            bucket_key=contribution.bucket_key,
            category=contribution.category,
            base_amount=contribution.base_amount,
            marginal_multiplier=contribution.marginal_multiplier,
            contribution=contribution.contribution,
            method=contribution.method,
            residual=contribution.residual,
            reason=contribution.reason,
            metadata={} if metadata is None else metadata,
        )


@dataclass(frozen=True, slots=True)
class ResultBundle:
    """Complete append-only payload for one FRTB result-store run."""

    run: CalculationRun
    nodes: tuple[CapitalNode, ...]
    hierarchy_definition: HierarchyDefinition | None = None
    hierarchy_nodes: tuple[HierarchyNode, ...] = ()
    edges: tuple[CapitalEdge, ...] = ()
    measures: tuple[CapitalMeasure, ...] = ()
    artifacts: tuple[ArtifactRef, ...] = ()
    lineage: tuple[LineageRef, ...] = ()
    attributions: tuple[CapitalAttributionRecord, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.run, CalculationRun):
            raise ResultStoreContractError("run must be a CalculationRun", field="run")
        _require_non_empty_tuple(self.nodes, "nodes")
        _tuple_bundle_sequences(self)
        _validate_bundle_hierarchy(self)
        run_id = self.run.run_id
        node_ids = [node.node_id for node in self.nodes]
        duplicate_nodes = _duplicate_values(node_ids)
        if duplicate_nodes:
            raise ResultStoreContractError(
                f"duplicate node ids: {', '.join(duplicate_nodes)}",
                field="nodes",
            )
        hierarchy_node_ids = [node.hierarchy_node_id for node in self.hierarchy_nodes]
        duplicate_hierarchy_node_ids = _duplicate_values(hierarchy_node_ids)
        if duplicate_hierarchy_node_ids:
            raise ResultStoreContractError(
                f"duplicate hierarchy node ids: {', '.join(duplicate_hierarchy_node_ids)}",
                field="hierarchy_nodes",
            )
        known_nodes = set(node_ids) | set(hierarchy_node_ids)
        for node in self.nodes:
            _require_run_id(node.run_id, run_id, "nodes")
        _validate_bundle_edges(self.edges, run_id, known_nodes)
        _validate_bundle_measures(self.measures, run_id, known_nodes)
        for artifact in self.artifacts:
            _require_run_id(artifact.run_id, run_id, "artifacts")
        for lineage in self.lineage:
            _require_run_id(lineage.run_id, run_id, "lineage")
        _validate_bundle_attributions(self.attributions, run_id, known_nodes)


def _coerce_enum(value: EnumT | str, enum_type: type[EnumT], field_name: str) -> EnumT:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ResultStoreContractError(
            f"{field_name} must be one of: {allowed}",
            field=field_name,
        ) from exc


def _normalize_identity_text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ResultStoreContractError("identity field must be non-empty text")
    return unicodedata.normalize("NFC", value)


def _normalize_identity_value(value: object, field: str) -> object:
    if isinstance(value, str):
        if not value:
            raise ResultStoreContractError(f"{field} must be non-empty text", field=field)
        return unicodedata.normalize("NFC", value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ResultStoreContractError(
                f"{field} datetime must be timezone-aware",
                field=field,
            )
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {
            _normalize_identity_text(key): _normalize_identity_value(item, field)
            for key, item in value.items()
        }
    if isinstance(value, tuple | list):
        return tuple(_normalize_identity_value(item, field) for item in value)
    if value is None:
        raise ResultStoreContractError(f"{field} must not be null", field=field)
    return value


def _require_non_empty_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ResultStoreContractError(f"{field} must be non-empty text", field=field)


def _require_mapping(value: object, field: str) -> None:
    if not isinstance(value, Mapping):
        raise ResultStoreContractError(f"{field} must be a mapping", field=field)


def _validate_optional_text(value: object, field: str) -> None:
    if value is not None and (not isinstance(value, str) or not value):
        raise ResultStoreContractError(f"{field} must be non-empty text when set", field=field)


def _require_plain_date(value: object, field: str) -> None:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ResultStoreContractError(f"{field} must be a date", field=field)


def _require_finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ResultStoreContractError(f"{field} must be numeric", field=field)
    number = float(value)
    if not math.isfinite(number):
        raise ResultStoreContractError(f"{field} must be finite", field=field)
    return number


def _require_non_negative_int(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ResultStoreContractError(f"{field} must be a non-negative integer", field=field)


def _require_int(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ResultStoreContractError(f"{field} must be an integer", field=field)


def _require_text_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, tuple) or not all(isinstance(item, str) and item for item in value):
        raise ResultStoreContractError(f"{field} must be a tuple of non-empty text", field=field)
    return value


def _require_non_empty_tuple(value: object, field: str) -> None:
    if not isinstance(value, tuple) or not value:
        raise ResultStoreContractError(f"{field} must be a non-empty tuple", field=field)


def _require_run_id(value: str, expected: str, field: str) -> None:
    if value != expected:
        raise ResultStoreContractError(
            f"{field} run_id {value!r} does not match bundle run_id {expected!r}",
            field=field,
        )


def _tuple_bundle_sequences(bundle: ResultBundle) -> None:
    for field_name in (
        "hierarchy_nodes",
        "edges",
        "measures",
        "artifacts",
        "lineage",
        "attributions",
    ):
        object.__setattr__(bundle, field_name, tuple(getattr(bundle, field_name)))


def _validate_bundle_hierarchy(bundle: ResultBundle) -> None:
    definition = bundle.hierarchy_definition
    if definition is not None and not isinstance(definition, HierarchyDefinition):
        raise ResultStoreContractError(
            "hierarchy_definition must be a HierarchyDefinition",
            field="hierarchy_definition",
        )
    if bundle.hierarchy_nodes and definition is None:
        raise ResultStoreContractError(
            "hierarchy_nodes require a hierarchy_definition",
            field="hierarchy_nodes",
        )
    if not bundle.hierarchy_nodes or definition is None:
        return
    if not any(node.level_name == definition.leaf_level for node in bundle.hierarchy_nodes):
        raise ResultStoreContractError(
            "hierarchy_nodes must include the configured leaf level",
            field="hierarchy_nodes",
        )


def _duplicate_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        else:
            seen.add(value)
    return sorted(duplicates)


def _validate_bundle_edges(
    edges: tuple[CapitalEdge, ...],
    run_id: str,
    known_nodes: set[str],
) -> None:
    for edge in edges:
        _require_run_id(edge.run_id, run_id, "edges")
        if edge.parent_node_id not in known_nodes:
            raise ResultStoreContractError(
                f"edge parent node not found: {edge.parent_node_id}",
                field="edges",
            )
        if edge.child_node_id not in known_nodes:
            raise ResultStoreContractError(
                f"edge child node not found: {edge.child_node_id}",
                field="edges",
            )


def _validate_bundle_measures(
    measures: tuple[CapitalMeasure, ...],
    run_id: str,
    known_nodes: set[str],
) -> None:
    for measure in measures:
        _require_run_id(measure.run_id, run_id, "measures")
        if measure.node_id not in known_nodes:
            raise ResultStoreContractError(
                f"measure node not found: {measure.node_id}",
                field="measures",
            )


def _validate_bundle_attributions(
    attributions: tuple[CapitalAttributionRecord, ...],
    run_id: str,
    known_nodes: set[str],
) -> None:
    for attribution in attributions:
        _require_run_id(attribution.run_id, run_id, "attributions")
        if attribution.node_id not in known_nodes:
            raise ResultStoreContractError(
                f"attribution node not found: {attribution.node_id}",
                field="attributions",
            )


def _freeze_metadata(instance: object, metadata: Mapping[str, object]) -> None:
    if not isinstance(metadata, Mapping):
        raise ResultStoreContractError("metadata must be a mapping", field="metadata")
    object.__setattr__(instance, "metadata", MappingProxyType(dict(metadata)))


def _freeze_mapping(instance: object, field_name: str, value: Mapping[str, object]) -> None:
    if not isinstance(value, Mapping):
        raise ResultStoreContractError(f"{field_name} must be a mapping", field=field_name)
    object.__setattr__(instance, field_name, MappingProxyType(dict(value)))
