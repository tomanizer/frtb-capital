"""Run identity, status, input evidence, and telemetry dataclasses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime

from frtb_common.hashing import stable_json_hash

from frtb_result_store.model_enums import (
    FrtbComponent,
    ResultEventSeverity,
    ResultEventType,
    ResultStoreContractError,
    RunStatus,
    TelemetryPhase,
)
from frtb_result_store.model_identity import (
    canonical_run_identity_payload,
    generate_run_group_id,
    generate_run_id,
)
from frtb_result_store.model_validation import (
    _coerce_enum,
    _freeze_mapping,
    _freeze_metadata,
    _require_finite_number,
    _require_non_empty_text,
    _require_non_negative_int,
    _require_plain_date,
    _validate_optional_text,
)


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
