"""Result-store domain entity dataclasses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime

from frtb_common import AttributionMethod, CapitalContribution
from frtb_common.hashing import stable_json_hash

from frtb_result_store.model_enums import (
    ArtifactType,
    CapitalNodeFamily,
    EdgeType,
    FrtbComponent,
    NodeType,
    ResultEventSeverity,
    ResultEventType,
    ResultStoreContractError,
    RunStatus,
    TelemetryPhase,
    VALID_ATTRIBUTION_TARGET_TYPES,
    VALID_MEASURE_NAMES,
)
from frtb_result_store.model_identity import (
    canonical_run_group_identity_payload,
    canonical_run_identity_payload,
    generate_run_group_id,
    generate_run_id,
)
from frtb_result_store.model_validation import (
    _coerce_enum,
    _duplicate_values,
    _freeze_mapping,
    _freeze_metadata,
    _normalize_identity_text,
    _registered_upper_value,
    _require_finite_number,
    _require_int,
    _require_non_empty_text,
    _require_non_empty_tuple,
    _require_non_negative_int,
    _require_plain_date,
    _require_registered_value,
    _require_run_id,
    _require_text_tuple,
    _tuple_bundle_sequences,
    _validate_bundle_attributions,
    _validate_bundle_edges,
    _validate_bundle_hierarchy,
    _validate_bundle_measures,
    _validate_bundle_movements,
    _validate_optional_text,
)

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
        _require_registered_value(self.measure_name, VALID_MEASURE_NAMES, "measure_name")
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
    target_type: str | None = None
    target_id: str | None = None
    unsupported_reason: str | None = None
    artifact_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_non_empty_text(self.node_id, "node_id")
        _require_non_empty_text(self.contribution_id, "contribution_id")
        _require_non_empty_text(self.source_id, "source_id")
        _require_non_empty_text(self.source_level, "source_level")
        object.__setattr__(
            self,
            "source_level",
            _registered_upper_value(
                self.source_level,
                VALID_ATTRIBUTION_TARGET_TYPES,
                "source_level",
            ),
        )
        object.__setattr__(self, "method", _coerce_enum(self.method, AttributionMethod, "method"))
        if self.target_type is None:
            object.__setattr__(self, "target_type", self.source_level)
        else:
            object.__setattr__(
                self,
                "target_type",
                _registered_upper_value(
                    self.target_type,
                    VALID_ATTRIBUTION_TARGET_TYPES,
                    "target_type",
                ),
            )
        if self.target_id is None:
            object.__setattr__(self, "target_id", self.source_id)
        else:
            _require_non_empty_text(self.target_id, "target_id")
        _validate_optional_text(self.artifact_id, "artifact_id")
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
        object.__setattr__(self, "residual", _require_finite_number(self.residual, "residual"))
        if not isinstance(self.reason, str):
            raise ResultStoreContractError("reason must be text", field="reason")
        unsupported_reason = self.unsupported_reason
        if unsupported_reason is None:
            unsupported_reason = (
                self.reason
                if self.method in (AttributionMethod.RESIDUAL, AttributionMethod.UNSUPPORTED)
                else ""
            )
        if not isinstance(unsupported_reason, str):
            raise ResultStoreContractError(
                "unsupported_reason must be text",
                field="unsupported_reason",
            )
        object.__setattr__(self, "unsupported_reason", unsupported_reason)
        if not self.reason and unsupported_reason:
            object.__setattr__(self, "reason", unsupported_reason)
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
        target_type: str | None = None,
        target_id: str | None = None,
        artifact_id: str | None = None,
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
            target_type=target_type,
            target_id=target_id,
            unsupported_reason=(
                contribution.reason
                if contribution.method
                in (AttributionMethod.RESIDUAL, AttributionMethod.UNSUPPORTED)
                else ""
            ),
            artifact_id=artifact_id,
            metadata={} if metadata is None else metadata,
        )

    @property
    def attribution_id(self) -> str:
        """Stable storage alias for the shared contribution identifier."""

        return self.contribution_id


@dataclass(frozen=True, slots=True)
class MovementResult:
    """Official movement explanation row between a baseline and current run."""

    run_id: str
    baseline_run_id: str
    movement_id: str
    node_id: str
    movement_type: str
    from_amount: float
    to_amount: float
    delta_amount: float
    base_currency: str
    driver_type: str
    driver_id: str
    explanation: str
    attribution_method: AttributionMethod | str | None = None
    artifact_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "run_id",
            "baseline_run_id",
            "movement_id",
            "node_id",
            "movement_type",
            "base_currency",
            "driver_type",
            "driver_id",
        ):
            _require_non_empty_text(getattr(self, field_name), field_name)
        for field_name in ("from_amount", "to_amount", "delta_amount"):
            object.__setattr__(
                self,
                field_name,
                _require_finite_number(getattr(self, field_name), field_name),
            )
        if not isinstance(self.explanation, str):
            raise ResultStoreContractError("explanation must be text", field="explanation")
        if self.attribution_method is not None:
            object.__setattr__(
                self,
                "attribution_method",
                _coerce_enum(self.attribution_method, AttributionMethod, "attribution_method"),
            )
        _validate_optional_text(self.artifact_id, "artifact_id")
        _freeze_metadata(self, self.metadata)


@dataclass(frozen=True, slots=True)
class MovementSummaryRow:
    """Persisted movement summary mart row queryable by capital node."""

    run_id: str
    baseline_run_id: str
    movement_id: str
    node_id: str
    movement_type: str
    from_amount: float
    to_amount: float
    delta_amount: float
    base_currency: str
    driver_type: str
    driver_id: str
    attribution_method: AttributionMethod | str | None = None
    artifact_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "run_id",
            "baseline_run_id",
            "movement_id",
            "node_id",
            "movement_type",
            "base_currency",
            "driver_type",
            "driver_id",
        ):
            _require_non_empty_text(getattr(self, field_name), field_name)
        for field_name in ("from_amount", "to_amount", "delta_amount"):
            object.__setattr__(
                self,
                field_name,
                _require_finite_number(getattr(self, field_name), field_name),
            )
        if self.attribution_method is not None:
            object.__setattr__(
                self,
                "attribution_method",
                _coerce_enum(self.attribution_method, AttributionMethod, "attribution_method"),
            )
        _validate_optional_text(self.artifact_id, "artifact_id")


@dataclass(frozen=True, slots=True)
class InputSnapshotManifest:
    """Compact evidence for an upstream input snapshot used by a run."""

    run_id: str
    input_snapshot_id: str
    input_snapshot_hash: str
    as_of_date: date
    source_system: str
    handoff_key: str
    row_count: int
    accepted_row_count: int
    rejected_row_count: int
    source_uri: str | None = None
    source_hash: str | None = None
    schema_fingerprint: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_non_empty_text(self.input_snapshot_id, "input_snapshot_id")
        _require_non_empty_text(self.input_snapshot_hash, "input_snapshot_hash")
        _require_plain_date(self.as_of_date, "as_of_date")
        _require_non_empty_text(self.source_system, "source_system")
        _require_non_empty_text(self.handoff_key, "handoff_key")
        for field_name in ("row_count", "accepted_row_count", "rejected_row_count"):
            _require_non_negative_int(getattr(self, field_name), field_name)
        for field_name in ("source_uri", "source_hash", "schema_fingerprint"):
            _validate_optional_text(getattr(self, field_name), field_name)
        _freeze_metadata(self, self.metadata)


@dataclass(frozen=True, slots=True)
class ResultEvent:
    """Non-lifecycle event emitted for a stored run."""

    event_id: str
    run_id: str
    event_time: datetime
    severity: ResultEventSeverity | str
    event_type: ResultEventType | str
    message: str
    component: FrtbComponent | str | None = None
    suggested_status: RunStatus | str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.event_id, "event_id")
        _require_non_empty_text(self.run_id, "run_id")
        if not isinstance(self.event_time, datetime) or self.event_time.tzinfo is None:
            raise ResultStoreContractError(
                "event_time must be timezone-aware datetime",
                field="event_time",
            )
        object.__setattr__(
            self, "severity", _coerce_enum(self.severity, ResultEventSeverity, "severity")
        )
        object.__setattr__(
            self, "event_type", _coerce_enum(self.event_type, ResultEventType, "event_type")
        )
        _require_non_empty_text(self.message, "message")
        if self.component is not None:
            object.__setattr__(
                self, "component", _coerce_enum(self.component, FrtbComponent, "component")
            )
        if self.suggested_status is not None:
            object.__setattr__(
                self,
                "suggested_status",
                _coerce_enum(self.suggested_status, RunStatus, "suggested_status"),
            )
        _freeze_metadata(self, self.metadata)


@dataclass(frozen=True, slots=True)
class RunTelemetry:
    """Compact persisted telemetry for one run phase."""

    run_id: str
    phase: TelemetryPhase | str
    duration_ms: float
    created_at: datetime
    trace_id: str | None = None
    span_id: str | None = None
    row_count: int | None = None
    byte_count: int | None = None
    artifact_id: str | None = None
    mart_name: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        object.__setattr__(self, "phase", _coerce_enum(self.phase, TelemetryPhase, "phase"))
        object.__setattr__(
            self,
            "duration_ms",
            _require_finite_number(self.duration_ms, "duration_ms"),
        )
        if self.duration_ms < 0:
            raise ResultStoreContractError("duration_ms must be non-negative", field="duration_ms")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise ResultStoreContractError(
                "created_at must be timezone-aware datetime",
                field="created_at",
            )
        for field_name in ("trace_id", "span_id", "artifact_id", "mart_name"):
            _validate_optional_text(getattr(self, field_name), field_name)
        for field_name in ("row_count", "byte_count"):
            value = getattr(self, field_name)
            if value is not None:
                _require_non_negative_int(value, field_name)


@dataclass(frozen=True, slots=True)
class CapitalSummaryRow:
    """Persisted dashboard summary for one committed run."""

    run_id: str
    as_of_date: date
    regime_id: str
    base_currency: str
    lifecycle_status: RunStatus | str
    suggested_status: RunStatus | str | None
    total_capital: float
    currency: str
    node_count: int
    measure_count: int
    component_count: int

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_plain_date(self.as_of_date, "as_of_date")
        _require_non_empty_text(self.regime_id, "regime_id")
        _require_non_empty_text(self.base_currency, "base_currency")
        object.__setattr__(
            self,
            "lifecycle_status",
            _coerce_enum(self.lifecycle_status, RunStatus, "lifecycle_status"),
        )
        if self.suggested_status is not None:
            object.__setattr__(
                self,
                "suggested_status",
                _coerce_enum(self.suggested_status, RunStatus, "suggested_status"),
            )
        object.__setattr__(
            self,
            "total_capital",
            _require_finite_number(self.total_capital, "total_capital"),
        )
        _require_non_empty_text(self.currency, "currency")
        for field_name in ("node_count", "measure_count", "component_count"):
            _require_non_negative_int(getattr(self, field_name), field_name)


@dataclass(frozen=True, slots=True)
class CapitalTreeMartRow:
    """Persisted flattened capital tree row for dashboard drilldown."""

    run_id: str
    node_id: str
    parent_node_id: str | None
    depth: int
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
        _validate_optional_text(self.parent_node_id, "parent_node_id")
        _require_non_negative_int(self.depth, "depth")
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
        if not isinstance(self.sort_key, int) or isinstance(self.sort_key, bool):
            raise ResultStoreContractError("sort_key must be an integer", field="sort_key")
        _freeze_metadata(self, self.metadata)

    def to_node(self) -> CapitalNode:
        """Return the capital-node contract represented by this mart row."""

        return CapitalNode(
            run_id=self.run_id,
            node_id=self.node_id,
            node_type=self.node_type,
            component=self.component,
            label=self.label,
            desk_id=self.desk_id,
            portfolio_id=self.portfolio_id,
            book_id=self.book_id,
            risk_class=self.risk_class,
            bucket=self.bucket,
            issuer_id=self.issuer_id,
            counterparty_id=self.counterparty_id,
            calculation_branch=self.calculation_branch,
            regulatory_rule_id=self.regulatory_rule_id,
            sort_key=self.sort_key,
            metadata=self.metadata,
        )


@dataclass(frozen=True, slots=True)
class ComponentBreakdownRow:
    """Persisted component-level capital total for dashboard summaries."""

    run_id: str
    component: FrtbComponent | str
    amount: float
    currency: str
    node_count: int
    measure_count: int

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        object.__setattr__(
            self, "component", _coerce_enum(self.component, FrtbComponent, "component")
        )
        object.__setattr__(self, "amount", _require_finite_number(self.amount, "amount"))
        _require_non_empty_text(self.currency, "currency")
        for field_name in ("node_count", "measure_count"):
            _require_non_negative_int(getattr(self, field_name), field_name)


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
    input_manifests: tuple[InputSnapshotManifest, ...] = ()
    lineage: tuple[LineageRef, ...] = ()
    attributions: tuple[CapitalAttributionRecord, ...] = ()
    movement_results: tuple[MovementResult, ...] = ()
    events: tuple[ResultEvent, ...] = ()
    telemetry: tuple[RunTelemetry, ...] = ()

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
        for manifest in self.input_manifests:
            _require_run_id(manifest.run_id, run_id, "input_manifests")
        for lineage in self.lineage:
            _require_run_id(lineage.run_id, run_id, "lineage")
        _validate_bundle_attributions(self.attributions, run_id, known_nodes)
        _validate_bundle_movements(self.movement_results, run_id, known_nodes)
        for event in self.events:
            _require_run_id(event.run_id, run_id, "events")
        for telemetry in self.telemetry:
            _require_run_id(telemetry.run_id, run_id, "telemetry")

